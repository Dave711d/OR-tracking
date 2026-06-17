"""Streamlit entrypoint for the OR tracking prototype."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from or_tracking import MotionTrackerConfig, process_video_file
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
        min_area = st.slider("Minimum tracked area", 100, 5000, 200, step=100)
        crowding_threshold = st.slider("Crowding threshold", 2, 8, 4)
        write_video = st.toggle("Create annotated video", value=True)

    uploaded_file = st.file_uploader(
        "Upload theatre video",
        type=["mp4", "mov", "avi", "m4v"],
        accept_multiple_files=False,
    )

    sample_col, tavr_col, upload_col = st.columns([1, 1, 2])
    with sample_col:
        use_sample = st.button("Use synthetic sample", use_container_width=True)
    with tavr_col:
        use_tavr_sample = st.button("Use TAVR sample", use_container_width=True)
    with upload_col:
        run_uploaded = st.button(
            "Analyze uploaded video",
            type="primary",
            use_container_width=True,
            disabled=uploaded_file is None,
        )

    if use_sample:
        sample_path = Path("samples/synthetic_or_sample.mp4")
        generate_synthetic_or_video(sample_path)
        _run_analysis(sample_path, max_frames, min_area, crowding_threshold, write_video)

    if use_tavr_sample:
        sample_path = Path("samples/synthetic_tavr_sample.mp4")
        generate_synthetic_tavr_video(sample_path)
        _run_analysis(sample_path, max_frames, min_area, crowding_threshold, write_video)

    if run_uploaded and uploaded_file is not None:
        suffix = Path(uploaded_file.name).suffix or ".mp4"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
            handle.write(uploaded_file.getbuffer())
            input_path = Path(handle.name)
        _run_analysis(input_path, max_frames, min_area, crowding_threshold, write_video)


def _run_analysis(
    video_path: Path,
    max_frames: int,
    min_area: int,
    crowding_threshold: int,
    write_video: bool,
) -> None:
    config = MotionTrackerConfig(
        min_area=min_area,
        crowding_threshold=crowding_threshold,
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
            write_annotated_video=write_video,
            progress_callback=on_progress,
        )
    progress.empty()

    summary = result.summary.to_dict()
    metric_cols = st.columns(7)
    metric_cols[0].metric("Frames", summary["frames_processed"])
    metric_cols[1].metric("Avg count", summary["average_people_count"])
    metric_cols[2].metric("Peak count", summary["peak_people_count"])
    metric_cols[3].metric("Tracks", summary["total_unique_tracks"])
    metric_cols[4].metric("Activity", summary["activity_score"])
    metric_cols[5].metric("TAVR stage", summary.get("dominant_tavr_stage") or "n/a")
    metric_cols[6].metric("Peak table", summary.get("peak_table_count", 0))

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
            use_container_width=True,
            hide_index=True,
        )

    downloads = st.columns(2)
    with downloads[0]:
        st.download_button(
            "Download metrics CSV",
            result.csv_path.read_bytes(),
            file_name=result.csv_path.name,
            mime="text/csv",
            use_container_width=True,
        )
    with downloads[1]:
        if result.annotated_video_path and result.annotated_video_path.exists():
            st.download_button(
                "Download annotated MP4",
                result.annotated_video_path.read_bytes(),
                file_name=result.annotated_video_path.name,
                mime="video/mp4",
                use_container_width=True,
            )

    if result.annotated_video_path and result.annotated_video_path.exists():
        st.subheader("Annotated output")
        st.video(str(result.annotated_video_path))


if __name__ == "__main__":
    main()
