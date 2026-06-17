from pathlib import Path

import cv2
import numpy as np

from or_tracking import MotionTrackerConfig, ORActivityTracker, process_video_file
from or_tracking.models import Detection
from or_tracking.synthetic import generate_synthetic_or_video, generate_synthetic_tavr_video
from or_tracking.tavr import TAVR_STAGE_ORDER
from or_tracking.video import _crop_frame, _resolve_roi


def test_tracker_detects_motion_on_synthetic_frames(tmp_path: Path) -> None:
    video_path = generate_synthetic_or_video(tmp_path / "sample.mp4", frames=48)
    capture = cv2.VideoCapture(str(video_path))
    tracker = ORActivityTracker(MotionTrackerConfig(min_area=250))

    people_counts = []
    for index in range(24):
        ok, frame = capture.read()
        assert ok
        metrics = tracker.process_frame(frame, index, index / 24)
        people_counts.append(metrics.people_count)
    capture.release()

    assert max(people_counts[4:]) >= 1
    assert tracker.total_tracks_seen >= 1


def test_process_video_file_writes_metrics_and_summary(tmp_path: Path) -> None:
    video_path = generate_synthetic_or_video(tmp_path / "sample.mp4", frames=36)

    result = process_video_file(
        video_path,
        output_dir=tmp_path / "outputs",
        config=MotionTrackerConfig(min_area=250),
        max_frames=24,
        write_annotated_video=True,
    )

    assert result.summary.frames_processed == 24
    assert result.summary.peak_people_count >= 1
    assert result.summary.total_unique_tracks >= 1
    assert result.csv_path.exists()
    assert "people_count" in result.csv_path.read_text(encoding="utf-8")
    assert result.annotated_video_path is not None
    assert result.annotated_video_path.exists()


def test_process_video_file_can_skip_annotated_video(tmp_path: Path) -> None:
    video_path = generate_synthetic_or_video(tmp_path / "sample.mp4", frames=12)

    result = process_video_file(
        video_path,
        output_dir=tmp_path / "outputs",
        max_frames=8,
        write_annotated_video=False,
    )

    assert result.summary.frames_processed == 8
    assert result.annotated_video_path is None


def test_process_video_file_can_start_from_offset(tmp_path: Path) -> None:
    video_path = generate_synthetic_or_video(
        tmp_path / "sample.mp4",
        frames=36,
        fps=24.0,
    )

    result = process_video_file(
        video_path,
        output_dir=tmp_path / "outputs",
        max_frames=8,
        start_frame=12,
        write_annotated_video=False,
    )

    assert result.summary.frames_processed == 8
    assert result.metrics[0].frame_index == 12
    assert result.metrics[0].timestamp_s == 0.5
    assert result.csv_path.name == "sample_f12_metrics.csv"


def test_process_video_file_can_crop_to_roi(tmp_path: Path) -> None:
    video_path = generate_synthetic_or_video(
        tmp_path / "sample.mp4",
        frames=12,
        width=200,
        height=100,
    )

    result = process_video_file(
        video_path,
        output_dir=tmp_path / "outputs",
        max_frames=4,
        roi=(0.25, 0.2, 0.75, 0.8),
        write_annotated_video=False,
    )

    assert result.summary.frames_processed == 4
    assert "_roi50-20-150-80" in result.csv_path.name


def test_resolve_roi_and_crop_frame() -> None:
    frame = np.zeros((10, 20, 3), dtype=np.uint8)
    frame[2:8, 5:15] = 255

    roi_rect = _resolve_roi((0.25, 0.2, 0.75, 0.8), width=20, height=10)
    cropped = _crop_frame(frame, roi_rect)

    assert roi_rect == (5, 2, 15, 8)
    assert cropped.shape == (6, 10, 3)
    assert int(cropped.mean()) == 255


def test_tracker_can_disable_tavr_inference(tmp_path: Path) -> None:
    video_path = generate_synthetic_or_video(tmp_path / "sample.mp4", frames=12)
    capture = cv2.VideoCapture(str(video_path))
    tracker = ORActivityTracker(MotionTrackerConfig(min_area=250, enable_tavr=False))

    ok, frame = capture.read()
    assert ok
    metrics = tracker.process_frame(frame, 0, 0)
    capture.release()

    assert metrics.tavr is None


def test_tracker_config_can_seed_tavr_initial_stage() -> None:
    tracker = ORActivityTracker(
        MotionTrackerConfig(
            min_area=250,
            tavr_initial_stage="valve_deployment",
        )
    )
    frame = np.zeros((120, 180, 3), dtype=np.uint8)

    metrics = tracker.process_frame(frame, 1200, 40.0)

    assert metrics.tavr is not None
    assert metrics.tavr.stage == "valve_deployment"


def test_tracker_assigns_one_primary_role_for_overlapping_zones() -> None:
    tracker = ORActivityTracker(MotionTrackerConfig())
    detections = [
        Detection(
            track_id=3,
            bbox=(30, 65, 10, 20),
            centroid=(35, 70),
            area=300,
        )
    ]

    roles = tracker._role_track_ids(detections, width=100, height=100)

    assert roles["access_operator"] == [3]
    assert roles["table_operator"] == []


def test_tavr_synthetic_footage_produces_ordered_stage_trace(tmp_path: Path) -> None:
    video_path = generate_synthetic_tavr_video(tmp_path / "tavr.mp4", frames=320)

    result = process_video_file(
        video_path,
        output_dir=tmp_path / "outputs",
        config=MotionTrackerConfig(min_area=180),
        max_frames=320,
        write_annotated_video=False,
    )

    stage_trace = []
    for metric in result.metrics:
        assert metric.tavr is not None
        if not stage_trace or stage_trace[-1] != metric.tavr.stage:
            stage_trace.append(metric.tavr.stage)

    assert stage_trace == TAVR_STAGE_ORDER
    assert result.summary.peak_table_count >= 2
    assert result.summary.dominant_tavr_stage in TAVR_STAGE_ORDER

    csv_text = result.csv_path.read_text(encoding="utf-8")
    assert "tavr_stage_label" in csv_text
    assert "table_track_ids" in csv_text
    assert "who_at_table" in csv_text
    assert "role_counts" in csv_text
    assert "role_track_ids" in csv_text
    assert "track_role_summary" in csv_text
