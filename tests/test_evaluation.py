import argparse
from pathlib import Path

import pytest

from evaluate_tavr import parse_roi
from or_tracking import MotionTrackerConfig, process_video_file
from or_tracking.evaluation import summarize_tavr_metrics
from or_tracking.models import FrameMetrics
from or_tracking.synthetic import generate_synthetic_tavr_video
from or_tracking.tavr import (
    TAVR_STAGE_LABELS,
    TAVR_STAGE_NOTES,
    TAVR_STAGE_ORDER,
    TAVRFrameState,
)


def test_summarize_tavr_metrics_reports_timeline_and_roster(tmp_path: Path) -> None:
    video_path = generate_synthetic_tavr_video(tmp_path / "tavr.mp4", frames=320)
    result = process_video_file(
        video_path,
        output_dir=tmp_path / "outputs",
        config=MotionTrackerConfig(min_area=180),
        max_frames=320,
        write_annotated_video=False,
    )

    summary = summarize_tavr_metrics(result.metrics)

    assert [item["stage"] for item in summary["stage_timeline"]] == TAVR_STAGE_ORDER
    assert summary["track_role_report"]
    assert summary["track_role_report"][0]["table_presence_ratio"] >= 0
    assert "current_table_roster" in summary
    assert summary["peak_table_roster"]["table_count"] >= 1
    assert summary["peak_table_roster"]["roster"]
    assert summary["table_presence_roster"]
    assert "low_confidence_segments" in summary
    assert "quality_flags" in summary


def test_summarize_tavr_metrics_flags_early_terminal_stage() -> None:
    metrics = [
        _metric(0, 0, "room_prep_drape"),
        _metric(1, 10, "access_sheathing"),
        _metric(2, 20, "closure_finish"),
        _metric(3, 100, "closure_finish"),
    ]

    summary = summarize_tavr_metrics(metrics)

    assert {
        flag["code"] for flag in summary["quality_flags"]
    } >= {"early_terminal_stage"}


def test_parse_roi_accepts_normalized_crop() -> None:
    assert parse_roi("0.1,0.2,0.8,0.9") == (0.1, 0.2, 0.8, 0.9)


def test_parse_roi_rejects_invalid_crop() -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        parse_roi("0.8,0.2,0.1,0.9")


def _metric(frame_index: int, timestamp_s: float, stage: str) -> FrameMetrics:
    return FrameMetrics(
        frame_index=frame_index,
        timestamp_s=timestamp_s,
        tavr=TAVRFrameState(
            stage=stage,
            stage_label=TAVR_STAGE_LABELS[stage],
            confidence=0.8,
            table_count=0,
            table_track_ids=[],
            role_counts={},
            role_track_ids={},
            track_role_summaries={},
            signals={},
            note=TAVR_STAGE_NOTES[stage],
        ),
    )
