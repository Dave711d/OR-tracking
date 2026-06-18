"""Evaluation helpers for TAVR tracking runs."""

from __future__ import annotations

import csv
import json
from dataclasses import replace
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
    "timebase_summary": [
        "timebase",
        "fps",
        "source_start_frame",
        "source_end_frame",
        "source_start_s",
        "source_end_s",
        "clip_start_frame",
        "clip_end_frame",
        "clip_start_s",
        "clip_end_s",
        "source_offset_s",
    ],
    "procedure_status_summary": [
        "timebase",
        "source_start_frame",
        "source_end_frame",
        "source_start_s",
        "source_end_s",
        "clip_start_frame",
        "clip_end_frame",
        "clip_start_s",
        "clip_end_s",
        "source_offset_s",
        "current_stage",
        "current_stage_label",
        "current_stage_status",
        "current_stage_evidence_status",
        "current_stage_evidence_label",
        "next_stage",
        "next_stage_label",
        "evidence_level",
        "observable_rate",
        "mean_confidence",
        "current_view",
        "tracking_available",
        "current_table_count",
        "current_table_track_ids",
        "current_table_roster",
        "effective_table_source",
        "effective_table_s",
        "effective_table_clip_s",
        "effective_table_age_from_clip_end_s",
        "effective_table_stage",
        "effective_table_stage_label",
        "effective_table_count",
        "effective_table_track_ids",
        "effective_table_roster",
        "last_observed_table_s",
        "last_observed_clip_s",
        "last_observed_age_from_clip_end_s",
        "last_observed_stage",
        "last_observed_stage_label",
        "last_observed_table_count",
        "last_observed_table_track_ids",
        "last_observed_table_roster",
        "peak_table_s",
        "peak_table_clip_s",
        "peak_table_stage",
        "peak_table_stage_label",
        "peak_table_count",
        "peak_table_track_ids",
        "peak_table_roster",
        "quality_flag_codes",
        "operator_summary",
    ],
    "operator_stage_packet": [
        "packet_index",
        "stage_segment_index",
        "stage",
        "stage_label",
        "stage_status",
        "stage_evidence_status",
        "stage_evidence_label",
        "is_current_stage",
        "next_stage",
        "next_stage_label",
        "start_s",
        "end_s",
        "clip_start_s",
        "clip_end_s",
        "duration_s",
        "evidence_level",
        "observable_rate",
        "mean_confidence",
        "tracking_available_rate",
        "handoff_type",
        "peak_table_count",
        "active_table_track_count",
        "canonical_table_identity_count",
        "lead_track_id",
        "lead_table_team_role",
        "active_table_track_ids",
        "continued_track_ids",
        "new_track_ids",
        "dropped_track_ids",
        "effective_table_source",
        "effective_table_count",
        "effective_table_track_ids",
        "roster_summary",
        "quality_flag_codes",
        "operator_packet",
    ],
    "table_team_summary": [
        "track_id",
        "canonical_table_id",
        "merged_track_ids",
        "team_status",
        "dominant_role",
        "table_team_role",
        "table_team_role_confidence",
        "is_current_table_member",
        "is_effective_table_member",
        "is_last_observed_table_member",
        "is_peak_table_member",
        "first_seen_frame",
        "last_seen_frame",
        "first_seen_s",
        "last_seen_s",
        "first_seen_clip_s",
        "last_seen_clip_s",
        "age_from_clip_end_s",
        "frames_seen",
        "observed_table_frames",
        "table_frames",
        "table_presence_ratio",
        "table_observed_duration_s",
        "interval_count",
        "dominant_stage",
        "dominant_stage_label",
        "stage_counts",
        "role_counts",
        "label",
    ],
    "table_identity_groups": [
        "canonical_table_id",
        "track_id",
        "merged_track_ids",
        "dominant_role",
        "table_team_role",
        "table_team_role_confidence",
        "first_seen_frame",
        "last_seen_frame",
        "first_seen_s",
        "last_seen_s",
        "first_seen_clip_s",
        "last_seen_clip_s",
        "observed_table_frames",
        "role_counts",
        "stage_counts",
    ],
    "view_segments": [
        "view",
        "is_room_view",
        "tracking_available",
        "start_frame",
        "end_frame",
        "start_s",
        "end_s",
        "clip_start_s",
        "clip_end_s",
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
        "clip_start_s",
        "clip_end_s",
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
        "clip_start_s",
        "clip_end_s",
        "duration_s",
        "frames",
        "room_view_frames",
        "non_room_view_frames",
        "tracking_available_rate",
        "mean_table_count",
        "mean_room_table_count",
        "peak_table_count",
        "table_occupancy_rate",
        "room_table_occupancy_rate",
        "table_count_distribution",
        "role_counts",
        "unique_table_track_count",
        "canonical_table_identity_count",
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
        "stage_clip_start_s",
        "stage_clip_end_s",
        "stage_duration_s",
        "stage_room_view_frames",
        "stage_non_room_view_frames",
        "tracking_available_rate",
        "track_id",
        "canonical_table_id",
        "merged_track_ids",
        "dominant_role",
        "table_team_role",
        "table_team_role_confidence",
        "observed_table_frames",
        "first_seen_frame",
        "last_seen_frame",
        "first_seen_s",
        "last_seen_s",
        "first_seen_clip_s",
        "last_seen_clip_s",
        "coverage_ratio",
        "room_coverage_ratio",
        "estimated_table_duration_s",
        "entered_during_stage",
        "exited_during_stage",
        "spans_full_stage",
        "role_counts",
        "label",
    ],
    "stage_handoff_summary": [
        "stage_segment_index",
        "previous_stage",
        "previous_stage_label",
        "stage",
        "stage_label",
        "start_frame",
        "end_frame",
        "start_s",
        "end_s",
        "clip_start_s",
        "clip_end_s",
        "duration_s",
        "room_view_frames",
        "non_room_view_frames",
        "tracking_available_rate",
        "active_table_track_count",
        "lead_track_id",
        "lead_role",
        "lead_dominant_role",
        "lead_table_team_role",
        "lead_table_team_role_confidence",
        "lead_observed_table_frames",
        "continued_track_ids",
        "new_track_ids",
        "dropped_track_ids",
        "within_stage_entry_track_ids",
        "within_stage_exit_track_ids",
        "handoff_type",
        "active_table_roster",
        "continued_table_roster",
        "new_table_roster",
        "dropped_table_roster",
        "label",
    ],
    "stage_roster_summary": [
        "stage_segment_index",
        "stage",
        "stage_label",
        "start_s",
        "end_s",
        "clip_start_s",
        "clip_end_s",
        "duration_s",
        "tracking_available_rate",
        "evidence_level",
        "observable_rate",
        "mean_confidence",
        "peak_table_count",
        "active_table_track_count",
        "canonical_table_identity_count",
        "lead_track_id",
        "lead_table_team_role",
        "active_table_track_ids",
        "continued_track_ids",
        "new_track_ids",
        "dropped_track_ids",
        "within_stage_entry_track_ids",
        "within_stage_exit_track_ids",
        "handoff_type",
        "active_table_roster",
        "roster_summary",
        "label",
    ],
    "stage_evidence_summary": [
        "stage_segment_index",
        "stage",
        "stage_label",
        "start_frame",
        "end_frame",
        "start_s",
        "end_s",
        "clip_start_s",
        "clip_end_s",
        "duration_s",
        "frames",
        "room_view_frames",
        "non_room_view_frames",
        "observable_rate",
        "mean_confidence",
        "min_confidence",
        "max_confidence",
        "evidence_level",
        "dominant_signal",
        "mean_table_signal",
        "mean_access_signal",
        "mean_imaging_signal",
        "mean_device_signal",
        "mean_anesthesia_signal",
        "mean_stillness_signal",
        "mean_crowd_signal",
        "support_label",
        "label",
    ],
    "procedure_milestones": [
        "milestone_index",
        "stage",
        "stage_label",
        "observed_in_clip",
        "milestone_status",
        "is_current_observed_stage",
        "first_observed_s",
        "last_observed_s",
        "duration_s",
        "segment_count",
        "evidence_level",
        "observable_rate",
        "mean_confidence",
        "peak_table_count",
        "unique_table_track_count",
        "canonical_table_identity_count",
        "support_label",
        "label",
    ],
    "procedure_event_timeline": [
        "event_type",
        "timestamp_s",
        "clip_timestamp_s",
        "frame_index",
        "end_s",
        "clip_end_s",
        "duration_s",
        "stage",
        "stage_label",
        "view",
        "tracking_available",
        "table_count",
        "track_id",
        "dominant_role",
        "table_team_role",
        "table_team_role_confidence",
        "handoff_type",
        "table_track_ids",
        "roster",
        "source",
        "label",
    ],
    "table_transition_events": [
        "event_type",
        "timestamp_s",
        "clip_timestamp_s",
        "frame_index",
        "track_id",
        "canonical_table_id",
        "merged_track_ids",
        "dominant_role",
        "table_team_role",
        "table_team_role_confidence",
        "stage",
        "stage_label",
        "stage_segment_index",
        "coverage_ratio",
        "room_coverage_ratio",
        "tracking_available_rate",
        "observed_table_frames",
        "label",
    ],
    "table_presence_intervals": [
        "track_id",
        "dominant_role",
        "table_team_role",
        "table_team_role_confidence",
        "dominant_stage",
        "start_frame",
        "end_frame",
        "start_s",
        "end_s",
        "clip_start_s",
        "clip_end_s",
        "observed_table_frames",
        "interval_duration_s",
        "role_counts",
        "stage_counts",
        "label",
    ],
    "table_roster_snapshots": [
        "snapshot_type",
        "frame_index",
        "timestamp_s",
        "clip_timestamp_s",
        "age_from_clip_end_s",
        "stage",
        "stage_label",
        "table_count",
        "track_id",
        "dominant_role",
        "table_team_role",
        "table_team_role_confidence",
        "frames_seen",
        "table_presence_ratio",
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
        "confidence_threshold",
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
        "timebase_summary": timebase_summary(tavr_metrics),
        "procedure_status_summary": procedure_status_summary(tavr_metrics),
        "operator_stage_packet": operator_stage_packet(tavr_metrics),
        "table_team_summary": table_team_summary(tavr_metrics),
        "table_identity_groups": table_identity_groups(tavr_metrics),
        "stage_timeline": tavr_stage_timeline(tavr_metrics),
        "track_role_report": tavr_track_role_report(tavr_metrics),
        "current_table_roster": current_table_roster(tavr_metrics),
        "last_observed_table_roster": last_observed_table_roster(tavr_metrics),
        "peak_table_roster": peak_table_roster(tavr_metrics),
        "table_roster_snapshots": table_roster_snapshots(tavr_metrics),
        "table_presence_roster": table_presence_roster(tavr_metrics),
        "table_presence_intervals": table_presence_intervals(
            tavr_metrics,
            min_observed_table_frames=3,
        ),
        "view_segments": view_segments(tavr_metrics),
        "table_transition_events": table_transition_events(tavr_metrics),
        "stage_table_coverage": stage_table_coverage(tavr_metrics),
        "stage_handoff_summary": stage_handoff_summary(tavr_metrics),
        "stage_roster_summary": stage_roster_summary(tavr_metrics),
        "stage_evidence_summary": stage_evidence_summary(tavr_metrics),
        "procedure_milestones": procedure_milestones(tavr_metrics),
        "procedure_event_timeline": procedure_event_timeline(tavr_metrics),
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
    label_timebase = _label_timebase(labels)
    scoring_metrics = _metrics_for_timebase(tavr_metrics, label_timebase)
    return {
        "timebase": {
            "label_timebase": label_timebase,
            "default_timebase": "clip",
        },
        "stage_score": _stage_score(scoring_metrics, labels.get("stage_segments", [])),
        "table_count_score": _table_count_score(
            scoring_metrics,
            labels.get("table_count_segments", []),
        ),
        "table_presence_score": _table_presence_score(
            scoring_metrics,
            labels.get("table_presence_expectations", []),
        ),
        "stage_staffing_score": _stage_staffing_score(
            scoring_metrics,
            labels.get("stage_staffing_expectations", []),
        ),
        "stage_table_coverage_score": _stage_table_coverage_score(
            scoring_metrics,
            labels.get("stage_table_coverage_expectations", []),
        ),
        "table_transition_score": _table_transition_score(
            scoring_metrics,
            labels.get("table_transition_expectations", []),
        ),
        "stage_handoff_score": _stage_handoff_score(
            scoring_metrics,
            labels.get("stage_handoff_expectations", []),
        ),
        "stage_roster_score": _stage_roster_score(
            scoring_metrics,
            labels.get("stage_roster_expectations", []),
        ),
        "stage_evidence_score": _stage_evidence_score(
            scoring_metrics,
            labels.get("stage_evidence_expectations", []),
        ),
        "procedure_milestone_score": _procedure_milestone_score(
            scoring_metrics,
            labels.get("procedure_milestone_expectations", []),
        ),
        "procedure_status_score": _procedure_status_score(
            scoring_metrics,
            labels.get("procedure_status_expectations", []),
        ),
        "operator_packet_score": _operator_packet_score(
            scoring_metrics,
            labels.get("operator_packet_expectations", []),
        ),
        "table_team_score": _table_team_score(
            scoring_metrics,
            labels.get("table_team_expectations", []),
        ),
        "table_identity_group_score": _table_identity_group_score(
            scoring_metrics,
            labels.get("table_identity_group_expectations", []),
        ),
        "event_timeline_score": _event_timeline_score(
            scoring_metrics,
            labels.get("event_timeline_expectations", []),
        ),
        "roster_snapshot_score": _roster_snapshot_score(
            scoring_metrics,
            labels.get("roster_snapshot_expectations", []),
        ),
        "quality_flag_score": _quality_flag_score(
            scoring_metrics,
            labels.get("quality_flag_expectations", []),
        ),
    }


def timebase_summary(metrics: Sequence[FrameMetrics]) -> List[Dict[str, Any]]:
    """Return one row describing source/case time versus clip-local time."""

    if not metrics:
        return []

    first = metrics[0]
    last = metrics[-1]
    source_offset_s = float(first.source_timestamp_s) - float(first.clip_timestamp_s)
    sample_period_s = _sample_period_s(metrics)
    fps = round(1.0 / sample_period_s, 3) if sample_period_s > 0 else None
    return [
        {
            "timebase": "source" if abs(source_offset_s) > 0.001 else "clip",
            "fps": fps,
            "source_start_frame": first.source_frame_index,
            "source_end_frame": last.source_frame_index,
            "source_start_s": round(float(first.source_timestamp_s), 3),
            "source_end_s": round(float(last.source_timestamp_s), 3),
            "clip_start_frame": first.clip_frame_index,
            "clip_end_frame": last.clip_frame_index,
            "clip_start_s": round(float(first.clip_timestamp_s), 3),
            "clip_end_s": round(float(last.clip_timestamp_s), 3),
            "source_offset_s": round(float(source_offset_s), 3),
        }
    ]


def _label_timebase(labels: Dict[str, Any]) -> str:
    value = str(labels.get("timebase", "clip")).strip().lower()
    aliases = {
        "clip": "clip",
        "clip-local": "clip",
        "clip_local": "clip",
        "local": "clip",
        "source": "source",
        "case": "source",
        "case-clock": "source",
        "case_clock": "source",
    }
    if value not in aliases:
        raise ValueError("Label timebase must be 'clip' or 'source'")
    return aliases[value]


def _metrics_for_timebase(
    metrics: Sequence[FrameMetrics],
    timebase: str,
) -> Sequence[FrameMetrics]:
    if timebase == "source":
        return metrics
    return [
        replace(metric, timestamp_s=float(metric.clip_timestamp_s))
        for metric in metrics
    ]


def procedure_status_summary(metrics: Sequence[FrameMetrics]) -> List[Dict[str, Any]]:
    """Return a one-row operator status for the latest TAVR procedure state."""

    if not metrics:
        return []

    latest_metric = metrics[-1]
    latest_state = _tavr_state(latest_metric)
    milestones = procedure_milestones(metrics)
    current_milestone = _current_milestone(milestones, latest_state.stage)
    next_milestone = _next_milestone(milestones, current_milestone)
    current_roster = current_table_roster(metrics)
    last_observed = last_observed_table_roster(metrics)
    peak = peak_table_roster(metrics)
    quality_flags = tavr_quality_flags(metrics)
    current_track_ids = [item["track_id"] for item in current_roster]
    last_observed_roster = last_observed.get("roster", [])
    peak_roster = peak.get("roster", [])
    timebase = timebase_summary(metrics)[0]
    evidence_level = current_milestone.get("evidence_level")
    observable_rate = current_milestone.get("observable_rate")
    mean_confidence = current_milestone.get("mean_confidence")
    current_stage_evidence_status = _stage_evidence_status(
        evidence_level,
        observable_rate,
    )
    tracking_available = _view_label(latest_metric) == "room"
    effective_table = _effective_table_status(
        latest_metric=latest_metric,
        latest_state=latest_state,
        current_roster=current_roster,
        last_observed=last_observed,
    )

    row = {
        "timebase": timebase["timebase"],
        "source_start_frame": timebase["source_start_frame"],
        "source_end_frame": timebase["source_end_frame"],
        "source_start_s": timebase["source_start_s"],
        "source_end_s": timebase["source_end_s"],
        "clip_start_frame": timebase["clip_start_frame"],
        "clip_end_frame": timebase["clip_end_frame"],
        "clip_start_s": timebase["clip_start_s"],
        "clip_end_s": timebase["clip_end_s"],
        "source_offset_s": timebase["source_offset_s"],
        "current_stage": current_milestone.get("stage") or latest_state.stage,
        "current_stage_label": (
            current_milestone.get("stage_label") or latest_state.stage_label
        ),
        "current_stage_status": current_milestone.get("milestone_status"),
        "current_stage_evidence_status": current_stage_evidence_status,
        "current_stage_evidence_label": _stage_evidence_status_label(
            current_stage_evidence_status
        ),
        "next_stage": next_milestone.get("stage") if next_milestone else None,
        "next_stage_label": (
            next_milestone.get("stage_label") if next_milestone else None
        ),
        "evidence_level": evidence_level,
        "observable_rate": observable_rate,
        "mean_confidence": mean_confidence,
        "current_view": _view_label(latest_metric),
        "tracking_available": tracking_available,
        "current_table_count": latest_state.table_count,
        "current_table_track_ids": current_track_ids,
        "current_table_roster": current_roster,
        "effective_table_source": effective_table["source"],
        "effective_table_s": effective_table["timestamp_s"],
        "effective_table_clip_s": effective_table["clip_timestamp_s"],
        "effective_table_age_from_clip_end_s": effective_table[
            "age_from_clip_end_s"
        ],
        "effective_table_stage": effective_table["stage"],
        "effective_table_stage_label": effective_table["stage_label"],
        "effective_table_count": effective_table["table_count"],
        "effective_table_track_ids": effective_table["track_ids"],
        "effective_table_roster": effective_table["roster"],
        "last_observed_table_s": last_observed.get("timestamp_s"),
        "last_observed_clip_s": last_observed.get("clip_timestamp_s"),
        "last_observed_age_from_clip_end_s": last_observed.get(
            "age_from_clip_end_s"
        ),
        "last_observed_stage": last_observed.get("stage"),
        "last_observed_stage_label": last_observed.get("stage_label"),
        "last_observed_table_count": last_observed.get("table_count", 0),
        "last_observed_table_track_ids": [
            item["track_id"] for item in last_observed_roster
        ],
        "last_observed_table_roster": last_observed_roster,
        "peak_table_s": peak.get("timestamp_s"),
        "peak_table_clip_s": peak.get("clip_timestamp_s"),
        "peak_table_stage": peak.get("stage"),
        "peak_table_stage_label": peak.get("stage_label"),
        "peak_table_count": peak.get("table_count", 0),
        "peak_table_track_ids": [item["track_id"] for item in peak_roster],
        "peak_table_roster": peak_roster,
        "quality_flag_codes": [flag["code"] for flag in quality_flags],
    }
    row["operator_summary"] = _procedure_status_label(row)
    return [row]


def operator_stage_packet(metrics: Sequence[FrameMetrics]) -> List[Dict[str, Any]]:
    """Return concise per-stage rows for operator review and handover."""

    if not metrics:
        return []

    status_rows = procedure_status_summary(metrics)
    if not status_rows:
        return []

    status = status_rows[0]
    milestones_by_stage = {
        row["stage"]: row for row in procedure_milestones(metrics)
    }
    quality_flag_codes = [
        flag["code"] for flag in tavr_quality_flags(metrics)
    ]
    roster_rows = stage_roster_summary(metrics)
    current_segment_index = (
        roster_rows[-1]["stage_segment_index"] if roster_rows else None
    )

    packets = []
    for packet_index, roster in enumerate(roster_rows):
        milestone = milestones_by_stage.get(roster["stage"], {})
        is_current_stage = (
            roster["stage"] == status.get("current_stage")
            and roster["stage_segment_index"] == current_segment_index
        )
        stage_status = (
            status.get("current_stage_status")
            if is_current_stage
            else milestone.get("milestone_status", "observed_prior")
        )
        stage_evidence_status = _stage_evidence_status(
            roster.get("evidence_level"),
            roster.get("observable_rate"),
        )
        row = {
            "packet_index": packet_index,
            "stage_segment_index": roster["stage_segment_index"],
            "stage": roster["stage"],
            "stage_label": roster["stage_label"],
            "stage_status": stage_status,
            "stage_evidence_status": stage_evidence_status,
            "stage_evidence_label": _stage_evidence_status_label(
                stage_evidence_status
            ),
            "is_current_stage": is_current_stage,
            "next_stage": status.get("next_stage") if is_current_stage else None,
            "next_stage_label": (
                status.get("next_stage_label") if is_current_stage else None
            ),
            "start_s": roster["start_s"],
            "end_s": roster["end_s"],
            "clip_start_s": roster.get("clip_start_s"),
            "clip_end_s": roster.get("clip_end_s"),
            "duration_s": roster["duration_s"],
            "evidence_level": roster.get("evidence_level"),
            "observable_rate": roster.get("observable_rate"),
            "mean_confidence": roster.get("mean_confidence"),
            "tracking_available_rate": roster.get("tracking_available_rate"),
            "handoff_type": roster.get("handoff_type"),
            "peak_table_count": roster.get("peak_table_count", 0),
            "active_table_track_count": roster.get("active_table_track_count", 0),
            "canonical_table_identity_count": roster.get(
                "canonical_table_identity_count",
                0,
            ),
            "lead_track_id": roster.get("lead_track_id"),
            "lead_table_team_role": roster.get("lead_table_team_role"),
            "active_table_track_ids": roster.get("active_table_track_ids", []),
            "continued_track_ids": roster.get("continued_track_ids", []),
            "new_track_ids": roster.get("new_track_ids", []),
            "dropped_track_ids": roster.get("dropped_track_ids", []),
            "effective_table_source": (
                status.get("effective_table_source") if is_current_stage else None
            ),
            "effective_table_count": (
                status.get("effective_table_count") if is_current_stage else None
            ),
            "effective_table_track_ids": (
                status.get("effective_table_track_ids", [])
                if is_current_stage
                else []
            ),
            "roster_summary": roster.get("roster_summary", "none"),
            "quality_flag_codes": quality_flag_codes,
        }
        row["operator_packet"] = _operator_stage_packet_label(row)
        packets.append(row)

    return packets


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


def last_observed_table_roster(metrics: Sequence[FrameMetrics]) -> Dict[str, Any]:
    """Return the latest room-view frame with table-side presence."""

    default = {
        "frame_index": None,
        "timestamp_s": None,
        "clip_timestamp_s": None,
        "age_from_clip_end_s": None,
        "stage": None,
        "stage_label": None,
        "table_count": 0,
        "roster": [],
    }
    if not metrics:
        return default

    clip_end_s = metrics[-1].timestamp_s
    clip_end_local_s = float(metrics[-1].clip_timestamp_s)
    for metric in reversed(metrics):
        if _view_label(metric) != "room":
            continue
        state = _tavr_state(metric)
        if state.table_count <= 0:
            continue
        return {
            "frame_index": metric.frame_index,
            "timestamp_s": round(float(metric.timestamp_s), 3),
            "clip_timestamp_s": round(float(metric.clip_timestamp_s), 3),
            "age_from_clip_end_s": round(
                max(0.0, clip_end_local_s - float(metric.clip_timestamp_s)),
                3,
            ),
            "stage": state.stage,
            "stage_label": state.stage_label,
            "table_count": state.table_count,
            "roster": _roster_from_state(state),
        }
    return default


def peak_table_roster(metrics: Sequence[FrameMetrics]) -> Dict[str, Any]:
    """Return the roster from the frame with the largest table-side count."""

    if not metrics:
        return {
            "frame_index": None,
            "timestamp_s": None,
            "clip_timestamp_s": None,
            "age_from_clip_end_s": None,
            "stage": None,
            "stage_label": None,
            "table_count": 0,
            "roster": [],
        }

    clip_end_s = float(metrics[-1].clip_timestamp_s)
    peak_metric = max(
        metrics,
        key=lambda metric: (_tavr_state(metric).table_count, metric.frame_index),
    )
    peak_state = _tavr_state(peak_metric)
    return {
        "frame_index": peak_metric.frame_index,
        "timestamp_s": round(float(peak_metric.timestamp_s), 3),
        "clip_timestamp_s": round(float(peak_metric.clip_timestamp_s), 3),
        "age_from_clip_end_s": round(
            max(0.0, clip_end_s - float(peak_metric.clip_timestamp_s)),
            3,
        ),
        "stage": peak_state.stage,
        "stage_label": peak_state.stage_label,
        "table_count": peak_state.table_count,
        "roster": _roster_from_state(peak_state),
    }


def table_roster_snapshots(metrics: Sequence[FrameMetrics]) -> List[Dict[str, Any]]:
    """Return row-oriented current/latest/peak table roster snapshots."""

    if not metrics:
        return []

    clip_end_s = float(metrics[-1].clip_timestamp_s)
    snapshot_items = [
        ("current", _roster_snapshot_from_metric(metrics[-1], clip_end_s)),
        ("last_observed", last_observed_table_roster(metrics)),
        ("peak", peak_table_roster(metrics)),
    ]
    rows: List[Dict[str, Any]] = []
    for snapshot_type, snapshot in snapshot_items:
        rows.extend(_snapshot_rows(snapshot_type, snapshot))
    return rows


def table_identity_groups(metrics: Sequence[FrameMetrics]) -> List[Dict[str, Any]]:
    """Return canonical table-person groups stitched from raw table track IDs."""

    _, groups = _table_identity_map(metrics)
    return groups


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


def table_team_summary(
    metrics: Sequence[FrameMetrics],
    min_observed_table_frames: int = 3,
    recent_age_s: float = 10.0,
) -> List[Dict[str, Any]]:
    """Return one row per meaningful table-side team track in the clip."""

    if not metrics:
        return []

    clip_end_s = float(metrics[-1].clip_timestamp_s)
    status_row = procedure_status_summary(metrics)[0]
    current_ids = set(status_row.get("current_table_track_ids", []))
    effective_ids = set(status_row.get("effective_table_track_ids", []))
    last_ids = set(status_row.get("last_observed_table_track_ids", []))
    peak_ids = set(status_row.get("peak_table_track_ids", []))
    identity_map, _ = _table_identity_map(metrics)
    frame_times = {
        metric.frame_index: float(metric.timestamp_s)
        for metric in metrics
    }
    frame_clip_times = {
        metric.frame_index: float(metric.clip_timestamp_s)
        for metric in metrics
    }

    team: Dict[int, Dict[str, Any]] = {}
    for summary in tavr_track_role_report(metrics):
        track_id = int(summary["track_id"])
        identity = identity_map.get(track_id)
        canonical_id = identity["canonical_table_id"] if identity else track_id
        merged_track_ids = (
            set(identity["merged_track_ids"]) if identity else {track_id}
        )
        row = team.setdefault(
            canonical_id,
            {
                "track_id": min(merged_track_ids),
                "canonical_table_id": canonical_id,
                "merged_track_ids": set(merged_track_ids),
                "dominant_role": summary.get("dominant_role") or "unassigned",
                "frames_seen": 0,
                "first_seen_frame": None,
                "last_seen_frame": None,
                "first_seen_s": None,
                "last_seen_s": None,
                "first_seen_clip_s": None,
                "last_seen_clip_s": None,
                "observed_table_frames": 0,
                "table_frames": 0,
                "role_counts": {},
                "stage_counts": {},
                "table_observed_duration_s": 0.0,
                "interval_count": 0,
            },
        )
        row["merged_track_ids"].update(merged_track_ids)
        row["track_id"] = min(row["merged_track_ids"])
        row["frames_seen"] += int(summary.get("frames_seen", 0) or 0)
        row["table_frames"] += int(summary.get("table_frames", 0) or 0)
        row["first_seen_frame"] = _min_optional(
            row.get("first_seen_frame"),
            summary.get("first_frame"),
        )
        row["last_seen_frame"] = _max_optional(
            row.get("last_seen_frame"),
            summary.get("last_frame"),
        )
        row["first_seen_s"] = _min_optional(
            row.get("first_seen_s"),
            frame_times.get(summary.get("first_frame")),
        )
        row["last_seen_s"] = _max_optional(
            row.get("last_seen_s"),
            frame_times.get(summary.get("last_frame")),
        )
        row["first_seen_clip_s"] = _min_optional(
            row.get("first_seen_clip_s"),
            frame_clip_times.get(summary.get("first_frame")),
        )
        row["last_seen_clip_s"] = _max_optional(
            row.get("last_seen_clip_s"),
            frame_clip_times.get(summary.get("last_frame")),
        )

    for roster in [
        status_row.get("current_table_roster", []),
        status_row.get("effective_table_roster", []),
        status_row.get("last_observed_table_roster", []),
        status_row.get("peak_table_roster", []),
    ]:
        for item in roster:
            track_id = int(item["track_id"])
            identity = identity_map.get(track_id)
            canonical_id = identity["canonical_table_id"] if identity else track_id
            merged_track_ids = (
                set(identity["merged_track_ids"]) if identity else {track_id}
            )
            row = team.setdefault(
                canonical_id,
                {
                    "track_id": min(merged_track_ids),
                    "canonical_table_id": canonical_id,
                    "merged_track_ids": set(merged_track_ids),
                    "dominant_role": item.get("dominant_role") or "unassigned",
                    "frames_seen": int(item.get("frames_seen", 0) or 0),
                    "first_seen_frame": None,
                    "last_seen_frame": None,
                    "first_seen_s": None,
                    "last_seen_s": None,
                    "first_seen_clip_s": None,
                    "last_seen_clip_s": None,
                    "observed_table_frames": 0,
                    "table_frames": 0,
                    "role_counts": {},
                    "stage_counts": {},
                    "table_observed_duration_s": 0.0,
                    "interval_count": 0,
                },
            )
            row["merged_track_ids"].update(merged_track_ids)
            row["track_id"] = min(row["merged_track_ids"])
            role = item.get("table_team_role") or item.get("dominant_role") or "unassigned"
            row["role_counts"][role] = row["role_counts"].get(role, 0) + 1
            if row["dominant_role"] == "unassigned":
                row["dominant_role"] = item.get("dominant_role") or role

    for interval in table_presence_intervals(
        metrics,
        min_observed_table_frames=1,
    ):
        track_id = int(interval["track_id"])
        identity = identity_map.get(track_id)
        canonical_id = identity["canonical_table_id"] if identity else track_id
        merged_track_ids = (
            set(identity["merged_track_ids"]) if identity else {track_id}
        )
        row = team.setdefault(
            canonical_id,
            {
                "track_id": min(merged_track_ids),
                "canonical_table_id": canonical_id,
                "merged_track_ids": set(merged_track_ids),
                "dominant_role": interval.get("dominant_role") or "unassigned",
                "frames_seen": 0,
                "first_seen_frame": None,
                "last_seen_frame": None,
                "first_seen_s": None,
                "last_seen_s": None,
                "first_seen_clip_s": None,
                "last_seen_clip_s": None,
                "observed_table_frames": 0,
                "table_frames": 0,
                "role_counts": {},
                "stage_counts": {},
                "table_observed_duration_s": 0.0,
                "interval_count": 0,
            },
        )
        row["merged_track_ids"].update(merged_track_ids)
        row["track_id"] = min(row["merged_track_ids"])
        row["first_seen_frame"] = _min_optional(
            row.get("first_seen_frame"),
            interval.get("start_frame"),
        )
        row["last_seen_frame"] = _max_optional(
            row.get("last_seen_frame"),
            interval.get("end_frame"),
        )
        row["first_seen_s"] = _min_optional(
            row.get("first_seen_s"),
            interval.get("start_s"),
        )
        row["last_seen_s"] = _max_optional(
            row.get("last_seen_s"),
            interval.get("end_s"),
        )
        row["first_seen_clip_s"] = _min_optional(
            row.get("first_seen_clip_s"),
            interval.get("clip_start_s"),
        )
        row["last_seen_clip_s"] = _max_optional(
            row.get("last_seen_clip_s"),
            interval.get("clip_end_s"),
        )
        row["observed_table_frames"] += int(
            interval.get("observed_table_frames", 0) or 0
        )
        row["table_observed_duration_s"] += float(
            interval.get("interval_duration_s", 0.0) or 0.0
        )
        row["interval_count"] += 1
        _merge_counts(row["role_counts"], interval.get("role_counts", {}))
        _merge_counts(row["stage_counts"], interval.get("stage_counts", {}))

    rows: List[Dict[str, Any]] = []
    for canonical_id, row in team.items():
        merged_track_ids = sorted(int(track_id) for track_id in row["merged_track_ids"])
        raw_ids = set(merged_track_ids)
        table_frames = max(
            int(row.get("table_frames", 0) or 0),
            int(row.get("observed_table_frames", 0) or 0),
        )
        if (
            table_frames < min_observed_table_frames
            and not (raw_ids & current_ids)
            and not (raw_ids & effective_ids)
            and not (raw_ids & last_ids)
            and not (raw_ids & peak_ids)
        ):
            continue

        frames_seen = max(int(row.get("frames_seen", 0) or 0), table_frames)
        last_seen_s = row.get("last_seen_s")
        last_seen_clip_s = row.get("last_seen_clip_s")
        age_from_clip_end_s = (
            round(max(0.0, clip_end_s - float(last_seen_clip_s)), 3)
            if last_seen_clip_s is not None
            else None
        )
        dominant_role = (
            _dominant_role_from_counts(row["role_counts"])
            if row["role_counts"]
            else row.get("dominant_role") or "unassigned"
        )
        table_team_role, table_team_role_confidence = _table_team_role(
            row["role_counts"],
            dominant_role,
            table_frames,
        )
        dominant_stage = _dominant_from_counts(row["stage_counts"])
        is_current_member = bool(raw_ids & current_ids)
        is_effective_member = bool(raw_ids & effective_ids)
        is_last_member = bool(raw_ids & last_ids)
        is_peak_member = bool(raw_ids & peak_ids)
        team_status = _table_team_status_from_membership(
            is_current_member=is_current_member,
            is_effective_member=is_effective_member,
            is_last_member=is_last_member,
            age_from_clip_end_s=age_from_clip_end_s,
            recent_age_s=recent_age_s,
        )
        item = {
            "track_id": row["track_id"],
            "canonical_table_id": canonical_id,
            "merged_track_ids": merged_track_ids,
            "team_status": team_status,
            "dominant_role": dominant_role,
            "table_team_role": table_team_role,
            "table_team_role_confidence": table_team_role_confidence,
            "is_current_table_member": is_current_member,
            "is_effective_table_member": is_effective_member,
            "is_last_observed_table_member": is_last_member,
            "is_peak_table_member": is_peak_member,
            "first_seen_frame": row.get("first_seen_frame"),
            "last_seen_frame": row.get("last_seen_frame"),
            "first_seen_s": _round_optional(row.get("first_seen_s")),
            "last_seen_s": _round_optional(last_seen_s),
            "first_seen_clip_s": _round_optional(row.get("first_seen_clip_s")),
            "last_seen_clip_s": _round_optional(last_seen_clip_s),
            "age_from_clip_end_s": age_from_clip_end_s,
            "frames_seen": frames_seen,
            "observed_table_frames": int(row.get("observed_table_frames", 0) or 0),
            "table_frames": table_frames,
            "table_presence_ratio": _ratio(table_frames, frames_seen) or 0.0,
            "table_observed_duration_s": round(
                float(row.get("table_observed_duration_s", 0.0) or 0.0),
                3,
            ),
            "interval_count": int(row.get("interval_count", 0) or 0),
            "dominant_stage": None if dominant_stage == "unassigned" else dominant_stage,
            "dominant_stage_label": (
                TAVR_STAGE_LABELS.get(dominant_stage)
                if dominant_stage != "unassigned"
                else None
            ),
            "stage_counts": dict(sorted(row["stage_counts"].items())),
            "role_counts": dict(sorted(row["role_counts"].items())),
        }
        item["label"] = _table_team_label(item)
        rows.append(item)

    status_order = {
        "active_current": 0,
        "recent_last_observed": 1,
        "historical_seen": 2,
    }
    rows.sort(
        key=lambda item: (
            status_order.get(item["team_status"], 9),
            not item["is_effective_table_member"],
            not item["is_last_observed_table_member"],
            not item["is_peak_table_member"],
            -(item["last_seen_s"] if item["last_seen_s"] is not None else -1),
            -item["observed_table_frames"],
            item["track_id"],
        )
    )
    return rows


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
    identity_map, _ = _table_identity_map(metrics)

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
                "clip_start_s": metric.clip_timestamp_s,
                "clip_end_s": metric.clip_timestamp_s,
                "frames": 0,
                "room_view_frames": 0,
                "non_room_view_frames": 0,
                "table_counts": [],
                "room_table_counts": [],
                "role_counts": {},
                "tracks": {},
            },
        )
        accumulator["first_frame"] = min(accumulator["first_frame"], metric.frame_index)
        accumulator["last_frame"] = max(accumulator["last_frame"], metric.frame_index)
        accumulator["start_s"] = min(accumulator["start_s"], metric.timestamp_s)
        accumulator["end_s"] = max(accumulator["end_s"], metric.timestamp_s)
        accumulator["clip_start_s"] = min(
            accumulator["clip_start_s"],
            metric.clip_timestamp_s,
        )
        accumulator["clip_end_s"] = max(
            accumulator["clip_end_s"],
            metric.clip_timestamp_s,
        )
        accumulator["frames"] += 1
        accumulator["table_counts"].append(state.table_count)
        is_room_view = _view_label(metric) == "room"
        if is_room_view:
            accumulator["room_view_frames"] += 1
            accumulator["room_table_counts"].append(state.table_count)
        else:
            accumulator["non_room_view_frames"] += 1
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
                    "first_clip_s": metric.clip_timestamp_s,
                    "last_clip_s": metric.clip_timestamp_s,
                    "observed_table_frames": 0,
                    "role_counts": {},
                },
            )
            track["first_frame"] = min(track["first_frame"], metric.frame_index)
            track["last_frame"] = max(track["last_frame"], metric.frame_index)
            track["first_s"] = min(track["first_s"], metric.timestamp_s)
            track["last_s"] = max(track["last_s"], metric.timestamp_s)
            track["first_clip_s"] = min(track["first_clip_s"], metric.clip_timestamp_s)
            track["last_clip_s"] = max(track["last_clip_s"], metric.clip_timestamp_s)
            track["observed_table_frames"] += 1
            track["role_counts"][role] = track["role_counts"].get(role, 0) + 1

    summaries: List[Dict[str, Any]] = []
    for stage, accumulator in accumulators.items():
        table_counts = accumulator["table_counts"]
        room_table_counts = accumulator["room_table_counts"]
        frames = accumulator["frames"]
        room_view_frames = accumulator["room_view_frames"]
        table_roster = [
            _stage_staffing_track_item(track, frames, sample_period_s)
            for track in accumulator["tracks"].values()
            if track["observed_table_frames"] >= min_observed_table_frames
        ]
        canonical_table_identity_ids = {
            int(identity_map[track["track_id"]]["canonical_table_id"])
            if track["track_id"] in identity_map
            else int(track["track_id"])
            for track in accumulator["tracks"].values()
            if track["observed_table_frames"] >= min_observed_table_frames
        }
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
                "clip_start_s": round(float(accumulator["clip_start_s"]), 3),
                "clip_end_s": round(float(accumulator["clip_end_s"]), 3),
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
                "room_view_frames": room_view_frames,
                "non_room_view_frames": accumulator["non_room_view_frames"],
                "tracking_available_rate": _ratio(room_view_frames, frames),
                "mean_table_count": (
                    round(sum(table_counts) / len(table_counts), 3)
                    if table_counts
                    else None
                ),
                "mean_room_table_count": (
                    round(sum(room_table_counts) / len(room_table_counts), 3)
                    if room_table_counts
                    else None
                ),
                "peak_table_count": max(table_counts) if table_counts else 0,
                "table_occupancy_rate": _ratio(
                    sum(1 for count in table_counts if count > 0),
                    len(table_counts),
                ),
                "room_table_occupancy_rate": _ratio(
                    sum(1 for count in room_table_counts if count > 0),
                    len(room_table_counts),
                ),
                "table_count_distribution": _counts(str(count) for count in table_counts),
                "role_counts": dict(sorted(accumulator["role_counts"].items())),
                "unique_table_track_count": len(accumulator["tracks"]),
                "canonical_table_identity_count": len(canonical_table_identity_ids),
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
    identity_map, _ = _table_identity_map(metrics)
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
                    identity_map=identity_map,
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
            identity_map=identity_map,
        )
    )
    return rows


