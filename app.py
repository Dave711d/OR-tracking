"""Streamlit entrypoint for the OR tracking prototype."""

from __future__ import annotations

import io
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Optional, Tuple

import pandas as pd
import streamlit as st

from or_tracking import (
    MotionTrackerConfig,
    TAVR_STAGE_LABELS,
    TAVR_STAGE_ORDER,
    process_video_file,
    summarize_tavr_metrics,
    write_tavr_summary_csvs,
)
from or_tracking.synthetic import generate_synthetic_or_video, generate_synthetic_tavr_video


st.set_page_config(
    page_title="OR Tracking Prototype",
    page_icon="OR",
    layout="wide",
)


def main() -> None:
    st.title("OR Tracking Prototype")

    with st.sidebar:
        st.header("Run settings")
        max_frames = st.slider("Max frames", 60, 1800, 360, step=60)
        min_area = st.slider("Minimum tracked area", 100, 5000, 180, step=20)
        crowding_threshold = st.slider("Crowding threshold", 2, 8, 4)
        initial_stage = st.selectbox(
            "Initial TAVR stage",
            TAVR_STAGE_ORDER,
            format_func=lambda stage: TAVR_STAGE_LABELS[stage],
        )
        static_table_fallback = st.toggle(
            "Static table fallback",
            value=False,
            help=(
                "Opt-in low-motion review mode: count conservative static "
                "table-zone silhouettes when room view is visible and table "
                "motion is otherwise absent."
            ),
        )
        use_roi = st.toggle("Crop to ROI", value=False)
        roi = None
        if use_roi:
            roi_cols = st.columns(2)
            with roi_cols[0]:
                x0 = st.number_input("ROI x0", 0.0, 0.99, 0.0, 0.01)
                y0 = st.number_input("ROI y0", 0.0, 0.99, 0.46, 0.01)
            with roi_cols[1]:
                x1 = st.number_input("ROI x1", 0.01, 1.0, 0.31, 0.01)
                y1 = st.number_input("ROI y1", 0.01, 1.0, 0.89, 0.01)
            if x0 < x1 and y0 < y1:
                roi = (x0, y0, x1, y1)
            else:
                st.warning("ROI must satisfy x0 < x1 and y0 < y1")
        write_video = st.toggle("Create annotated video", value=True)

    uploaded_file = st.file_uploader(
        "Upload theatre video",
        type=["mp4", "mov", "avi", "m4v"],
        accept_multiple_files=False,
    )

    sample_col, tavr_col, upload_col = st.columns([1, 1, 2])
    with sample_col:
        use_sample = st.button("Use synthetic sample", width="stretch")
    with tavr_col:
        use_tavr_sample = st.button("Use TAVR sample", width="stretch")
    with upload_col:
        run_uploaded = st.button(
            "Analyze uploaded video",
            type="primary",
            width="stretch",
            disabled=uploaded_file is None,
        )

    if use_sample:
        sample_path = Path("samples/synthetic_or_sample.mp4")
        generate_synthetic_or_video(sample_path)
        _run_analysis(
            sample_path,
            max_frames,
            min_area,
            crowding_threshold,
            initial_stage,
            static_table_fallback,
            roi,
            write_video,
        )

    if use_tavr_sample:
        sample_path = Path("samples/synthetic_tavr_sample.mp4")
        generate_synthetic_tavr_video(sample_path)
        _run_analysis(
            sample_path,
            max_frames,
            min_area,
            crowding_threshold,
            initial_stage,
            static_table_fallback,
            roi,
            write_video,
        )

    if run_uploaded and uploaded_file is not None:
        suffix = Path(uploaded_file.name).suffix or ".mp4"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
            handle.write(uploaded_file.getbuffer())
            input_path = Path(handle.name)
        _run_analysis(
            input_path,
            max_frames,
            min_area,
            crowding_threshold,
            initial_stage,
            static_table_fallback,
            roi,
            write_video,
        )


