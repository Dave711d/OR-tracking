"""TAVR-specific workflow inference for OR video metrics.

The stage model is deliberately conservative: it estimates what is visually
plausible from room video and avoids pretending to know catheter-internal events
that require fluoroscopy, hemodynamics, audio, or procedure logs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

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


ROLE_DOMINANCE_ORDER = (
    "access_operator",
    "table_operator",
    "device_prep",
    "imaging",
    "anesthesia",
    "entry_supply",
    "unassigned",
)


@dataclass(frozen=True)
class TrackRoleSummary:
    """Persistent role estimate for one tracked person/object."""

    track_id: int
    dominant_role: str
    frames_seen: int
    first_frame: int
    last_frame: int
    table_frames: int
    role_counts: Dict[str, int]
    last_table_frame: Optional[int] = None
    last_seen_at_table: bool = False

    @property
    def table_presence_ratio(self) -> float:
        if self.frames_seen <= 0:
            return 0.0
        return self.table_frames / self.frames_seen

    def to_compact(self) -> str:
        return (
            f"{self.track_id}:{self.dominant_role}:frames={self.frames_seen}:"
            f"table={self.table_presence_ratio:.2f}:last={self.last_frame}"
        )

    def to_who_at_table(self) -> str:
        return (
            f"ID {self.track_id} {self.dominant_role} "
            f"table={self.table_presence_ratio:.0%}"
        )


@dataclass
class _TrackRoleHistory:
    track_id: int
    first_frame: int
    last_frame: int
    frames_seen: int = 0
    table_frames: int = 0
    last_table_frame: Optional[int] = None
    last_seen_at_table: bool = False
    role_counts: Dict[str, int] = field(default_factory=dict)

    def update(self, frame_index: int, roles: Sequence[str], at_table: bool) -> None:
        self.last_frame = frame_index
        self.frames_seen += 1
        if at_table:
            self.table_frames += 1
            self.last_table_frame = frame_index
        self.last_seen_at_table = at_table
        for role in roles or ("unassigned",):
            self.role_counts[role] = self.role_counts.get(role, 0) + 1

    def snapshot(self) -> TrackRoleSummary:
        return TrackRoleSummary(
            track_id=self.track_id,
            dominant_role=_dominant_role(self.role_counts),
            frames_seen=self.frames_seen,
            first_frame=self.first_frame,
            last_frame=self.last_frame,
            table_frames=self.table_frames,
            role_counts=dict(sorted(self.role_counts.items())),
            last_table_frame=self.last_table_frame,
            last_seen_at_table=self.last_seen_at_table,
        )


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
    track_role_summaries: Dict[int, TrackRoleSummary]
    signals: Dict[str, float]
    note: str
    recent_table_track_ids: List[int] = field(default_factory=list)
    recent_table_summaries: Dict[int, TrackRoleSummary] = field(default_factory=dict)

    def to_row_fields(self) -> Dict[str, object]:
        track_summaries = [
            self.track_role_summaries[track_id].to_compact()
            for track_id in sorted(self.track_role_summaries)
        ]
        table_summaries = [
            self.track_role_summaries[track_id].to_who_at_table()
            for track_id in self.table_track_ids
            if track_id in self.track_role_summaries
        ]
        recent_table_summaries = [
            self.recent_table_summaries[track_id].to_who_at_table()
            for track_id in self.recent_table_track_ids
            if track_id in self.recent_table_summaries
        ]
        return {
            "tavr_stage": self.stage,
            "tavr_stage_label": self.stage_label,
            "tavr_confidence": round(float(self.confidence), 3),
            "table_count": self.table_count,
            "table_track_ids": ",".join(str(track_id) for track_id in self.table_track_ids),
            "who_at_table": "; ".join(table_summaries),
            "recent_table_track_ids": ",".join(
                str(track_id) for track_id in self.recent_table_track_ids
            ),
            "recent_who_at_table": "; ".join(recent_table_summaries),
            "role_counts": ",".join(
                f"{role}:{count}" for role, count in sorted(self.role_counts.items())
            ),
            "role_track_ids": ";".join(
                f"{role}:{','.join(str(track_id) for track_id in track_ids)}"
                for role, track_ids in sorted(self.role_track_ids.items())
            ),
            "track_role_summary": ";".join(track_summaries),
            "tavr_signals": ",".join(
                f"{name}:{value:.2f}" for name, value in sorted(self.signals.items())
            ),
        }


@dataclass
class TAVRWorkflowAnalyzer:
    """Small stateful heuristic stage estimator for TAVR-room footage."""

    initial_stage: str = "room_prep_drape"
    min_confidence_to_advance: float = 0.42
    advance_margin: float = 0.06
    min_stage_frames: int = 30
    recent_table_hold_frames: int = 12
    current_stage_index: int = 0
    current_stage_start_frame: int = 0
    track_histories: Dict[int, _TrackRoleHistory] = field(default_factory=dict)
    initialized: bool = False

    def __post_init__(self) -> None:
        if self.initial_stage not in TAVR_STAGE_ORDER:
            valid = ", ".join(TAVR_STAGE_ORDER)
            raise ValueError(f"Unknown TAVR stage '{self.initial_stage}'. Valid: {valid}")
        self.current_stage_index = TAVR_STAGE_ORDER.index(self.initial_stage)

    def update(
        self,
        detections: Sequence[Detection],
        zone_counts: Mapping[str, int],
        table_track_ids: Sequence[int],
        role_track_ids: Mapping[str, Sequence[int]],
        frame_index: int,
        movement_px: float,
        stage_observable: bool = True,
        stage_hold_reason: Optional[str] = None,
        stage_frame_index: Optional[int] = None,
    ) -> TAVRFrameState:
        stage_frame = frame_index if stage_frame_index is None else stage_frame_index
        normalized_role_track_ids = {
            role: sorted(set(track_ids)) for role, track_ids in role_track_ids.items()
        }
        if not self.initialized:
            self.current_stage_start_frame = stage_frame
            self.initialized = True
        role_counts = {
            role: len(track_ids) for role, track_ids in normalized_role_track_ids.items()
        }
        track_role_summaries = self._update_track_histories(
            detections=detections,
            table_track_ids=table_track_ids,
            role_track_ids=normalized_role_track_ids,
            frame_index=frame_index,
        )
        recent_table_summaries = self._recent_table_summaries(
            current_table_track_ids=table_track_ids,
            frame_index=frame_index,
        )
        recent_table_track_ids = sorted(recent_table_summaries)
        signals = _signals(zone_counts, len(detections), movement_px)
        signals["stage_observable"] = 1.0 if stage_observable else 0.0
        if not stage_observable and stage_hold_reason:
            signals[f"stage_hold_{stage_hold_reason}"] = 1.0
        if not stage_observable:
            stage = TAVR_STAGE_ORDER[self.current_stage_index]
            return TAVRFrameState(
                stage=stage,
                stage_label=TAVR_STAGE_LABELS[stage],
                confidence=0.2,
                table_count=len(set(table_track_ids)),
                table_track_ids=sorted(set(table_track_ids)),
                role_counts=role_counts,
                role_track_ids=normalized_role_track_ids,
                track_role_summaries=track_role_summaries,
                signals=signals,
                note=_stage_hold_note(stage, stage_hold_reason),
                recent_table_track_ids=recent_table_track_ids,
                recent_table_summaries=recent_table_summaries,
            )
        stage_scores = _stage_scores(signals, stage_frame)
        stage_index, confidence = self._choose_stage(stage_scores, stage_frame)
        if stage_index != self.current_stage_index:
            self.current_stage_start_frame = stage_frame
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
            track_role_summaries=track_role_summaries,
            signals=signals,
            note=TAVR_STAGE_NOTES[stage],
            recent_table_track_ids=recent_table_track_ids,
            recent_table_summaries=recent_table_summaries,
        )

    def _update_track_histories(
        self,
        detections: Sequence[Detection],
        table_track_ids: Sequence[int],
        role_track_ids: Mapping[str, Sequence[int]],
        frame_index: int,
    ) -> Dict[int, TrackRoleSummary]:
        roles_by_track: Dict[int, List[str]] = {}
        for role, track_ids in role_track_ids.items():
            for track_id in track_ids:
                roles_by_track.setdefault(track_id, []).append(role)

        table_ids = set(table_track_ids)
        active_summaries: Dict[int, TrackRoleSummary] = {}
        for detection in detections:
            history = self.track_histories.setdefault(
                detection.track_id,
                _TrackRoleHistory(
                    track_id=detection.track_id,
                    first_frame=frame_index,
                    last_frame=frame_index,
                ),
            )
            history.update(
                frame_index=frame_index,
                roles=roles_by_track.get(detection.track_id, ["unassigned"]),
                at_table=detection.track_id in table_ids,
            )
            active_summaries[detection.track_id] = history.snapshot()
        return active_summaries

    def _recent_table_summaries(
        self,
        current_table_track_ids: Sequence[int],
        frame_index: int,
    ) -> Dict[int, TrackRoleSummary]:
        recent: Dict[int, TrackRoleSummary] = {}
        current_ids = set(current_table_track_ids)
        for track_id in current_ids:
            history = self.track_histories.get(track_id)
            if history is not None:
                recent[track_id] = history.snapshot()

        for track_id, history in self.track_histories.items():
            if track_id in recent:
                continue
            if not history.last_seen_at_table or history.last_table_frame is None:
                continue
            if frame_index - history.last_table_frame > self.recent_table_hold_frames:
                continue
            recent[track_id] = history.snapshot()
        return recent

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
                and delivery_score > current_score + self.advance_margin
                and delivery_score > next_score + 0.05
            ):
                return delivery_index, min(delivery_score, 0.95)

        if (
            next_index > self.current_stage_index
            and next_score >= self.min_confidence_to_advance
            and next_score > current_score + self.advance_margin
        ):
            return next_index, min(next_score, 0.95)
        return self.current_stage_index, min(max(current_score, next_score), 0.9)


def _stage_hold_note(stage: str, reason: Optional[str]) -> str:
    base_note = TAVR_STAGE_NOTES[stage]
    if reason == "static_table_fallback":
        return (
            f"{base_note} Stage held because static table fallback is "
            "table-roster evidence, not procedure-stage evidence."
        )
    if reason == "non_room_view":
        return f"{base_note} Stage held because the room view is unavailable."
    return f"{base_note} Stage held because procedure-stage evidence is not observable."


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


def _dominant_role(role_counts: Mapping[str, int]) -> str:
    if not role_counts:
        return "unassigned"
    priority = {role: index for index, role in enumerate(ROLE_DOMINANCE_ORDER)}
    return max(
        role_counts.items(),
        key=lambda item: (item[1], -priority.get(item[0], len(priority))),
    )[0]