def stage_handoff_summary(
    metrics: Sequence[FrameMetrics],
    min_observed_table_frames: int = 1,
) -> List[Dict[str, Any]]:
    """Summarize table-side roster continuity at each stage boundary."""

    if not metrics:
        return []

    coverage_by_segment: Dict[int, List[Dict[str, Any]]] = {}
    for row in stage_table_coverage(
        metrics,
        min_observed_table_frames=min_observed_table_frames,
    ):
        coverage_by_segment.setdefault(row["stage_segment_index"], []).append(row)

    summaries: List[Dict[str, Any]] = []
    previous_stage: Optional[str] = None
    previous_stage_label: Optional[str] = None
    previous_roster_by_id: Dict[int, Dict[str, Any]] = {}
    for segment_index, segment_metrics in enumerate(_stage_metric_segments(metrics)):
        summary = _stage_handoff_item(
            segment_metrics=segment_metrics,
            segment_index=segment_index,
            coverage_rows=coverage_by_segment.get(segment_index, []),
            previous_stage=previous_stage,
            previous_stage_label=previous_stage_label,
            previous_roster_by_id=previous_roster_by_id,
        )
        summaries.append(summary)
        previous_stage = summary["stage"]
        previous_stage_label = summary["stage_label"]
        previous_roster_by_id = {
            item["track_id"]: item
            for item in summary["active_table_roster"]
        }

    return summaries


def stage_roster_summary(
    metrics: Sequence[FrameMetrics],
    min_observed_table_frames: int = 1,
) -> List[Dict[str, Any]]:
    """Return one operator-facing table roster row per contiguous TAVR stage."""

    if not metrics:
        return []

    evidence_by_segment = {
        row["stage_segment_index"]: row for row in stage_evidence_summary(metrics)
    }
    segment_metrics_by_index = {
        index: segment_metrics
        for index, segment_metrics in enumerate(_stage_metric_segments(metrics))
    }
    rows = []
    for handoff in stage_handoff_summary(
        metrics,
        min_observed_table_frames=min_observed_table_frames,
    ):
        segment_index = int(handoff["stage_segment_index"])
        rows.append(
            _stage_roster_summary_item(
                handoff=handoff,
                evidence=evidence_by_segment.get(segment_index, {}),
                segment_metrics=segment_metrics_by_index.get(segment_index, []),
            )
        )

    return rows


def stage_evidence_summary(metrics: Sequence[FrameMetrics]) -> List[Dict[str, Any]]:
    """Summarize visual support for each contiguous stage segment."""

    if not metrics:
        return []

    return [
        _stage_evidence_item(segment_index, segment_metrics)
        for segment_index, segment_metrics in enumerate(_stage_metric_segments(metrics))
    ]


def procedure_milestones(metrics: Sequence[FrameMetrics]) -> List[Dict[str, Any]]:
    """Return TAVR milestone progress rows in canonical procedure order."""

    if not metrics:
        return []

    evidence_rows = stage_evidence_summary(metrics)
    staffing_rows = {
        row["stage"]: row
        for row in stage_staffing_summary(metrics, min_observed_table_frames=1)
    }
    evidence_by_stage: Dict[str, List[Dict[str, Any]]] = {}
    for row in evidence_rows:
        evidence_by_stage.setdefault(row["stage"], []).append(row)
    latest_stage = evidence_rows[-1]["stage"] if evidence_rows else None

    milestones = []
    for index, stage in enumerate(TAVR_STAGE_ORDER):
        stage_rows = evidence_by_stage.get(stage, [])
        staffing = staffing_rows.get(stage, {})
        milestones.append(
            _procedure_milestone_item(
                milestone_index=index,
                stage=stage,
                evidence_rows=stage_rows,
                staffing=staffing,
                is_current_observed_stage=stage == latest_stage,
            )
        )
    return milestones


