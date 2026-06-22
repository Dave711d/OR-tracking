"""De-identified room workflow state derived from OR video tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Sequence, Set

from .models import Detection
from .tavr import TAVRFrameState


PATIENT_STATE_LABELS: Dict[str, str] = {
    "waiting_outside": "Patient out of room",
    "entering_room": "Patient entering room",
    "in_room": "Patient in room",
    "on_table": "Patient on table",
    "in_room_unverified": "Patient in room - room view unavailable",
    "leaving_room": "Patient leaving room",
    "out_of_room": "Patient out of room",
}

ROLE_LABELS: Dict[str, str] = {
    "access_operator": "Proceduralist",
    "table_operator": "Proceduralist",
    "anesthesia": "Anaesthetist",
    "device_prep": "Device prep",
    "imaging": "Imaging operator",
    "entry_supply": "Circulator",
    "unassigned": "Unassigned motion",
}

PROCEDURALIST_ROLES = {"access_operator", "table_operator"}


@dataclass(frozen=True)
class WorkflowEvent:
    """One de-identified workflow event surfaced to the operator."""

    frame_index: int
    code: str
    label: str
    detail: str
    severity: str = "info"

    def to_compact(self) -> str:
        return f"{self.code}:{self.label}:{self.detail}"


@dataclass(frozen=True)
class WorkflowFrameState:
    """Current workflow state attached to a tracked frame."""

    patient_state: str
    patient_label: str
    patient_confidence: float
    room_view: str
    tracking_available: bool
    active_role_track_ids: Dict[str, List[int]]
    key_events: List[WorkflowEvent] = field(default_factory=list)
    event_log: List[WorkflowEvent] = field(default_factory=list)

    @property
    def anaesthetist_track_ids(self) -> List[int]:
        return self.active_role_track_ids.get("anesthesia", [])

    @property
    def proceduralist_track_ids(self) -> List[int]:
        ids: Set[int] = set()
        for role in PROCEDURALIST_ROLES:
            ids.update(self.active_role_track_ids.get(role, []))
        return sorted(ids)

    def to_row_fields(self) -> Dict[str, object]:
        return {
            "patient_room_state": self.patient_state,
            "patient_room_label": self.patient_label,
            "patient_confidence": round(float(self.patient_confidence), 3),
            "workflow_room_view": self.room_view,
            "workflow_tracking_available": self.tracking_available,
            "anaesthetist_track_ids": ",".join(
                str(track_id) for track_id in self.anaesthetist_track_ids
            ),
            "proceduralist_track_ids": ",".join(
                str(track_id) for track_id in self.proceduralist_track_ids
            ),
            "workflow_role_track_ids": ";".join(
                f"{role}:{','.join(str(track_id) for track_id in track_ids)}"
                for role, track_ids in sorted(self.active_role_track_ids.items())
            ),
            "workflow_event_codes": ",".join(event.code for event in self.key_events),
            "workflow_events": "; ".join(event.to_compact() for event in self.key_events),
            "workflow_event_log": "; ".join(
                event.to_compact() for event in self.event_log[-10:]
            ),
        }


@dataclass
class CaseWorkflowAnalyzer:
    """Stateful patient-room and key-event inference over tracked frames.

    The analyzer intentionally emits de-identified room-state events. It tracks
    the case/patient position in the room, not a patient identity.
    """

    patient_state: str = "waiting_outside"
    patient_seen_in_room: bool = False
    last_stage: Optional[str] = None
    last_room_view: Optional[str] = None
    seen_role_events: Set[str] = field(default_factory=set)
    last_table_ids: Set[int] = field(default_factory=set)
    event_log: List[WorkflowEvent] = field(default_factory=list)

    def update(
        self,
        *,
        detections: Sequence[Detection],
        zone_counts: Mapping[str, int],
        role_track_ids: Mapping[str, Sequence[int]],
        tavr: Optional[TAVRFrameState],
        alert_flags: Sequence[str],
        frame_index: int,
    ) -> WorkflowFrameState:
        active_roles = {
            role: sorted(set(track_ids))
            for role, track_ids in role_track_ids.items()
        }
        room_view = "non_room" if "non_room_view" in alert_flags else "room"
        tracking_available = room_view == "room"
        table_ids = set(tavr.table_track_ids if tavr else [])
        table_count = len(table_ids)
        recent_table_count = len(tavr.recent_table_track_ids if tavr else [])
        stage = tavr.stage if tavr else None
        next_patient_state = self._patient_state(
            stage=stage,
            table_count=table_count,
            recent_table_count=recent_table_count,
            zone_counts=zone_counts,
            role_track_ids=active_roles,
            tracking_available=tracking_available,
        )

        events: List[WorkflowEvent] = []
        if self.last_stage is not None and stage and stage != self.last_stage:
            events.append(
                WorkflowEvent(
                    frame_index=frame_index,
                    code="procedure_stage_changed",
                    label="Procedure stage changed",
                    detail=tavr.stage_label if tavr else stage,
                )
            )
        if self.last_room_view is not None and room_view != self.last_room_view:
            events.append(
                WorkflowEvent(
                    frame_index=frame_index,
                    code="room_view_changed",
                    label="Room view changed",
                    detail=(
                        "Room camera visible"
                        if room_view == "room"
                        else "Room view unavailable / fluoroscopy"
                    ),
                    severity="warn" if room_view != "room" else "info",
                )
            )
        if next_patient_state != self.patient_state:
            events.append(self._patient_event(next_patient_state, frame_index))
        elif not self.event_log and next_patient_state in {"waiting_outside", "in_room"}:
            events.append(self._patient_event(next_patient_state, frame_index))

        for code, role, label in (
            ("anaesthetist_detected", "anesthesia", "Anaesthetist visible"),
            ("proceduralist_detected", "table_operator", "Proceduralist visible"),
            ("access_proceduralist_detected", "access_operator", "Access proceduralist visible"),
            ("imaging_operator_detected", "imaging", "Imaging operator visible"),
            ("circulator_detected", "entry_supply", "Circulator / entry activity visible"),
        ):
            ids = active_roles.get(role, [])
            if ids and code not in self.seen_role_events:
                self.seen_role_events.add(code)
                events.append(
                    WorkflowEvent(
                        frame_index=frame_index,
                        code=code,
                        label=label,
                        detail=f"track IDs {', '.join(str(track_id) for track_id in ids)}",
                    )
                )

        if table_ids != self.last_table_ids:
            if table_ids:
                detail = f"active table track IDs {', '.join(str(track_id) for track_id in sorted(table_ids))}"
            else:
                detail = "table-side roster cleared"
            events.append(
                WorkflowEvent(
                    frame_index=frame_index,
                    code="table_roster_changed",
                    label="Table roster changed",
                    detail=detail,
                )
            )

        self.patient_state = next_patient_state
        if next_patient_state in {"in_room", "on_table", "in_room_unverified", "leaving_room"}:
            self.patient_seen_in_room = True
        self.last_stage = stage
        self.last_room_view = room_view
        self.last_table_ids = table_ids
        if events:
            self.event_log.extend(events)
            self.event_log = self.event_log[-50:]

        return WorkflowFrameState(
            patient_state=next_patient_state,
            patient_label=PATIENT_STATE_LABELS[next_patient_state],
            patient_confidence=self._patient_confidence(
                next_patient_state,
                tracking_available=tracking_available,
                table_count=table_count,
                recent_table_count=recent_table_count,
                detections_count=len(detections),
            ),
            room_view=room_view,
            tracking_available=tracking_available,
            active_role_track_ids=active_roles,
            key_events=events,
            event_log=list(self.event_log),
        )

    def _patient_state(
        self,
        *,
        stage: Optional[str],
        table_count: int,
        recent_table_count: int,
        zone_counts: Mapping[str, int],
        role_track_ids: Mapping[str, Sequence[int]],
        tracking_available: bool,
    ) -> str:
        entry_count = zone_counts.get("entry", 0)
        anaesthesia_count = len(role_track_ids.get("anesthesia", []))
        proceduralist_count = len(role_track_ids.get("table_operator", [])) + len(
            role_track_ids.get("access_operator", [])
        )

        if not tracking_available:
            if self.patient_seen_in_room or recent_table_count:
                return "in_room_unverified"
            return self.patient_state

        if stage == "closure_finish" and self.patient_seen_in_room:
            if table_count == 0 and entry_count > 0:
                return "leaving_room"
            if table_count == 0 and recent_table_count == 0:
                return "out_of_room"

        if table_count > 0:
            return "on_table"

        if self.patient_seen_in_room or stage not in {None, "room_prep_drape"}:
            return "in_room"

        if entry_count > 0:
            return "entering_room"

        if anaesthesia_count > 0 or proceduralist_count > 0:
            return "in_room"

        return "waiting_outside"

    def _patient_confidence(
        self,
        patient_state: str,
        *,
        tracking_available: bool,
        table_count: int,
        recent_table_count: int,
        detections_count: int,
    ) -> float:
        if patient_state == "in_room_unverified":
            return 0.42 if recent_table_count else 0.25
        if table_count > 0:
            return 0.86
        if not tracking_available:
            return 0.25
        if detections_count > 0:
            return 0.68
        return 0.55 if patient_state in {"waiting_outside", "out_of_room"} else 0.5

    def _patient_event(self, patient_state: str, frame_index: int) -> WorkflowEvent:
        label = PATIENT_STATE_LABELS[patient_state]
        code = {
            "waiting_outside": "patient_out_of_room",
            "entering_room": "patient_entering_room",
            "in_room": "patient_in_room",
            "on_table": "patient_on_table",
            "in_room_unverified": "patient_room_status_held",
            "leaving_room": "patient_leaving_room",
            "out_of_room": "patient_out_of_room",
        }[patient_state]
        detail = {
            "waiting_outside": "No patient-room evidence yet",
            "entering_room": "Entry-zone activity before table evidence",
            "in_room": "Room workflow evidence indicates patient present",
            "on_table": "Table-side procedural evidence indicates patient on table",
            "in_room_unverified": "Holding last room-state while room view is unavailable",
            "leaving_room": "Closure with entry activity and no active table roster",
            "out_of_room": "Closure complete with no active table roster",
        }[patient_state]
        return WorkflowEvent(
            frame_index=frame_index,
            code=code,
            label=label,
            detail=detail,
            severity="warn" if patient_state == "in_room_unverified" else "info",
        )
