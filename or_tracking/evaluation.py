"""Evaluation helpers for TAVR tracking runs."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from .models import FrameMetrics
from .tavr import TAVRFrameState, TrackRoleSummary


def summarize_tavr_metrics(
    metrics: Sequence[FrameMetrics],
    confidence_threshold: float = 0.45,
) -> Dict[str, Any]:
    """Return an auditable TAVR summary for one processed video."""

    tavr_metrics = [metric for metric in metrics if metric.tavr is not None]
    return {
        "stage_timeline": tavr_stage_timeline(tavr_metrics),
        "track_role_report": tavr_track_role_report(tavr_metrics),
        "current_table_roster": current_table_roster(tavr_metrics),
        "peak_table_roster": peak_table_roster(tavr_metrics),
        "table_presence_roster": table_presence_roster(tavr_metrics),
        "low_confidence_segments": low_confidence_segments(
            tavr_metrics,
            threshold=confidence_threshold,
        ),
        "quality_flags": tavr_quality_flags(tavr_metrics),
    }


def tavr_stage_timeline(metrics: Sequence[FrameMetrics]) -> List[Dict[str, Any]]:
    """Group contiguous TAVR stage estimates with table-roster context."""

    if not metrics:
        return []

    timeline: List[Dict[str, Any]] = []
    active_metric = metrics[0]
    active_state = _tavr_state(active_metric)
    start_index = 0

    for index, metric in enumerate(metrics[1:], start=1):
        state = _tavr_state(metric)
        if state.stage != active_state.stage:
            timeline.append(
                _timeline_item(metrics, start_index, index - 1, active_state)
            )
            active_state = state
            start_index = index

    timeline.append(_timeline_item(metrics, start_index, len(metrics) - 1, active_state))
    return timeline


def tavr_track_role_report(metrics: Sequence[FrameMetrics]) -> List[Dict[str, Any]]:
    """Return the latest persistent role summary for every seen track."""

    latest: Dict[int, TrackRoleSummary] = {}
    for metric in metrics:
        state = _tavr_state(metric)
        for track_id, summary in state.track_role_summaries.items():
            previous = latest.get(track_id)
            if previous is None or summary.last_frame >= previous.last_frame:
                latest[track_id] = summary

    return [
        {
            "track_id": summary.track_id,
            "dominant_role": summary.dominant_role,
            "frames_seen": summary.frames_seen,
            "first_frame": summary.first_frame,
            "last_frame": summary.last_frame,
            "table_frames": summary.table_frames,
            "table_presence_ratio": round(summary.table_presence_ratio, 3),
            "role_counts": summary.role_counts,
        }
        for summary in sorted(
            latest.values(),
            key=lambda item: (-item.table_presence_ratio, -item.frames_seen, item.track_id),
        )
    ]


def current_table_roster(metrics: Sequence[FrameMetrics]) -> List[Dict[str, Any]]:
    """Return the most recent table-side roster, including role dwell."""

    if not metrics:
        return []

    state = _tavr_state(metrics[-1])
    return _roster_from_state(state)


def peak_table_roster(metrics: Sequence[FrameMetrics]) -> Dict[str, Any]:
    """Return the roster from the frame with the largest table-side count."""

    if not metrics:
        return {
            "frame_index": None,
            "timestamp_s": None,
            "table_count": 0,
            "roster": [],
        }

    peak_metric = max(
        metrics,
        key=lambda metric: (_tavr_state(metric).table_count, metric.frame_index),
    )
    peak_state = _tavr_state(peak_metric)
    return {
        "frame_index": peak_metric.frame_index,
        "timestamp_s": peak_metric.timestamp_s,
        "table_count": peak_state.table_count,
        "roster": _roster_from_state(peak_state),
    }


def table_presence_roster(
    metrics: Sequence[FrameMetrics],
    min_table_frames: int = 3,
) -> List[Dict[str, Any]]:
    """Return tracks that spent meaningful time at the table during the clip."""

    roster = []
    for summary in tavr_track_role_report(metrics):
        if summary["table_frames"] < min_table_frames:
            continue
        roster.append(
            {
                "track_id": summary["track_id"],
                "dominant_role": summary["dominant_role"],
                "frames_seen": summary["frames_seen"],
                "table_frames": summary["table_frames"],
                "table_presence_ratio": summary["table_presence_ratio"],
                "first_frame": summary["first_frame"],
                "last_frame": summary["last_frame"],
                "label": (
                    f"ID {summary['track_id']} {summary['dominant_role']} "
                    f"table={summary['table_presence_ratio']:.0%}"
                ),
            }
        )
    return roster


def _roster_from_state(state: TAVRFrameState) -> List[Dict[str, Any]]:
    roster = []
    for track_id in state.table_track_ids:
        summary = state.track_role_summaries.get(track_id)
        if summary is None:
            continue
        roster.append(
            {
                "track_id": track_id,
                "dominant_role": summary.dominant_role,
                "frames_seen": summary.frames_seen,
                "table_presence_ratio": round(summary.table_presence_ratio, 3),
                "label": summary.to_who_at_table(),
            }
        )
    return roster


def low_confidence_segments(
    metrics: Sequence[FrameMetrics],
    threshold: float = 0.45,
) -> List[Dict[str, Any]]:
    """Group contiguous frames where TAVR stage confidence is weak."""

    segments: List[Dict[str, Any]] = []
    active_start: Optional[int] = None
    active_end: Optional[int] = None

    for index, metric in enumerate(metrics):
        state = _tavr_state(metric)
        if state.confidence < threshold:
            if active_start is None:
                active_start = index
            active_end = index
            continue
        if active_start is not None and active_end is not None:
            segments.append(_confidence_item(metrics, active_start, active_end))
            active_start = None
            active_end = None

    if active_start is not None and active_end is not None:
        segments.append(_confidence_item(metrics, active_start, active_end))

    return segments


def tavr_quality_flags(metrics: Sequence[FrameMetrics]) -> List[Dict[str, Any]]:
    """Flag clips that are likely poor chronology or tracking evidence."""

    if not metrics:
        return []

    flags: List[Dict[str, Any]] = []
    timeline = tavr_stage_timeline(metrics)
    duration_s = max(metrics[-1].timestamp_s - metrics[0].timestamp_s, 0.0)
    if duration_s > 0 and len(timeline) / duration_s > 0.06:
        flags.append(
            {
                "code": "rapid_stage_progression",
                "message": (
                    "Stage changes are dense for the clip duration; this may be "
                    "edited footage or an unseeded slice rather than a continuous case."
                ),
                "stage_count": len(timeline),
                "duration_s": round(duration_s, 3),
            }
        )
    terminal_stage = next(
        (item for item in timeline if item["stage"] == "closure_finish"),
        None,
    )
    if (
        terminal_stage is not None
        and duration_s > 0
        and terminal_stage["start_s"] - metrics[0].timestamp_s < duration_s * 0.5
    ):
        flags.append(
            {
                "code": "early_terminal_stage",
                "message": (
                    "The timeline reached closure early in the clip; the footage may "
                    "be edited, montage-like, or too visually ambiguous for procedure chronology."
                ),
                "closure_start_s": round(terminal_stage["start_s"], 3),
                "duration_s": round(duration_s, 3),
            }
        )

    track_report = tavr_track_role_report(metrics)
    if len(track_report) > max(80, len(metrics) * 0.08):
        flags.append(
            {
                "code": "fragmented_tracks",
                "message": (
                    "Many short-lived track IDs were created; raise min-area, use a "
                    "cleaner view, or inspect the annotated video before trusting roster dwell."
                ),
                "track_count": len(track_report),
                "frames_processed": len(metrics),
            }
        )

    peak_people_count = max((metric.people_count for metric in metrics), default=0)
    if peak_people_count >= 25:
        flags.append(
            {
                "code": "high_motion_noise",
                "message": (
                    "A frame had unusually many detections for OR staff tracking; "
                    "graphics, camera motion, or montage edits may be included."
                ),
                "peak_people_count": peak_people_count,
            }
        )

    return flags


def _timeline_item(
    metrics: Sequence[FrameMetrics],
    start_index: int,
    end_index: int,
    state: TAVRFrameState,
) -> Dict[str, Any]:
    end_state = _tavr_state(metrics[end_index])
    return {
        "stage": state.stage,
        "stage_label": state.stage_label,
        "start_frame": metrics[start_index].frame_index,
        "end_frame": metrics[end_index].frame_index,
        "start_s": metrics[start_index].timestamp_s,
        "end_s": metrics[end_index].timestamp_s,
        "peak_table_count": max(
            _tavr_state(metric).table_count
            for metric in metrics[start_index : end_index + 1]
        ),
        "table_roster": [
            end_state.track_role_summaries[track_id].to_who_at_table()
            for track_id in end_state.table_track_ids
            if track_id in end_state.track_role_summaries
        ],
        "note": state.note,
    }


def _confidence_item(
    metrics: Sequence[FrameMetrics],
    start_index: int,
    end_index: int,
) -> Dict[str, Any]:
    confidences = [
        _tavr_state(metric).confidence for metric in metrics[start_index : end_index + 1]
    ]
    return {
        "start_frame": metrics[start_index].frame_index,
        "end_frame": metrics[end_index].frame_index,
        "start_s": metrics[start_index].timestamp_s,
        "end_s": metrics[end_index].timestamp_s,
        "min_confidence": round(min(confidences), 3),
        "max_confidence": round(max(confidences), 3),
    }


def _tavr_state(metric: FrameMetrics) -> TAVRFrameState:
    if metric.tavr is None:
        raise ValueError("TAVR evaluation requires metrics with TAVR state")
    return metric.tavr