def procedure_event_timeline(metrics: Sequence[FrameMetrics]) -> List[Dict[str, Any]]:
    """Return a single chronological event list for stage/view/table review."""

    if not metrics:
        return []

    events: List[Dict[str, Any]] = []
    for segment_index, segment_metrics in enumerate(_stage_metric_segments(metrics)):
        events.append(_stage_started_event(segment_index, segment_metrics))

    metrics_by_frame = {metric.frame_index: metric for metric in metrics}
    for view_segment in view_segments(metrics):
        start_metric = metrics_by_frame.get(view_segment["start_frame"])
        events.append(_view_started_event(view_segment, start_metric))

    for handoff in stage_handoff_summary(metrics):
        events.append(_handoff_event(handoff))

    for stage_segment in tavr_stage_timeline(metrics):
        peak = stage_segment.get("peak_table_roster", {})
        if peak.get("table_count", 0) > 0:
            events.append(_table_peak_event(peak))

    event_order = {
        "stage_started": 0,
        "view_started": 1,
        "table_handoff": 2,
        "table_peak": 3,
    }
    events.sort(
        key=lambda item: (
            item["timestamp_s"],
            event_order.get(item["event_type"], 9),
            item.get("frame_index") if item.get("frame_index") is not None else -1,
            item["event_type"],
        )
    )
    return events


def _roster_from_state(state: TAVRFrameState) -> List[Dict[str, Any]]:
    roster = []
    for track_id in state.table_track_ids:
        summary = state.track_role_summaries.get(track_id)
        if summary is None:
            continue
        table_team_role, table_team_role_confidence = _table_team_role(
            dict(summary.role_counts),
            summary.dominant_role,
            summary.table_frames,
        )
        roster.append(
            {
                "track_id": track_id,
                "dominant_role": summary.dominant_role,
                "table_team_role": table_team_role,
                "table_team_role_confidence": table_team_role_confidence,
                "frames_seen": summary.frames_seen,
                "table_presence_ratio": round(summary.table_presence_ratio, 3),
                "label": _role_label(
                    track_id=track_id,
                    role=table_team_role,
                    dominant_role=summary.dominant_role,
                    suffix=f"table={summary.table_presence_ratio:.0%}",
                ),
            }
        )
    return roster


def _roster_snapshot_from_metric(
    metric: FrameMetrics,
    clip_end_s: float,
) -> Dict[str, Any]:
    state = _tavr_state(metric)
    return {
        "frame_index": metric.frame_index,
        "timestamp_s": round(float(metric.timestamp_s), 3),
        "clip_timestamp_s": round(float(metric.clip_timestamp_s), 3),
        "age_from_clip_end_s": round(
            max(0.0, clip_end_s - float(metric.clip_timestamp_s)),
            3,
        ),
        "stage": state.stage,
        "stage_label": state.stage_label,
        "table_count": state.table_count,
        "roster": _roster_from_state(state),
    }


