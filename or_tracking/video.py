"""Video file processing helpers for the OR tracking prototype."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple

import cv2

from .models import FrameMetrics, TrackingSummary, rows_from_metrics
from .tracker import MotionTrackerConfig, ORActivityTracker


ProgressCallback = Callable[[int, Optional[int]], None]
NormalizedROI = Tuple[float, float, float, float]


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
    start_frame: int = 0,
    start_s: Optional[float] = None,
    roi: Optional[NormalizedROI] = None,
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
    resolved_start_frame = _start_frame(fps, start_frame, start_s)
    if resolved_start_frame > 0:
        capture.set(cv2.CAP_PROP_POS_FRAMES, resolved_start_frame)

    remaining_frames = (
        max(total_frames - resolved_start_frame, 0) if total_frames > 0 else total_frames
    )
    frame_limit = _frame_limit(remaining_frames, max_frames)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    roi_rect = _resolve_roi(roi, width, height)
    output_width, output_height = _output_dimensions(width, height, roi_rect)

    tracker = ORActivityTracker(config)
    metrics: List[FrameMetrics] = []
    writer = None
    annotated_path: Optional[Path] = None
    run_stem = _run_stem(source, resolved_start_frame, roi_rect)

    if write_annotated_video:
        annotated_path = output_path / f"{run_stem}_tracked.mp4"
        writer = _make_writer(annotated_path, fps, output_width, output_height)

    processed_count = 0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            if frame_limit is not None and processed_count >= frame_limit:
                break

            frame = _crop_frame(frame, roi_rect)
            source_frame_index = resolved_start_frame + processed_count
            timestamp_s = source_frame_index / max(fps, 1.0)
            frame_metrics = tracker.process_frame(frame, source_frame_index, timestamp_s)
            metrics.append(frame_metrics)

            if writer is not None:
                writer.write(tracker.annotate_frame(frame, frame_metrics))

            processed_count += 1
            if progress_callback:
                progress_callback(processed_count, frame_limit or remaining_frames or None)
    finally:
        capture.release()
        if writer is not None:
            writer.release()

    summary = TrackingSummary.from_metrics(metrics)
    csv_path = output_path / f"{run_stem}_metrics.csv"
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
        "view_colorfulness",
        "zone_counts",
        "alert_flags",
        "tavr_stage",
        "tavr_stage_label",
        "tavr_confidence",
        "table_count",
        "table_track_ids",
        "who_at_table",
        "role_counts",
        "role_track_ids",
        "track_role_summary",
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


def _start_frame(fps: float, start_frame: int, start_s: Optional[float]) -> int:
    if start_s is not None:
        return max(0, int(start_s * max(fps, 1.0)))
    return max(0, int(start_frame))


def _run_stem(
    source: Path,
    start_frame: int,
    roi_rect: Optional[Tuple[int, int, int, int]],
) -> str:
    stem = source.stem if start_frame <= 0 else f"{source.stem}_f{start_frame}"
    if roi_rect is None:
        return stem
    left, top, right, bottom = roi_rect
    return f"{stem}_roi{left}-{top}-{right}-{bottom}"


def _resolve_roi(
    roi: Optional[NormalizedROI],
    width: int,
    height: int,
) -> Optional[Tuple[int, int, int, int]]:
    if roi is None:
        return None
    if width <= 0 or height <= 0:
        raise ValueError("Video width and height must be available for ROI cropping")
    x0, y0, x1, y1 = roi
    if not (0.0 <= x0 < x1 <= 1.0 and 0.0 <= y0 < y1 <= 1.0):
        raise ValueError("ROI must be normalized as x0,y0,x1,y1 within 0..1")
    left = int(round(x0 * width))
    top = int(round(y0 * height))
    right = int(round(x1 * width))
    bottom = int(round(y1 * height))
    if right <= left or bottom <= top:
        raise ValueError("ROI resolved to an empty crop")
    return left, top, right, bottom


def _output_dimensions(
    width: int,
    height: int,
    roi_rect: Optional[Tuple[int, int, int, int]],
) -> Tuple[int, int]:
    if roi_rect is None:
        return width, height
    left, top, right, bottom = roi_rect
    return right - left, bottom - top


def _crop_frame(
    frame: Any,
    roi_rect: Optional[Tuple[int, int, int, int]],
) -> Any:
    if roi_rect is None:
        return frame
    left, top, right, bottom = roi_rect
    return frame[top:bottom, left:right]
