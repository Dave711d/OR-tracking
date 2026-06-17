import argparse
from pathlib import Path
from typing import List, Optional

import pytest

from evaluate_tavr import parse_roi
from or_tracking import MotionTrackerConfig, process_video_file
from or_tracking.evaluation import (
    score_tavr_metrics,
    stage_table_coverage,
    summarize_tavr_metrics,
    table_presence_intervals,
)
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
    assert summary["table_presence_intervals"]
    assert summary["stage_table_coverage"]
    assert summary["stage_staffing_summary"]
    assert any(
        item["table_presence_roster"]
        for item in summary["stage_timeline"]
    )
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


def test_summarize_tavr_metrics_flags_non_room_view() -> None:
    metrics = [
        _metric(0, 0.0, "valve_deployment", alert_flags=["non_room_view"]),
        _metric(1, 0.1, "valve_deployment", alert_flags=["non_room_view"]),
        _metric(2, 0.2, "valve_deployment"),
        _metric(3, 0.3, "valve_deployment"),
    ]

    summary = summarize_tavr_metrics(metrics)

    non_room = [
        flag for flag in summary["quality_flags"] if flag["code"] == "non_room_view"
    ]
    assert non_room
    assert non_room[0]["frames"] == 2
    assert non_room[0]["ratio"] == 0.5


def test_table_presence_intervals_group_by_track_and_gap() -> None:
    metrics = [
        _table_metric(0, 0.0, "access_sheathing", [7]),
        _table_metric(1, 0.1, "access_sheathing", [7]),
        _table_metric(20, 2.0, "valve_deployment", [7]),
        _table_metric(21, 2.1, "valve_deployment", [7]),
        _table_metric(22, 2.2, "valve_deployment", [9]),
    ]

    intervals = table_presence_intervals(
        metrics,
        max_gap_frames=3,
        max_gap_s=0.5,
        min_observed_table_frames=1,
    )

    assert [item["track_id"] for item in intervals] == [7, 7, 9]
    assert intervals[0]["dominant_stage"] == "access_sheathing"
    assert intervals[0]["observed_table_frames"] == 2
    assert intervals[0]["interval_duration_s"] == 0.2
    assert intervals[1]["dominant_stage"] == "valve_deployment"
    assert intervals[2]["dominant_role"] == "table_operator"


def test_stage_table_coverage_splits_tracks_by_stage_segment() -> None:
    metrics = [
        _table_metric(0, 0.0, "access_sheathing", [7]),
        _table_metric(1, 0.1, "access_sheathing", [7]),
        _table_metric(2, 0.2, "valve_deployment", [7]),
        _table_metric(3, 0.3, "valve_deployment", [7, 8]),
        _table_metric(4, 0.4, "valve_deployment", [8]),
    ]

    coverage = stage_table_coverage(metrics)

    assert [(item["stage"], item["track_id"]) for item in coverage] == [
        ("access_sheathing", 7),
        ("valve_deployment", 7),
        ("valve_deployment", 8),
    ]
    assert coverage[0]["spans_full_stage"] is True
    assert coverage[1]["coverage_ratio"] == 0.667
    assert coverage[1]["entered_during_stage"] is False
    assert coverage[1]["exited_during_stage"] is True
    assert coverage[2]["entered_during_stage"] is True
    assert coverage[2]["exited_during_stage"] is False


def test_score_tavr_metrics_compares_stage_table_count_and_presence() -> None:
    metrics = [
        _table_metric(0, 0.0, "access_sheathing", [7]),
        _table_metric(1, 0.1, "access_sheathing", [7]),
        _table_metric(2, 0.2, "access_sheathing", []),
        _table_metric(20, 2.0, "valve_deployment", [9, 10]),
        _table_metric(21, 2.1, "valve_deployment", [9, 10]),
        _table_metric(22, 2.2, "closure_finish", [9]),
    ]
    labels = {
        "stage_segments": [
            {"start_s": 0.0, "end_s": 0.2, "stage": "access_sheathing"},
            {"start_s": 2.0, "end_s": 2.2, "stage": "valve_deployment"},
        ],
        "table_count_segments": [
            {"start_s": 0.0, "end_s": 0.1, "min_count": 1},
            {"start_s": 2.0, "end_s": 2.1, "min_count": 2},
            {"start_s": 0.0, "end_s": 2.2, "min_peak_count": 2},
        ],
        "table_presence_expectations": [
            {
                "start_s": 2.0,
                "end_s": 2.2,
                "role": "table_operator",
                "min_intervals": 1,
                "min_observed_table_frames": 3,
            }
        ],
        "stage_staffing_expectations": [
            {
                "stage": "valve_deployment",
                "role": "table_operator",
                "min_tracks": 2,
                "min_observed_table_frames": 2,
                "min_peak_count": 2,
                "min_table_occupancy_rate": 1.0,
            }
        ],
        "quality_flag_expectations": [
            {"code": "non_room_view", "min_ratio": 0.5}
        ],
    }
    metrics[0].alert_flags.append("non_room_view")
    metrics[1].alert_flags.append("non_room_view")
    metrics[2].alert_flags.append("non_room_view")

    score = score_tavr_metrics(metrics, labels)

    assert score["stage_score"]["covered_frames"] == 6
    assert score["stage_score"]["accuracy"] == 0.833
    assert score["stage_score"]["confusion"]["valve_deployment"]["closure_finish"] == 1
    assert score["table_count_score"]["pass_rate"] == 1.0
    assert score["table_presence_score"]["pass_rate"] == 1.0
    assert score["table_presence_score"]["expectations"][0]["matched_count"] == 1
    assert score["stage_staffing_score"]["pass_rate"] == 1.0
    assert score["stage_staffing_score"]["expectations"][0]["matched_track_count"] == 2
    assert score["quality_flag_score"]["pass_rate"] == 1.0


def test_parse_roi_accepts_normalized_crop() -> None:
    assert parse_roi("0.1,0.2,0.8,0.9") == (0.1, 0.2, 0.8, 0.9)


def test_parse_roi_rejects_invalid_crop() -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        parse_roi("0.8,0.2,0.1,0.9")


def _metric(
    frame_index: int,
    timestamp_s: float,
    stage: str,
    alert_flags: Optional[List[str]] = None,
) -> FrameMetrics:
    return FrameMetrics(
        frame_index=frame_index,
        timestamp_s=timestamp_s,
        alert_flags=alert_flags or [],
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


def _table_metric(
    frame_index: int,
    timestamp_s: float,
    stage: str,
    table_track_ids: list[int],
) -> FrameMetrics:
    return FrameMetrics(
        frame_index=frame_index,
        timestamp_s=timestamp_s,
        tavr=TAVRFrameState(
            stage=stage,
            stage_label=TAVR_STAGE_LABELS[stage],
            confidence=0.8,
            table_count=len(table_track_ids),
            table_track_ids=table_track_ids,
            role_counts={"table_operator": len(table_track_ids)},
            role_track_ids={"table_operator": table_track_ids},
            track_role_summaries={
                track_id: _track_summary(track_id, frame_index)
                for track_id in table_track_ids
            },
            signals={},
            note=TAVR_STAGE_NOTES[stage],
        ),
    )


def _track_summary(track_id: int, frame_index: int):
    from or_tracking.tavr import TrackRoleSummary

    return TrackRoleSummary(
        track_id=track_id,
        dominant_role="table_operator",
        frames_seen=1,
        first_frame=frame_index,
        last_frame=frame_index,
        table_frames=1,
        role_counts={"table_operator": 1},
    )
