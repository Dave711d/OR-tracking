"""TAVR-specific workflow inference for OR video metrics.

The stage model is deliberately conservative: it estimates what is visually
plausible from room video and avoids pretending to know catheter-internal events
that require fluoroscopy, hemodynamics, audio, or procedure logs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

from .models import Detection


ZoneRect = Tuple[float, float, float, float]


TAVR_STAGE_ORDER = [
    "room_prep_drape",
    "access_sheathing",
    "angio_alignment_crossing",
    "bav_optional",
    "valve_delivery_positioning",
    "valve_deployment",
    "post_deploy_assessment",
    "closure_finish",
]


TAVR_STAGE_LABELS: Dict[str, str] = {
    "room_prep_drape": "Room prep / drape",
    "access_sheathing": "Access / sheathing",
    "angio_alignment_crossing": "Angio alignment / crossing",
    "bav_optional": "Balloon valvuloplasty",
    "valve_delivery_positioning": "Valve delivery / positioning",
    "valve_deployment": "Valve deployment",
    "post_deploy_assessment": "Post-deploy assessment",
    "closure_finish": "Closure / finish",
}


TAVR_STAGE_NOTES: Dict[str, str] = {
    "room_prep_drape": "Room setup, anesthesia, sterile prep, and device-table activity.",
    "access_sheathing": "Access-site work and sheath/wire setup, usually groin-focused for transfemoral cases.",
    "angio_alignment_crossing": "Monitor/C-arm focus, aortography alignment, and valve crossing work.",
    "bav_optional": "Optional pre-dilation; visually confusable with post-dilation or deployment.",
    "valve_delivery_positioning": "Delivery system/device preparation with concentrated table-side attention.",
    "valve_deployment": "High-attention deployment moment; video-only confidence should remain modest.",
    "post_deploy_assessment": "Angiographic/echo assessment and possible post-dilation loop.",
    "closure_finish": "Access closure, final vessel checks, drape-down, and room cleanup.",
}


ROLE_ZONE_MAP: Dict[str, str] = {
    "entry": "entry_supply",
    "anesthesia": "anesthesia",
    "imaging": "imaging",
    "device_table": "device_prep",
    "access": "access_operator",
    "table_left": "table_operator",
    "table_right": "table_operator",
    "table": "table_operator",
}


TABLE_ZONES = ("table", "table_left", "table_right", "access")


@dataclass(frozen=True)
class TAVRFrameState:
    """TAVR-specific interpretation attached to one frame."""

    stage: str
    stage_label: str
    confidence: float
    table_count: int
    table_track_ids: List[int]
    role_counts: Dict[str, int]
    role_track_ids: Dict[str, List[int]]
    signals: Dict[str, float]
    note: str

    def to_row_fields(self) -> Dict[str, object]:
        return {
            "tavr_stage": self.stage,
            "tavr_stage_label": self.stage_label,
            "tavr_confidence": round(float(self.confidence), 3),
            "table_count": self.table_count,
            "table_track_ids": ",".join(str(track_id) for track_id in self.table_track_ids),
            "role_counts": ",".join(
                f"{role}:{count}" for role, count in sorted(self.role_counts.items())
            ),
            "role_track_ids": ";".join(
                f"{role}:{','.join(str(track_id) for track_id in track_ids)}"
                for role, track_ids in sorted(self.role_track_ids.items())
            ),
            "tavr_signals": ",".join(
                f"{name}:{value:.2f}" for name, value in sorted(self.signals.items())
            ),
        }


@dataclass
class TAVRWorkflowAnalyzer:
    """Small stateful heuristic stage estimator for TAVR-room footage."""

    min_confidence_to_advance: float = 0.42
    min_stage_frames: int = 30
    current_stage_index: int = 0
    current_stage_start_frame: int = 0

    def update(
        self,
        detections: Sequence[Detection],
        zone_counts: Mapping[str, int],
        table_track_ids: Sequence[int],
        role_track_ids: Mapping[str, Sequence[int]],
        frame_index: int,
        movement_px: float,
    ) -> TAVRFrameState:
        normalized_role_track_ids = {
            role: sorted(set(track_ids)) for role, track_ids in role_track_ids.items()
        }
        role_counts = {
            role: len(track_ids) for role, track_ids in normalized_role_track_ids.items()
        }
        signals = _signals(zone_counts, len(detections), movement_px)
        stage_scores = _stage_scores(signals, frame_index)
        stage_index, confidence = self._choose_stage(stage_scores, frame_index)
        if stage_index != self.current_stage_index:
            self.current_stage_start_frame = frame_index
        self.current_stage_index = stage_index
        stage = TAVR_STAGE_ORDER[stage_index]
        return TAVRFrameState(
            stage=stage,
            stage_label=TAVR_STAGE_LABELS[stage],
            confidence=confidence,
            table_count=len(set(table_track_ids)),
            table_track_ids=sorted(set(table_track_ids)),
            role_counts=role_counts,
            role_track_ids=normalized_role_track_ids,
            signals=signals,
            note=TAVR_STAGE_NOTES[stage],
        )

    def _choose_stage(self, scores: Mapping[str, float], frame_index: int) -> Tuple[int, float]:
        current_stage = TAVR_STAGE_ORDER[self.current_stage_index]
        current_score = scores.get(current_stage, 0.0)
        if frame_index - self.current_stage_start_frame < self.min_stage_frames:
            return self.current_stage_index, min(current_score, 0.9)

        next_index = min(self.current_stage_index + 1, len(TAVR_STAGE_ORDER) - 1)
        next_stage = TAVR_STAGE_ORDER[next_index]
        next_score = scores.get(next_stage, 0.0)

        if next_stage == "bav_optional":
            delivery_index = TAVR_STAGE_ORDER.index("valve_delivery_positioning")
            delivery_score = scores.get("valve_delivery_positioning", 0.0)
            if (
                delivery_score >= self.min_confidence_to_advance
                and delivery_score > next_score + 0.05
            ):
                return delivery_index, min(delivery_score, 0.95)

        if next_index > self.current_stage_index and next_score >= self.min_confidence_to_advance:
            return next_index, min(next_score, 0.95)
        return self.current_stage_index, min(max(current_score, next_score), 0.9)


def tavr_default_zones() -> Dict[str, ZoneRect]:
    """Normalized room zones for a table-centered TAVR/cath-lab camera."""

    return {
        "entry": (0.0, 0.0, 0.16, 1.0),
        "access": (0.22, 0.58, 0.50, 0.98),
        "table": (0.30, 0.24, 0.70, 0.82),
        "table_left": (0.22, 0.22, 0.42, 0.78),
        "table_right": (0.58, 0.22, 0.78, 0.78),
        "anesthesia": (0.72, 0.0, 1.0, 0.34),
        "imaging": (0.42, 0.0, 0.76, 0.24),
        "device_table": (0.0, 0.0, 0.28, 0.35),
    }


def role_counts_from_zones(zone_counts: Mapping[str, int]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for zone_name, count in zone_counts.items():
        role = ROLE_ZONE_MAP.get(zone_name)
        if role:
            counts[role] = counts.get(role, 0) + count
    return counts


def dominant_stage(states: Iterable[TAVRFrameState]) -> str:
    counts: Dict[str, int] = {}
    for state in states:
        counts[state.stage] = counts.get(state.stage, 0) + 1
    if not counts:
        return ""
    return max(counts.items(), key=lambda item: item[1])[0]


def stage_timeline(states: Sequence[TAVRFrameState]) -> List[Dict[str, object]]:
    timeline: List[Dict[str, object]] = []
    if not states:
        return timeline

    active = states[0]
    start_index = 0
    for index, state in enumerate(states[1:], start=1):
        if state.stage != active.stage:
            timeline.append(_timeline_item(active, start_index, index - 1))
            active = state
            start_index = index
    timeline.append(_timeline_item(active, start_index, len(states) - 1))
    return timeline


def _timeline_item(state: TAVRFrameState, start_index: int, end_index: int) -> Dict[str, object]:
    return {
        "stage": state.stage,
        "stage_label": state.stage_label,
        "start_frame": start_index,
        "end_frame": end_index,
        "note": state.note,
    }


def _signals(
    zone_counts: Mapping[str, int],
    people_count: int,
    movement_px: float,
) -> Dict[str, float]:
    table_count = sum(zone_counts.get(zone, 0) for zone in TABLE_ZONES)
    imaging = zone_counts.get("imaging", 0)
    access = zone_counts.get("access", 0)
    anesthesia = zone_counts.get("anesthesia", 0)
    device = zone_counts.get("device_table", 0)
    stillness = max(0.0, 1.0 - min(movement_px / 90.0, 1.0))
    crowd = min(people_count / 5.0, 1.0)
    return {
        "table": min(table_count / 3.0, 1.0),
        "access": min(access / 2.0, 1.0),
        "imaging": min(imaging / 2.0, 1.0),
        "device": min(device / 2.0, 1.0),
        "anesthesia": min(anesthesia / 2.0, 1.0),
        "stillness": stillness,
        "crowd": crowd,
    }


def _stage_scores(signals: Mapping[str, float], frame_index: int) -> Dict[str, float]:
    early_bonus = 0.14 if frame_index < 36 else 0.0
    late_bonus = 0.08 if frame_index > 240 else 0.0
    return {
        "room_prep_drape": 0.32 + 0.28 * signals["device"] + 0.18 * signals["anesthesia"] + early_bonus,
        "access_sheathing": 0.24 + 0.42 * signals["access"] + 0.18 * signals["table"],
        "angio_alignment_crossing": 0.22 + 0.38 * signals["imaging"] + 0.16 * signals["table"],
        "bav_optional": 0.18 + 0.30 * signals["imaging"] + 0.24 * signals["stillness"] + 0.16 * signals["table"],
        "valve_delivery_positioning": 0.20 + 0.32 * signals["device"] + 0.26 * signals["table"] + 0.16 * signals["imaging"],
        "valve_deployment": 0.16 + 0.32 * signals["stillness"] + 0.26 * signals["table"] + 0.20 * signals["imaging"],
        "post_deploy_assessment": 0.20 + 0.34 * signals["imaging"] + 0.18 * signals["anesthesia"] + 0.08 * signals["table"],
        "closure_finish": 0.18 + 0.38 * signals["access"] + 0.16 * signals["stillness"] + late_bonus,
    }
