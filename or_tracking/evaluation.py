"""Evaluation helpers for TAVR tracking runs."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .models import FrameMetrics
from .tavr import (
    ROLE_DOMINANCE_ORDER,
    TAVRFrameState,
    TAVR_STAGE_LABELS,
    TAVR_STAGE_ORDER,
    TrackRoleSummary,
)


TAVR_SUMMARY_CSV_TABLES: Dict[str, List[str]] = {
    "view_segments": [
        "view",
        "is_room_view",
        "tracking_available",
        "start_frame",
        "end_frame",
        "start_s",
        "end_s",
        "duration_s",
        "frames",
        "mean_colorfulness",
        "mean_table_count",
        "peak_table_count",
        "dominant_stage",
        "stage_counts",
        "label",
    ],
    "stage_timeline": [
        "stage",
        "stage_label",
        "start_frame",
        "end_frame",
        "start_s",
        "end_s",
        "peak_table_count",
        "peak_table_roster",
        "table_presence_roster",
        "table_roster",
        "note",
    ],
    "stage_staffing_summary": [
        "stage",
        "stage_label",
        "segment_count",
        "start_frame",
        "end_frame",
        "start_s",
        "end_s",
        "duration_s",
        "frames",
        "mean_table_count",
        "peak_table_count",
        "table_occupancy_rate",
        "table_count_distribution",
        "role_counts",
        "unique_table_track_count",
        "table_roster",
    ],
    "stage_table_coverage": [
        "stage_segment_index",
        "stage",
        "stage_label",
        "stage_start_frame",
        "stage_end_frame",
        "stage_start_s",
        "stage_end_s",
        "stage_duration_s",
        "track_id",
        "dominant_role",
        "observed_table_frames",
        "first_seen_frame",
        "last_seen_frame",
        "first_seen_s",
        "last_seen_s",
        "coverage_ratio",
        "estimated_table_duration_s",
        "entered_during_stage",
        "exited_during_stage",
        "spans_full_stage",
        "role_counts",
        "label",
    ],
    "table_transition_events": [
        "event_type",
        "timestamp_s",
        "frame_index",
        "track_id",
        "dominant_role",
        "stage",
        "stage_label",
        "stage_segment_index",
        "coverage_ratio",
        "observed_table_frames",
        "label",
    ],
    "table_presence_intervals": [
        "track_id",
        "dominant_role",
        "dominant_stage",
        "start_frame",
        "end_frame",
        "start_s",
        "end_s",
        "observed_table_frames",
        "interval_duration_s",
        "role_counts",
        "stage_counts",
        "label",
    ],
    "track_role_report": [
        "track_id",
        "dominant_role",
        "frames_seen",
        "first_frame",
        "last_frame",
        "table_frames",
        "table_presence_ratio",
        "role_counts",
    ],
    "quality_flags": [
        "code",
        "message",
        "stage_count",
        "duration_s",
        "closure_start_s",
        "track_count",
        "frames_processed",
        "peak_people_count",
        "peak_table_count",
        "mean_movement_px",
        "frames",
        "ratio",
    ],
    "low_confidence_segments": [
        "start_frame",
        "end_frame",
        "start_s",
        "end_s",
        "min_confidence",
        "max_confidence",
    ],
}


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
        "table_presence_intervals": table_presence_intervals(
            tavr_metrics,
            min_observed_table_frames=3,
        ),
        "view_segments": view_segments(tavr_metrics),
        "table_transition_events": table_transition_events(tavr_metrics),
        "stage_table_coverage": stage_table_coverage(tavr_metrics),
        "stage_staffing_summary": stage_staffing_summary(tavr_metrics),
        "low_confidence_segments": low_confidence_segments(
            tavr_metrics,
            threshold=confidence_threshold,
        ),
        "quality_flags": tavr_quality_flags(tavr_metrics),
    }


def write_tavr_summary_csvs(
    output_dir: str | Path,
    run_stem: str,
    tavr_summary: Dict[str, Any],
) -> Dict[str, str]:
    """Write derived TAVR summary tables as CSV files."""

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    paths = {}
    for table_name, fieldnames in TAVR_SUMMARY_CSV_TABLES.items():
        rows = tavr_summary.get(table_name, [])
        if not rows:
            continue
        path = output_path / f"{run_stem}_{table_name}.csv"
        _write_summary_rows(path, rows, fieldnames)
        paths[table_name] = str(path)
    return paths


def score_tavr_metrics(
    metrics: Sequence[FrameMetrics],
    labels: Dict[str, Any],
) -> Dict[str, Any]:
    """Score tracker output against lightweight human/test labels."""

    tavr_metrics = [metric for metric in metrics if metric.tavr is not None]
    return {
        "stage_score": _stage_score(tavr_metrics, labels.get("stage_segments", [])),
        "table_count_score": _table_count_score(
            tavr_metrics,
            labels.get("table_count_segments", []),
        ),
        "table_presence_score": _table_presence_score(
            tavr_metrics,
            labels.get("table_presence_expectations", []),
        ),
        "stage_staffing_score": _stage_staffing_score(
            tavr_metrics,
            labels.get("stage_staffing_expectations", []),
        ),
        "quality_flag_score": _quality_flag_score(
            tavr_metrics,
            labels.get("quality_flag_expectations", []),
        ),
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


def table_presence_intervals(
    metrics: Sequence[FrameMetrics],
    max_gap_frames: int = 12,
    max_gap_s: float = 1.0,
    min_observed_table_frames: int = 1,
) -> List[Dict[str, Any]]:
    """Return contiguous table-side intervals for each tracked ID."""

    if not metrics:
        return []

    observations = _table_observations(metrics)
    sample_period_s = _sample_period_s(metrics)
    intervals: List[Dict[str, Any]] = []
    for track_id in sorted(observations):
        active: List[Dict[str, Any]] = []
        for observation in observations[track_id]:
            if active and _observation_gap_exceeded(
                active[-1],
                observation,
                max_gap_frames=max_gap_frames,
                max_gap_s=max_gap_s,
            ):
                if len(active) >= min_observed_table_frames:
                    intervals.append(_table_interval_item(track_id, active, sample_period_s))
                active = []
            active.append(observation)
        if len(active) >= min_observed_table_frames:
            intervals.append(_table_interval_item(track_id, active, sample_period_s))

    intervals.sort(
        key=lambda item: (
            item["start_s"],
            item["track_id"],
            -item["observed_table_frames"],
        )
    )
    return intervals


def view_segments(metrics: Sequence[FrameMetrics]) -> List[Dict[str, Any]]:
    """Group contiguous room/non-room view stretches."""

    if not metrics:
        return []

    segments: List[Dict[str, Any]] = []
    start_index = 0
    active_view = _view_label(metrics[0])
    for index, metric in enumerate(metrics[1:], start=1):
        view = _view_label(metric)
        if view != active_view:
            segments.append(_view_segment_item(metrics, start_index, index - 1))
            start_index = index
            active_view = view
    segments.append(_view_segment_item(metrics, start_index, len(metrics) - 1))
    return segments


def table_transition_events(
    metrics: Sequence[FrameMetrics],
    min_observed_table_frames: int = 3,
) -> List[Dict[str, Any]]:
    """Return entry/exit-style table events split by stage coverage rows."""

    events: List[Dict[str, Any]] = []
    for coverage in stage_table_coverage(
        metrics,
        min_observed_table_frames=min_observed_table_frames,
    ):
        entry_type = (
            "table_entry"
            if coverage["entered_during_stage"]
            else "table_present_at_stage_start"
        )
        exit_type = (
            "table_exit"
            if coverage["exited_during_stage"]
            else "table_present_at_stage_end"
        )
        events.append(_table_transition_event(coverage, entry_type, is_entry=True))
        events.append(_table_transition_event(coverage, exit_type, is_entry=False))

    event_order = {
        "table_present_at_stage_start": 0,
        "table_entry": 1,
        "table_exit": 2,
        "table_present_at_stage_end": 3,
    }
    events.sort(
        key=lambda item: (
            item["timestamp_s"],
            event_order.get(item["event_type"], 9),
            item["track_id"],
        )
    )
    return events


def stage_staffing_summary(
    metrics: Sequence[FrameMetrics],
    min_observed_table_frames: int = 3,
) -> List[Dict[str, Any]]:
    """Summarize table-side staffing and role mix for each observed TAVR stage."""

    if not metrics:
        return []

    sample_period_s = _sample_period_s(metrics)
    accumulators: Dict[str, Dict[str, Any]] = {}
    timeline = tavr_stage_timeline(metrics)
    segment_counts = _counts(item["stage"] for item in timeline)

    for metric in metrics:
        state = _tavr_state(metric)
        accumulator = accumulators.setdefault(
            state.stage,
            {
                "stage": state.stage,
                "stage_label": state.stage_label,
                "first_frame": metric.frame_index,
                "last_frame": metric.frame_index,
                "start_s": metric.timestamp_s,
                "end_s": metric.timestamp_s,
                "frames": 0,
                "table_counts": [],
                "role_counts": {},
                "tracks": {},
            },
        )
        accumulator["first_frame"] = min(accumulator["first_frame"], metric.frame_index)
        accumulator["last_frame"] = max(accumulator["last_frame"], metric.frame_index)
        accumulator["start_s"] = min(accumulator["start_s"], metric.timestamp_s)
        accumulator["end_s"] = max(accumulator["end_s"], metric.timestamp_s)
        accumulator["frames"] += 1
        accumulator["table_counts"].append(state.table_count)
        _merge_counts(accumulator["role_counts"], state.role_counts)

        for track_id in state.table_track_ids:
            role = _role_for_track(state, track_id)
            track = accumulator["tracks"].setdefault(
                track_id,
                {
                    "track_id": track_id,
                    "first_frame": metric.frame_index,
                    "last_frame": metric.frame_index,
                    "first_s": metric.timestamp_s,
                    "last_s": metric.timestamp_s,
                    "observed_table_frames": 0,
                    "role_counts": {},
                },
            )
            track["first_frame"] = min(track["first_frame"], metric.frame_index)
            track["last_frame"] = max(track["last_frame"], metric.frame_index)
            track["first_s"] = min(track["first_s"], metric.timestamp_s)
            track["last_s"] = max(track["last_s"], metric.timestamp_s)
            track["observed_table_frames"] += 1
            track["role_counts"][role] = track["role_counts"].get(role, 0) + 1

    summaries: List[Dict[str, Any]] = []
    for stage, accumulator in accumulators.items():
        table_counts = accumulator["table_counts"]
        frames = accumulator["frames"]
        table_roster = [
            _stage_staffing_track_item(track, frames, sample_period_s)
            for track in accumulator["tracks"].values()
            if track["observed_table_frames"] >= min_observed_table_frames
        ]
        table_roster.sort(
            key=lambda item: (
                -item["observed_table_frames"],
                item["first_s"],
                item["track_id"],
            )
        )
        summaries.append(
            {
                "stage": stage,
                "stage_label": accumulator["stage_label"],
                "segment_count": segment_counts.get(stage, 0),
                "start_frame": accumulator["first_frame"],
                "end_frame": accumulator["last_frame"],
                "start_s": round(float(accumulator["start_s"]), 3),
                "end_s": round(float(accumulator["end_s"]), 3),
                "duration_s": round(
                    float(
                        max(
                            0.0,
                            accumulator["end_s"]
                            - accumulator["start_s"]
                            + sample_period_s,
                        )
                    ),
                    3,
                ),
                "frames": frames,
                "mean_table_count": (
                    round(sum(table_counts) / len(table_counts), 3)
                    if table_counts
                    else None
                ),
                "peak_table_count": max(table_counts) if table_counts else 0,
                "table_occupancy_rate": _ratio(
                    sum(1 for count in table_counts if count > 0),
                    len(table_counts),
                ),
                "table_count_distribution": _counts(str(count) for count in table_counts),
                "role_counts": dict(sorted(accumulator["role_counts"].items())),
                "unique_table_track_count": len(accumulator["tracks"]),
                "table_roster": table_roster,
            }
        )

    order = {stage: index for index, stage in enumerate(TAVR_STAGE_ORDER)}
    summaries.sort(
        key=lambda item: (
            item["start_s"],
            order.get(item["stage"], len(order)),
        )
    )
    return summaries


def stage_table_coverage(
    metrics: Sequence[FrameMetrics],
    min_observed_table_frames: int = 1,
) -> List[Dict[str, Any]]:
    """Return table-side track coverage rows split by contiguous TAVR stage."""

    if not metrics:
        return []

    rows: List[Dict[str, Any]] = []
    active_state = _tavr_state(metrics[0])
    segment_start = 0
    segment_index = 0
    for index, metric in enumerate(metrics[1:], start=1):
        state = _tavr_state(metric)
        if state.stage != active_state.stage:
            rows.extend(
                _stage_table_coverage_rows(
                    metrics[segment_start:index],
                    segment_index=segment_index,
                    min_observed_table_frames=min_observed_table_frames,
                )
            )
            segment_index += 1
            segment_start = index
            active_state = state

    rows.extend(
        _stage_table_coverage_rows(
            metrics[segment_start:],
            segment_index=segment_index,
            min_observed_table_frames=min_observed_table_frames,
        )
    )
    return rows


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

    non_room_frames = sum(
        1 for metric in metrics if "non_room_view" in metric.alert_flags
    )
    non_room_ratio = non_room_frames / max(len(metrics), 1)
    if non_room_ratio >= 0.2:
        flags.append(
            {
                "code": "non_room_view",
                "message": (
                    "A substantial portion of the clip appears to be fluoroscopy "
                    "or another non-room view; staff/table tracking is suppressed "
                    "for those frames."
                ),
                "frames": non_room_frames,
                "ratio": round(non_room_ratio, 3),
            }
        )

    room_metrics = [
        metric for metric in metrics if "non_room_view" not in metric.alert_flags
    ]
    room_frames = len(room_metrics)
    room_ratio = room_frames / max(len(metrics), 1)
    room_peak_people = max((metric.people_count for metric in room_metrics), default=0)
    room_peak_table = max(
        (_tavr_state(metric).table_count for metric in room_metrics),
        default=0,
    )
    room_mean_movement = (
        sum(metric.movement_px for metric in room_metrics) / room_frames
        if room_frames
        else 0.0
    )
    if room_frames >= 60 and room_peak_people <= 1 and room_peak_table == 0:
        flags.append(
            {
                "code": "low_motion_room_view",
                "message": (
                    "Room view is visible, but foreground motion evidence is sparse; "
                    "table staffing may be undercounted in this segment."
                ),
                "frames": room_frames,
                "ratio": round(room_ratio, 3),
                "peak_people_count": room_peak_people,
                "peak_table_count": room_peak_table,
                "mean_movement_px": round(room_mean_movement, 3),
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
    segment_metrics = metrics[start_index : end_index + 1]
    return {
        "stage": state.stage,
        "stage_label": state.stage_label,
        "start_frame": metrics[start_index].frame_index,
        "end_frame": metrics[end_index].frame_index,
        "start_s": metrics[start_index].timestamp_s,
        "end_s": metrics[end_index].timestamp_s,
        "peak_table_count": max(
            _tavr_state(metric).table_count
            for metric in segment_metrics
        ),
        "peak_table_roster": peak_table_roster(segment_metrics),
        "table_presence_roster": _interval_roster(segment_metrics),
        "table_roster": [
            end_state.track_role_summaries[track_id].to_who_at_table()
            for track_id in end_state.table_track_ids
            if track_id in end_state.track_role_summaries
        ],
        "note": state.note,
    }


def _view_segment_item(
    metrics: Sequence[FrameMetrics],
    start_index: int,
    end_index: int,
) -> Dict[str, Any]:
    segment_metrics = metrics[start_index : end_index + 1]
    view = _view_label(metrics[start_index])
    sample_period_s = _sample_period_s(segment_metrics)
    colorfulness = [metric.view_colorfulness for metric in segment_metrics]
    table_counts = [_tavr_state(metric).table_count for metric in segment_metrics]
    stages = _counts(_tavr_state(metric).stage for metric in segment_metrics)
    start_metric = metrics[start_index]
    end_metric = metrics[end_index]
    duration_s = max(
        0.0,
        end_metric.timestamp_s - start_metric.timestamp_s + sample_period_s,
    )
    return {
        "view": view,
        "is_room_view": view == "room",
        "tracking_available": view == "room",
        "start_frame": start_metric.frame_index,
        "end_frame": end_metric.frame_index,
        "start_s": round(float(start_metric.timestamp_s), 3),
        "end_s": round(float(end_metric.timestamp_s), 3),
        "duration_s": round(float(duration_s), 3),
        "frames": len(segment_metrics),
        "mean_colorfulness": (
            round(sum(colorfulness) / len(colorfulness), 3)
            if colorfulness
            else None
        ),
        "mean_table_count": (
            round(sum(table_counts) / len(table_counts), 3)
            if table_counts
            else None
        ),
        "peak_table_count": max(table_counts) if table_counts else 0,
        "dominant_stage": _dominant_from_counts(stages),
        "stage_counts": stages,
        "label": (
            f"{view} view {start_metric.timestamp_s:.1f}-"
            f"{end_metric.timestamp_s:.1f}s"
        ),
    }


def _view_label(metric: FrameMetrics) -> str:
    if "non_room_view" in metric.alert_flags:
        return "non_room"
    return "room"


def _table_transition_event(
    coverage: Dict[str, Any],
    event_type: str,
    is_entry: bool,
) -> Dict[str, Any]:
    timestamp_s = coverage["first_seen_s"] if is_entry else coverage["last_seen_s"]
    frame = coverage["first_seen_frame"] if is_entry else coverage["last_seen_frame"]
    return {
        "event_type": event_type,
        "timestamp_s": timestamp_s,
        "frame_index": frame,
        "track_id": coverage["track_id"],
        "dominant_role": coverage["dominant_role"],
        "stage": coverage["stage"],
        "stage_label": coverage["stage_label"],
        "stage_segment_index": coverage["stage_segment_index"],
        "coverage_ratio": coverage["coverage_ratio"],
        "observed_table_frames": coverage["observed_table_frames"],
        "label": (
            f"{timestamp_s:.1f}s {event_type}: ID {coverage['track_id']} "
            f"{coverage['dominant_role']} during {coverage['stage_label']}"
        ),
    }


def _write_summary_rows(
    path: Path,
    rows: Sequence[Dict[str, Any]],
    fieldnames: Sequence[str],
) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    field: _csv_cell(row.get(field))
                    for field in fieldnames
                }
            )


def _csv_cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        labels = [
            item.get("label")
            for item in value
            if isinstance(item, dict) and item.get("label")
        ]
        if labels:
            return "; ".join(str(label) for label in labels)
    return json.dumps(value, sort_keys=True)


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


def _stage_score(
    metrics: Sequence[FrameMetrics],
    stage_segments: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    if not stage_segments:
        return {"covered_frames": 0, "accuracy": None, "segments": [], "confusion": {}}

    correct = 0
    covered = 0
    confusion: Dict[str, Dict[str, int]] = {}
    segment_scores = []
    for segment in stage_segments:
        expected_stage = str(segment["stage"])
        segment_metrics = _metrics_in_window(metrics, segment)
        segment_correct = 0
        for metric in segment_metrics:
            predicted_stage = _tavr_state(metric).stage
            if predicted_stage == expected_stage:
                correct += 1
                segment_correct += 1
            covered += 1
            confusion.setdefault(expected_stage, {})
            confusion[expected_stage][predicted_stage] = (
                confusion[expected_stage].get(predicted_stage, 0) + 1
            )
        segment_scores.append(
            {
                "stage": expected_stage,
                "start_s": segment.get("start_s"),
                "end_s": segment.get("end_s"),
                "frames": len(segment_metrics),
                "accuracy": _ratio(segment_correct, len(segment_metrics)),
            }
        )

    return {
        "covered_frames": covered,
        "accuracy": _ratio(correct, covered),
        "segments": segment_scores,
        "confusion": confusion,
    }


def _table_count_score(
    metrics: Sequence[FrameMetrics],
    count_segments: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    if not count_segments:
        return {"segments": [], "pass_rate": None}

    passed = 0
    segment_scores = []
    for segment in count_segments:
        segment_metrics = _metrics_in_window(metrics, segment)
        counts = [_tavr_state(metric).table_count for metric in segment_metrics]
        min_count = segment.get("min_count")
        max_count = segment.get("max_count")
        min_peak_count = segment.get("min_peak_count")
        min_within_range_rate = float(segment.get("min_within_range_rate", 1.0))
        within = [
            count
            for count in counts
            if (min_count is None or count >= min_count)
            and (max_count is None or count <= max_count)
        ]
        within_rate = _ratio(len(within), len(counts))
        peak_table_count = max(counts) if counts else 0
        range_pass = (
            within_rate is not None
            and (min_count is not None or max_count is not None)
            and within_rate >= min_within_range_rate
        )
        if min_count is None and max_count is None:
            range_pass = True
        peak_pass = min_peak_count is None or peak_table_count >= min_peak_count
        segment_pass = bool(counts) and range_pass and peak_pass
        if segment_pass:
            passed += 1
        segment_scores.append(
            {
                "start_s": segment.get("start_s"),
                "end_s": segment.get("end_s"),
                "min_count": min_count,
                "max_count": max_count,
                "min_peak_count": min_peak_count,
                "min_within_range_rate": min_within_range_rate,
                "frames": len(counts),
                "mean_table_count": round(sum(counts) / len(counts), 3) if counts else None,
                "peak_table_count": peak_table_count,
                "within_range_rate": within_rate,
                "passed": segment_pass,
            }
        )

    return {
        "segments": segment_scores,
        "pass_rate": _ratio(passed, len(count_segments)),
    }


def _table_presence_score(
    metrics: Sequence[FrameMetrics],
    expectations: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    if not expectations:
        return {"expectations": [], "pass_rate": None}

    intervals = table_presence_intervals(metrics, min_observed_table_frames=3)
    passed = 0
    scored_expectations = []
    for expectation in expectations:
        role = expectation.get("role")
        min_intervals = int(expectation.get("min_intervals", 1))
        min_observed_table_frames = int(expectation.get("min_observed_table_frames", 3))
        overlapping = [
            interval
            for interval in intervals
            if _interval_overlaps_expectation(interval, expectation)
            and (role is None or interval["dominant_role"] == role)
            and interval["observed_table_frames"] >= min_observed_table_frames
        ]
        expectation_pass = len(overlapping) >= min_intervals
        if expectation_pass:
            passed += 1
        scored_expectations.append(
            {
                "start_s": expectation.get("start_s"),
                "end_s": expectation.get("end_s"),
                "role": role,
                "min_intervals": min_intervals,
                "min_observed_table_frames": min_observed_table_frames,
                "matched_intervals": overlapping,
                "matched_count": len(overlapping),
                "passed": expectation_pass,
            }
        )

    return {
        "expectations": scored_expectations,
        "pass_rate": _ratio(passed, len(expectations)),
    }


def _stage_staffing_score(
    metrics: Sequence[FrameMetrics],
    expectations: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    if not expectations:
        return {"expectations": [], "pass_rate": None}

    stage_summaries = {
        item["stage"]: item
        for item in stage_staffing_summary(metrics, min_observed_table_frames=1)
    }
    passed = 0
    scored_expectations = []
    for expectation in expectations:
        stage = str(expectation["stage"])
        role = expectation.get("role")
        min_tracks = int(expectation.get("min_tracks", 0))
        min_observed_table_frames = int(expectation.get("min_observed_table_frames", 1))
        min_peak_count = expectation.get("min_peak_count")
        min_mean_count = expectation.get("min_mean_count")
        min_table_occupancy_rate = expectation.get("min_table_occupancy_rate")
        stage_summary = stage_summaries.get(stage)
        matching_roster = []
        if stage_summary is not None:
            matching_roster = [
                track
                for track in stage_summary["table_roster"]
                if (role is None or track["dominant_role"] == role)
                and track["observed_table_frames"] >= min_observed_table_frames
            ]

        checks = {
            "stage_present": stage_summary is not None,
            "min_tracks": len(matching_roster) >= min_tracks,
            "min_peak_count": (
                min_peak_count is None
                or (
                    stage_summary is not None
                    and stage_summary["peak_table_count"] >= min_peak_count
                )
            ),
            "min_mean_count": (
                min_mean_count is None
                or (
                    stage_summary is not None
                    and stage_summary["mean_table_count"] is not None
                    and stage_summary["mean_table_count"] >= min_mean_count
                )
            ),
            "min_table_occupancy_rate": (
                min_table_occupancy_rate is None
                or (
                    stage_summary is not None
                    and stage_summary["table_occupancy_rate"] is not None
                    and stage_summary["table_occupancy_rate"] >= min_table_occupancy_rate
                )
            ),
        }
        expectation_pass = all(checks.values())
        if expectation_pass:
            passed += 1
        scored_expectations.append(
            {
                "stage": stage,
                "stage_label": TAVR_STAGE_LABELS.get(stage, stage),
                "role": role,
                "min_tracks": min_tracks,
                "min_observed_table_frames": min_observed_table_frames,
                "min_peak_count": min_peak_count,
                "min_mean_count": min_mean_count,
                "min_table_occupancy_rate": min_table_occupancy_rate,
                "matched_tracks": matching_roster,
                "matched_track_count": len(matching_roster),
                "checks": checks,
                "passed": expectation_pass,
            }
        )

    return {
        "expectations": scored_expectations,
        "pass_rate": _ratio(passed, len(expectations)),
    }


def _quality_flag_score(
    metrics: Sequence[FrameMetrics],
    expectations: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    if not expectations:
        return {"expectations": [], "pass_rate": None}

    flags = {flag["code"]: flag for flag in tavr_quality_flags(metrics)}
    passed = 0
    scored_expectations = []
    for expectation in expectations:
        code = str(expectation["code"])
        min_frames = int(expectation.get("min_frames", 1))
        min_ratio = expectation.get("min_ratio")
        max_ratio = expectation.get("max_ratio")
        flag = flags.get(code)
        frames = int(flag.get("frames", 0)) if flag else 0
        ratio = float(flag.get("ratio", 0.0)) if flag else 0.0
        checks = {
            "present": flag is not None,
            "min_frames": frames >= min_frames,
            "min_ratio": min_ratio is None or ratio >= float(min_ratio),
            "max_ratio": max_ratio is None or ratio <= float(max_ratio),
        }
        expectation_pass = all(checks.values())
        if expectation_pass:
            passed += 1
        scored_expectations.append(
            {
                "code": code,
                "min_frames": min_frames,
                "min_ratio": min_ratio,
                "max_ratio": max_ratio,
                "matched_flag": flag,
                "checks": checks,
                "passed": expectation_pass,
            }
        )

    return {
        "expectations": scored_expectations,
        "pass_rate": _ratio(passed, len(expectations)),
    }


def _table_observations(
    metrics: Sequence[FrameMetrics],
) -> Dict[int, List[Dict[str, Any]]]:
    observations: Dict[int, List[Dict[str, Any]]] = {}
    for metric in metrics:
        state = _tavr_state(metric)
        for track_id in state.table_track_ids:
            summary = state.track_role_summaries.get(track_id)
            observations.setdefault(track_id, []).append(
                {
                    "frame_index": metric.frame_index,
                    "timestamp_s": metric.timestamp_s,
                    "stage": state.stage,
                    "role": summary.dominant_role if summary else "unassigned",
                }
            )
    return observations


def _observation_gap_exceeded(
    previous: Dict[str, Any],
    current: Dict[str, Any],
    max_gap_frames: int,
    max_gap_s: float,
) -> bool:
    frame_gap = current["frame_index"] - previous["frame_index"]
    time_gap = current["timestamp_s"] - previous["timestamp_s"]
    return frame_gap > max_gap_frames or time_gap > max_gap_s


def _table_interval_item(
    track_id: int,
    observations: Sequence[Dict[str, Any]],
    sample_period_s: float,
) -> Dict[str, Any]:
    start = observations[0]
    end = observations[-1]
    role_counts = _counts(item["role"] for item in observations)
    stage_counts = _counts(item["stage"] for item in observations)
    dominant_role = _dominant_from_counts(role_counts)
    dominant_stage = _dominant_from_counts(stage_counts)
    duration_s = max(0.0, end["timestamp_s"] - start["timestamp_s"] + sample_period_s)
    return {
        "track_id": track_id,
        "dominant_role": dominant_role,
        "dominant_stage": dominant_stage,
        "start_frame": start["frame_index"],
        "end_frame": end["frame_index"],
        "start_s": round(float(start["timestamp_s"]), 3),
        "end_s": round(float(end["timestamp_s"]), 3),
        "observed_table_frames": len(observations),
        "interval_duration_s": round(float(duration_s), 3),
        "role_counts": role_counts,
        "stage_counts": stage_counts,
        "label": (
            f"ID {track_id} {dominant_role} "
            f"{start['timestamp_s']:.1f}-{end['timestamp_s']:.1f}s"
        ),
    }


def _interval_roster(metrics: Sequence[FrameMetrics]) -> List[Dict[str, Any]]:
    roster = []
    for interval in table_presence_intervals(metrics):
        roster.append(
            {
                "track_id": interval["track_id"],
                "dominant_role": interval["dominant_role"],
                "observed_table_frames": interval["observed_table_frames"],
                "interval_duration_s": interval["interval_duration_s"],
                "start_s": interval["start_s"],
                "end_s": interval["end_s"],
                "label": interval["label"],
            }
        )
    roster.sort(
        key=lambda item: (
            -item["observed_table_frames"],
            item["start_s"],
            item["track_id"],
        )
    )
    return roster


def _stage_staffing_track_item(
    track: Dict[str, Any],
    stage_frames: int,
    sample_period_s: float,
) -> Dict[str, Any]:
    role_counts = dict(sorted(track["role_counts"].items()))
    dominant_role = _dominant_role_from_counts(role_counts)
    observed_frames = track["observed_table_frames"]
    estimated_duration_s = observed_frames * sample_period_s
    return {
        "track_id": track["track_id"],
        "dominant_role": dominant_role,
        "observed_table_frames": observed_frames,
        "stage_table_presence_ratio": _ratio(observed_frames, stage_frames),
        "estimated_table_duration_s": round(float(estimated_duration_s), 3),
        "first_frame": track["first_frame"],
        "last_frame": track["last_frame"],
        "first_s": round(float(track["first_s"]), 3),
        "last_s": round(float(track["last_s"]), 3),
        "role_counts": role_counts,
        "label": (
            f"ID {track['track_id']} {dominant_role} "
            f"frames={observed_frames}"
        ),
    }


def _stage_table_coverage_rows(
    segment_metrics: Sequence[FrameMetrics],
    segment_index: int,
    min_observed_table_frames: int,
) -> List[Dict[str, Any]]:
    if not segment_metrics:
        return []

    stage_state = _tavr_state(segment_metrics[0])
    stage_start = segment_metrics[0]
    stage_end = segment_metrics[-1]
    stage_frames = len(segment_metrics)
    sample_period_s = _sample_period_s(segment_metrics)
    stage_duration_s = max(
        0.0,
        stage_end.timestamp_s - stage_start.timestamp_s + sample_period_s,
    )
    tracks: Dict[int, Dict[str, Any]] = {}

    for metric in segment_metrics:
        state = _tavr_state(metric)
        for track_id in state.table_track_ids:
            role = _role_for_track(state, track_id)
            track = tracks.setdefault(
                track_id,
                {
                    "track_id": track_id,
                    "first_frame": metric.frame_index,
                    "last_frame": metric.frame_index,
                    "first_s": metric.timestamp_s,
                    "last_s": metric.timestamp_s,
                    "observed_table_frames": 0,
                    "role_counts": {},
                },
            )
            track["first_frame"] = min(track["first_frame"], metric.frame_index)
            track["last_frame"] = max(track["last_frame"], metric.frame_index)
            track["first_s"] = min(track["first_s"], metric.timestamp_s)
            track["last_s"] = max(track["last_s"], metric.timestamp_s)
            track["observed_table_frames"] += 1
            track["role_counts"][role] = track["role_counts"].get(role, 0) + 1

    rows = []
    for track in tracks.values():
        if track["observed_table_frames"] < min_observed_table_frames:
            continue
        role_counts = dict(sorted(track["role_counts"].items()))
        dominant_role = _dominant_role_from_counts(role_counts)
        coverage_ratio = _ratio(track["observed_table_frames"], stage_frames)
        estimated_duration_s = track["observed_table_frames"] * sample_period_s
        row = {
            "stage_segment_index": segment_index,
            "stage": stage_state.stage,
            "stage_label": stage_state.stage_label,
            "stage_start_frame": stage_start.frame_index,
            "stage_end_frame": stage_end.frame_index,
            "stage_start_s": round(float(stage_start.timestamp_s), 3),
            "stage_end_s": round(float(stage_end.timestamp_s), 3),
            "stage_duration_s": round(float(stage_duration_s), 3),
            "track_id": track["track_id"],
            "dominant_role": dominant_role,
            "observed_table_frames": track["observed_table_frames"],
            "first_seen_frame": track["first_frame"],
            "last_seen_frame": track["last_frame"],
            "first_seen_s": round(float(track["first_s"]), 3),
            "last_seen_s": round(float(track["last_s"]), 3),
            "coverage_ratio": coverage_ratio,
            "estimated_table_duration_s": round(float(estimated_duration_s), 3),
            "entered_during_stage": track["first_frame"] > stage_start.frame_index,
            "exited_during_stage": track["last_frame"] < stage_end.frame_index,
            "role_counts": role_counts,
        }
        row["spans_full_stage"] = (
            not row["entered_during_stage"] and not row["exited_during_stage"]
        )
        row["label"] = (
            f"{row['stage_label']}: ID {track['track_id']} {dominant_role} "
            f"{coverage_ratio:.0%}"
        )
        rows.append(row)

    rows.sort(
        key=lambda item: (
            item["stage_start_s"],
            item["track_id"],
            -item["observed_table_frames"],
        )
    )
    return rows


def _role_for_track(state: TAVRFrameState, track_id: int) -> str:
    roles = [
        role
        for role, track_ids in state.role_track_ids.items()
        if track_id in track_ids
    ]
    if roles:
        priority = {role: index for index, role in enumerate(ROLE_DOMINANCE_ORDER)}
        return min(roles, key=lambda role: priority.get(role, len(priority)))
    summary = state.track_role_summaries.get(track_id)
    if summary is not None:
        return summary.dominant_role
    return "unassigned"


def _merge_counts(target: Dict[str, int], source: Dict[str, int]) -> None:
    for key, value in source.items():
        target[key] = target.get(key, 0) + value


def _counts(values: Iterable[str]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _dominant_from_counts(counts: Dict[str, int]) -> str:
    if not counts:
        return "unassigned"
    return max(counts.items(), key=lambda item: (item[1], item[0]))[0]


def _dominant_role_from_counts(counts: Dict[str, int]) -> str:
    if not counts:
        return "unassigned"
    priority = {role: index for index, role in enumerate(ROLE_DOMINANCE_ORDER)}
    return max(
        counts.items(),
        key=lambda item: (item[1], -priority.get(item[0], len(priority))),
    )[0]


def _sample_period_s(metrics: Sequence[FrameMetrics]) -> float:
    deltas = [
        current.timestamp_s - previous.timestamp_s
        for previous, current in zip(metrics, metrics[1:])
        if current.timestamp_s > previous.timestamp_s
    ]
    if not deltas:
        return 0.0
    deltas.sort()
    return deltas[len(deltas) // 2]


def _metrics_in_window(
    metrics: Sequence[FrameMetrics],
    window: Dict[str, Any],
) -> List[FrameMetrics]:
    start_s = float(window.get("start_s", float("-inf")))
    end_s = float(window.get("end_s", float("inf")))
    return [
        metric
        for metric in metrics
        if start_s <= metric.timestamp_s <= end_s
    ]


def _interval_overlaps_expectation(
    interval: Dict[str, Any],
    expectation: Dict[str, Any],
) -> bool:
    start_s = float(expectation.get("start_s", float("-inf")))
    end_s = float(expectation.get("end_s", float("inf")))
    return interval["start_s"] <= end_s and interval["end_s"] >= start_s


def _ratio(numerator: int, denominator: int) -> Optional[float]:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 3)
