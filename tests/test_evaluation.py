import argparse
from pathlib import Path
from typing import List, Optional

import pytest

from evaluate_tavr import parse_roi
from or_tracking import MotionTrackerConfig, process_video_file
from or_tracking.evaluation import (
    procedure_event_timeline,
    procedure_milestones,
    procedure_status_summary,
    score_tavr_metrics,
    stage_evidence_summary,
    stage_handoff_summary,
    stage_staffing_summary,
    stage_table_coverage,
    summarize_tavr_metrics,
    table_presence_intervals,
    table_transition_events,
    view_segments,
    write_tavr_summary_csvs,
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
    assert "last_observed_table_roster" in summary
    assert summary["peak_table_roster"]["table_count"] >= 1
    assert summary["peak_table_roster"]["roster"]
    assert summary["table_roster_snapshots"]
    assert summary["table_presence_roster"]
    assert summary["table_presence_intervals"]
    assert summary["view_segments"]
    assert summary["table_transition_events"]
    assert summary["stage_table_coverage"]
    assert summary["stage_handoff_summary"]
    assert summary["stage_evidence_summary"]
    assert summary["procedure_status_summary"]
    assert summary["procedure_milestones"]
    assert summary["procedure_event_timeline"]
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


def test_summarize_tavr_metrics_flags_low_motion_room_view() -> None:
    metrics = [
        _metric(index, index / 10, "access_sheathing", view_colorfulness=35.0)
        for index in range(70)
    ]

    summary = summarize_tavr_metrics(metrics)

    low_motion = [
        flag
        for flag in summary["quality_flags"]
        if flag["code"] == "low_motion_room_view"
    ]
    assert low_motion
    assert low_motion[0]["frames"] == 70
    assert low_motion[0]["peak_people_count"] == 0
    assert low_motion[0]["peak_table_count"] == 0


def test_summarize_tavr_metrics_flags_low_stage_confidence() -> None:
    metrics = [
        _metric(index, index / 10, "valve_deployment", confidence=0.2)
        for index in range(8)
    ] + [
        _metric(8, 0.8, "valve_deployment", confidence=0.8),
        _metric(9, 0.9, "valve_deployment", confidence=0.8),
    ]

    summary = summarize_tavr_metrics(metrics)

    low_confidence = [
        flag
        for flag in summary["quality_flags"]
        if flag["code"] == "low_stage_confidence"
    ]
    assert low_confidence
    assert low_confidence[0]["frames"] == 8
    assert low_confidence[0]["ratio"] == 0.8
    assert low_confidence[0]["confidence_threshold"] == 0.45


def test_view_segments_group_room_and_non_room_stretches() -> None:
    metrics = [
        _metric(0, 0.0, "valve_deployment", view_colorfulness=34.0),
        _metric(1, 0.1, "valve_deployment", view_colorfulness=35.0),
        _metric(
            2,
            0.2,
            "valve_deployment",
            alert_flags=["non_room_view"],
            view_colorfulness=1.4,
        ),
        _metric(
            3,
            0.3,
            "valve_deployment",
            alert_flags=["non_room_view"],
            view_colorfulness=1.2,
        ),
        _metric(4, 0.4, "closure_finish", view_colorfulness=36.0),
    ]

    segments = view_segments(metrics)

    assert [item["view"] for item in segments] == ["room", "non_room", "room"]
    assert segments[0]["tracking_available"] is True
    assert segments[1]["tracking_available"] is False
    assert segments[1]["frames"] == 2
    assert segments[1]["mean_colorfulness"] == 1.3
    assert segments[2]["dominant_stage"] == "closure_finish"


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


def test_stage_table_coverage_reports_room_view_denominator() -> None:
    metrics = [
        _table_metric(
            0,
            0.0,
            "valve_deployment",
            [],
            alert_flags=["non_room_view"],
        ),
        _table_metric(
            1,
            0.1,
            "valve_deployment",
            [],
            alert_flags=["non_room_view"],
        ),
        _table_metric(2, 0.2, "valve_deployment", [7]),
        _table_metric(3, 0.3, "valve_deployment", [7]),
        _table_metric(4, 0.4, "valve_deployment", []),
    ]

    coverage = stage_table_coverage(metrics)

    assert len(coverage) == 1
    assert coverage[0]["stage_room_view_frames"] == 3
    assert coverage[0]["stage_non_room_view_frames"] == 2
    assert coverage[0]["tracking_available_rate"] == 0.6
    assert coverage[0]["coverage_ratio"] == 0.4
    assert coverage[0]["room_coverage_ratio"] == 0.667


def test_stage_handoff_summary_reports_boundary_roster_changes() -> None:
    metrics = [
        _table_metric(0, 0.0, "access_sheathing", [7]),
        _table_metric(1, 0.1, "access_sheathing", [7]),
        _table_metric(2, 0.2, "valve_deployment", [7]),
        _table_metric(3, 0.3, "valve_deployment", [7, 8]),
        _table_metric(4, 0.4, "valve_deployment", [8]),
        _table_metric(5, 0.5, "closure_finish", []),
        _table_metric(6, 0.6, "closure_finish", []),
    ]

    handoffs = stage_handoff_summary(metrics)

    assert [item["handoff_type"] for item in handoffs] == [
        "initial_table_roster",
        "roster_added",
        "table_cleared",
    ]
    assert handoffs[0]["lead_track_id"] == 7
    assert handoffs[1]["continued_track_ids"] == [7]
    assert handoffs[1]["new_track_ids"] == [8]
    assert handoffs[1]["active_table_track_count"] == 2
    assert handoffs[1]["lead_role"] == "table_operator"
    assert handoffs[2]["dropped_track_ids"] == [7, 8]
    assert handoffs[2]["active_table_roster"] == []
    assert handoffs[2]["dropped_table_roster"]


def test_procedure_event_timeline_combines_stage_view_handoff_and_peak() -> None:
    metrics = [
        _table_metric(0, 0.0, "access_sheathing", [], alert_flags=["non_room_view"]),
        _table_metric(1, 0.1, "access_sheathing", []),
        _table_metric(2, 0.2, "valve_deployment", [7]),
        _table_metric(3, 0.3, "valve_deployment", [7, 8]),
    ]

    events = procedure_event_timeline(metrics)

    assert events[0]["event_type"] == "stage_started"
    assert events[0]["stage"] == "access_sheathing"
    assert any(
        event["event_type"] == "view_started"
        and event["view"] == "room"
        and event["timestamp_s"] == 0.1
        for event in events
    )
    assert any(
        event["event_type"] == "table_handoff"
        and event["handoff_type"] == "table_roster_started"
        and event["table_count"] == 2
        for event in events
    )
    assert any(
        event["event_type"] == "table_peak"
        and event["stage"] == "valve_deployment"
        and event["table_count"] == 2
        for event in events
    )


def test_stage_evidence_summary_marks_room_support_and_non_room_holds() -> None:
    metrics = [
        _table_metric(0, 0.0, "valve_delivery_positioning", [], alert_flags=["non_room_view"]),
        _table_metric(1, 0.1, "valve_delivery_positioning", [], alert_flags=["non_room_view"]),
        _table_metric(2, 0.2, "valve_deployment", [7]),
        _table_metric(3, 0.3, "valve_deployment", [7, 8]),
    ]

    evidence = stage_evidence_summary(metrics)

    assert [item["stage"] for item in evidence] == [
        "valve_delivery_positioning",
        "valve_deployment",
    ]
    assert evidence[0]["evidence_level"] == "held_non_room"
    assert evidence[0]["observable_rate"] == 0.0
    assert evidence[0]["non_room_view_frames"] == 2
    assert evidence[1]["evidence_level"] == "strong_visual_support"
    assert evidence[1]["observable_rate"] == 1.0
    assert evidence[1]["mean_confidence"] == 0.8


def test_procedure_milestones_report_current_observed_stage() -> None:
    metrics = [
        _table_metric(0, 0.0, "access_sheathing", [7]),
        _table_metric(1, 0.1, "access_sheathing", [7]),
        _table_metric(2, 0.2, "valve_deployment", [7, 8]),
        _table_metric(3, 0.3, "valve_deployment", [8]),
    ]

    milestones = procedure_milestones(metrics)

    access = next(item for item in milestones if item["stage"] == "access_sheathing")
    deployment = next(item for item in milestones if item["stage"] == "valve_deployment")
    closure = next(item for item in milestones if item["stage"] == "closure_finish")
    assert access["milestone_status"] == "observed_prior"
    assert access["observed_in_clip"] is True
    assert deployment["milestone_status"] == "current_observed"
    assert deployment["is_current_observed_stage"] is True
    assert deployment["peak_table_count"] == 2
    assert deployment["unique_table_track_count"] == 2
    assert deployment["evidence_level"] == "strong_visual_support"
    assert closure["milestone_status"] == "not_observed_in_clip"
    assert closure["observed_in_clip"] is False


def test_procedure_status_summary_reports_current_stage_and_table_roster() -> None:
    metrics = [
        _table_metric(0, 0.0, "access_sheathing", [7]),
        _table_metric(1, 0.1, "valve_deployment", [7, 8]),
        _table_metric(
            2,
            0.2,
            "closure_finish",
            [],
            alert_flags=["non_room_view"],
        ),
    ]

    status = procedure_status_summary(metrics)[0]

    assert status["current_stage"] == "closure_finish"
    assert status["current_stage_status"] == "current_observed"
    assert status["next_stage"] is None
    assert status["current_view"] == "non_room"
    assert status["tracking_available"] is False
    assert status["current_table_count"] == 0
    assert status["current_table_track_ids"] == []
    assert status["last_observed_stage"] == "valve_deployment"
    assert status["last_observed_table_count"] == 2
    assert status["last_observed_table_track_ids"] == [7, 8]
    assert status["peak_table_count"] == 2
    assert status["peak_table_track_ids"] == [7, 8]
    assert "Current observed stage: Closure / finish" in status["operator_summary"]
    assert "last observed table: ID 7" in status["operator_summary"]


def test_table_transition_events_report_stage_entries_and_exits() -> None:
    metrics = [
        _table_metric(0, 0.0, "access_sheathing", [7]),
        _table_metric(1, 0.1, "access_sheathing", [7]),
        _table_metric(2, 0.2, "valve_deployment", [7]),
        _table_metric(3, 0.3, "valve_deployment", [7, 8]),
        _table_metric(4, 0.4, "valve_deployment", [8]),
    ]

    events = table_transition_events(metrics, min_observed_table_frames=1)

    assert [
        (item["event_type"], item["stage"], item["track_id"])
        for item in events
    ] == [
        ("table_present_at_stage_start", "access_sheathing", 7),
        ("table_present_at_stage_end", "access_sheathing", 7),
        ("table_present_at_stage_start", "valve_deployment", 7),
        ("table_entry", "valve_deployment", 8),
        ("table_exit", "valve_deployment", 7),
        ("table_present_at_stage_end", "valve_deployment", 8),
    ]
    assert events[2]["room_coverage_ratio"] == 0.667
    assert events[2]["tracking_available_rate"] == 1.0


def test_last_observed_table_roster_survives_non_room_or_quiet_end() -> None:
    metrics = [
        _table_metric(0, 0.0, "valve_deployment", [7]),
        _table_metric(1, 0.1, "valve_deployment", [7, 8]),
        _table_metric(2, 0.2, "valve_deployment", []),
        _table_metric(
            3,
            0.3,
            "valve_deployment",
            [],
            alert_flags=["non_room_view"],
        ),
    ]

    summary = summarize_tavr_metrics(metrics)

    assert summary["current_table_roster"] == []
    last_roster = summary["last_observed_table_roster"]
    assert last_roster["frame_index"] == 1
    assert last_roster["timestamp_s"] == 0.1
    assert last_roster["age_from_clip_end_s"] == 0.2
    assert last_roster["table_count"] == 2
    assert [item["track_id"] for item in last_roster["roster"]] == [7, 8]
    snapshot_keys = [
        (item["snapshot_type"], item["track_id"])
        for item in summary["table_roster_snapshots"]
    ]
    assert snapshot_keys == [
        ("last_observed", 7),
        ("last_observed", 8),
        ("peak", 7),
        ("peak", 8),
    ]


def test_stage_staffing_summary_reports_room_view_rates() -> None:
    metrics = [
        _table_metric(
            0,
            0.0,
            "valve_deployment",
            [],
            alert_flags=["non_room_view"],
        ),
        _table_metric(
            1,
            0.1,
            "valve_deployment",
            [],
            alert_flags=["non_room_view"],
        ),
        _table_metric(2, 0.2, "valve_deployment", [7]),
        _table_metric(3, 0.3, "valve_deployment", [7]),
        _table_metric(4, 0.4, "valve_deployment", []),
    ]

    staffing = stage_staffing_summary(metrics, min_observed_table_frames=1)

    assert len(staffing) == 1
    assert staffing[0]["frames"] == 5
    assert staffing[0]["room_view_frames"] == 3
    assert staffing[0]["non_room_view_frames"] == 2
    assert staffing[0]["tracking_available_rate"] == 0.6
    assert staffing[0]["mean_table_count"] == 0.4
    assert staffing[0]["mean_room_table_count"] == 0.667
    assert staffing[0]["table_occupancy_rate"] == 0.4
    assert staffing[0]["room_table_occupancy_rate"] == 0.667


def test_write_tavr_summary_csvs_exports_derived_tables(tmp_path: Path) -> None:
    metrics = [
        _table_metric(0, 0.0, "access_sheathing", [7]),
        _table_metric(1, 0.1, "access_sheathing", [7]),
        _table_metric(2, 0.2, "access_sheathing", [7]),
        _table_metric(3, 0.3, "valve_deployment", [7, 8]),
        _table_metric(4, 0.4, "valve_deployment", [7, 8]),
        _table_metric(5, 0.5, "valve_deployment", [7, 8]),
    ]
    summary = summarize_tavr_metrics(metrics)

    paths = write_tavr_summary_csvs(tmp_path, "case", summary)

    assert {
        "stage_timeline",
        "stage_table_coverage",
        "stage_handoff_summary",
        "stage_evidence_summary",
        "procedure_status_summary",
        "procedure_milestones",
        "procedure_event_timeline",
        "table_roster_snapshots",
        "table_transition_events",
        "view_segments",
    }.issubset(paths)
    coverage_csv = Path(paths["stage_table_coverage"]).read_text(encoding="utf-8")
    staffing_csv = Path(paths["stage_staffing_summary"]).read_text(encoding="utf-8")
    handoff_csv = Path(paths["stage_handoff_summary"]).read_text(encoding="utf-8")
    evidence_csv = Path(paths["stage_evidence_summary"]).read_text(encoding="utf-8")
    status_csv = Path(paths["procedure_status_summary"]).read_text(encoding="utf-8")
    milestones_csv = Path(paths["procedure_milestones"]).read_text(encoding="utf-8")
    event_csv = Path(paths["procedure_event_timeline"]).read_text(encoding="utf-8")
    snapshots_csv = Path(paths["table_roster_snapshots"]).read_text(encoding="utf-8")
    assert "track_id" in coverage_csv
    assert "coverage_ratio" in coverage_csv
    assert "room_coverage_ratio" in coverage_csv
    assert "tracking_available_rate" in staffing_csv
    assert "room_table_occupancy_rate" in staffing_csv
    assert "handoff_type" in handoff_csv
    assert "roster_added" in handoff_csv
    assert "evidence_level" in evidence_csv
    assert "strong_visual_support" in evidence_csv
    assert "operator_summary" in status_csv
    assert "Current observed stage" in status_csv
    assert "milestone_status" in milestones_csv
    assert "current_observed" in milestones_csv
    assert "event_type" in event_csv
    assert "table_handoff" in event_csv
    assert "snapshot_type" in snapshots_csv
    assert "last_observed" in snapshots_csv
    assert "ID 7" in coverage_csv


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
                "min_tracking_available_rate": 0.5,
                "min_room_mean_count": 1.0,
                "min_room_table_occupancy_rate": 1.0,
            }
        ],
        "stage_handoff_expectations": [
            {
                "stage": "valve_deployment",
                "role": "table_operator",
                "handoff_type": "roster_changed",
                "lead_role": "table_operator",
                "min_active_tracks": 2,
                "min_new_tracks": 2,
                "min_dropped_tracks": 1,
                "min_lead_observed_table_frames": 2,
            }
        ],
        "stage_evidence_expectations": [
            {
                "stage": "access_sheathing",
                "evidence_level": "held_non_room",
                "max_observable_rate": 0.0,
                "min_non_room_view_frames": 3,
            },
            {
                "stage": "valve_deployment",
                "evidence_level": "strong_visual_support",
                "min_observable_rate": 1.0,
                "min_mean_confidence": 0.7,
                "min_room_view_frames": 2,
            },
        ],
        "procedure_milestone_expectations": [
            {
                "stage": "access_sheathing",
                "milestone_status": "observed_prior",
                "observed_in_clip": True,
                "evidence_level": "held_non_room",
                "max_observable_rate": 0.0,
                "max_unique_table_track_count": 1,
            },
            {
                "stage": "valve_deployment",
                "milestone_status": "observed_prior",
                "observed_in_clip": True,
                "evidence_level": "strong_visual_support",
                "min_peak_table_count": 2,
                "min_unique_table_track_count": 2,
            },
            {
                "stage": "closure_finish",
                "milestone_status": "current_observed",
                "is_current_observed_stage": True,
                "observed_in_clip": True,
                "min_peak_table_count": 1,
            },
        ],
        "procedure_status_expectations": [
            {
                "current_stage": "closure_finish",
                "current_stage_status": "current_observed",
                "next_stage": None,
                "current_view": "room",
                "tracking_available": True,
                "evidence_level": "strong_visual_support",
                "min_current_table_count": 1,
                "min_last_observed_table_count": 1,
                "max_last_observed_age_from_clip_end_s": 0.0,
                "min_peak_table_count": 2,
                "required_quality_flags": ["non_room_view"],
            }
        ],
        "event_timeline_expectations": [
            {
                "event_type": "table_handoff",
                "stage": "valve_deployment",
                "handoff_type": "roster_changed",
                "role": "table_operator",
                "min_tracks": 2,
                "min_table_count": 2,
            },
            {
                "event_type": "table_peak",
                "stage": "valve_deployment",
                "role": "table_operator",
                "min_tracks": 2,
                "min_table_count": 2,
            },
        ],
        "roster_snapshot_expectations": [
            {
                "snapshot_type": "last_observed",
                "role": "table_operator",
                "min_tracks": 1,
                "min_table_count": 1,
                "max_age_from_clip_end_s": 0.1,
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
    assert score["stage_handoff_score"]["pass_rate"] == 1.0
    assert score["stage_handoff_score"]["expectations"][0]["matched_count"] == 1
    assert score["stage_evidence_score"]["pass_rate"] == 1.0
    assert score["stage_evidence_score"]["expectations"][1]["matched_count"] == 1
    assert score["procedure_milestone_score"]["pass_rate"] == 1.0
    assert score["procedure_milestone_score"]["expectations"][2]["matched_count"] == 1
    assert score["procedure_status_score"]["pass_rate"] == 1.0
    assert score["procedure_status_score"]["expectations"][0]["matched_count"] == 1
    assert score["event_timeline_score"]["pass_rate"] == 1.0
    assert score["event_timeline_score"]["expectations"][0]["matched_count"] == 1
    assert score["roster_snapshot_score"]["pass_rate"] == 1.0
    assert score["roster_snapshot_score"]["expectations"][0]["matched_count"] == 1
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
    view_colorfulness: float = 0.0,
    confidence: float = 0.8,
) -> FrameMetrics:
    return FrameMetrics(
        frame_index=frame_index,
        timestamp_s=timestamp_s,
        alert_flags=alert_flags or [],
        view_colorfulness=view_colorfulness,
        tavr=TAVRFrameState(
            stage=stage,
            stage_label=TAVR_STAGE_LABELS[stage],
            confidence=confidence,
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