def _run_analysis(
    video_path: Path,
    max_frames: int,
    min_area: int,
    crowding_threshold: int,
    initial_stage: str,
    static_table_fallback: bool,
    roi: Optional[Tuple[float, float, float, float]],
    write_video: bool,
) -> None:
    config = MotionTrackerConfig(
        min_area=min_area,
        crowding_threshold=crowding_threshold,
        tavr_initial_stage=initial_stage,
        enable_static_table_fallback=static_table_fallback,
    )
    progress = st.progress(0, text="Processing video")

    def on_progress(done: int, total: int | None) -> None:
        denominator = total or max_frames
        progress.progress(min(done / max(denominator, 1), 1.0), text=f"Frame {done}")

    with st.spinner("Analyzing movement and zones"):
        result = process_video_file(
            video_path,
            output_dir="outputs",
            config=config,
            max_frames=max_frames,
            roi=roi,
            write_annotated_video=write_video,
            progress_callback=on_progress,
    )
    progress.empty()

    tavr_summary = summarize_tavr_metrics(result.metrics)
    timebase_rows = tavr_summary.get("timebase_summary", [])
    timebase = timebase_rows[0] if timebase_rows else {}
    summary = result.summary.to_dict()
    metric_cols = st.columns(7)
    metric_cols[0].metric("Frames", summary["frames_processed"])
    metric_cols[1].metric("Avg count", summary["average_people_count"])
    metric_cols[2].metric("Peak count", summary["peak_people_count"])
    metric_cols[3].metric("Tracks", summary["total_unique_tracks"])
    metric_cols[4].metric("Activity", summary["activity_score"])
    metric_cols[5].metric("TAVR stage", summary.get("dominant_tavr_stage") or "n/a")
    metric_cols[6].metric("Peak table", summary.get("peak_table_count", 0))
    if timebase:
        st.caption(_timebase_label(timebase))

    rows = [metric.to_row() for metric in result.metrics]
    metrics_df = pd.DataFrame(rows)
    if not metrics_df.empty and "tavr_stage_label" in metrics_df:
        latest = metrics_df.iloc[-1]
        st.info(
            "Latest TAVR estimate: "
            f"{latest.get('tavr_stage_label', 'n/a')} "
            f"(confidence {latest.get('tavr_confidence', 0)}) | "
            f"table IDs: {latest.get('table_track_ids', '') or 'none'}"
        )
        if latest.get("who_at_table"):
            st.success(f"At table now: {latest['who_at_table']}")

    run_stem = result.csv_path.name.replace("_metrics.csv", "")
    tavr_csv_paths = write_tavr_summary_csvs("outputs", run_stem, tavr_summary)
    status_rows = tavr_summary.get("procedure_status_summary", [])
    if status_rows:
        st.subheader("Procedure status")
        st.info(status_rows[0].get("operator_summary", ""))
        st.dataframe(
            pd.DataFrame(_procedure_status_rows(status_rows)),
            width="stretch",
            hide_index=True,
        )

    operator_packets = tavr_summary.get("operator_stage_packet", [])
    if operator_packets:
        st.subheader("Operator stage packet")
        st.dataframe(
            pd.DataFrame(_operator_stage_packet_rows(operator_packets)),
            width="stretch",
            hide_index=True,
        )

    team_rows = tavr_summary.get("table_team_summary", [])
    if team_rows:
        st.subheader("Table team summary")
        st.dataframe(
            pd.DataFrame(_table_team_rows(team_rows)),
            width="stretch",
            hide_index=True,
        )

    identity_rows = tavr_summary.get("table_identity_groups", [])
    if identity_rows:
        st.subheader("Table identity groups")
        st.dataframe(
            pd.DataFrame(_table_identity_rows(identity_rows)),
            width="stretch",
            hide_index=True,
        )

    view_rows = tavr_summary.get("view_segments", [])
    if view_rows:
        st.subheader("View segments")
        view_columns = [
            "view",
            "start_s",
            "end_s",
            "duration_s",
            "tracking_available",
            "mean_colorfulness",
            "dominant_stage",
            "peak_table_count",
        ]
        st.dataframe(
            pd.DataFrame(view_rows)[view_columns].head(20),
            width="stretch",
            hide_index=True,
        )

    event_rows = tavr_summary.get("procedure_event_timeline", [])
    if event_rows:
        st.subheader("Procedure event timeline")
        st.dataframe(
            pd.DataFrame(_procedure_event_rows(event_rows)),
            width="stretch",
            hide_index=True,
        )

    milestones = tavr_summary.get("procedure_milestones", [])
    if milestones:
        st.subheader("Procedure milestones")
        st.dataframe(
            pd.DataFrame(_procedure_milestone_rows(milestones)),
            width="stretch",
            hide_index=True,
        )

    evidence = tavr_summary.get("stage_evidence_summary", [])
    if evidence:
        st.subheader("Stage evidence summary")
        st.dataframe(
            pd.DataFrame(_stage_evidence_rows(evidence)),
            width="stretch",
            hide_index=True,
        )

    staffing = tavr_summary.get("stage_staffing_summary", [])
    if staffing:
        st.subheader("Stage staffing summary")
        st.dataframe(
            pd.DataFrame(_stage_staffing_rows(staffing)),
            width="stretch",
            hide_index=True,
        )

    handoffs = tavr_summary.get("stage_handoff_summary", [])
    if handoffs:
        st.subheader("Stage handoff summary")
        st.dataframe(
            pd.DataFrame(_stage_handoff_rows(handoffs)),
            width="stretch",
            hide_index=True,
        )

    stage_rosters = tavr_summary.get("stage_roster_summary", [])
    if stage_rosters:
        st.subheader("Stage roster summary")
        st.dataframe(
            pd.DataFrame(_stage_roster_rows(stage_rosters)),
            width="stretch",
            hide_index=True,
        )

    last_observed = tavr_summary.get("last_observed_table_roster", {})
    if last_observed.get("roster"):
        st.subheader("Last observed table roster")
        roster_text = "; ".join(
            item["label"] for item in last_observed.get("roster", [])
        )
        st.success(
            f"{last_observed.get('stage_label', 'n/a')} at "
            f"{last_observed.get('timestamp_s', 'n/a')}s "
            f"({last_observed.get('age_from_clip_end_s', 'n/a')}s before clip end): "
            f"{roster_text}"
        )

    snapshots = tavr_summary.get("table_roster_snapshots", [])
    if snapshots:
        st.subheader("Table roster snapshots")
        snapshot_columns = [
            "snapshot_type",
            "timestamp_s",
            "age_from_clip_end_s",
            "stage_label",
            "table_count",
            "track_id",
            "dominant_role",
            "table_presence_ratio",
            "label",
        ]
        st.dataframe(
            pd.DataFrame(snapshots)[snapshot_columns].head(30),
            width="stretch",
            hide_index=True,
        )

    coverage = tavr_summary.get("stage_table_coverage", [])
    if coverage:
        st.subheader("Stage table coverage")
        coverage_columns = [
            "stage_label",
            "track_id",
            "dominant_role",
            "coverage_ratio",
            "room_coverage_ratio",
            "tracking_available_rate",
            "observed_table_frames",
            "first_seen_s",
            "last_seen_s",
            "entered_during_stage",
            "exited_during_stage",
        ]
        st.dataframe(
            pd.DataFrame(coverage)[coverage_columns].head(40),
            width="stretch",
            hide_index=True,
        )

    events = tavr_summary.get("table_transition_events", [])
    if events:
        st.subheader("Table transition events")
        event_columns = [
            "timestamp_s",
            "event_type",
            "track_id",
            "dominant_role",
            "stage_label",
            "coverage_ratio",
            "observed_table_frames",
        ]
        st.dataframe(
            pd.DataFrame(events)[event_columns].head(50),
            width="stretch",
            hide_index=True,
        )

    intervals = tavr_summary.get("table_presence_intervals", [])
    if intervals:
        st.subheader("Table presence intervals")
        interval_columns = [
            "track_id",
            "dominant_role",
            "dominant_stage",
            "start_s",
            "end_s",
            "observed_table_frames",
            "interval_duration_s",
        ]
        st.dataframe(
            pd.DataFrame(intervals)[interval_columns].head(20),
            width="stretch",
            hide_index=True,
        )

    quality_flags = tavr_summary.get("quality_flags", [])
    if quality_flags:
        st.subheader("Quality flags")
        quality_df = pd.DataFrame(quality_flags)
        quality_columns = [
            column
            for column in [
                "code",
                "ratio",
                "frames",
                "confidence_threshold",
                "peak_people_count",
                "peak_table_count",
                "mean_movement_px",
                "message",
            ]
            if column in quality_df.columns
        ]
        st.dataframe(
            quality_df[quality_columns],
            width="stretch",
            hide_index=True,
        )

    low_confidence = tavr_summary.get("low_confidence_segments", [])
    if low_confidence:
        st.subheader("Low-confidence stage spans")
        confidence_columns = [
            "start_s",
            "end_s",
            "min_confidence",
            "max_confidence",
        ]
        st.dataframe(
            pd.DataFrame(low_confidence)[confidence_columns].head(30),
            width="stretch",
            hide_index=True,
        )

    chart_col, table_col = st.columns([3, 2])
    with chart_col:
        if not metrics_df.empty:
            st.line_chart(
                metrics_df.set_index("timestamp_s")[["people_count", "movement_px"]]
            )
    with table_col:
        display_columns = [
            column
            for column in [
                "clip_timestamp_s",
                "source_timestamp_s",
                "timestamp_s",
                "people_count",
                "tavr_stage_label",
                "tavr_confidence",
                "table_count",
                "table_track_ids",
                "who_at_table",
                "role_counts",
                "track_role_summary",
                "movement_px",
                "alert_flags",
            ]
            if column in metrics_df.columns
        ]
        st.dataframe(
            metrics_df[display_columns].tail(20) if display_columns else metrics_df.tail(20),
            width="stretch",
            hide_index=True,
        )

    downloads = st.columns(3)
    with downloads[0]:
        st.download_button(
            "Download metrics CSV",
            result.csv_path.read_bytes(),
            file_name=result.csv_path.name,
            mime="text/csv",
            width="stretch",
        )
    with downloads[1]:
        if tavr_csv_paths:
            st.download_button(
                "Download TAVR tables",
                _zip_paths(tavr_csv_paths),
                file_name=f"{run_stem}_tavr_tables.zip",
                mime="application/zip",
                width="stretch",
            )
    with downloads[2]:
        if result.annotated_video_path and result.annotated_video_path.exists():
            st.download_button(
                "Download annotated MP4",
                result.annotated_video_path.read_bytes(),
                file_name=result.annotated_video_path.name,
                mime="video/mp4",
                width="stretch",
            )

    if result.annotated_video_path and result.annotated_video_path.exists():
        st.subheader("Annotated output")
        st.video(str(result.annotated_video_path))