def _snapshot_rows(
    snapshot_type: str,
    snapshot: Dict[str, Any],
) -> List[Dict[str, Any]]:
    rows = []
    for roster_item in snapshot.get("roster", []):
        rows.append(
            {
                "snapshot_type": snapshot_type,
                "frame_index": snapshot.get("frame_index"),
                "timestamp_s": snapshot.get("timestamp_s"),
                "clip_timestamp_s": snapshot.get("clip_timestamp_s"),
                "age_from_clip_end_s": snapshot.get("age_from_clip_end_s"),
                "stage": snapshot.get("stage"),
                "stage_label": snapshot.get("stage_label"),
                "table_count": snapshot.get("table_count", 0),
                "track_id": roster_item["track_id"],
                "dominant_role": roster_item["dominant_role"],
                "table_team_role": roster_item["table_team_role"],
                "table_team_role_confidence": roster_item["table_team_role_confidence"],
                "frames_seen": roster_item["frames_seen"],
                "table_presence_ratio": roster_item["table_presence_ratio"],
                "label": roster_item["label"],
            }
        )
    return rows


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

    confidence_threshold = 0.45
    low_confidence_frames = sum(
        1 for metric in metrics if _tavr_state(metric).confidence < confidence_threshold
    )
    low_confidence_ratio = low_confidence_frames / max(len(metrics), 1)
    if low_confidence_ratio >= 0.2:
        flags.append(
            {
                "code": "low_stage_confidence",
                "message": (
                    "Procedure-stage inference is visually weak for a substantial "
                    "portion of the clip; treat stage labels as seeded or held "
                    "context in those frames."
                ),
                "confidence_threshold": confidence_threshold,
                "frames": low_confidence_frames,
                "ratio": round(low_confidence_ratio, 3),
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
        "clip_start_s": metrics[start_index].clip_timestamp_s,
        "clip_end_s": metrics[end_index].clip_timestamp_s,
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


def _stage_metric_segments(
    metrics: Sequence[FrameMetrics],
) -> List[Sequence[FrameMetrics]]:
    if not metrics:
        return []

    segments: List[Sequence[FrameMetrics]] = []
    start_index = 0
    active_stage = _tavr_state(metrics[0]).stage
    for index, metric in enumerate(metrics[1:], start=1):
        stage = _tavr_state(metric).stage
        if stage != active_stage:
            segments.append(metrics[start_index:index])
            start_index = index
            active_stage = stage
    segments.append(metrics[start_index:])
    return segments


def _stage_handoff_item(
    segment_metrics: Sequence[FrameMetrics],
    segment_index: int,
    coverage_rows: Sequence[Dict[str, Any]],
    previous_stage: Optional[str],
    previous_stage_label: Optional[str],
    previous_roster_by_id: Dict[int, Dict[str, Any]],
) -> Dict[str, Any]:
    stage_state = _tavr_state(segment_metrics[0])
    stage_start = segment_metrics[0]
    stage_end = segment_metrics[-1]
    stage_frames = len(segment_metrics)
    room_view_frames = sum(
        1 for metric in segment_metrics if _view_label(metric) == "room"
    )
    sample_period_s = _sample_period_s(segment_metrics)
    duration_s = max(
        0.0,
        stage_end.timestamp_s - stage_start.timestamp_s + sample_period_s,
    )
    active_roster = [
        _handoff_roster_item(row)
        for row in coverage_rows
    ]
    active_roster.sort(
        key=lambda item: (
            -item["observed_table_frames"],
            item["first_seen_s"],
            item["track_id"],
        )
    )
    active_roster_by_id = {
        item["track_id"]: item for item in active_roster
    }
    active_ids = set(active_roster_by_id)
    previous_ids = set(previous_roster_by_id)
    continued_ids = sorted(active_ids & previous_ids)
    new_ids = sorted(active_ids - previous_ids)
    dropped_ids = sorted(previous_ids - active_ids)
    within_stage_entry_ids = sorted(
        row["track_id"] for row in coverage_rows if row["entered_during_stage"]
    )
    within_stage_exit_ids = sorted(
        row["track_id"] for row in coverage_rows if row["exited_during_stage"]
    )
    lead = active_roster[0] if active_roster else None
    handoff_type = _handoff_type(
        has_previous_stage=previous_stage is not None,
        previous_ids=previous_ids,
        active_ids=active_ids,
        new_ids=set(new_ids),
        dropped_ids=set(dropped_ids),
    )
    return {
        "stage_segment_index": segment_index,
        "previous_stage": previous_stage,
        "previous_stage_label": previous_stage_label,
        "stage": stage_state.stage,
        "stage_label": stage_state.stage_label,
        "start_frame": stage_start.frame_index,
        "end_frame": stage_end.frame_index,
        "start_s": round(float(stage_start.timestamp_s), 3),
        "end_s": round(float(stage_end.timestamp_s), 3),
        "clip_start_s": round(float(stage_start.clip_timestamp_s), 3),
        "clip_end_s": round(float(stage_end.clip_timestamp_s), 3),
        "duration_s": round(float(duration_s), 3),
        "room_view_frames": room_view_frames,
        "non_room_view_frames": stage_frames - room_view_frames,
        "tracking_available_rate": _ratio(room_view_frames, stage_frames),
        "active_table_track_count": len(active_roster),
        "lead_track_id": lead["track_id"] if lead else None,
        "lead_role": lead["table_team_role"] if lead else None,
        "lead_dominant_role": lead["dominant_role"] if lead else None,
        "lead_table_team_role": lead["table_team_role"] if lead else None,
        "lead_table_team_role_confidence": (
            lead["table_team_role_confidence"] if lead else None
        ),
        "lead_observed_table_frames": (
            lead["observed_table_frames"] if lead else 0
        ),
        "continued_track_ids": continued_ids,
        "new_track_ids": new_ids,
        "dropped_track_ids": dropped_ids,
        "within_stage_entry_track_ids": within_stage_entry_ids,
        "within_stage_exit_track_ids": within_stage_exit_ids,
        "handoff_type": handoff_type,
        "active_table_roster": active_roster,
        "continued_table_roster": [
            active_roster_by_id[track_id] for track_id in continued_ids
        ],
        "new_table_roster": [
            active_roster_by_id[track_id] for track_id in new_ids
        ],
        "dropped_table_roster": [
            previous_roster_by_id[track_id] for track_id in dropped_ids
        ],
        "label": _handoff_label(stage_state.stage_label, handoff_type, lead, active_roster),
    }


def _stage_roster_summary_item(
    handoff: Dict[str, Any],
    evidence: Dict[str, Any],
    segment_metrics: Sequence[FrameMetrics],
) -> Dict[str, Any]:
    active_roster = list(handoff.get("active_table_roster", []))
    active_track_ids = [int(item["track_id"]) for item in active_roster]
    canonical_ids = sorted(
        {
            int(item.get("canonical_table_id", item["track_id"]))
            for item in active_roster
        }
    )
    lead = active_roster[0] if active_roster else None
    peak_table_count = max(
        (_tavr_state(metric).table_count for metric in segment_metrics),
        default=0,
    )
    roster_summary = _roster_status_label(active_roster)
    return {
        "stage_segment_index": handoff["stage_segment_index"],
        "stage": handoff["stage"],
        "stage_label": handoff["stage_label"],
        "start_s": handoff["start_s"],
        "end_s": handoff["end_s"],
        "clip_start_s": handoff.get("clip_start_s"),
        "clip_end_s": handoff.get("clip_end_s"),
        "duration_s": handoff["duration_s"],
        "tracking_available_rate": handoff["tracking_available_rate"],
        "evidence_level": evidence.get("evidence_level"),
        "observable_rate": evidence.get("observable_rate"),
        "mean_confidence": evidence.get("mean_confidence"),
        "peak_table_count": peak_table_count,
        "active_table_track_count": len(active_roster),
        "canonical_table_identity_count": len(canonical_ids),
        "lead_track_id": lead["track_id"] if lead else None,
        "lead_table_team_role": lead["table_team_role"] if lead else None,
        "active_table_track_ids": active_track_ids,
        "continued_track_ids": handoff.get("continued_track_ids", []),
        "new_track_ids": handoff.get("new_track_ids", []),
        "dropped_track_ids": handoff.get("dropped_track_ids", []),
        "within_stage_entry_track_ids": handoff.get(
            "within_stage_entry_track_ids", []
        ),
        "within_stage_exit_track_ids": handoff.get(
            "within_stage_exit_track_ids", []
        ),
        "handoff_type": handoff["handoff_type"],
        "active_table_roster": active_roster,
        "roster_summary": roster_summary,
        "label": (
            f"{handoff['stage_label']}: peak table {peak_table_count}; "
            f"{len(active_roster)} table IDs; {handoff['handoff_type']}; "
            f"{roster_summary}"
        ),
    }


def _stage_evidence_item(
    segment_index: int,
    segment_metrics: Sequence[FrameMetrics],
) -> Dict[str, Any]:
    stage_state = _tavr_state(segment_metrics[0])
    start_metric = segment_metrics[0]
    end_metric = segment_metrics[-1]
    sample_period_s = _sample_period_s(segment_metrics)
    duration_s = max(
        0.0,
        end_metric.timestamp_s - start_metric.timestamp_s + sample_period_s,
    )
    frames = len(segment_metrics)
    room_view_frames = sum(
        1 for metric in segment_metrics if _view_label(metric) == "room"
    )
    confidences = [_tavr_state(metric).confidence for metric in segment_metrics]
    observable_values = [
        _tavr_state(metric).signals.get(
            "stage_observable",
            1.0 if _view_label(metric) == "room" else 0.0,
        )
        for metric in segment_metrics
    ]
    signal_means = {
        name: _mean_signal(segment_metrics, name)
        for name in [
            "table",
            "access",
            "imaging",
            "device",
            "anesthesia",
            "stillness",
            "crowd",
        ]
    }
    dominant_signal = _dominant_signal(signal_means)
    mean_confidence = round(sum(confidences) / len(confidences), 3)
    observable_rate = round(sum(observable_values) / len(observable_values), 3)
    evidence_level = _stage_evidence_level(
        observable_rate=observable_rate,
        mean_confidence=mean_confidence,
        room_view_frames=room_view_frames,
    )
    support_label = (
        f"observable={observable_rate:.0%}, confidence={mean_confidence:.2f}, "
        f"strongest={dominant_signal}:{signal_means[dominant_signal]:.2f}"
    )
    return {
        "stage_segment_index": segment_index,
        "stage": stage_state.stage,
        "stage_label": stage_state.stage_label,
        "start_frame": start_metric.frame_index,
        "end_frame": end_metric.frame_index,
        "start_s": round(float(start_metric.timestamp_s), 3),
        "end_s": round(float(end_metric.timestamp_s), 3),
        "clip_start_s": round(float(start_metric.clip_timestamp_s), 3),
        "clip_end_s": round(float(end_metric.clip_timestamp_s), 3),
        "duration_s": round(float(duration_s), 3),
        "frames": frames,
        "room_view_frames": room_view_frames,
        "non_room_view_frames": frames - room_view_frames,
        "observable_rate": observable_rate,
        "mean_confidence": mean_confidence,
        "min_confidence": round(min(confidences), 3),
        "max_confidence": round(max(confidences), 3),
        "evidence_level": evidence_level,
        "dominant_signal": dominant_signal,
        "mean_table_signal": signal_means["table"],
        "mean_access_signal": signal_means["access"],
        "mean_imaging_signal": signal_means["imaging"],
        "mean_device_signal": signal_means["device"],
        "mean_anesthesia_signal": signal_means["anesthesia"],
        "mean_stillness_signal": signal_means["stillness"],
        "mean_crowd_signal": signal_means["crowd"],
        "support_label": support_label,
        "label": (
            f"{stage_state.stage_label}: {evidence_level}; {support_label}"
        ),
    }


def _procedure_milestone_item(
    milestone_index: int,
    stage: str,
    evidence_rows: Sequence[Dict[str, Any]],
    staffing: Dict[str, Any],
    is_current_observed_stage: bool,
) -> Dict[str, Any]:
    observed = bool(evidence_rows)
    stage_label = TAVR_STAGE_LABELS.get(stage, stage)
    if not observed:
        return {
            "milestone_index": milestone_index,
            "stage": stage,
            "stage_label": stage_label,
            "observed_in_clip": False,
            "milestone_status": "not_observed_in_clip",
            "is_current_observed_stage": False,
            "first_observed_s": None,
            "last_observed_s": None,
            "duration_s": 0.0,
            "segment_count": 0,
            "evidence_level": None,
            "observable_rate": None,
            "mean_confidence": None,
            "peak_table_count": 0,
            "unique_table_track_count": 0,
            "canonical_table_identity_count": 0,
            "support_label": "",
            "label": f"{stage_label}: not observed in this clip",
        }

    duration_s = round(sum(row["duration_s"] for row in evidence_rows), 3)
    observable_rate = _weighted_average(evidence_rows, "observable_rate", "frames")
    mean_confidence = _weighted_average(evidence_rows, "mean_confidence", "frames")
    evidence_level = _dominant_evidence_level(evidence_rows)
    status = "current_observed" if is_current_observed_stage else "observed_prior"
    peak_table_count = int(staffing.get("peak_table_count", 0) or 0)
    unique_table_track_count = int(staffing.get("unique_table_track_count", 0) or 0)
    canonical_table_identity_count = int(
        staffing.get("canonical_table_identity_count", unique_table_track_count) or 0
    )
    support_label = (
        f"{status}; evidence={evidence_level}; observable={observable_rate:.0%}; "
        f"confidence={mean_confidence:.2f}; table_peak={peak_table_count}; "
        f"table_people={canonical_table_identity_count}"
    )
    return {
        "milestone_index": milestone_index,
        "stage": stage,
        "stage_label": stage_label,
        "observed_in_clip": True,
        "milestone_status": status,
        "is_current_observed_stage": is_current_observed_stage,
        "first_observed_s": round(min(row["start_s"] for row in evidence_rows), 3),
        "last_observed_s": round(max(row["end_s"] for row in evidence_rows), 3),
        "duration_s": duration_s,
        "segment_count": len(evidence_rows),
        "evidence_level": evidence_level,
        "observable_rate": observable_rate,
        "mean_confidence": mean_confidence,
        "peak_table_count": peak_table_count,
        "unique_table_track_count": unique_table_track_count,
        "canonical_table_identity_count": canonical_table_identity_count,
        "support_label": support_label,
        "label": f"{stage_label}: {support_label}",
    }


def _current_milestone(
    milestones: Sequence[Dict[str, Any]],
    fallback_stage: str,
) -> Dict[str, Any]:
    for item in milestones:
        if item.get("is_current_observed_stage"):
            return item
    for item in milestones:
        if item.get("stage") == fallback_stage:
            return item
    return {
        "stage": fallback_stage,
        "stage_label": TAVR_STAGE_LABELS.get(fallback_stage, fallback_stage),
        "milestone_status": "not_observed_in_clip",
        "evidence_level": None,
        "observable_rate": None,
        "mean_confidence": None,
    }


def _next_milestone(
    milestones: Sequence[Dict[str, Any]],
    current_milestone: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    current_index = current_milestone.get("milestone_index")
    if current_index is None:
        current_stage = current_milestone.get("stage")
        current_index = (
            TAVR_STAGE_ORDER.index(current_stage)
            if current_stage in TAVR_STAGE_ORDER
            else -1
        )
    for item in milestones:
        if item.get("milestone_index", -1) > current_index:
            return item
    return None


def _effective_table_status(
    latest_metric: FrameMetrics,
    latest_state: TAVRFrameState,
    current_roster: Sequence[Dict[str, Any]],
    last_observed: Dict[str, Any],
    recent_hold_s: float = 5.0,
) -> Dict[str, Any]:
    if _view_label(latest_metric) == "room":
        last_roster = last_observed.get("roster", [])
        last_age_s = last_observed.get("age_from_clip_end_s")
        if (
            not current_roster
            and last_roster
            and last_age_s is not None
            and float(last_age_s) <= recent_hold_s
        ):
            return {
                "source": "recent_room_view_hold",
                "timestamp_s": last_observed.get("timestamp_s"),
                "clip_timestamp_s": last_observed.get("clip_timestamp_s"),
                "age_from_clip_end_s": last_age_s,
                "stage": last_observed.get("stage"),
                "stage_label": last_observed.get("stage_label"),
                "table_count": last_observed.get("table_count", 0),
                "track_ids": [item["track_id"] for item in last_roster],
                "roster": list(last_roster),
            }
        source = (
            "current_room_view"
            if current_roster
            else "current_room_view_empty"
        )
        return {
            "source": source,
            "timestamp_s": round(float(latest_metric.timestamp_s), 3),
            "clip_timestamp_s": round(float(latest_metric.clip_timestamp_s), 3),
            "age_from_clip_end_s": 0.0,
            "stage": latest_state.stage,
            "stage_label": latest_state.stage_label,
            "table_count": latest_state.table_count,
            "track_ids": [item["track_id"] for item in current_roster],
            "roster": list(current_roster),
        }

    last_roster = last_observed.get("roster", [])
    if last_roster:
        return {
            "source": "last_observed_room_view",
            "timestamp_s": last_observed.get("timestamp_s"),
            "clip_timestamp_s": last_observed.get("clip_timestamp_s"),
            "age_from_clip_end_s": last_observed.get("age_from_clip_end_s"),
            "stage": last_observed.get("stage"),
            "stage_label": last_observed.get("stage_label"),
            "table_count": last_observed.get("table_count", 0),
            "track_ids": [item["track_id"] for item in last_roster],
            "roster": list(last_roster),
        }

    return {
        "source": "no_room_table_evidence",
        "timestamp_s": None,
        "clip_timestamp_s": None,
        "age_from_clip_end_s": None,
        "stage": None,
        "stage_label": None,
        "table_count": 0,
        "track_ids": [],
        "roster": [],
    }


def _stage_evidence_status(
    evidence_level: Optional[str],
    observable_rate: Optional[float],
) -> str:
    if evidence_level == "held_non_room" or observable_rate == 0:
        return "held_non_room_context"
    if evidence_level in {
        "weak_visual_support",
        "moderate_visual_support",
        "strong_visual_support",
    }:
        return evidence_level
    return "unknown_stage_support"


def _stage_evidence_status_label(status: Optional[str]) -> str:
    labels = {
        "held_non_room_context": "held from non-room context",
        "weak_visual_support": "weak visual support",
        "moderate_visual_support": "moderate visual support",
        "strong_visual_support": "strong visual support",
        "unknown_stage_support": "unknown stage support",
    }
    return labels.get(status or "", "unknown stage support")


def _evidence_level_label(evidence_level: Optional[str]) -> str:
    if not evidence_level:
        return "no evidence"
    labels = {
        "held_non_room": "held non-room",
        "weak_visual_support": "weak visual support",
        "moderate_visual_support": "moderate visual support",
        "strong_visual_support": "strong visual support",
    }
    return labels.get(evidence_level, _text_status_label(evidence_level))


def _evidence_support_clause(
    evidence_level: Optional[str],
    stage_support: str,
) -> str:
    evidence_label = _evidence_level_label(evidence_level)
    if evidence_label == stage_support:
        return evidence_label
    return f"{evidence_label}, stage support {stage_support}"


def _current_stage_phrase(stage_evidence_status: Optional[str]) -> str:
    if stage_evidence_status == "held_non_room_context":
        return "Current held stage"
    if stage_evidence_status == "weak_visual_support":
        return "Current weakly supported stage"
    if stage_evidence_status == "unknown_stage_support":
        return "Current stage context"
    return "Current observed stage"


def _procedure_status_label(row: Dict[str, Any]) -> str:
    current_roster = _roster_status_label(row.get("current_table_roster", []))
    effective_roster = _roster_status_label(row.get("effective_table_roster", []))
    last_roster = _roster_status_label(row.get("last_observed_table_roster", []))
    current_confidence = _maybe_float_label(row.get("mean_confidence"))
    observable_rate = _maybe_percent_label(row.get("observable_rate"))
    next_stage = row.get("next_stage_label") or "procedure end"
    tracking_label = "available" if row.get("tracking_available") else "not available"
    quality_flags = row.get("quality_flag_codes", [])
    quality_label = ", ".join(quality_flags) if quality_flags else "none"
    stage_phrase = _current_stage_phrase(row.get("current_stage_evidence_status"))
    stage_support = row.get("current_stage_evidence_label") or "stage support n/a"
    evidence_clause = _evidence_support_clause(row.get("evidence_level"), stage_support)
    return (
        f"{stage_phrase}: {row.get('current_stage_label') or 'n/a'} "
        f"({evidence_clause}, confidence {current_confidence}, "
        f"observable {observable_rate}); "
        f"tracking {tracking_label}; at table now: {current_roster}; "
        f"table status: {_text_status_label(row.get('effective_table_source'))} "
        f"{effective_roster}; "
        f"last observed table: {last_roster}; next: {next_stage}; "
        f"quality flags: {quality_label}"
    )


def _operator_stage_packet_label(row: Dict[str, Any]) -> str:
    status_label = (
        "Current stage" if row.get("is_current_stage") else "Observed stage"
    )
    stage_support = row.get("stage_evidence_label") or "stage support n/a"
    evidence = _evidence_support_clause(row.get("evidence_level"), stage_support)
    observable_rate = _maybe_percent_label(row.get("observable_rate"))
    mean_confidence = _maybe_float_label(row.get("mean_confidence"))
    handoff = _text_status_label(row.get("handoff_type"))
    active_ids = _track_ids_text(row.get("active_table_track_ids", []))
    new_ids = _track_ids_text(row.get("new_track_ids", []))
    dropped_ids = _track_ids_text(row.get("dropped_track_ids", []))
    quality_flags = row.get("quality_flag_codes", [])
    quality_label = ", ".join(quality_flags) if quality_flags else "none"
    packet = (
        f"{status_label}: {row.get('stage_label') or 'n/a'} "
        f"{row.get('start_s')}s-{row.get('end_s')}s; "
        f"evidence {evidence}, "
        f"confidence {mean_confidence}, "
        f"observable {observable_rate}; handoff {handoff}; "
        f"peak table {row.get('peak_table_count', 0)}; "
        f"active IDs {active_ids}; new IDs {new_ids}; "
        f"dropped IDs {dropped_ids}; roster {row.get('roster_summary') or 'none'}"
    )
    if row.get("is_current_stage"):
        packet += (
            f"; latest table status "
            f"{_text_status_label(row.get('effective_table_source'))} "
            f"{row.get('effective_table_count', 0)} IDs "
            f"{_track_ids_text(row.get('effective_table_track_ids', []))}"
        )
        if row.get("next_stage_label"):
            packet += f"; next {row['next_stage_label']}"
    packet += f"; quality flags {quality_label}"
    return packet


def _table_team_status(
    track_id: int,
    current_ids: set[int],
    effective_ids: set[int],
    last_ids: set[int],
    age_from_clip_end_s: Optional[float],
    recent_age_s: float,
) -> str:
    if track_id in current_ids:
        return "active_current"
    if track_id in effective_ids:
        return "recent_last_observed"
    if (
        track_id in last_ids
        and age_from_clip_end_s is not None
        and age_from_clip_end_s <= recent_age_s
    ):
        return "recent_last_observed"
    return "historical_seen"


def _table_team_status_from_membership(
    is_current_member: bool,
    is_effective_member: bool,
    is_last_member: bool,
    age_from_clip_end_s: Optional[float],
    recent_age_s: float,
) -> str:
    if is_current_member:
        return "active_current"
    if is_effective_member:
        return "recent_last_observed"
    if (
        is_last_member
        and age_from_clip_end_s is not None
        and age_from_clip_end_s <= recent_age_s
    ):
        return "recent_last_observed"
    return "historical_seen"


def _table_team_role(
    role_counts: Dict[str, int],
    dominant_role: str,
    table_frames: int,
) -> tuple[str, Optional[float]]:
    if table_frames <= 0:
        return dominant_role, None

    table_facing_roles = ("access_operator", "table_operator")
    minimum_support = max(3, int(table_frames * 0.1))
    candidates = [
        (role, min(int(role_counts.get(role, 0) or 0), table_frames))
        for role in table_facing_roles
        if int(role_counts.get(role, 0) or 0) >= minimum_support
    ]
    if not candidates:
        dominant_count = min(int(role_counts.get(dominant_role, 0) or 0), table_frames)
        return dominant_role, _ratio(dominant_count, table_frames)

    priority = {role: index for index, role in enumerate(table_facing_roles)}
    role, count = max(
        candidates,
        key=lambda item: (item[1], -priority.get(item[0], len(priority))),
    )
    return role, _ratio(count, table_frames)


def _table_team_label(row: Dict[str, Any]) -> str:
    stage_label = row.get("dominant_stage_label") or "stage n/a"
    age = row.get("age_from_clip_end_s")
    age_label = f"{float(age):.1f}s ago" if age is not None else "age n/a"
    ratio = _maybe_percent_label(row.get("table_presence_ratio"))
    return (
        f"{_role_label(row['track_id'], row.get('table_team_role'), row.get('dominant_role'))} "
        f"{_text_status_label(row['team_status'])}; "
        f"table={ratio}; last={age_label}; dominant={stage_label}"
    )


def _role_label(
    track_id: int,
    role: Optional[str],
    dominant_role: Optional[str],
    suffix: Optional[str] = None,
) -> str:
    role_label = role or dominant_role or "unassigned"
    role_detail = (
        f"{role_label} (dominant {dominant_role})"
        if dominant_role and role_label != dominant_role
        else str(role_label)
    )
    label = f"ID {track_id} {role_detail}"
    if suffix:
        label = f"{label} {suffix}"
    return label


def _roster_status_label(roster: Sequence[Dict[str, Any]]) -> str:
    labels = [str(item.get("label")) for item in roster if item.get("label")]
    return "; ".join(labels[:6]) if labels else "none"


def _track_ids_text(track_ids: Sequence[Any]) -> str:
    return ", ".join(str(track_id) for track_id in track_ids) or "none"


def _text_status_label(value: Any) -> str:
    return str(value or "n/a").replace("_", " ")


def _maybe_float_label(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.2f}"


def _maybe_percent_label(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.0%}"


def _min_optional(first: Any, second: Any) -> Any:
    if first is None:
        return second
    if second is None:
        return first
    return min(first, second)


def _max_optional(first: Any, second: Any) -> Any:
    if first is None:
        return second
    if second is None:
        return first
    return max(first, second)


def _round_optional(value: Any) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), 3)


def _weighted_average(
    rows: Sequence[Dict[str, Any]],
    value_key: str,
    weight_key: str,
) -> float:
    total_weight = sum(int(row.get(weight_key, 0) or 0) for row in rows)
    if total_weight <= 0:
        return 0.0
    total_value = sum(
        float(row.get(value_key, 0.0) or 0.0) * int(row.get(weight_key, 0) or 0)
        for row in rows
    )
    return round(total_value / total_weight, 3)


def _dominant_evidence_level(rows: Sequence[Dict[str, Any]]) -> str:
    if not rows:
        return "not_observed"
    level_rank = {
        "held_non_room": 0,
        "weak_visual_support": 1,
        "moderate_visual_support": 2,
        "strong_visual_support": 3,
    }
    return max(
        rows,
        key=lambda row: (
            level_rank.get(row["evidence_level"], -1),
            row.get("duration_s", 0.0),
        ),
    )["evidence_level"]


def _mean_signal(
    segment_metrics: Sequence[FrameMetrics],
    name: str,
) -> float:
    values = [_tavr_state(metric).signals.get(name, 0.0) for metric in segment_metrics]
    if not values:
        return 0.0
    return round(sum(values) / len(values), 3)


def _dominant_signal(signal_means: Dict[str, float]) -> str:
    if not signal_means:
        return "none"
    return max(signal_means.items(), key=lambda item: (item[1], item[0]))[0]


def _stage_evidence_level(
    observable_rate: float,
    mean_confidence: float,
    room_view_frames: int,
) -> str:
    if room_view_frames <= 0 or observable_rate <= 0.0:
        return "held_non_room"
    if observable_rate >= 0.8 and mean_confidence >= 0.5:
        return "strong_visual_support"
    if observable_rate >= 0.5 and mean_confidence >= 0.35:
        return "moderate_visual_support"
    return "weak_visual_support"


def _stage_started_event(
    segment_index: int,
    segment_metrics: Sequence[FrameMetrics],
) -> Dict[str, Any]:
    start_metric = segment_metrics[0]
    end_metric = segment_metrics[-1]
    state = _tavr_state(start_metric)
    sample_period_s = _sample_period_s(segment_metrics)
    duration_s = max(
        0.0,
        end_metric.timestamp_s - start_metric.timestamp_s + sample_period_s,
    )
    roster = _roster_from_state(state)
    return {
        "event_type": "stage_started",
        "timestamp_s": round(float(start_metric.timestamp_s), 3),
        "clip_timestamp_s": round(float(start_metric.clip_timestamp_s), 3),
        "frame_index": start_metric.frame_index,
        "end_s": round(float(end_metric.timestamp_s), 3),
        "clip_end_s": round(float(end_metric.clip_timestamp_s), 3),
        "duration_s": round(float(duration_s), 3),
        "stage": state.stage,
        "stage_label": state.stage_label,
        "view": _view_label(start_metric),
        "tracking_available": _view_label(start_metric) == "room",
        "table_count": state.table_count,
        "track_id": None,
        "dominant_role": None,
        "table_team_role": None,
        "table_team_role_confidence": None,
        "handoff_type": None,
        "table_track_ids": list(state.table_track_ids),
        "roster": roster,
        "source": "stage_timeline",
        "label": (
            f"{start_metric.clip_timestamp_s:.1f}s stage started: "
            f"{state.stage_label}"
        ),
    }


def _view_started_event(
    view_segment: Dict[str, Any],
    start_metric: Optional[FrameMetrics],
) -> Dict[str, Any]:
    start_state = _tavr_state(start_metric) if start_metric is not None else None
    stage = start_state.stage if start_state is not None else view_segment.get("dominant_stage")
    stage_label = (
        start_state.stage_label
        if start_state is not None
        else TAVR_STAGE_LABELS.get(stage, stage)
    )
    return {
        "event_type": "view_started",
        "timestamp_s": view_segment["start_s"],
        "clip_timestamp_s": view_segment.get("clip_start_s"),
        "frame_index": view_segment["start_frame"],
        "end_s": view_segment["end_s"],
        "clip_end_s": view_segment.get("clip_end_s"),
        "duration_s": view_segment["duration_s"],
        "stage": stage,
        "stage_label": stage_label,
        "view": view_segment["view"],
        "tracking_available": view_segment["tracking_available"],
        "table_count": view_segment["peak_table_count"],
        "track_id": None,
        "dominant_role": None,
        "table_team_role": None,
        "table_team_role_confidence": None,
        "handoff_type": None,
        "table_track_ids": [],
        "roster": [],
        "source": "view_segments",
        "label": (
            f"{view_segment.get('clip_start_s', view_segment['start_s']):.1f}s "
            f"{view_segment['view']} view started"
        ),
    }


def _handoff_event(handoff: Dict[str, Any]) -> Dict[str, Any]:
    lead_track_id = handoff.get("lead_track_id")
    return {
        "event_type": "table_handoff",
        "timestamp_s": handoff["start_s"],
        "clip_timestamp_s": handoff.get("clip_start_s"),
        "frame_index": handoff["start_frame"],
        "end_s": handoff["end_s"],
        "clip_end_s": handoff.get("clip_end_s"),
        "duration_s": handoff["duration_s"],
        "stage": handoff["stage"],
        "stage_label": handoff["stage_label"],
        "view": "room" if handoff["tracking_available_rate"] else "non_room",
        "tracking_available": bool(handoff["tracking_available_rate"]),
        "table_count": handoff["active_table_track_count"],
        "track_id": lead_track_id,
        "dominant_role": handoff.get("lead_dominant_role"),
        "table_team_role": handoff.get("lead_table_team_role"),
        "table_team_role_confidence": handoff.get("lead_table_team_role_confidence"),
        "handoff_type": handoff["handoff_type"],
        "table_track_ids": [
            item["track_id"] for item in handoff["active_table_roster"]
        ],
        "roster": handoff["active_table_roster"],
        "source": "stage_handoff_summary",
        "label": handoff["label"],
    }


def _table_peak_event(peak: Dict[str, Any]) -> Dict[str, Any]:
    roster = peak.get("roster", [])
    lead = roster[0] if roster else None
    return {
        "event_type": "table_peak",
        "timestamp_s": peak.get("timestamp_s"),
        "clip_timestamp_s": peak.get("clip_timestamp_s"),
        "frame_index": peak.get("frame_index"),
        "end_s": peak.get("timestamp_s"),
        "clip_end_s": peak.get("clip_timestamp_s"),
        "duration_s": 0.0,
        "stage": peak.get("stage"),
        "stage_label": peak.get("stage_label"),
        "view": "room",
        "tracking_available": True,
        "table_count": peak.get("table_count", 0),
        "track_id": lead.get("track_id") if lead else None,
        "dominant_role": lead.get("dominant_role") if lead else None,
        "table_team_role": lead.get("table_team_role") if lead else None,
        "table_team_role_confidence": (
            lead.get("table_team_role_confidence") if lead else None
        ),
        "handoff_type": None,
        "table_track_ids": [item["track_id"] for item in roster],
        "roster": roster,
        "source": "peak_table_roster",
        "label": (
            f"{peak.get('clip_timestamp_s', peak.get('timestamp_s'))}s table peak: "
            f"{peak.get('table_count', 0)} active during "
            f"{peak.get('stage_label') or 'unknown stage'}"
        ),
    }


def _handoff_roster_item(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "track_id": row["track_id"],
        "canonical_table_id": row["canonical_table_id"],
        "merged_track_ids": row["merged_track_ids"],
        "dominant_role": row["dominant_role"],
        "table_team_role": row["table_team_role"],
        "table_team_role_confidence": row["table_team_role_confidence"],
        "observed_table_frames": row["observed_table_frames"],
        "coverage_ratio": row["coverage_ratio"],
        "room_coverage_ratio": row["room_coverage_ratio"],
        "first_seen_s": row["first_seen_s"],
        "last_seen_s": row["last_seen_s"],
        "first_seen_clip_s": row["first_seen_clip_s"],
        "last_seen_clip_s": row["last_seen_clip_s"],
        "label": (
            f"{_role_label(row['track_id'], row['table_team_role'], row['dominant_role'])} "
            f"{row['observed_table_frames']} frames "
            f"{row['first_seen_clip_s']:.1f}-{row['last_seen_clip_s']:.1f}s"
        ),
    }


def _handoff_type(
    has_previous_stage: bool,
    previous_ids: set[int],
    active_ids: set[int],
    new_ids: set[int],
    dropped_ids: set[int],
) -> str:
    if not has_previous_stage and not previous_ids and not active_ids:
        return "initial_no_table_evidence"
    if not has_previous_stage and not previous_ids and active_ids:
        return "initial_table_roster"
    if not previous_ids and not active_ids:
        return "no_table_evidence"
    if not previous_ids and active_ids:
        return "table_roster_started"
    if previous_ids and not active_ids:
        return "table_cleared"
    if new_ids and dropped_ids:
        return "roster_changed"
    if new_ids:
        return "roster_added"
    if dropped_ids:
        return "roster_removed"
    if active_ids:
        return "roster_continued"
    return "no_table_evidence"


def _handoff_label(
    stage_label: str,
    handoff_type: str,
    lead: Optional[Dict[str, Any]],
    active_roster: Sequence[Dict[str, Any]],
) -> str:
    if lead is None:
        return f"{stage_label}: {handoff_type}; no table roster evidence"
    return (
        f"{stage_label}: {handoff_type}; lead ID {lead['track_id']} "
        f"{lead['table_team_role']}; active table tracks={len(active_roster)}"
    )


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
        "clip_start_s": round(float(start_metric.clip_timestamp_s), 3),
        "clip_end_s": round(float(end_metric.clip_timestamp_s), 3),
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
            f"{view} view {start_metric.clip_timestamp_s:.1f}-"
            f"{end_metric.clip_timestamp_s:.1f}s"
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
        "clip_timestamp_s": coverage["first_seen_clip_s"]
        if is_entry
        else coverage["last_seen_clip_s"],
        "frame_index": frame,
        "track_id": coverage["track_id"],
        "canonical_table_id": coverage["canonical_table_id"],
        "merged_track_ids": coverage["merged_track_ids"],
        "dominant_role": coverage["dominant_role"],
        "table_team_role": coverage["table_team_role"],
        "table_team_role_confidence": coverage["table_team_role_confidence"],
        "stage": coverage["stage"],
        "stage_label": coverage["stage_label"],
        "stage_segment_index": coverage["stage_segment_index"],
        "coverage_ratio": coverage["coverage_ratio"],
        "room_coverage_ratio": coverage["room_coverage_ratio"],
        "tracking_available_rate": coverage["tracking_available_rate"],
        "observed_table_frames": coverage["observed_table_frames"],
        "label": (
            f"{(coverage['first_seen_clip_s'] if is_entry else coverage['last_seen_clip_s']):.1f}s "
            f"{event_type}: ID {coverage['track_id']} "
            f"{coverage['table_team_role']} during {coverage['stage_label']}"
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
        dominant_role = expectation.get("dominant_role")
        min_intervals = int(expectation.get("min_intervals", 1))
        min_observed_table_frames = int(expectation.get("min_observed_table_frames", 3))
        overlapping = [
            interval
            for interval in intervals
            if _interval_overlaps_expectation(interval, expectation)
            and _role_expectation_matches(interval, role, dominant_role)
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
                "dominant_role": dominant_role,
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
        dominant_role = expectation.get("dominant_role")
        min_tracks = int(expectation.get("min_tracks", 0))
        min_observed_table_frames = int(expectation.get("min_observed_table_frames", 1))
        min_peak_count = expectation.get("min_peak_count")
        min_mean_count = expectation.get("min_mean_count")
        min_table_occupancy_rate = expectation.get("min_table_occupancy_rate")
        min_tracking_available_rate = expectation.get("min_tracking_available_rate")
        min_room_mean_count = expectation.get("min_room_mean_count")
        min_room_table_occupancy_rate = expectation.get(
            "min_room_table_occupancy_rate"
        )
        min_canonical_table_identity_count = expectation.get(
            "min_canonical_table_identity_count"
        )
        max_canonical_table_identity_count = expectation.get(
            "max_canonical_table_identity_count"
        )
        stage_summary = stage_summaries.get(stage)
        matching_roster = []
        if stage_summary is not None:
            matching_roster = [
                track
                for track in stage_summary["table_roster"]
                if _role_expectation_matches(track, role, dominant_role)
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
            "min_tracking_available_rate": (
                min_tracking_available_rate is None
                or (
                    stage_summary is not None
                    and stage_summary["tracking_available_rate"] is not None
                    and stage_summary["tracking_available_rate"]
                    >= min_tracking_available_rate
                )
            ),
            "min_room_mean_count": (
                min_room_mean_count is None
                or (
                    stage_summary is not None
                    and stage_summary["mean_room_table_count"] is not None
                    and stage_summary["mean_room_table_count"] >= min_room_mean_count
                )
            ),
            "min_room_table_occupancy_rate": (
                min_room_table_occupancy_rate is None
                or (
                    stage_summary is not None
                    and stage_summary["room_table_occupancy_rate"] is not None
                    and stage_summary["room_table_occupancy_rate"]
                    >= min_room_table_occupancy_rate
                )
            ),
            "min_canonical_table_identity_count": (
                min_canonical_table_identity_count is None
                or (
                    stage_summary is not None
                    and stage_summary["canonical_table_identity_count"]
                    >= int(min_canonical_table_identity_count)
                )
            ),
            "max_canonical_table_identity_count": (
                max_canonical_table_identity_count is None
                or (
                    stage_summary is not None
                    and stage_summary["canonical_table_identity_count"]
                    <= int(max_canonical_table_identity_count)
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
                "dominant_role": dominant_role,
                "min_tracks": min_tracks,
                "min_observed_table_frames": min_observed_table_frames,
                "min_peak_count": min_peak_count,
                "min_mean_count": min_mean_count,
                "min_table_occupancy_rate": min_table_occupancy_rate,
                "min_tracking_available_rate": min_tracking_available_rate,
                "min_room_mean_count": min_room_mean_count,
                "min_room_table_occupancy_rate": min_room_table_occupancy_rate,
                "canonical_table_identity_count": (
                    stage_summary.get("canonical_table_identity_count")
                    if stage_summary is not None
                    else None
                ),
                "min_canonical_table_identity_count": (
                    min_canonical_table_identity_count
                ),
                "max_canonical_table_identity_count": (
                    max_canonical_table_identity_count
                ),
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


def _stage_table_coverage_score(
    metrics: Sequence[FrameMetrics],
    expectations: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    if not expectations:
        return {"expectations": [], "pass_rate": None}

    rows = stage_table_coverage(metrics, min_observed_table_frames=1)
    passed = 0
    scored_expectations = []
    for expectation in expectations:
        stage = expectation.get("stage")
        stage_segment_index = expectation.get("stage_segment_index")
        if "min_tracks" in expectation:
            min_tracks = int(expectation["min_tracks"])
        elif "max_tracks" in expectation:
            min_tracks = 0
        else:
            min_tracks = 1
        max_tracks = expectation.get("max_tracks")
        candidates = [
            row
            for row in rows
            if (stage is None or row["stage"] == stage)
            and (
                stage_segment_index is None
                or row["stage_segment_index"] == int(stage_segment_index)
            )
            and _stage_coverage_overlaps_expectation(row, expectation)
        ]
        scored_candidates = [
            _score_stage_table_coverage_candidate(row, expectation)
            for row in candidates
        ]
        passed_candidates = [
            candidate for candidate in scored_candidates if candidate["passed"]
        ]
        checks = {
            "min_tracks": len(passed_candidates) >= min_tracks,
            "max_tracks": (
                max_tracks is None or len(passed_candidates) <= int(max_tracks)
            ),
        }
        expectation_pass = all(checks.values())
        if expectation_pass:
            passed += 1
        scored_expectations.append(
            {
                "stage": stage,
                "stage_segment_index": stage_segment_index,
                "role": expectation.get("role")
                or expectation.get("table_team_role"),
                "dominant_role": expectation.get("dominant_role"),
                "min_tracks": min_tracks,
                "max_tracks": max_tracks,
                "start_s": expectation.get("start_s"),
                "end_s": expectation.get("end_s"),
                "candidate_checks": scored_candidates,
                "candidate_count": len(scored_candidates),
                "matched_candidates": passed_candidates,
                "matched_count": len(passed_candidates),
                "passed_candidate_count": len(passed_candidates),
                "checks": checks,
                "passed": expectation_pass,
            }
        )

    return {
        "expectations": scored_expectations,
        "pass_rate": _ratio(passed, len(expectations)),
    }


def _table_transition_score(
    metrics: Sequence[FrameMetrics],
    expectations: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    if not expectations:
        return {"expectations": [], "pass_rate": None}

    events = table_transition_events(metrics, min_observed_table_frames=1)
    passed = 0
    scored_expectations = []
    for expectation in expectations:
        event_types = _expected_event_types(expectation)
        stage = expectation.get("stage")
        stage_segment_index = expectation.get("stage_segment_index")
        min_events = int(
            expectation.get(
                "min_events",
                0 if "max_events" in expectation else 1,
            )
        )
        max_events = expectation.get("max_events")
        candidates = [
            event
            for event in events
            if (not event_types or event["event_type"] in event_types)
            and (stage is None or event["stage"] == stage)
            and (
                stage_segment_index is None
                or event["stage_segment_index"] == int(stage_segment_index)
            )
            and _transition_event_overlaps_expectation(event, expectation)
        ]
        scored_candidates = [
            _score_table_transition_candidate(event, expectation)
            for event in candidates
        ]
        matched_candidates = [
            candidate for candidate in scored_candidates if candidate["passed"]
        ]
        matched_count = len(matched_candidates)
        checks = {
            "min_events": matched_count >= min_events,
            "max_events": (
                max_events is None or matched_count <= int(max_events)
            ),
        }
        expectation_pass = all(checks.values())
        if expectation_pass:
            passed += 1
        scored_expectations.append(
            {
                "event_types": sorted(event_types) or None,
                "stage": stage,
                "stage_segment_index": stage_segment_index,
                "role": expectation.get("role")
                or expectation.get("table_team_role"),
                "dominant_role": expectation.get("dominant_role"),
                "min_events": min_events,
                "max_events": max_events,
                "start_s": expectation.get("start_s"),
                "end_s": expectation.get("end_s"),
                "candidate_checks": scored_candidates,
                "candidate_count": len(scored_candidates),
                "matched_candidates": matched_candidates,
                "matched_count": matched_count,
                "checks": checks,
                "passed": expectation_pass,
            }
        )

    return {
        "expectations": scored_expectations,
        "pass_rate": _ratio(passed, len(expectations)),
    }


def _stage_handoff_score(
    metrics: Sequence[FrameMetrics],
    expectations: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    if not expectations:
        return {"expectations": [], "pass_rate": None}

    handoffs = stage_handoff_summary(metrics, min_observed_table_frames=1)
    passed = 0
    scored_expectations = []
    for expectation in expectations:
        stage = expectation.get("stage")
        stage_segment_index = expectation.get("stage_segment_index")
        role = expectation.get("role")
        dominant_role = expectation.get("dominant_role")
        lead_role = expectation.get("lead_role")
        lead_dominant_role = expectation.get("lead_dominant_role")
        min_active_tracks = int(expectation.get("min_active_tracks", 0))
        min_new_tracks = int(expectation.get("min_new_tracks", 0))
        min_continued_tracks = int(expectation.get("min_continued_tracks", 0))
        min_dropped_tracks = int(expectation.get("min_dropped_tracks", 0))
        min_lead_observed_table_frames = int(
            expectation.get("min_lead_observed_table_frames", 0)
        )
        min_tracking_available_rate = expectation.get("min_tracking_available_rate")
        expected_handoff_types = _expected_handoff_types(expectation)
        candidates = [
            handoff
            for handoff in handoffs
            if (stage is None or handoff["stage"] == stage)
            and (
                stage_segment_index is None
                or handoff["stage_segment_index"] == int(stage_segment_index)
            )
            and _handoff_overlaps_expectation(handoff, expectation)
        ]
        scored_candidates = [
            _score_handoff_candidate(
                handoff=handoff,
                role=role,
                dominant_role=dominant_role,
                lead_role=lead_role,
                lead_dominant_role=lead_dominant_role,
                expected_handoff_types=expected_handoff_types,
                min_active_tracks=min_active_tracks,
                min_new_tracks=min_new_tracks,
                min_continued_tracks=min_continued_tracks,
                min_dropped_tracks=min_dropped_tracks,
                min_lead_observed_table_frames=min_lead_observed_table_frames,
                min_tracking_available_rate=min_tracking_available_rate,
            )
            for handoff in candidates
        ]
        expectation_pass = any(candidate["passed"] for candidate in scored_candidates)
        if expectation_pass:
            passed += 1
        scored_expectations.append(
            {
                "stage": stage,
                "stage_segment_index": stage_segment_index,
                "role": role,
                "dominant_role": dominant_role,
                "lead_role": lead_role,
                "lead_dominant_role": lead_dominant_role,
                "handoff_types": sorted(expected_handoff_types)
                if expected_handoff_types
                else None,
                "min_active_tracks": min_active_tracks,
                "min_new_tracks": min_new_tracks,
                "min_continued_tracks": min_continued_tracks,
                "min_dropped_tracks": min_dropped_tracks,
                "min_lead_observed_table_frames": min_lead_observed_table_frames,
                "min_tracking_available_rate": min_tracking_available_rate,
                "matched_candidates": scored_candidates,
                "matched_count": len(scored_candidates),
                "passed": expectation_pass,
            }
        )

    return {
        "expectations": scored_expectations,
        "pass_rate": _ratio(passed, len(expectations)),
    }


def _stage_roster_score(
    metrics: Sequence[FrameMetrics],
    expectations: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    if not expectations:
        return {"expectations": [], "pass_rate": None}

    rows = stage_roster_summary(metrics, min_observed_table_frames=1)
    passed = 0
    scored_expectations = []
    for expectation in expectations:
        stage = expectation.get("stage")
        stage_segment_index = expectation.get("stage_segment_index")
        candidates = [
            row
            for row in rows
            if (stage is None or row["stage"] == stage)
            and (
                stage_segment_index is None
                or row["stage_segment_index"] == int(stage_segment_index)
            )
            and _stage_row_overlaps_expectation(row, expectation)
        ]
        scored_candidates = [
            _score_stage_roster_candidate(row, expectation)
            for row in candidates
        ]
        expectation_pass = any(candidate["passed"] for candidate in scored_candidates)
        if expectation_pass:
            passed += 1
        scored_expectations.append(
            {
                "stage": stage,
                "stage_segment_index": stage_segment_index,
                "handoff_types": sorted(_expected_handoff_types(expectation)) or None,
                "evidence_levels": sorted(_expected_evidence_levels(expectation))
                or None,
                "start_s": expectation.get("start_s"),
                "end_s": expectation.get("end_s"),
                "matched_candidates": scored_candidates,
                "matched_count": len(scored_candidates),
                "passed": expectation_pass,
            }
        )

    return {
        "expectations": scored_expectations,
        "pass_rate": _ratio(passed, len(expectations)),
    }


def _stage_evidence_score(
    metrics: Sequence[FrameMetrics],
    expectations: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    if not expectations:
        return {"expectations": [], "pass_rate": None}

    evidence_rows = stage_evidence_summary(metrics)
    passed = 0
    scored_expectations = []
    for expectation in expectations:
        candidates = [
            row
            for row in evidence_rows
            if _stage_evidence_matches_expectation(row, expectation)
        ]
        scored_candidates = [
            _score_stage_evidence_candidate(row, expectation)
            for row in candidates
        ]
        expectation_pass = any(candidate["passed"] for candidate in scored_candidates)
        if expectation_pass:
            passed += 1
        scored_expectations.append(
            {
                "stage": expectation.get("stage"),
                "stage_segment_index": expectation.get("stage_segment_index"),
                "evidence_levels": sorted(_expected_evidence_levels(expectation))
                or None,
                "dominant_signal": expectation.get("dominant_signal"),
                "start_s": expectation.get("start_s"),
                "end_s": expectation.get("end_s"),
                "matched_candidates": scored_candidates,
                "matched_count": len(scored_candidates),
                "passed": expectation_pass,
            }
        )

    return {
        "expectations": scored_expectations,
        "pass_rate": _ratio(passed, len(expectations)),
    }


def _procedure_milestone_score(
    metrics: Sequence[FrameMetrics],
    expectations: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    if not expectations:
        return {"expectations": [], "pass_rate": None}

    milestones = procedure_milestones(metrics)
    passed = 0
    scored_expectations = []
    for expectation in expectations:
        stage = str(expectation["stage"])
        candidates = [row for row in milestones if row["stage"] == stage]
        scored_candidates = [
            _score_procedure_milestone_candidate(row, expectation)
            for row in candidates
        ]
        expectation_pass = any(candidate["passed"] for candidate in scored_candidates)
        if expectation_pass:
            passed += 1
        scored_expectations.append(
            {
                "stage": stage,
                "milestone_status": expectation.get("milestone_status"),
                "observed_in_clip": expectation.get("observed_in_clip"),
                "is_current_observed_stage": expectation.get("is_current_observed_stage"),
                "evidence_level": expectation.get("evidence_level"),
                "matched_candidates": scored_candidates,
                "matched_count": len(scored_candidates),
                "passed": expectation_pass,
            }
        )

    return {
        "expectations": scored_expectations,
        "pass_rate": _ratio(passed, len(expectations)),
    }


def _procedure_status_score(
    metrics: Sequence[FrameMetrics],
    expectations: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    if not expectations:
        return {"expectations": [], "pass_rate": None}

    status_rows = procedure_status_summary(metrics)
    passed = 0
    scored_expectations = []
    for expectation in expectations:
        scored_candidates = [
            _score_procedure_status_candidate(row, expectation)
            for row in status_rows
        ]
        expectation_pass = any(candidate["passed"] for candidate in scored_candidates)
        if expectation_pass:
            passed += 1
        scored_expectations.append(
            {
                "current_stage": expectation.get("current_stage"),
                "current_stage_status": expectation.get("current_stage_status"),
                "tracking_available": expectation.get("tracking_available"),
                "effective_table_source": expectation.get("effective_table_source"),
                "evidence_level": expectation.get("evidence_level"),
                "matched_candidates": scored_candidates,
                "matched_count": len(scored_candidates),
                "passed": expectation_pass,
            }
        )

    return {
        "expectations": scored_expectations,
        "pass_rate": _ratio(passed, len(expectations)),
    }


def _operator_packet_score(
    metrics: Sequence[FrameMetrics],
    expectations: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    if not expectations:
        return {"expectations": [], "pass_rate": None}

    packets = operator_stage_packet(metrics)
    passed = 0
    scored_expectations = []
    for expectation in expectations:
        stage = expectation.get("stage")
        stage_segment_index = expectation.get("stage_segment_index")
        is_current_stage = _expected_current_stage(expectation)
        candidates = [
            packet
            for packet in packets
            if (stage is None or packet["stage"] == stage)
            and (
                stage_segment_index is None
                or packet["stage_segment_index"] == int(stage_segment_index)
            )
            and (
                is_current_stage is None
                or bool(packet.get("is_current_stage")) == is_current_stage
            )
            and _stage_row_overlaps_expectation(packet, expectation)
        ]
        scored_candidates = [
            _score_operator_packet_candidate(packet, expectation)
            for packet in candidates
        ]
        expectation_pass = any(candidate["passed"] for candidate in scored_candidates)
        if expectation_pass:
            passed += 1
        scored_expectations.append(
            {
                "stage": stage,
                "stage_segment_index": stage_segment_index,
                "is_current_stage": is_current_stage,
                "stage_status": expectation.get("stage_status"),
                "handoff_types": sorted(_expected_handoff_types(expectation)) or None,
                "evidence_levels": sorted(_expected_evidence_levels(expectation))
                or None,
                "matched_candidates": scored_candidates,
                "matched_count": len(scored_candidates),
                "passed": expectation_pass,
            }
        )

    return {
        "expectations": scored_expectations,
        "pass_rate": _ratio(passed, len(expectations)),
    }


def _table_team_score(
    metrics: Sequence[FrameMetrics],
    expectations: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    if not expectations:
        return {"expectations": [], "pass_rate": None}

    team_rows = table_team_summary(metrics)
    passed = 0
    scored_expectations = []
    for expectation in expectations:
        min_tracks = int(
            expectation.get(
                "min_tracks",
                0 if "max_tracks" in expectation else 1,
            )
        )
        max_tracks = expectation.get("max_tracks")
        scored_candidates = [
            _score_table_team_candidate(row, expectation)
            for row in team_rows
        ]
        matched_candidates = [
            candidate for candidate in scored_candidates if candidate["passed"]
        ]
        matched_count = len(matched_candidates)
        count_checks = {
            "min_tracks": matched_count >= min_tracks,
            "max_tracks": (
                max_tracks is None or matched_count <= int(max_tracks)
            ),
        }
        expectation_pass = all(count_checks.values())
        if expectation_pass:
            passed += 1
        scored_expectations.append(
            {
                "team_status": expectation.get("team_status")
                or expectation.get("status"),
                "role": expectation.get("role")
                or expectation.get("dominant_role"),
                "table_team_role": expectation.get("table_team_role"),
                "dominant_stage": expectation.get("dominant_stage")
                or expectation.get("stage"),
                "min_tracks": min_tracks,
                "max_tracks": max_tracks,
                "matched_candidates": matched_candidates,
                "matched_count": matched_count,
                "candidate_count": len(scored_candidates),
                "checks": count_checks,
                "passed": expectation_pass,
            }
        )

    return {
        "expectations": scored_expectations,
        "pass_rate": _ratio(passed, len(expectations)),
    }


def _table_identity_group_score(
    metrics: Sequence[FrameMetrics],
    expectations: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    if not expectations:
        return {"expectations": [], "pass_rate": None}

    groups = table_identity_groups(metrics)
    passed = 0
    scored_expectations = []
    for expectation in expectations:
        min_groups = int(
            expectation.get(
                "min_groups",
                0 if "max_groups" in expectation else 1,
            )
        )
        max_groups = expectation.get("max_groups")
        candidates = [
            group
            for group in groups
            if _identity_group_overlaps_expectation(group, expectation)
        ]
        scored_candidates = [
            _score_table_identity_group_candidate(group, expectation)
            for group in candidates
        ]
        matched_candidates = [
            candidate for candidate in scored_candidates if candidate["passed"]
        ]
        matched_count = len(matched_candidates)
        count_checks = {
            "min_groups": matched_count >= min_groups,
            "max_groups": (
                max_groups is None or matched_count <= int(max_groups)
            ),
        }
        expectation_pass = all(count_checks.values())
        if expectation_pass:
            passed += 1
        scored_expectations.append(
            {
                "role": expectation.get("role"),
                "table_team_role": expectation.get("table_team_role"),
                "dominant_role": expectation.get("dominant_role"),
                "stage": expectation.get("stage")
                or expectation.get("required_stage"),
                "min_groups": min_groups,
                "max_groups": max_groups,
                "matched_candidates": matched_candidates,
                "matched_count": matched_count,
                "candidate_count": len(scored_candidates),
                "checks": count_checks,
                "passed": expectation_pass,
            }
        )

    return {
        "expectations": scored_expectations,
        "pass_rate": _ratio(passed, len(expectations)),
    }


def _event_timeline_score(
    metrics: Sequence[FrameMetrics],
    expectations: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    if not expectations:
        return {"expectations": [], "pass_rate": None}

    events = procedure_event_timeline(metrics)
    passed = 0
    scored_expectations = []
    for expectation in expectations:
        candidates = [
            event
            for event in events
            if _event_matches_expectation(event, expectation)
        ]
        scored_candidates = [
            _score_event_candidate(event, expectation)
            for event in candidates
        ]
        expectation_pass = any(candidate["passed"] for candidate in scored_candidates)
        if expectation_pass:
            passed += 1
        scored_expectations.append(
            {
                "event_type": expectation.get("event_type"),
                "stage": expectation.get("stage"),
                "view": expectation.get("view"),
                "handoff_type": expectation.get("handoff_type"),
                "start_s": expectation.get("start_s"),
                "end_s": expectation.get("end_s"),
                "role": expectation.get("role"),
                "min_tracks": int(expectation.get("min_tracks", 0)),
                "min_table_count": expectation.get("min_table_count"),
                "max_table_count": expectation.get("max_table_count"),
                "tracking_available": expectation.get("tracking_available"),
                "matched_candidates": scored_candidates,
                "matched_count": len(scored_candidates),
                "passed": expectation_pass,
            }
        )

    return {
        "expectations": scored_expectations,
        "pass_rate": _ratio(passed, len(expectations)),
    }


def _roster_snapshot_score(
    metrics: Sequence[FrameMetrics],
    expectations: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    if not expectations:
        return {"expectations": [], "pass_rate": None}

    snapshot_rows = table_roster_snapshots(metrics)
    passed = 0
    scored_expectations = []
    for expectation in expectations:
        snapshot_type = str(expectation.get("snapshot_type", "last_observed"))
        role = expectation.get("role")
        dominant_role = expectation.get("dominant_role")
        min_tracks = int(expectation.get("min_tracks", 1))
        min_table_count = expectation.get("min_table_count")
        max_age_from_clip_end_s = expectation.get("max_age_from_clip_end_s")
        snapshot_matches = [
            row
            for row in snapshot_rows
            if row["snapshot_type"] == snapshot_type
        ]
        role_matches = [
            row
            for row in snapshot_matches
            if _role_expectation_matches(row, role, dominant_role)
        ]
        table_count = max(
            (int(row["table_count"]) for row in snapshot_matches),
            default=0,
        )
        age_values = [
            float(row["age_from_clip_end_s"])
            for row in snapshot_matches
            if row.get("age_from_clip_end_s") is not None
        ]
        age_from_clip_end_s = min(age_values) if age_values else None
        checks = {
            "snapshot_present": bool(snapshot_matches) or min_tracks == 0,
            "min_tracks": len(role_matches) >= min_tracks,
            "min_table_count": (
                min_table_count is None or table_count >= int(min_table_count)
            ),
            "max_age_from_clip_end_s": (
                max_age_from_clip_end_s is None
                or (
                    age_from_clip_end_s is not None
                    and age_from_clip_end_s <= float(max_age_from_clip_end_s)
                )
            ),
        }
        expectation_pass = all(checks.values())
        if expectation_pass:
            passed += 1
        scored_expectations.append(
            {
                "snapshot_type": snapshot_type,
                "role": role,
                "dominant_role": dominant_role,
                "min_tracks": min_tracks,
                "min_table_count": min_table_count,
                "max_age_from_clip_end_s": max_age_from_clip_end_s,
                "matched_rows": role_matches,
                "matched_count": len(role_matches),
                "table_count": table_count,
                "age_from_clip_end_s": (
                    round(age_from_clip_end_s, 3)
                    if age_from_clip_end_s is not None
                    else None
                ),
                "checks": checks,
                "passed": expectation_pass,
            }
        )

    return {
        "expectations": scored_expectations,
        "pass_rate": _ratio(passed, len(expectations)),
    }


def _expected_handoff_types(expectation: Dict[str, Any]) -> set[str]:
    values = expectation.get("handoff_types")
    if values is None and expectation.get("handoff_type") is not None:
        values = [expectation["handoff_type"]]
    if values is None:
        return set()
    if isinstance(values, str):
        return {values}
    return {str(value) for value in values}


def _expected_event_types(expectation: Dict[str, Any]) -> set[str]:
    values = expectation.get("event_types")
    if values is None and expectation.get("event_type") is not None:
        values = [expectation["event_type"]]
    if values is None:
        return set()
    if isinstance(values, str):
        return {values}
    return {str(value) for value in values}


def _expected_evidence_levels(expectation: Dict[str, Any]) -> set[str]:
    values = expectation.get("evidence_levels")
    if values is None and expectation.get("evidence_level") is not None:
        values = [expectation["evidence_level"]]
    if values is None:
        return set()
    if isinstance(values, str):
        return {values}
    return {str(value) for value in values}


def _expected_current_stage(expectation: Dict[str, Any]) -> Optional[bool]:
    if "is_current_stage" in expectation:
        return bool(expectation["is_current_stage"])
    if "current" in expectation:
        return bool(expectation["current"])
    return None


def _expected_text_fragments(values: Any) -> List[str]:
    if values is None:
        return []
    if isinstance(values, str):
        return [values]
    return [str(value) for value in values]


def _stage_evidence_matches_expectation(
    row: Dict[str, Any],
    expectation: Dict[str, Any],
) -> bool:
    stage = expectation.get("stage")
    stage_segment_index = expectation.get("stage_segment_index")
    start_s = float(expectation.get("start_s", float("-inf")))
    end_s = float(expectation.get("end_s", float("inf")))
    return (
        (stage is None or row["stage"] == stage)
        and (
            stage_segment_index is None
            or row["stage_segment_index"] == int(stage_segment_index)
        )
        and row["start_s"] <= end_s
        and row["end_s"] >= start_s
    )


def _score_stage_evidence_candidate(
    row: Dict[str, Any],
    expectation: Dict[str, Any],
) -> Dict[str, Any]:
    expected_levels = _expected_evidence_levels(expectation)
    dominant_signal = expectation.get("dominant_signal")
    min_observable_rate = expectation.get("min_observable_rate")
    max_observable_rate = expectation.get("max_observable_rate")
    min_mean_confidence = expectation.get("min_mean_confidence")
    max_mean_confidence = expectation.get("max_mean_confidence")
    min_room_view_frames = expectation.get("min_room_view_frames")
    max_room_view_frames = expectation.get("max_room_view_frames")
    min_non_room_view_frames = expectation.get("min_non_room_view_frames")
    checks = {
        "evidence_level": (
            not expected_levels or row["evidence_level"] in expected_levels
        ),
        "dominant_signal": (
            dominant_signal is None or row["dominant_signal"] == dominant_signal
        ),
        "min_observable_rate": (
            min_observable_rate is None
            or row["observable_rate"] >= float(min_observable_rate)
        ),
        "max_observable_rate": (
            max_observable_rate is None
            or row["observable_rate"] <= float(max_observable_rate)
        ),
        "min_mean_confidence": (
            min_mean_confidence is None
            or row["mean_confidence"] >= float(min_mean_confidence)
        ),
        "max_mean_confidence": (
            max_mean_confidence is None
            or row["mean_confidence"] <= float(max_mean_confidence)
        ),
        "min_room_view_frames": (
            min_room_view_frames is None
            or row["room_view_frames"] >= int(min_room_view_frames)
        ),
        "max_room_view_frames": (
            max_room_view_frames is None
            or row["room_view_frames"] <= int(max_room_view_frames)
        ),
        "min_non_room_view_frames": (
            min_non_room_view_frames is None
            or row["non_room_view_frames"] >= int(min_non_room_view_frames)
        ),
    }
    return {
        "stage_segment_index": row["stage_segment_index"],
        "stage": row["stage"],
        "stage_label": row["stage_label"],
        "start_s": row["start_s"],
        "end_s": row["end_s"],
        "evidence_level": row["evidence_level"],
        "dominant_signal": row["dominant_signal"],
        "observable_rate": row["observable_rate"],
        "mean_confidence": row["mean_confidence"],
        "room_view_frames": row["room_view_frames"],
        "non_room_view_frames": row["non_room_view_frames"],
        "support_label": row["support_label"],
        "checks": checks,
        "passed": all(checks.values()),
    }


def _stage_row_overlaps_expectation(
    row: Dict[str, Any],
    expectation: Dict[str, Any],
) -> bool:
    start_s = float(expectation.get("start_s", float("-inf")))
    end_s = float(expectation.get("end_s", float("inf")))
    return row["start_s"] <= end_s and row["end_s"] >= start_s


def _stage_coverage_overlaps_expectation(
    row: Dict[str, Any],
    expectation: Dict[str, Any],
) -> bool:
    start_s = float(expectation.get("start_s", float("-inf")))
    end_s = float(expectation.get("end_s", float("inf")))
    return row["first_seen_s"] <= end_s and row["last_seen_s"] >= start_s


def _transition_event_overlaps_expectation(
    event: Dict[str, Any],
    expectation: Dict[str, Any],
) -> bool:
    start_s = float(expectation.get("start_s", float("-inf")))
    end_s = float(expectation.get("end_s", float("inf")))
    return start_s <= event["timestamp_s"] <= end_s


def _score_stage_table_coverage_candidate(
    row: Dict[str, Any],
    expectation: Dict[str, Any],
) -> Dict[str, Any]:
    role = expectation.get("role") or expectation.get("table_team_role")
    dominant_role = expectation.get("dominant_role")
    track_id = expectation.get("track_id")
    canonical_table_id = expectation.get("canonical_table_id")
    required_merged_track_ids = {
        int(track_id) for track_id in expectation.get("required_merged_track_ids", [])
    }
    min_observed_table_frames = expectation.get("min_observed_table_frames")
    max_observed_table_frames = expectation.get("max_observed_table_frames")
    min_coverage_ratio = expectation.get("min_coverage_ratio")
    max_coverage_ratio = expectation.get("max_coverage_ratio")
    min_room_coverage_ratio = expectation.get("min_room_coverage_ratio")
    max_room_coverage_ratio = expectation.get("max_room_coverage_ratio")
    min_tracking_available_rate = expectation.get("min_tracking_available_rate")
    min_table_team_role_confidence = expectation.get(
        "min_table_team_role_confidence"
    )
    min_estimated_table_duration_s = expectation.get(
        "min_estimated_table_duration_s"
    )
    max_estimated_table_duration_s = expectation.get(
        "max_estimated_table_duration_s"
    )
    entered_during_stage = expectation.get("entered_during_stage")
    exited_during_stage = expectation.get("exited_during_stage")
    spans_full_stage = expectation.get("spans_full_stage")
    required_label_text = _expected_text_fragments(
        expectation.get("required_label_text")
    )
    forbidden_label_text = _expected_text_fragments(
        expectation.get("forbidden_label_text")
    )
    label_text = row.get("label", "")
    merged_track_ids = {int(track_id) for track_id in row.get("merged_track_ids", [])}
    checks = {
        "role": role is None or row.get("table_team_role") == role,
        "dominant_role": (
            dominant_role is None or row.get("dominant_role") == dominant_role
        ),
        "track_id": track_id is None or row.get("track_id") == int(track_id),
        "canonical_table_id": (
            canonical_table_id is None
            or row.get("canonical_table_id") == int(canonical_table_id)
        ),
        "required_merged_track_ids": required_merged_track_ids.issubset(
            merged_track_ids
        ),
        "min_observed_table_frames": (
            min_observed_table_frames is None
            or row.get("observed_table_frames", 0)
            >= int(min_observed_table_frames)
        ),
        "max_observed_table_frames": (
            max_observed_table_frames is None
            or row.get("observed_table_frames", 0)
            <= int(max_observed_table_frames)
        ),
        "min_coverage_ratio": (
            min_coverage_ratio is None
            or row.get("coverage_ratio", 0.0) >= float(min_coverage_ratio)
        ),
        "max_coverage_ratio": (
            max_coverage_ratio is None
            or row.get("coverage_ratio", 0.0) <= float(max_coverage_ratio)
        ),
        "min_room_coverage_ratio": (
            min_room_coverage_ratio is None
            or (
                row.get("room_coverage_ratio") is not None
                and row.get("room_coverage_ratio") >= float(min_room_coverage_ratio)
            )
        ),
        "max_room_coverage_ratio": (
            max_room_coverage_ratio is None
            or (
                row.get("room_coverage_ratio") is not None
                and row.get("room_coverage_ratio") <= float(max_room_coverage_ratio)
            )
        ),
        "min_tracking_available_rate": (
            min_tracking_available_rate is None
            or (
                row.get("tracking_available_rate") is not None
                and row.get("tracking_available_rate")
                >= float(min_tracking_available_rate)
            )
        ),
        "min_table_team_role_confidence": (
            min_table_team_role_confidence is None
            or (
                row.get("table_team_role_confidence") is not None
                and row.get("table_team_role_confidence")
                >= float(min_table_team_role_confidence)
            )
        ),
        "min_estimated_table_duration_s": (
            min_estimated_table_duration_s is None
            or row.get("estimated_table_duration_s", 0.0)
            >= float(min_estimated_table_duration_s)
        ),
        "max_estimated_table_duration_s": (
            max_estimated_table_duration_s is None
            or row.get("estimated_table_duration_s", 0.0)
            <= float(max_estimated_table_duration_s)
        ),
        "entered_during_stage": (
            entered_during_stage is None
            or bool(row.get("entered_during_stage")) == bool(entered_during_stage)
        ),
        "exited_during_stage": (
            exited_during_stage is None
            or bool(row.get("exited_during_stage")) == bool(exited_during_stage)
        ),
        "spans_full_stage": (
            spans_full_stage is None
            or bool(row.get("spans_full_stage")) == bool(spans_full_stage)
        ),
        "required_label_text": all(
            fragment in label_text for fragment in required_label_text
        ),
        "forbidden_label_text": not any(
            fragment in label_text for fragment in forbidden_label_text
        ),
    }
    return {
        "stage_segment_index": row["stage_segment_index"],
        "stage": row["stage"],
        "stage_label": row["stage_label"],
        "track_id": row["track_id"],
        "canonical_table_id": row["canonical_table_id"],
        "merged_track_ids": row.get("merged_track_ids", []),
        "dominant_role": row.get("dominant_role"),
        "table_team_role": row.get("table_team_role"),
        "table_team_role_confidence": row.get("table_team_role_confidence"),
        "observed_table_frames": row.get("observed_table_frames"),
        "coverage_ratio": row.get("coverage_ratio"),
        "room_coverage_ratio": row.get("room_coverage_ratio"),
        "tracking_available_rate": row.get("tracking_available_rate"),
        "estimated_table_duration_s": row.get("estimated_table_duration_s"),
        "first_seen_s": row.get("first_seen_s"),
        "last_seen_s": row.get("last_seen_s"),
        "entered_during_stage": row.get("entered_during_stage"),
        "exited_during_stage": row.get("exited_during_stage"),
        "spans_full_stage": row.get("spans_full_stage"),
        "label": row.get("label", ""),
        "checks": checks,
        "passed": all(checks.values()),
    }


def _score_table_transition_candidate(
    event: Dict[str, Any],
    expectation: Dict[str, Any],
) -> Dict[str, Any]:
    role = expectation.get("role") or expectation.get("table_team_role")
    dominant_role = expectation.get("dominant_role")
    track_id = expectation.get("track_id")
    canonical_table_id = expectation.get("canonical_table_id")
    required_merged_track_ids = {
        int(track_id) for track_id in expectation.get("required_merged_track_ids", [])
    }
    min_observed_table_frames = expectation.get("min_observed_table_frames")
    max_observed_table_frames = expectation.get("max_observed_table_frames")
    min_coverage_ratio = expectation.get("min_coverage_ratio")
    max_coverage_ratio = expectation.get("max_coverage_ratio")
    min_room_coverage_ratio = expectation.get("min_room_coverage_ratio")
    max_room_coverage_ratio = expectation.get("max_room_coverage_ratio")
    min_tracking_available_rate = expectation.get("min_tracking_available_rate")
    min_table_team_role_confidence = expectation.get(
        "min_table_team_role_confidence"
    )
    required_label_text = _expected_text_fragments(
        expectation.get("required_label_text")
    )
    forbidden_label_text = _expected_text_fragments(
        expectation.get("forbidden_label_text")
    )
    label_text = event.get("label", "")
    merged_track_ids = {
        int(track_id) for track_id in event.get("merged_track_ids", [])
    }
    checks = {
        "role": role is None or event.get("table_team_role") == role,
        "dominant_role": (
            dominant_role is None or event.get("dominant_role") == dominant_role
        ),
        "track_id": track_id is None or event.get("track_id") == int(track_id),
        "canonical_table_id": (
            canonical_table_id is None
            or event.get("canonical_table_id") == int(canonical_table_id)
        ),
        "required_merged_track_ids": required_merged_track_ids.issubset(
            merged_track_ids
        ),
        "min_observed_table_frames": (
            min_observed_table_frames is None
            or event.get("observed_table_frames", 0)
            >= int(min_observed_table_frames)
        ),
        "max_observed_table_frames": (
            max_observed_table_frames is None
            or event.get("observed_table_frames", 0)
            <= int(max_observed_table_frames)
        ),
        "min_coverage_ratio": (
            min_coverage_ratio is None
            or event.get("coverage_ratio", 0.0) >= float(min_coverage_ratio)
        ),
        "max_coverage_ratio": (
            max_coverage_ratio is None
            or event.get("coverage_ratio", 0.0) <= float(max_coverage_ratio)
        ),
        "min_room_coverage_ratio": (
            min_room_coverage_ratio is None
            or (
                event.get("room_coverage_ratio") is not None
                and event.get("room_coverage_ratio")
                >= float(min_room_coverage_ratio)
            )
        ),
        "max_room_coverage_ratio": (
            max_room_coverage_ratio is None
            or (
                event.get("room_coverage_ratio") is not None
                and event.get("room_coverage_ratio")
                <= float(max_room_coverage_ratio)
            )
        ),
        "min_tracking_available_rate": (
            min_tracking_available_rate is None
            or (
                event.get("tracking_available_rate") is not None
                and event.get("tracking_available_rate")
                >= float(min_tracking_available_rate)
            )
        ),
        "min_table_team_role_confidence": (
            min_table_team_role_confidence is None
            or (
                event.get("table_team_role_confidence") is not None
                and event.get("table_team_role_confidence")
                >= float(min_table_team_role_confidence)
            )
        ),
        "required_label_text": all(
            fragment in label_text for fragment in required_label_text
        ),
        "forbidden_label_text": not any(
            fragment in label_text for fragment in forbidden_label_text
        ),
    }
    return {
        "event_type": event["event_type"],
        "timestamp_s": event["timestamp_s"],
        "frame_index": event["frame_index"],
        "stage_segment_index": event["stage_segment_index"],
        "stage": event["stage"],
        "stage_label": event["stage_label"],
        "track_id": event["track_id"],
        "canonical_table_id": event["canonical_table_id"],
        "merged_track_ids": event.get("merged_track_ids", []),
        "dominant_role": event.get("dominant_role"),
        "table_team_role": event.get("table_team_role"),
        "table_team_role_confidence": event.get("table_team_role_confidence"),
        "observed_table_frames": event.get("observed_table_frames"),
        "coverage_ratio": event.get("coverage_ratio"),
        "room_coverage_ratio": event.get("room_coverage_ratio"),
        "tracking_available_rate": event.get("tracking_available_rate"),
        "label": event.get("label", ""),
        "checks": checks,
        "passed": all(checks.values()),
    }


def _score_stage_roster_candidate(
    row: Dict[str, Any],
    expectation: Dict[str, Any],
) -> Dict[str, Any]:
    expected_handoff_types = _expected_handoff_types(expectation)
    expected_evidence_levels = _expected_evidence_levels(expectation)
    role = expectation.get("role") or expectation.get("table_team_role")
    dominant_role = expectation.get("dominant_role")
    lead_role = expectation.get("lead_role") or expectation.get("lead_table_team_role")
    lead_dominant_role = expectation.get("lead_dominant_role")
    active_roster = row.get("active_table_roster", [])
    active_matches = _roster_role_matches(active_roster, role, dominant_role)
    lead = active_roster[0] if active_roster else None

    min_tracks = expectation.get("min_tracks", expectation.get("min_active_tracks"))
    max_tracks = expectation.get("max_tracks", expectation.get("max_active_tracks"))
    min_peak_table_count = expectation.get("min_peak_table_count")
    max_peak_table_count = expectation.get("max_peak_table_count")
    min_canonical_table_identity_count = expectation.get(
        "min_canonical_table_identity_count"
    )
    max_canonical_table_identity_count = expectation.get(
        "max_canonical_table_identity_count"
    )
    min_continued_tracks = expectation.get("min_continued_tracks")
    min_new_tracks = expectation.get("min_new_tracks")
    min_dropped_tracks = expectation.get("min_dropped_tracks")
    min_within_stage_entry_tracks = expectation.get("min_within_stage_entry_tracks")
    min_within_stage_exit_tracks = expectation.get("min_within_stage_exit_tracks")
    min_tracking_available_rate = expectation.get("min_tracking_available_rate")
    min_observable_rate = expectation.get("min_observable_rate")
    max_observable_rate = expectation.get("max_observable_rate")
    min_mean_confidence = expectation.get("min_mean_confidence")
    max_mean_confidence = expectation.get("max_mean_confidence")
    required_active_track_ids = {
        int(track_id) for track_id in expectation.get("required_active_track_ids", [])
    }
    active_track_ids = {int(track_id) for track_id in row["active_table_track_ids"]}
    checks = {
        "handoff_type": (
            not expected_handoff_types
            or row["handoff_type"] in expected_handoff_types
        ),
        "evidence_level": (
            not expected_evidence_levels
            or row.get("evidence_level") in expected_evidence_levels
        ),
        "min_tracks": min_tracks is None or len(active_matches) >= int(min_tracks),
        "max_tracks": max_tracks is None or len(active_matches) <= int(max_tracks),
        "min_peak_table_count": (
            min_peak_table_count is None
            or row["peak_table_count"] >= int(min_peak_table_count)
        ),
        "max_peak_table_count": (
            max_peak_table_count is None
            or row["peak_table_count"] <= int(max_peak_table_count)
        ),
        "min_canonical_table_identity_count": (
            min_canonical_table_identity_count is None
            or row["canonical_table_identity_count"]
            >= int(min_canonical_table_identity_count)
        ),
        "max_canonical_table_identity_count": (
            max_canonical_table_identity_count is None
            or row["canonical_table_identity_count"]
            <= int(max_canonical_table_identity_count)
        ),
        "min_continued_tracks": (
            min_continued_tracks is None
            or len(row["continued_track_ids"]) >= int(min_continued_tracks)
        ),
        "min_new_tracks": (
            min_new_tracks is None
            or len(row["new_track_ids"]) >= int(min_new_tracks)
        ),
        "min_dropped_tracks": (
            min_dropped_tracks is None
            or len(row["dropped_track_ids"]) >= int(min_dropped_tracks)
        ),
        "min_within_stage_entry_tracks": (
            min_within_stage_entry_tracks is None
            or len(row["within_stage_entry_track_ids"])
            >= int(min_within_stage_entry_tracks)
        ),
        "min_within_stage_exit_tracks": (
            min_within_stage_exit_tracks is None
            or len(row["within_stage_exit_track_ids"])
            >= int(min_within_stage_exit_tracks)
        ),
        "min_tracking_available_rate": (
            min_tracking_available_rate is None
            or (
                row["tracking_available_rate"] is not None
                and row["tracking_available_rate"]
                >= float(min_tracking_available_rate)
            )
        ),
        "min_observable_rate": (
            min_observable_rate is None
            or (
                row["observable_rate"] is not None
                and row["observable_rate"] >= float(min_observable_rate)
            )
        ),
        "max_observable_rate": (
            max_observable_rate is None
            or (
                row["observable_rate"] is not None
                and row["observable_rate"] <= float(max_observable_rate)
            )
        ),
        "min_mean_confidence": (
            min_mean_confidence is None
            or (
                row["mean_confidence"] is not None
                and row["mean_confidence"] >= float(min_mean_confidence)
            )
        ),
        "max_mean_confidence": (
            max_mean_confidence is None
            or (
                row["mean_confidence"] is not None
                and row["mean_confidence"] <= float(max_mean_confidence)
            )
        ),
        "lead_role": (
            lead_role is None
            or (lead is not None and lead.get("table_team_role") == lead_role)
        ),
        "lead_dominant_role": (
            lead_dominant_role is None
            or (lead is not None and lead.get("dominant_role") == lead_dominant_role)
        ),
        "required_active_track_ids": required_active_track_ids.issubset(
            active_track_ids
        ),
    }
    return {
        "stage_segment_index": row["stage_segment_index"],
        "stage": row["stage"],
        "stage_label": row["stage_label"],
        "start_s": row["start_s"],
        "end_s": row["end_s"],
        "handoff_type": row["handoff_type"],
        "evidence_level": row.get("evidence_level"),
        "observable_rate": row.get("observable_rate"),
        "mean_confidence": row.get("mean_confidence"),
        "peak_table_count": row["peak_table_count"],
        "active_table_track_count": row["active_table_track_count"],
        "canonical_table_identity_count": row["canonical_table_identity_count"],
        "lead_track_id": row.get("lead_track_id"),
        "lead_table_team_role": row.get("lead_table_team_role"),
        "active_match_count": len(active_matches),
        "active_table_track_ids": row["active_table_track_ids"],
        "continued_track_ids": row["continued_track_ids"],
        "new_track_ids": row["new_track_ids"],
        "dropped_track_ids": row["dropped_track_ids"],
        "within_stage_entry_track_ids": row["within_stage_entry_track_ids"],
        "within_stage_exit_track_ids": row["within_stage_exit_track_ids"],
        "roster_summary": row["roster_summary"],
        "checks": checks,
        "passed": all(checks.values()),
    }


def _score_procedure_milestone_candidate(
    row: Dict[str, Any],
    expectation: Dict[str, Any],
) -> Dict[str, Any]:
    observed_in_clip = expectation.get("observed_in_clip")
    is_current_observed_stage = expectation.get("is_current_observed_stage")
    milestone_status = expectation.get("milestone_status")
    evidence_level = expectation.get("evidence_level")
    min_observable_rate = expectation.get("min_observable_rate")
    max_observable_rate = expectation.get("max_observable_rate")
    min_mean_confidence = expectation.get("min_mean_confidence")
    max_mean_confidence = expectation.get("max_mean_confidence")
    min_peak_table_count = expectation.get("min_peak_table_count")
    max_peak_table_count = expectation.get("max_peak_table_count")
    min_unique_table_track_count = expectation.get("min_unique_table_track_count")
    max_unique_table_track_count = expectation.get("max_unique_table_track_count")
    min_canonical_table_identity_count = expectation.get(
        "min_canonical_table_identity_count"
    )
    max_canonical_table_identity_count = expectation.get(
        "max_canonical_table_identity_count"
    )
    checks = {
        "observed_in_clip": (
            observed_in_clip is None
            or bool(row["observed_in_clip"]) == bool(observed_in_clip)
        ),
        "is_current_observed_stage": (
            is_current_observed_stage is None
            or bool(row["is_current_observed_stage"])
            == bool(is_current_observed_stage)
        ),
        "milestone_status": (
            milestone_status is None or row["milestone_status"] == milestone_status
        ),
        "evidence_level": (
            evidence_level is None or row["evidence_level"] == evidence_level
        ),
        "min_observable_rate": (
            min_observable_rate is None
            or (
                row["observable_rate"] is not None
                and row["observable_rate"] >= float(min_observable_rate)
            )
        ),
        "max_observable_rate": (
            max_observable_rate is None
            or (
                row["observable_rate"] is not None
                and row["observable_rate"] <= float(max_observable_rate)
            )
        ),
        "min_mean_confidence": (
            min_mean_confidence is None
            or (
                row["mean_confidence"] is not None
                and row["mean_confidence"] >= float(min_mean_confidence)
            )
        ),
        "max_mean_confidence": (
            max_mean_confidence is None
            or (
                row["mean_confidence"] is not None
                and row["mean_confidence"] <= float(max_mean_confidence)
            )
        ),
        "min_peak_table_count": (
            min_peak_table_count is None
            or row["peak_table_count"] >= int(min_peak_table_count)
        ),
        "max_peak_table_count": (
            max_peak_table_count is None
            or row["peak_table_count"] <= int(max_peak_table_count)
        ),
        "min_unique_table_track_count": (
            min_unique_table_track_count is None
            or row["unique_table_track_count"] >= int(min_unique_table_track_count)
        ),
        "max_unique_table_track_count": (
            max_unique_table_track_count is None
            or row["unique_table_track_count"] <= int(max_unique_table_track_count)
        ),
        "min_canonical_table_identity_count": (
            min_canonical_table_identity_count is None
            or row["canonical_table_identity_count"]
            >= int(min_canonical_table_identity_count)
        ),
        "max_canonical_table_identity_count": (
            max_canonical_table_identity_count is None
            or row["canonical_table_identity_count"]
            <= int(max_canonical_table_identity_count)
        ),
    }
    return {
        "stage": row["stage"],
        "stage_label": row["stage_label"],
        "observed_in_clip": row["observed_in_clip"],
        "milestone_status": row["milestone_status"],
        "is_current_observed_stage": row["is_current_observed_stage"],
        "evidence_level": row["evidence_level"],
        "observable_rate": row["observable_rate"],
        "mean_confidence": row["mean_confidence"],
        "peak_table_count": row["peak_table_count"],
        "unique_table_track_count": row["unique_table_track_count"],
        "canonical_table_identity_count": row["canonical_table_identity_count"],
        "label": row["label"],
        "checks": checks,
        "passed": all(checks.values()),
    }


def _score_procedure_status_candidate(
    row: Dict[str, Any],
    expectation: Dict[str, Any],
) -> Dict[str, Any]:
    current_stage = expectation.get("current_stage")
    current_stage_status = expectation.get("current_stage_status")
    current_stage_evidence_status = expectation.get(
        "current_stage_evidence_status"
    )
    has_next_stage_expectation = "next_stage" in expectation
    next_stage = expectation.get("next_stage")
    current_view = expectation.get("current_view")
    tracking_available = expectation.get("tracking_available")
    effective_table_source = expectation.get("effective_table_source")
    evidence_level = expectation.get("evidence_level")
    min_observable_rate = expectation.get("min_observable_rate")
    max_observable_rate = expectation.get("max_observable_rate")
    min_mean_confidence = expectation.get("min_mean_confidence")
    max_mean_confidence = expectation.get("max_mean_confidence")
    min_current_table_count = expectation.get("min_current_table_count")
    max_current_table_count = expectation.get("max_current_table_count")
    min_last_observed_table_count = expectation.get(
        "min_last_observed_table_count"
    )
    max_last_observed_table_count = expectation.get(
        "max_last_observed_table_count"
    )
    max_last_observed_age_from_clip_end_s = expectation.get(
        "max_last_observed_age_from_clip_end_s"
    )
    min_effective_table_count = expectation.get("min_effective_table_count")
    max_effective_table_count = expectation.get("max_effective_table_count")
    max_effective_table_age_from_clip_end_s = expectation.get(
        "max_effective_table_age_from_clip_end_s"
    )
    min_peak_table_count = expectation.get("min_peak_table_count")
    max_peak_table_count = expectation.get("max_peak_table_count")
    required_quality_flags = set(expectation.get("required_quality_flags", []))
    forbidden_quality_flags = set(expectation.get("forbidden_quality_flags", []))
    actual_quality_flags = set(row.get("quality_flag_codes", []))
    checks = {
        "current_stage": (
            current_stage is None or row["current_stage"] == current_stage
        ),
        "current_stage_status": (
            current_stage_status is None
            or row["current_stage_status"] == current_stage_status
        ),
        "current_stage_evidence_status": (
            current_stage_evidence_status is None
            or row["current_stage_evidence_status"] == current_stage_evidence_status
        ),
        "next_stage": (
            not has_next_stage_expectation or row["next_stage"] == next_stage
        ),
        "current_view": current_view is None or row["current_view"] == current_view,
        "tracking_available": (
            tracking_available is None
            or bool(row["tracking_available"]) == bool(tracking_available)
        ),
        "effective_table_source": (
            effective_table_source is None
            or row["effective_table_source"] == effective_table_source
        ),
        "evidence_level": (
            evidence_level is None or row["evidence_level"] == evidence_level
        ),
        "min_observable_rate": (
            min_observable_rate is None
            or (
                row["observable_rate"] is not None
                and row["observable_rate"] >= float(min_observable_rate)
            )
        ),
        "max_observable_rate": (
            max_observable_rate is None
            or (
                row["observable_rate"] is not None
                and row["observable_rate"] <= float(max_observable_rate)
            )
        ),
        "min_mean_confidence": (
            min_mean_confidence is None
            or (
                row["mean_confidence"] is not None
                and row["mean_confidence"] >= float(min_mean_confidence)
            )
        ),
        "max_mean_confidence": (
            max_mean_confidence is None
            or (
                row["mean_confidence"] is not None
                and row["mean_confidence"] <= float(max_mean_confidence)
            )
        ),
        "min_current_table_count": (
            min_current_table_count is None
            or row["current_table_count"] >= int(min_current_table_count)
        ),
        "max_current_table_count": (
            max_current_table_count is None
            or row["current_table_count"] <= int(max_current_table_count)
        ),
        "min_last_observed_table_count": (
            min_last_observed_table_count is None
            or row["last_observed_table_count"]
            >= int(min_last_observed_table_count)
        ),
        "max_last_observed_table_count": (
            max_last_observed_table_count is None
            or row["last_observed_table_count"]
            <= int(max_last_observed_table_count)
        ),
        "max_last_observed_age_from_clip_end_s": (
            max_last_observed_age_from_clip_end_s is None
            or (
                row["last_observed_age_from_clip_end_s"] is not None
                and row["last_observed_age_from_clip_end_s"]
                <= float(max_last_observed_age_from_clip_end_s)
            )
        ),
        "min_effective_table_count": (
            min_effective_table_count is None
            or row["effective_table_count"] >= int(min_effective_table_count)
        ),
        "max_effective_table_count": (
            max_effective_table_count is None
            or row["effective_table_count"] <= int(max_effective_table_count)
        ),
        "max_effective_table_age_from_clip_end_s": (
            max_effective_table_age_from_clip_end_s is None
            or (
                row["effective_table_age_from_clip_end_s"] is not None
                and row["effective_table_age_from_clip_end_s"]
                <= float(max_effective_table_age_from_clip_end_s)
            )
        ),
        "min_peak_table_count": (
            min_peak_table_count is None
            or row["peak_table_count"] >= int(min_peak_table_count)
        ),
        "max_peak_table_count": (
            max_peak_table_count is None
            or row["peak_table_count"] <= int(max_peak_table_count)
        ),
        "required_quality_flags": required_quality_flags.issubset(
            actual_quality_flags
        ),
        "forbidden_quality_flags": not (
            forbidden_quality_flags & actual_quality_flags
        ),
    }
    return {
        "current_stage": row["current_stage"],
        "current_stage_status": row["current_stage_status"],
        "current_stage_evidence_status": row["current_stage_evidence_status"],
        "current_stage_evidence_label": row["current_stage_evidence_label"],
        "next_stage": row["next_stage"],
        "current_view": row["current_view"],
        "tracking_available": row["tracking_available"],
        "effective_table_source": row["effective_table_source"],
        "effective_table_count": row["effective_table_count"],
        "effective_table_age_from_clip_end_s": row[
            "effective_table_age_from_clip_end_s"
        ],
        "evidence_level": row["evidence_level"],
        "observable_rate": row["observable_rate"],
        "mean_confidence": row["mean_confidence"],
        "current_table_count": row["current_table_count"],
        "last_observed_table_count": row["last_observed_table_count"],
        "last_observed_age_from_clip_end_s": row[
            "last_observed_age_from_clip_end_s"
        ],
        "peak_table_count": row["peak_table_count"],
        "quality_flag_codes": row["quality_flag_codes"],
        "operator_summary": row["operator_summary"],
        "checks": checks,
        "passed": all(checks.values()),
    }


def _score_operator_packet_candidate(
    row: Dict[str, Any],
    expectation: Dict[str, Any],
) -> Dict[str, Any]:
    stage_status = expectation.get("stage_status")
    stage_evidence_status = expectation.get("stage_evidence_status")
    next_stage_expected = "next_stage" in expectation
    next_stage = expectation.get("next_stage")
    expected_handoff_types = _expected_handoff_types(expectation)
    expected_evidence_levels = _expected_evidence_levels(expectation)
    effective_table_source = expectation.get("effective_table_source")
    lead_role = expectation.get("lead_role") or expectation.get("lead_table_team_role")
    min_peak_table_count = expectation.get("min_peak_table_count")
    max_peak_table_count = expectation.get("max_peak_table_count")
    min_active_tracks = expectation.get(
        "min_active_tracks",
        expectation.get("min_active_table_track_count"),
    )
    max_active_tracks = expectation.get(
        "max_active_tracks",
        expectation.get("max_active_table_track_count"),
    )
    min_canonical_table_identity_count = expectation.get(
        "min_canonical_table_identity_count"
    )
    max_canonical_table_identity_count = expectation.get(
        "max_canonical_table_identity_count"
    )
    min_continued_tracks = expectation.get("min_continued_tracks")
    min_new_tracks = expectation.get("min_new_tracks")
    min_dropped_tracks = expectation.get("min_dropped_tracks")
    min_effective_table_count = expectation.get("min_effective_table_count")
    max_effective_table_count = expectation.get("max_effective_table_count")
    min_tracking_available_rate = expectation.get("min_tracking_available_rate")
    min_observable_rate = expectation.get("min_observable_rate")
    max_observable_rate = expectation.get("max_observable_rate")
    min_mean_confidence = expectation.get("min_mean_confidence")
    max_mean_confidence = expectation.get("max_mean_confidence")
    required_active_track_ids = {
        int(track_id) for track_id in expectation.get("required_active_track_ids", [])
    }
    required_effective_track_ids = {
        int(track_id)
        for track_id in expectation.get("required_effective_track_ids", [])
    }
    required_quality_flags = set(expectation.get("required_quality_flags", []))
    forbidden_quality_flags = set(expectation.get("forbidden_quality_flags", []))
    actual_quality_flags = set(row.get("quality_flag_codes", []))
    required_packet_text = _expected_text_fragments(
        expectation.get("required_packet_text")
    )
    forbidden_packet_text = _expected_text_fragments(
        expectation.get("forbidden_packet_text")
    )
    packet_text = row.get("operator_packet", "")
    active_track_ids = {
        int(track_id) for track_id in row.get("active_table_track_ids", [])
    }
    effective_track_ids = {
        int(track_id) for track_id in row.get("effective_table_track_ids", [])
    }
    checks = {
        "stage_status": stage_status is None or row.get("stage_status") == stage_status,
        "stage_evidence_status": (
            stage_evidence_status is None
            or row.get("stage_evidence_status") == stage_evidence_status
        ),
        "next_stage": (
            not next_stage_expected or row.get("next_stage") == next_stage
        ),
        "handoff_type": (
            not expected_handoff_types
            or row.get("handoff_type") in expected_handoff_types
        ),
        "evidence_level": (
            not expected_evidence_levels
            or row.get("evidence_level") in expected_evidence_levels
        ),
        "lead_role": (
            lead_role is None or row.get("lead_table_team_role") == lead_role
        ),
        "effective_table_source": (
            effective_table_source is None
            or row.get("effective_table_source") == effective_table_source
        ),
        "min_peak_table_count": (
            min_peak_table_count is None
            or row.get("peak_table_count", 0) >= int(min_peak_table_count)
        ),
        "max_peak_table_count": (
            max_peak_table_count is None
            or row.get("peak_table_count", 0) <= int(max_peak_table_count)
        ),
        "min_active_tracks": (
            min_active_tracks is None
            or row.get("active_table_track_count", 0) >= int(min_active_tracks)
        ),
        "max_active_tracks": (
            max_active_tracks is None
            or row.get("active_table_track_count", 0) <= int(max_active_tracks)
        ),
        "min_canonical_table_identity_count": (
            min_canonical_table_identity_count is None
            or row.get("canonical_table_identity_count", 0)
            >= int(min_canonical_table_identity_count)
        ),
        "max_canonical_table_identity_count": (
            max_canonical_table_identity_count is None
            or row.get("canonical_table_identity_count", 0)
            <= int(max_canonical_table_identity_count)
        ),
        "min_continued_tracks": (
            min_continued_tracks is None
            or len(row.get("continued_track_ids", [])) >= int(min_continued_tracks)
        ),
        "min_new_tracks": (
            min_new_tracks is None
            or len(row.get("new_track_ids", [])) >= int(min_new_tracks)
        ),
        "min_dropped_tracks": (
            min_dropped_tracks is None
            or len(row.get("dropped_track_ids", [])) >= int(min_dropped_tracks)
        ),
        "min_effective_table_count": (
            min_effective_table_count is None
            or (
                row.get("effective_table_count") is not None
                and row.get("effective_table_count", 0)
                >= int(min_effective_table_count)
            )
        ),
        "max_effective_table_count": (
            max_effective_table_count is None
            or (
                row.get("effective_table_count") is not None
                and row.get("effective_table_count", 0)
                <= int(max_effective_table_count)
            )
        ),
        "min_tracking_available_rate": (
            min_tracking_available_rate is None
            or (
                row.get("tracking_available_rate") is not None
                and row.get("tracking_available_rate")
                >= float(min_tracking_available_rate)
            )
        ),
        "min_observable_rate": (
            min_observable_rate is None
            or (
                row.get("observable_rate") is not None
                and row.get("observable_rate") >= float(min_observable_rate)
            )
        ),
        "max_observable_rate": (
            max_observable_rate is None
            or (
                row.get("observable_rate") is not None
                and row.get("observable_rate") <= float(max_observable_rate)
            )
        ),
        "min_mean_confidence": (
            min_mean_confidence is None
            or (
                row.get("mean_confidence") is not None
                and row.get("mean_confidence") >= float(min_mean_confidence)
            )
        ),
        "max_mean_confidence": (
            max_mean_confidence is None
            or (
                row.get("mean_confidence") is not None
                and row.get("mean_confidence") <= float(max_mean_confidence)
            )
        ),
        "required_active_track_ids": required_active_track_ids.issubset(
            active_track_ids
        ),
        "required_effective_track_ids": required_effective_track_ids.issubset(
            effective_track_ids
        ),
        "required_quality_flags": required_quality_flags.issubset(
            actual_quality_flags
        ),
        "forbidden_quality_flags": not (
            actual_quality_flags & forbidden_quality_flags
        ),
        "required_packet_text": all(
            fragment in packet_text for fragment in required_packet_text
        ),
        "forbidden_packet_text": not any(
            fragment in packet_text for fragment in forbidden_packet_text
        ),
    }
    return {
        "stage_segment_index": row["stage_segment_index"],
        "stage": row["stage"],
        "stage_label": row["stage_label"],
        "stage_status": row.get("stage_status"),
        "stage_evidence_status": row.get("stage_evidence_status"),
        "stage_evidence_label": row.get("stage_evidence_label"),
        "is_current_stage": row.get("is_current_stage"),
        "start_s": row["start_s"],
        "end_s": row["end_s"],
        "evidence_level": row.get("evidence_level"),
        "handoff_type": row.get("handoff_type"),
        "peak_table_count": row.get("peak_table_count", 0),
        "active_table_track_count": row.get("active_table_track_count", 0),
        "canonical_table_identity_count": row.get(
            "canonical_table_identity_count",
            0,
        ),
        "effective_table_source": row.get("effective_table_source"),
        "effective_table_count": row.get("effective_table_count"),
        "active_table_track_ids": row.get("active_table_track_ids", []),
        "effective_table_track_ids": row.get("effective_table_track_ids", []),
        "new_track_ids": row.get("new_track_ids", []),
        "dropped_track_ids": row.get("dropped_track_ids", []),
        "quality_flag_codes": row.get("quality_flag_codes", []),
        "operator_packet": row.get("operator_packet", ""),
        "checks": checks,
        "passed": all(checks.values()),
    }


def _score_table_team_candidate(
    row: Dict[str, Any],
    expectation: Dict[str, Any],
) -> Dict[str, Any]:
    track_id = expectation.get("track_id")
    team_status = expectation.get("team_status") or expectation.get("status")
    dominant_role = expectation.get("dominant_role") or expectation.get("role")
    table_team_role = expectation.get("table_team_role")
    dominant_stage = expectation.get("dominant_stage") or expectation.get("stage")
    min_frames_seen = expectation.get("min_frames_seen")
    min_observed_table_frames = expectation.get("min_observed_table_frames")
    min_table_frames = expectation.get("min_table_frames")
    min_table_presence_ratio = expectation.get("min_table_presence_ratio")
    max_table_presence_ratio = expectation.get("max_table_presence_ratio")
    min_interval_count = expectation.get("min_interval_count")
    max_interval_count = expectation.get("max_interval_count")
    max_age = expectation.get(
        "max_last_seen_age_from_clip_end_s",
        expectation.get("max_age_from_clip_end_s"),
    )
    checks = {
        "track_id": track_id is None or row["track_id"] == int(track_id),
        "team_status": (
            team_status is None or row["team_status"] == team_status
        ),
        "dominant_role": (
            dominant_role is None or row["dominant_role"] == dominant_role
        ),
        "table_team_role": (
            table_team_role is None or row["table_team_role"] == table_team_role
        ),
        "dominant_stage": (
            dominant_stage is None or row["dominant_stage"] == dominant_stage
        ),
        "min_frames_seen": (
            min_frames_seen is None
            or row["frames_seen"] >= int(min_frames_seen)
        ),
        "min_observed_table_frames": (
            min_observed_table_frames is None
            or row["observed_table_frames"] >= int(min_observed_table_frames)
        ),
        "min_table_frames": (
            min_table_frames is None
            or row["table_frames"] >= int(min_table_frames)
        ),
        "min_table_presence_ratio": (
            min_table_presence_ratio is None
            or row["table_presence_ratio"] >= float(min_table_presence_ratio)
        ),
        "max_table_presence_ratio": (
            max_table_presence_ratio is None
            or row["table_presence_ratio"] <= float(max_table_presence_ratio)
        ),
        "min_interval_count": (
            min_interval_count is None
            or row["interval_count"] >= int(min_interval_count)
        ),
        "max_interval_count": (
            max_interval_count is None
            or row["interval_count"] <= int(max_interval_count)
        ),
        "max_last_seen_age_from_clip_end_s": (
            max_age is None
            or (
                row["age_from_clip_end_s"] is not None
                and row["age_from_clip_end_s"] <= float(max_age)
            )
        ),
        "require_in_current_table_roster": _membership_expectation_matches(
            row,
            expectation,
            "require_in_current_table_roster",
            "is_current_table_member",
        ),
        "require_in_effective_table_roster": _membership_expectation_matches(
            row,
            expectation,
            "require_in_effective_table_roster",
            "is_effective_table_member",
        ),
        "require_in_last_table_roster": _membership_expectation_matches(
            row,
            expectation,
            "require_in_last_table_roster",
            "is_last_observed_table_member",
        ),
        "require_in_peak_table_roster": _membership_expectation_matches(
            row,
            expectation,
            "require_in_peak_table_roster",
            "is_peak_table_member",
        ),
    }
    return {
        "track_id": row["track_id"],
        "team_status": row["team_status"],
        "dominant_role": row["dominant_role"],
        "table_team_role": row["table_team_role"],
        "table_team_role_confidence": row["table_team_role_confidence"],
        "dominant_stage": row["dominant_stage"],
        "is_current_table_member": row["is_current_table_member"],
        "is_effective_table_member": row["is_effective_table_member"],
        "is_last_observed_table_member": row["is_last_observed_table_member"],
        "is_peak_table_member": row["is_peak_table_member"],
        "age_from_clip_end_s": row["age_from_clip_end_s"],
        "frames_seen": row["frames_seen"],
        "observed_table_frames": row["observed_table_frames"],
        "table_frames": row["table_frames"],
        "table_presence_ratio": row["table_presence_ratio"],
        "interval_count": row["interval_count"],
        "label": row["label"],
        "checks": checks,
        "passed": all(checks.values()),
    }


def _identity_group_overlaps_expectation(
    group: Dict[str, Any],
    expectation: Dict[str, Any],
) -> bool:
    start_s = float(expectation.get("start_s", float("-inf")))
    end_s = float(expectation.get("end_s", float("inf")))
    return group["first_seen_s"] <= end_s and group["last_seen_s"] >= start_s


def _score_table_identity_group_candidate(
    group: Dict[str, Any],
    expectation: Dict[str, Any],
) -> Dict[str, Any]:
    track_id = expectation.get("track_id")
    canonical_table_id = expectation.get("canonical_table_id")
    role = expectation.get("role") or expectation.get("table_team_role")
    dominant_role = expectation.get("dominant_role")
    required_merged_track_ids = {
        int(track_id) for track_id in expectation.get("required_merged_track_ids", [])
    }
    required_stage = expectation.get("stage") or expectation.get("required_stage")
    min_stage_frames = expectation.get("min_stage_frames")
    max_stage_frames = expectation.get("max_stage_frames")
    min_merged_track_count = expectation.get("min_merged_track_count")
    max_merged_track_count = expectation.get("max_merged_track_count")
    min_observed_table_frames = expectation.get("min_observed_table_frames")
    max_observed_table_frames = expectation.get("max_observed_table_frames")
    min_table_team_role_confidence = expectation.get(
        "min_table_team_role_confidence"
    )
    min_first_seen_s = expectation.get("min_first_seen_s")
    max_first_seen_s = expectation.get("max_first_seen_s")
    min_last_seen_s = expectation.get("min_last_seen_s")
    max_last_seen_s = expectation.get("max_last_seen_s")
    merged_track_ids = {
        int(track_id) for track_id in group.get("merged_track_ids", [])
    }
    stage_counts = group.get("stage_counts", {})
    stage_frames = (
        int(stage_counts.get(required_stage, 0))
        if required_stage is not None
        else None
    )
    checks = {
        "track_id": track_id is None or group.get("track_id") == int(track_id),
        "canonical_table_id": (
            canonical_table_id is None
            or group.get("canonical_table_id") == int(canonical_table_id)
        ),
        "table_team_role": role is None or group.get("table_team_role") == role,
        "dominant_role": (
            dominant_role is None or group.get("dominant_role") == dominant_role
        ),
        "required_merged_track_ids": required_merged_track_ids.issubset(
            merged_track_ids
        ),
        "min_merged_track_count": (
            min_merged_track_count is None
            or len(merged_track_ids) >= int(min_merged_track_count)
        ),
        "max_merged_track_count": (
            max_merged_track_count is None
            or len(merged_track_ids) <= int(max_merged_track_count)
        ),
        "min_observed_table_frames": (
            min_observed_table_frames is None
            or group.get("observed_table_frames", 0)
            >= int(min_observed_table_frames)
        ),
        "max_observed_table_frames": (
            max_observed_table_frames is None
            or group.get("observed_table_frames", 0)
            <= int(max_observed_table_frames)
        ),
        "min_table_team_role_confidence": (
            min_table_team_role_confidence is None
            or group.get("table_team_role_confidence", 0.0)
            >= float(min_table_team_role_confidence)
        ),
        "required_stage": required_stage is None or stage_frames > 0,
        "min_stage_frames": (
            min_stage_frames is None
            or (stage_frames is not None and stage_frames >= int(min_stage_frames))
        ),
        "max_stage_frames": (
            max_stage_frames is None
            or (stage_frames is not None and stage_frames <= int(max_stage_frames))
        ),
        "min_first_seen_s": (
            min_first_seen_s is None
            or group.get("first_seen_s") >= float(min_first_seen_s)
        ),
        "max_first_seen_s": (
            max_first_seen_s is None
            or group.get("first_seen_s") <= float(max_first_seen_s)
        ),
        "min_last_seen_s": (
            min_last_seen_s is None
            or group.get("last_seen_s") >= float(min_last_seen_s)
        ),
        "max_last_seen_s": (
            max_last_seen_s is None
            or group.get("last_seen_s") <= float(max_last_seen_s)
        ),
    }
    return {
        "canonical_table_id": group.get("canonical_table_id"),
        "track_id": group.get("track_id"),
        "merged_track_ids": group.get("merged_track_ids", []),
        "dominant_role": group.get("dominant_role"),
        "table_team_role": group.get("table_team_role"),
        "table_team_role_confidence": group.get("table_team_role_confidence"),
        "first_seen_s": group.get("first_seen_s"),
        "last_seen_s": group.get("last_seen_s"),
        "observed_table_frames": group.get("observed_table_frames", 0),
        "stage_counts": stage_counts,
        "stage_frames": stage_frames,
        "checks": checks,
        "passed": all(checks.values()),
    }


def _membership_expectation_matches(
    row: Dict[str, Any],
    expectation: Dict[str, Any],
    expectation_key: str,
    row_key: str,
) -> bool:
    if expectation_key not in expectation:
        return True
    return bool(row[row_key]) == bool(expectation[expectation_key])


def _event_matches_expectation(
    event: Dict[str, Any],
    expectation: Dict[str, Any],
) -> bool:
    event_type = expectation.get("event_type")
    stage = expectation.get("stage")
    view = expectation.get("view")
    handoff_type = expectation.get("handoff_type")
    start_s = float(expectation.get("start_s", float("-inf")))
    end_s = float(expectation.get("end_s", float("inf")))
    timestamp_s = event.get("timestamp_s")
    return (
        (event_type is None or event["event_type"] == event_type)
        and (stage is None or event.get("stage") == stage)
        and (view is None or event.get("view") == view)
        and (handoff_type is None or event.get("handoff_type") == handoff_type)
        and timestamp_s is not None
        and start_s <= float(timestamp_s) <= end_s
    )


def _score_event_candidate(
    event: Dict[str, Any],
    expectation: Dict[str, Any],
) -> Dict[str, Any]:
    role = expectation.get("role")
    dominant_role = expectation.get("dominant_role")
    min_tracks = int(expectation.get("min_tracks", 0))
    min_table_count = expectation.get("min_table_count")
    max_table_count = expectation.get("max_table_count")
    tracking_available = expectation.get("tracking_available")
    roster_matches = _roster_role_matches(event.get("roster", []), role, dominant_role)
    checks = {
        "min_tracks": len(roster_matches) >= min_tracks,
        "min_table_count": (
            min_table_count is None
            or int(event.get("table_count", 0)) >= int(min_table_count)
        ),
        "max_table_count": (
            max_table_count is None
            or int(event.get("table_count", 0)) <= int(max_table_count)
        ),
        "tracking_available": (
            tracking_available is None
            or bool(event.get("tracking_available")) == bool(tracking_available)
        ),
    }
    return {
        "event_type": event["event_type"],
        "timestamp_s": event["timestamp_s"],
        "frame_index": event.get("frame_index"),
        "stage": event.get("stage"),
        "stage_label": event.get("stage_label"),
        "view": event.get("view"),
        "handoff_type": event.get("handoff_type"),
        "table_count": event.get("table_count", 0),
        "track_id": event.get("track_id"),
        "dominant_role": event.get("dominant_role"),
        "table_team_role": event.get("table_team_role"),
        "table_team_role_confidence": event.get("table_team_role_confidence"),
        "label": event.get("label"),
        "roster_matches": roster_matches,
        "roster_match_count": len(roster_matches),
        "checks": checks,
        "passed": all(checks.values()),
    }


def _score_handoff_candidate(
    handoff: Dict[str, Any],
    role: Optional[str],
    dominant_role: Optional[str],
    lead_role: Optional[str],
    lead_dominant_role: Optional[str],
    expected_handoff_types: set[str],
    min_active_tracks: int,
    min_new_tracks: int,
    min_continued_tracks: int,
    min_dropped_tracks: int,
    min_lead_observed_table_frames: int,
    min_tracking_available_rate: Optional[float],
) -> Dict[str, Any]:
    active_matches = _roster_role_matches(
        handoff["active_table_roster"],
        role,
        dominant_role,
    )
    new_matches = _roster_role_matches(handoff["new_table_roster"], role, dominant_role)
    continued_matches = _roster_role_matches(
        handoff["continued_table_roster"],
        role,
        dominant_role,
    )
    dropped_matches = _roster_role_matches(
        handoff["dropped_table_roster"],
        role,
        dominant_role,
    )
    checks = {
        "handoff_type": (
            not expected_handoff_types
            or handoff["handoff_type"] in expected_handoff_types
        ),
        "min_active_tracks": len(active_matches) >= min_active_tracks,
        "min_new_tracks": len(new_matches) >= min_new_tracks,
        "min_continued_tracks": len(continued_matches) >= min_continued_tracks,
        "min_dropped_tracks": len(dropped_matches) >= min_dropped_tracks,
        "lead_role": lead_role is None or handoff["lead_role"] == lead_role,
        "lead_dominant_role": (
            lead_dominant_role is None
            or handoff["lead_dominant_role"] == lead_dominant_role
        ),
        "min_lead_observed_table_frames": (
            handoff["lead_observed_table_frames"] >= min_lead_observed_table_frames
        ),
        "min_tracking_available_rate": (
            min_tracking_available_rate is None
            or (
                handoff["tracking_available_rate"] is not None
                and handoff["tracking_available_rate"]
                >= float(min_tracking_available_rate)
            )
        ),
    }
    return {
        "stage_segment_index": handoff["stage_segment_index"],
        "stage": handoff["stage"],
        "stage_label": handoff["stage_label"],
        "handoff_type": handoff["handoff_type"],
        "lead_track_id": handoff["lead_track_id"],
        "lead_role": handoff["lead_role"],
        "lead_dominant_role": handoff["lead_dominant_role"],
        "lead_table_team_role": handoff["lead_table_team_role"],
        "lead_table_team_role_confidence": handoff[
            "lead_table_team_role_confidence"
        ],
        "lead_observed_table_frames": handoff["lead_observed_table_frames"],
        "active_matches": active_matches,
        "new_matches": new_matches,
        "continued_matches": continued_matches,
        "dropped_matches": dropped_matches,
        "active_match_count": len(active_matches),
        "new_match_count": len(new_matches),
        "continued_match_count": len(continued_matches),
        "dropped_match_count": len(dropped_matches),
        "tracking_available_rate": handoff["tracking_available_rate"],
        "checks": checks,
        "passed": all(checks.values()),
    }


def _roster_role_matches(
    roster: Sequence[Dict[str, Any]],
    role: Optional[str],
    dominant_role: Optional[str] = None,
) -> List[Dict[str, Any]]:
    return [
        item
        for item in roster
        if _role_expectation_matches(item, role, dominant_role)
    ]


def _role_expectation_matches(
    row: Dict[str, Any],
    role: Optional[str],
    dominant_role: Optional[str] = None,
) -> bool:
    return (
        (role is None or row.get("table_team_role", row.get("dominant_role")) == role)
        and (dominant_role is None or row.get("dominant_role") == dominant_role)
    )


def _handoff_overlaps_expectation(
    handoff: Dict[str, Any],
    expectation: Dict[str, Any],
) -> bool:
    start_s = float(expectation.get("start_s", float("-inf")))
    end_s = float(expectation.get("end_s", float("inf")))
    return handoff["start_s"] <= end_s and handoff["end_s"] >= start_s


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
        detections_by_id = {
            detection.track_id: detection for detection in metric.detections
        }
        for track_id in state.table_track_ids:
            summary = state.track_role_summaries.get(track_id)
            detection = detections_by_id.get(track_id)
            observations.setdefault(track_id, []).append(
                {
                    "frame_index": metric.frame_index,
                    "timestamp_s": metric.timestamp_s,
                    "clip_timestamp_s": metric.clip_timestamp_s,
                    "stage": state.stage,
                    "role": summary.dominant_role if summary else "unassigned",
                    "cx": detection.centroid[0] if detection else None,
                    "cy": detection.centroid[1] if detection else None,
                    "area": detection.area if detection else None,
                }
            )
    return observations


def _table_identity_map(
    metrics: Sequence[FrameMetrics],
    max_gap_frames: int = 90,
    max_gap_s: float = 2.5,
    max_centroid_distance_px: float = 140.0,
    max_area_ratio: float = 3.0,
) -> tuple[Dict[int, Dict[str, Any]], List[Dict[str, Any]]]:
    intervals = table_presence_intervals(metrics, min_observed_table_frames=1)
    groups: List[Dict[str, Any]] = []
    raw_to_group: Dict[int, Dict[str, Any]] = {}

    for interval in sorted(
        intervals,
        key=lambda item: (item["start_s"], item["start_frame"], item["track_id"]),
    ):
        track_id = int(interval["track_id"])
        group = raw_to_group.get(track_id)
        if group is None:
            group = _best_identity_group(
                groups,
                interval,
                max_gap_frames=max_gap_frames,
                max_gap_s=max_gap_s,
                max_centroid_distance_px=max_centroid_distance_px,
                max_area_ratio=max_area_ratio,
            )
        if group is None:
            group = {
                "raw_track_ids": set(),
                "first_frame": interval["start_frame"],
                "last_frame": interval["end_frame"],
                "first_s": interval["start_s"],
                "last_s": interval["end_s"],
                "first_clip_s": interval["clip_start_s"],
                "last_clip_s": interval["clip_end_s"],
                "last_cx": interval.get("last_cx"),
                "last_cy": interval.get("last_cy"),
                "last_area": interval.get("last_area"),
                "observed_table_frames": 0,
                "role_counts": {},
                "stage_counts": {},
            }
            groups.append(group)

        _merge_identity_interval(group, interval)
        raw_to_group[track_id] = group

    groups.sort(
        key=lambda item: (
            item["first_s"],
            min(item["raw_track_ids"]) if item["raw_track_ids"] else 0,
        )
    )
    identity_map: Dict[int, Dict[str, Any]] = {}
    public_groups: List[Dict[str, Any]] = []
    for index, group in enumerate(groups, start=1):
        merged_track_ids = sorted(int(track_id) for track_id in group["raw_track_ids"])
        dominant_role = _dominant_role_from_counts(group["role_counts"])
        table_team_role, table_team_role_confidence = _table_team_role(
            group["role_counts"],
            dominant_role,
            int(group["observed_table_frames"]),
        )
        public_group = {
            "canonical_table_id": index,
            "track_id": merged_track_ids[0] if merged_track_ids else None,
            "merged_track_ids": merged_track_ids,
            "dominant_role": dominant_role,
            "table_team_role": table_team_role,
            "table_team_role_confidence": table_team_role_confidence,
            "first_seen_frame": group["first_frame"],
            "last_seen_frame": group["last_frame"],
            "first_seen_s": group["first_s"],
            "last_seen_s": group["last_s"],
            "first_seen_clip_s": group["first_clip_s"],
            "last_seen_clip_s": group["last_clip_s"],
            "observed_table_frames": int(group["observed_table_frames"]),
            "role_counts": dict(sorted(group["role_counts"].items())),
            "stage_counts": dict(sorted(group["stage_counts"].items())),
        }
        public_groups.append(public_group)
        for raw_track_id in merged_track_ids:
            identity_map[raw_track_id] = public_group
    return identity_map, public_groups


def _best_identity_group(
    groups: Sequence[Dict[str, Any]],
    interval: Dict[str, Any],
    max_gap_frames: int,
    max_gap_s: float,
    max_centroid_distance_px: float,
    max_area_ratio: float,
) -> Optional[Dict[str, Any]]:
    candidates = [
        group
        for group in groups
        if _identity_group_can_accept(
            group,
            interval,
            max_gap_frames=max_gap_frames,
            max_gap_s=max_gap_s,
            max_centroid_distance_px=max_centroid_distance_px,
            max_area_ratio=max_area_ratio,
        )
    ]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda group: (
            interval["start_s"] - group["last_s"],
            _identity_centroid_distance(group, interval) or 0.0,
            min(group["raw_track_ids"]) if group["raw_track_ids"] else 0,
        ),
    )


def _identity_group_can_accept(
    group: Dict[str, Any],
    interval: Dict[str, Any],
    max_gap_frames: int,
    max_gap_s: float,
    max_centroid_distance_px: float,
    max_area_ratio: float,
) -> bool:
    frame_gap = int(interval["start_frame"]) - int(group["last_frame"])
    time_gap = float(interval["start_s"]) - float(group["last_s"])
    if frame_gap <= 0 or frame_gap > max_gap_frames:
        return False
    if time_gap < 0 or time_gap > max_gap_s:
        return False
    if not _identity_roles_compatible(group, interval):
        return False

    distance = _identity_centroid_distance(group, interval)
    if distance is None or distance > max_centroid_distance_px:
        return False

    area_ratio = _identity_area_ratio(group.get("last_area"), interval.get("first_area"))
    return area_ratio is None or area_ratio <= max_area_ratio


def _identity_roles_compatible(
    group: Dict[str, Any],
    interval: Dict[str, Any],
) -> bool:
    group_role = _dominant_role_from_counts(group.get("role_counts", {}))
    interval_role = interval.get("table_team_role") or interval.get("dominant_role")
    if group_role == interval_role:
        return True
    table_roles = {"access_operator", "table_operator"}
    return group_role in table_roles and interval_role in table_roles


def _identity_centroid_distance(
    group: Dict[str, Any],
    interval: Dict[str, Any],
) -> Optional[float]:
    if (
        group.get("last_cx") is None
        or group.get("last_cy") is None
        or interval.get("first_cx") is None
        or interval.get("first_cy") is None
    ):
        return None
    dx = float(group["last_cx"]) - float(interval["first_cx"])
    dy = float(group["last_cy"]) - float(interval["first_cy"])
    return (dx * dx + dy * dy) ** 0.5


def _identity_area_ratio(first: Any, second: Any) -> Optional[float]:
    if first is None or second is None:
        return None
    first_value = max(float(first), 1.0)
    second_value = max(float(second), 1.0)
    return max(first_value, second_value) / min(first_value, second_value)


def _merge_identity_interval(
    group: Dict[str, Any],
    interval: Dict[str, Any],
) -> None:
    group["raw_track_ids"].add(int(interval["track_id"]))
    group["first_frame"] = min(group["first_frame"], interval["start_frame"])
    group["last_frame"] = max(group["last_frame"], interval["end_frame"])
    group["first_s"] = min(group["first_s"], interval["start_s"])
    group["last_s"] = max(group["last_s"], interval["end_s"])
    group["first_clip_s"] = min(group["first_clip_s"], interval["clip_start_s"])
    group["last_clip_s"] = max(group["last_clip_s"], interval["clip_end_s"])
    group["last_cx"] = interval.get("last_cx")
    group["last_cy"] = interval.get("last_cy")
    group["last_area"] = interval.get("last_area")
    group["observed_table_frames"] += int(interval["observed_table_frames"])
    _merge_counts(group["role_counts"], interval.get("role_counts", {}))
    _merge_counts(group["stage_counts"], interval.get("stage_counts", {}))


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
    table_team_role, table_team_role_confidence = _table_team_role(
        role_counts,
        dominant_role,
        len(observations),
    )
    dominant_stage = _dominant_from_counts(stage_counts)
    duration_s = max(0.0, end["timestamp_s"] - start["timestamp_s"] + sample_period_s)
    return {
        "track_id": track_id,
        "dominant_role": dominant_role,
        "table_team_role": table_team_role,
        "table_team_role_confidence": table_team_role_confidence,
        "dominant_stage": dominant_stage,
        "start_frame": start["frame_index"],
        "end_frame": end["frame_index"],
        "start_s": round(float(start["timestamp_s"]), 3),
        "end_s": round(float(end["timestamp_s"]), 3),
        "clip_start_s": round(float(start["clip_timestamp_s"]), 3),
        "clip_end_s": round(float(end["clip_timestamp_s"]), 3),
        "first_cx": start.get("cx"),
        "first_cy": start.get("cy"),
        "last_cx": end.get("cx"),
        "last_cy": end.get("cy"),
        "first_area": start.get("area"),
        "last_area": end.get("area"),
        "observed_table_frames": len(observations),
        "interval_duration_s": round(float(duration_s), 3),
        "role_counts": role_counts,
        "stage_counts": stage_counts,
        "label": (
            f"{_role_label(track_id, table_team_role, dominant_role)} "
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
                "table_team_role": interval["table_team_role"],
                "table_team_role_confidence": interval["table_team_role_confidence"],
                "observed_table_frames": interval["observed_table_frames"],
                "interval_duration_s": interval["interval_duration_s"],
                "start_s": interval["start_s"],
                "end_s": interval["end_s"],
                "clip_start_s": interval["clip_start_s"],
                "clip_end_s": interval["clip_end_s"],
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
    table_team_role, table_team_role_confidence = _table_team_role(
        role_counts,
        dominant_role,
        observed_frames,
    )
    estimated_duration_s = observed_frames * sample_period_s
    return {
        "track_id": track["track_id"],
        "dominant_role": dominant_role,
        "table_team_role": table_team_role,
        "table_team_role_confidence": table_team_role_confidence,
        "observed_table_frames": observed_frames,
        "stage_table_presence_ratio": _ratio(observed_frames, stage_frames),
        "estimated_table_duration_s": round(float(estimated_duration_s), 3),
        "first_frame": track["first_frame"],
        "last_frame": track["last_frame"],
        "first_s": round(float(track["first_s"]), 3),
        "last_s": round(float(track["last_s"]), 3),
        "role_counts": role_counts,
        "label": (
            f"{_role_label(track['track_id'], table_team_role, dominant_role)} "
            f"frames={observed_frames}"
        ),
    }


def _stage_table_coverage_rows(
    segment_metrics: Sequence[FrameMetrics],
    segment_index: int,
    min_observed_table_frames: int,
    identity_map: Optional[Dict[int, Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    if not segment_metrics:
        return []

    stage_state = _tavr_state(segment_metrics[0])
    stage_start = segment_metrics[0]
    stage_end = segment_metrics[-1]
    stage_frames = len(segment_metrics)
    stage_room_view_frames = sum(
        1 for metric in segment_metrics if _view_label(metric) == "room"
    )
    stage_non_room_view_frames = stage_frames - stage_room_view_frames
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
            identity = (identity_map or {}).get(track_id)
            canonical_table_id = (
                identity["canonical_table_id"] if identity else track_id
            )
            merged_track_ids = (
                list(identity["merged_track_ids"]) if identity else [track_id]
            )
            track = tracks.setdefault(
                canonical_table_id,
                {
                    "track_id": min(merged_track_ids),
                    "canonical_table_id": canonical_table_id,
                    "merged_track_ids": set(merged_track_ids),
                    "first_frame": metric.frame_index,
                    "last_frame": metric.frame_index,
                    "first_s": metric.timestamp_s,
                    "last_s": metric.timestamp_s,
                    "first_clip_s": metric.clip_timestamp_s,
                    "last_clip_s": metric.clip_timestamp_s,
                    "observed_table_frames": 0,
                    "role_counts": {},
                },
            )
            track["merged_track_ids"].add(track_id)
            track["track_id"] = min(track["merged_track_ids"])
            track["first_frame"] = min(track["first_frame"], metric.frame_index)
            track["last_frame"] = max(track["last_frame"], metric.frame_index)
            track["first_s"] = min(track["first_s"], metric.timestamp_s)
            track["last_s"] = max(track["last_s"], metric.timestamp_s)
            track["first_clip_s"] = min(track["first_clip_s"], metric.clip_timestamp_s)
            track["last_clip_s"] = max(track["last_clip_s"], metric.clip_timestamp_s)
            track["observed_table_frames"] += 1
            track["role_counts"][role] = track["role_counts"].get(role, 0) + 1

    rows = []
    for track in tracks.values():
        if track["observed_table_frames"] < min_observed_table_frames:
            continue
        role_counts = dict(sorted(track["role_counts"].items()))
        dominant_role = _dominant_role_from_counts(role_counts)
        table_team_role, table_team_role_confidence = _table_team_role(
            role_counts,
            dominant_role,
            track["observed_table_frames"],
        )
        coverage_ratio = _ratio(track["observed_table_frames"], stage_frames)
        room_coverage_ratio = _ratio(
            track["observed_table_frames"],
            stage_room_view_frames,
        )
        estimated_duration_s = track["observed_table_frames"] * sample_period_s
        row = {
            "stage_segment_index": segment_index,
            "stage": stage_state.stage,
            "stage_label": stage_state.stage_label,
            "stage_start_frame": stage_start.frame_index,
            "stage_end_frame": stage_end.frame_index,
            "stage_start_s": round(float(stage_start.timestamp_s), 3),
            "stage_end_s": round(float(stage_end.timestamp_s), 3),
            "stage_clip_start_s": round(float(stage_start.clip_timestamp_s), 3),
            "stage_clip_end_s": round(float(stage_end.clip_timestamp_s), 3),
            "stage_duration_s": round(float(stage_duration_s), 3),
            "stage_room_view_frames": stage_room_view_frames,
            "stage_non_room_view_frames": stage_non_room_view_frames,
            "tracking_available_rate": _ratio(stage_room_view_frames, stage_frames),
            "track_id": track["track_id"],
            "canonical_table_id": track["canonical_table_id"],
            "merged_track_ids": sorted(int(track_id) for track_id in track["merged_track_ids"]),
            "dominant_role": dominant_role,
            "table_team_role": table_team_role,
            "table_team_role_confidence": table_team_role_confidence,
            "observed_table_frames": track["observed_table_frames"],
            "first_seen_frame": track["first_frame"],
            "last_seen_frame": track["last_frame"],
            "first_seen_s": round(float(track["first_s"]), 3),
            "last_seen_s": round(float(track["last_s"]), 3),
            "first_seen_clip_s": round(float(track["first_clip_s"]), 3),
            "last_seen_clip_s": round(float(track["last_clip_s"]), 3),
            "coverage_ratio": coverage_ratio,
            "room_coverage_ratio": room_coverage_ratio,
            "estimated_table_duration_s": round(float(estimated_duration_s), 3),
            "entered_during_stage": track["first_frame"] > stage_start.frame_index,
            "exited_during_stage": track["last_frame"] < stage_end.frame_index,
            "role_counts": role_counts,
        }
        row["spans_full_stage"] = (
            not row["entered_during_stage"] and not row["exited_during_stage"]
        )
        row["label"] = (
            f"{row['stage_label']}: "
            f"{_role_label(track['track_id'], table_team_role, dominant_role)} "
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
