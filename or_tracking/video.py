"""Video file processing helpers for the OR tracking prototype."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

import cv2

from .models import FrameMetrics, TrackingSummary, rows_from_metrics
from .tracker import MotionTrackerConfig, ORActivityTracker


ProgressCallback = Callable[[int, Optional[int]], None]


@dataclass
class TrackingRunResult:
    input_path: Path
    metrics: List[FrameMetrics]
    summary: TrackingSummary
    csv_path: Path
    annotated_video_path: Optional[Path]


def process_video_file(
    input_path: str | Path,
    output_dir: str | Path = "outputs",
    config: Optional[MotionTrackerConfig] = None,
    max_frames: Optional[int] = None,
    write_annotated_video: bool = True,
    progress_callback: Optional[ProgressCallback] = None,
) -> TrackingRunResult:
    """Process a video and return metrics, summary, CSV, and optional video."""

    source = Path(input_path)
    if not source.exists():
        raise FileNotFoundError(f"Video file not found: {source}")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise ValueError(f"Could not open video file: {source}")

    fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    frame_limit = _frame_limit(total_frames, max_frames)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

    tracker = ORActivityTracker(config)
    metrics: List[FrameMetrics] = []
    writer = None
    annotated_path: Optional[Path] = None

    if write_annotated_video:
        annotated_path = output_path / f"{source.stem}_tracked.mp4"
        writer = _make_writer(annotated_path, fps, width, height)

    frame_index = 0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            if frame_limit is not None and frame_index >= frame_limit:
                break

            timestamp_s = frame_index / max(fps, 1.0)
            frame_metrics = tracker.process_frame(frame, frame_index, timestamp_s)
            metrics.append(frame_metrics)

            if writer is not None:
                writer.write(tracker.annotate_frame(frame, frame_metrics))

            frame_index += 1
            if progress_callback:
                progress_callback(frame_index, frame_limit or total_frames or None)
    finally:
        capture.release()
        if writer is not None:
            writer.release()

    summary = TrackingSummary.from_metrics(metrics)
    csv_path = output_path / f"{source.stem}_metrics.csv"
    write_metrics_csv(csv_path, metrics)
    return TrackingRunResult(
        input_path=source,
        metrics=metrics,
        summary=summary,
        csv_path=csv_path,
        annotated_video_path=annotated_path,
    )


def write_metrics_csv(path: str | Path, metrics: List[FrameMetrics]) -> None:
    rows = rows_from_metrics(metrics)
    fieldnames = [
        "frame_index",
        "timestamp_s",
        "people_count",
        "active_track_ids",
        "movement_px",
        "zone_counts",
        "alert_flags",
        "tavr_stage",
        "tavr_stage_label",
        "tavr_confidence",
        "table_count",
        "table_track_ids",
        "role_counts",
        "role_track_ids",
        "tavr_signals",
    ]
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _make_writer(path: Path, fps: float, width: int, height: int) -> cv2.VideoWriter:
    if width <= 0 or height <= 0:
        raise ValueError("Video width and height must be available for annotation")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, max(fps, 1.0), (width, height))
    if not writer.isOpened():
        raise ValueError(f"Could not create annotated video: {path}")
    return writer


def _frame_limit(total_frames: int, max_frames: Optional[int]) -> Optional[int]:
    if max_frames is None or max_frames <= 0:
        return total_frames or None
    if total_frames <= 0:
        return max_frames
    return min(total_frames, max_frames)