def _stage_staffing_rows(staffing: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in staffing:
        roster = "; ".join(
            track["label"] for track in item.get("table_roster", [])[:6]
        )
        rows.append(
            {
                "stage_label": item["stage_label"],
                "duration_s": item["duration_s"],
                "frames": item["frames"],
                "room_view_frames": item["room_view_frames"],
                "tracking_available_rate": item["tracking_available_rate"],
                "mean_table_count": item["mean_table_count"],
                "mean_room_table_count": item["mean_room_table_count"],
                "peak_table_count": item["peak_table_count"],
                "table_occupancy_rate": item["table_occupancy_rate"],
                "room_table_occupancy_rate": item["room_table_occupancy_rate"],
                "unique_table_track_count": item["unique_table_track_count"],
                "canonical_table_people": item.get(
                    "canonical_table_identity_count", 0
                ),
                "role_mix": _count_label(item.get("role_counts", {})),
                "table_roster": roster or "none",
            }
        )
    return rows


def _stage_handoff_rows(handoffs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in handoffs:
        rows.append(
            {
                "stage_label": item["stage_label"],
                "previous_stage_label": item.get("previous_stage_label") or "clip start",
                "start_s": item["start_s"],
                "end_s": item["end_s"],
                "tracking_available_rate": item["tracking_available_rate"],
                "handoff_type": item["handoff_type"],
                "active_table_track_count": item["active_table_track_count"],
                "lead_track_id": item.get("lead_track_id"),
                "lead_role": item.get("lead_role") or "none",
                "lead_dominant_role": item.get("lead_dominant_role") or "none",
                "continued_track_ids": _id_label(item.get("continued_track_ids", [])),
                "new_track_ids": _id_label(item.get("new_track_ids", [])),
                "dropped_track_ids": _id_label(item.get("dropped_track_ids", [])),
                "active_table_roster": _roster_label(
                    item.get("active_table_roster", [])
                ),
            }
        )
    return rows


def _stage_roster_rows(stage_rosters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in stage_rosters:
        rows.append(
            {
                "stage_label": item["stage_label"],
                "start_s": item["start_s"],
                "end_s": item["end_s"],
                "evidence": _status_label(item.get("evidence_level")),
                "tracking_available_rate": item["tracking_available_rate"],
                "peak_table_count": item["peak_table_count"],
                "table_people": item["canonical_table_identity_count"],
                "lead_track_id": item.get("lead_track_id"),
                "lead_role": _status_label(item.get("lead_table_team_role")),
                "handoff_type": _status_label(item.get("handoff_type")),
                "active_ids": _id_label(item.get("active_table_track_ids", [])),
                "new_ids": _id_label(item.get("new_track_ids", [])),
                "dropped_ids": _id_label(item.get("dropped_track_ids", [])),
                "roster": _roster_label(item.get("active_table_roster", [])),
            }
        )
    return rows


def _operator_stage_packet_rows(packets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in packets:
        rows.append(
            {
                "stage_label": item["stage_label"],
                "stage_status": _status_label(item.get("stage_status")),
                "current": _yes_no(item.get("is_current_stage")),
                "start_s": item["start_s"],
                "end_s": item["end_s"],
                "evidence": _status_label(item.get("evidence_level")),
                "confidence": item.get("mean_confidence"),
                "handoff": _status_label(item.get("handoff_type")),
                "peak_table": item.get("peak_table_count", 0),
                "active_ids": _id_label(item.get("active_table_track_ids", [])),
                "new_ids": _id_label(item.get("new_track_ids", [])),
                "dropped_ids": _id_label(item.get("dropped_track_ids", [])),
                "effective_table": _status_label(item.get("effective_table_source")),
                "effective_ids": _id_label(
                    item.get("effective_table_track_ids", [])
                ),
                "packet": item.get("operator_packet", ""),
            }
        )
    return rows


def _procedure_event_rows(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in events:
        rows.append(
            {
                "timestamp_s": item["timestamp_s"],
                "clip_timestamp_s": item.get("clip_timestamp_s"),
                "event_type": item["event_type"],
                "stage_label": item.get("stage_label") or "n/a",
                "view": item.get("view") or "n/a",
                "tracking_available": item.get("tracking_available"),
                "table_count": item.get("table_count", 0),
                "lead_track_id": item.get("track_id"),
                "table_role": item.get("table_team_role") or "none",
                "dominant_role": item.get("dominant_role") or "none",
                "handoff_type": item.get("handoff_type") or "none",
                "table_track_ids": _id_label(item.get("table_track_ids", [])),
                "roster": _roster_label(item.get("roster", [])),
                "label": item.get("label", ""),
            }
        )
    return rows


def _procedure_status_rows(status_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in status_rows:
        rows.append(
            {
                "current_stage": item.get("current_stage_label") or "n/a",
                "status": _status_label(item.get("current_stage_status")),
                "next_stage": item.get("next_stage_label") or "procedure end",
                "evidence": _status_label(item.get("evidence_level")),
                "observable_rate": item.get("observable_rate"),
                "mean_confidence": item.get("mean_confidence"),
                "current_view": item.get("current_view") or "n/a",
                "tracking_available": _yes_no(item.get("tracking_available")),
                "at_table_now": _roster_label(item.get("current_table_roster", [])),
                "table_status_source": _status_label(
                    item.get("effective_table_source")
                ),
                "table_status_count": item.get("effective_table_count", 0),
                "table_status_age_s": item.get(
                    "effective_table_age_from_clip_end_s"
                ),
                "table_status_roster": _roster_label(
                    item.get("effective_table_roster", [])
                ),
                "last_observed_table_s": item.get("last_observed_table_s"),
                "last_observed_clip_s": item.get("last_observed_clip_s"),
                "last_observed_stage": (
                    item.get("last_observed_stage_label") or "n/a"
                ),
                "last_observed_roster": _roster_label(
                    item.get("last_observed_table_roster", [])
                ),
                "peak_table_count": item.get("peak_table_count", 0),
                "quality_flags": ", ".join(item.get("quality_flag_codes", [])),
            }
        )
    return rows


def _procedure_milestone_rows(milestones: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in milestones:
        rows.append(
            {
                "stage": item.get("stage_label") or item.get("stage") or "n/a",
                "status": _status_label(item.get("milestone_status")),
                "current": _yes_no(item.get("is_current_observed_stage")),
                "observed": _yes_no(item.get("observed_in_clip")),
                "first_observed_s": item.get("first_observed_s"),
                "last_observed_s": item.get("last_observed_s"),
                "duration_s": item.get("duration_s"),
                "evidence": _status_label(item.get("evidence_level")),
                "observable_rate": item.get("observable_rate"),
                "mean_confidence": item.get("mean_confidence"),
                "peak_table_count": item.get("peak_table_count", 0),
                "unique_table_tracks": item.get("unique_table_track_count", 0),
                "canonical_table_people": item.get(
                    "canonical_table_identity_count", 0
                ),
                "support": item.get("support_label") or item.get("label") or "",
            }
        )
    return rows


def _table_team_rows(team_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in team_rows:
        rows.append(
            {
                "track_id": item.get("track_id"),
                "canonical_id": item.get("canonical_table_id"),
                "merged_track_ids": _id_label(item.get("merged_track_ids", [])),
                "status": _status_label(item.get("team_status")),
                "table_role": _status_label(item.get("table_team_role")),
                "dominant_role": _status_label(item.get("dominant_role")),
                "role_confidence": item.get("table_team_role_confidence"),
                "current": _yes_no(item.get("is_current_table_member")),
                "effective": _yes_no(item.get("is_effective_table_member")),
                "last_observed": _yes_no(item.get("is_last_observed_table_member")),
                "peak": _yes_no(item.get("is_peak_table_member")),
                "last_seen_s": item.get("last_seen_s"),
                "last_seen_clip_s": item.get("last_seen_clip_s"),
                "age_s": item.get("age_from_clip_end_s"),
                "table_frames": item.get("table_frames", 0),
                "table_presence_ratio": item.get("table_presence_ratio"),
                "dominant_stage": item.get("dominant_stage_label") or "n/a",
                "label": item.get("label", ""),
            }
        )
    return rows


def _table_identity_rows(identity_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in identity_rows:
        rows.append(
            {
                "canonical_id": item.get("canonical_table_id"),
                "representative_track_id": item.get("track_id"),
                "merged_track_ids": _id_label(item.get("merged_track_ids", [])),
                "table_role": _status_label(item.get("table_team_role")),
                "dominant_role": _status_label(item.get("dominant_role")),
                "role_confidence": item.get("table_team_role_confidence"),
                "first_seen_s": item.get("first_seen_s"),
                "last_seen_s": item.get("last_seen_s"),
                "first_seen_clip_s": item.get("first_seen_clip_s"),
                "last_seen_clip_s": item.get("last_seen_clip_s"),
                "table_frames": item.get("observed_table_frames", 0),
            }
        )
    return rows


def _stage_evidence_rows(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in evidence:
        rows.append(
            {
                "stage_label": item["stage_label"],
                "start_s": item["start_s"],
                "end_s": item["end_s"],
                "duration_s": item["duration_s"],
                "evidence_level": item["evidence_level"],
                "observable_rate": item["observable_rate"],
                "mean_confidence": item["mean_confidence"],
                "room_view_frames": item["room_view_frames"],
                "non_room_view_frames": item["non_room_view_frames"],
                "dominant_signal": item["dominant_signal"],
                "support": item["support_label"],
            }
        )
    return rows


def _id_label(track_ids: list[int]) -> str:
    return ", ".join(str(track_id) for track_id in track_ids) or "none"


def _roster_label(roster: list[dict[str, Any]]) -> str:
    return "; ".join(item["label"] for item in roster[:6]) or "none"


def _count_label(counts: dict[str, int]) -> str:
    return ", ".join(
        f"{key}:{value}" for key, value in sorted(counts.items()) if value
    )


def _timebase_label(timebase: dict[str, Any]) -> str:
    clip = (
        f"clip {_seconds_label(timebase.get('clip_start_s'))}-"
        f"{_seconds_label(timebase.get('clip_end_s'))}"
    )
    source = (
        f"source {_seconds_label(timebase.get('source_start_s'))}-"
        f"{_seconds_label(timebase.get('source_end_s'))}"
    )
    return (
        f"Clock: {clip}; {source}; "
        f"offset {_seconds_label(timebase.get('source_offset_s'))}"
    )


def _seconds_label(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.1f}s"


def _yes_no(value: Any) -> str:
    return "yes" if bool(value) else "no"


def _status_label(value: Any) -> str:
    return str(value or "n/a").replace("_", " ")


def _zip_paths(paths: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for table_name, path_text in sorted(paths.items()):
            path = Path(path_text)
            if path.exists():
                archive.write(path, arcname=path.name)
    return buffer.getvalue()


if __name__ == "__main__":
    main()
