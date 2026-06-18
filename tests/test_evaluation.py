import argparse
import sys
from pathlib import Path
from typing import List, Optional

import pytest

import or_tracking.evaluation as evaluation_module
from evaluate_tavr import parse_args, parse_roi
from or_tracking import MotionTrackerConfig, process_video_file
from or_tracking.evaluation import (
    operator_status_snapshots,
    operator_stage_packet,
    procedure_event_timeline,
    procedure_milestones,
    procedure_status_summary,
    score_tavr_metrics,
    stage_evidence_summary,
    stage_handoff_summary,
    stage_roster_summary,
    stage_staffing_summary,
    stage_table_coverage,
    summarize_tavr_metrics,
    table_presence_intervals,
    table_team_summary,
    table_transition_events,
    view_segments,
    write_tavr_summary_csvs,
)
from or_tracking.models import Detection, FrameMetrics
from or_tracking.synthetic import generate_synthetic_tavr_video
from or_tracking.tavr import (
    TAVR_STAGE_LABELS,
    TAVR_STAGE_NOTES,
    TAVR_STAGE_ORDER,
    TAVRFrameState,
)


def test_evaluate_tavr_cli_accepts_static_table_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["evaluate_tavr.py", "clip.mp4", "--static-table-fallback"],
    )

    args = parse_args()

    assert args.video == Path("clip.mp4")
    assert args.static_table_fallback is True


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
    assert summary["stage_roster_summary"]
    assert summary["operator_stage_packet"]
    assert summary["operator_status_snapshots"]
    assert summary["stage_evidence_summary"]
    assert summary["procedure_status_summary"]
    assert summary["table_team_summary"]
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


def test_score_tavr_metrics_respects_label_timebase() -> None:
    metrics = [
        _table_metric(300, 10.0, "access_sheathing", [7]),
        _table_metric(301, 10.1, "access_sheathing", [7]),
    ]
    metrics[0].clip_frame_index = 0
    metrics[0].clip_timestamp_s = 0.0
    metrics[1].clip_frame_index = 1
    metrics[1].clip_timestamp_s = 0.1

    clip_score = score_tavr_metrics(
        metrics,
        {
            "timebase": "clip",
            "stage_segments": [
                {"start_s": 0.0, "end_s": 0.1, "stage": "access_sheathing"}
            ],
            "table_count_segments": [
                {"start_s": 0.0, "end_s": 0.1, "min_count": 1}
            ],
        },
    )
    source_score = score_tavr_metrics(
        metrics,
        {
            "timebase": "source",
            "stage_segments": [
                {"start_s": 10.0, "end_s": 10.1, "stage": "access_sheathing"}
            ],
            "table_count_segments": [
                {"start_s": 10.0, "end_s": 10.1, "min_count": 1}
            ],
        },
    )

    assert clip_score["timebase"]["label_timebase"] == "clip"
    assert clip_score["stage_score"]["accuracy"] == 1.0
    assert clip_score["table_count_score"]["pass_rate"] == 1.0
    assert source_score["timebase"]["label_timebase"] == "source"
    assert source_score["stage_score"]["accuracy"] == 1.0
    assert source_score["table_count_score"]["pass_rate"] == 1.0


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


def test_stage_roster_summary_reports_per_stage_table_team() -> None:
    metrics = [
        _table_metric(0, 0.0, "access_sheathing", [7]),
        _table_metric(1, 0.1, "access_sheathing", [7]),
        _table_metric(2, 0.2, "valve_deployment", [7]),
        _table_metric(3, 0.3, "valve_deployment", [7, 8]),
        _table_metric(4, 0.4, "valve_deployment", [8]),
        _table_metric(5, 0.5, "closure_finish", []),
    ]

    rosters = stage_roster_summary(metrics)

    assert [item["stage"] for item in rosters] == [
        "access_sheathing",
        "valve_deployment",
        "closure_finish",
    ]
    assert rosters[0]["active_table_track_ids"] == [7]
    assert rosters[0]["lead_track_id"] == 7
    assert rosters[0]["peak_table_count"] == 1
    assert rosters[0]["handoff_type"] == "initial_table_roster"
    assert rosters[1]["active_table_track_ids"] == [7, 8]
    assert rosters[1]["continued_track_ids"] == [7]
    assert rosters[1]["new_track_ids"] == [8]
    assert rosters[1]["within_stage_entry_track_ids"] == [8]
    assert rosters[1]["within_stage_exit_track_ids"] == [7]
    assert rosters[1]["peak_table_count"] == 2
    assert rosters[1]["active_table_track_count"] == 2
    assert rosters[1]["canonical_table_identity_count"] == 2
    assert "ID 7 table_operator" in rosters[1]["roster_summary"]
    assert "peak table 2" in rosters[1]["label"]
    assert rosters[2]["active_table_track_ids"] == []
    assert rosters[2]["dropped_track_ids"] == [7, 8]
    assert rosters[2]["roster_summary"] == "none"


def test_operator_stage_packet_rolls_up_current_stage_and_table_context() -> None:
    metrics = [
        _table_metric(0, 0.0, "access_sheathing", [7]),
        _table_metric(1, 0.1, "access_sheathing", [7]),
        _table_metric(2, 0.2, "valve_deployment", [7, 8]),
        _table_metric(3, 0.3, "valve_deployment", [7, 8]),
        _table_metric(
            4,
            0.4,
            "closure_finish",
            [],
            alert_flags=["non_room_view"],
        ),
    ]

    packets = operator_stage_packet(metrics)

    assert [item["stage"] for item in packets] == [
        "access_sheathing",
        "valve_deployment",
        "closure_finish",
    ]
    assert packets[1]["stage_status"] == "observed_prior"
    assert packets[1]["stage_table_track_count"] == 2
    assert packets[1]["stage_table_track_ids"] == [7, 8]
    assert packets[1]["stage_table_canonical_ids"] == [1, 2]
    assert packets[1]["active_table_track_ids"] == [7, 8]
    assert packets[1]["handoff_type"] == "roster_added"
    assert "Valve deployment" in packets[1]["operator_packet"]
    assert "stage roster people Person 1, Person 2 (raw IDs 7, 8)" in (
        packets[1]["operator_packet"]
    )
    assert "active people" not in packets[1]["operator_packet"]

    current = packets[-1]
    assert current["is_current_stage"] is True
    assert current["stage_status"] == "current_held_context"
    assert current["stage_evidence_status"] == "held_non_room_context"
    assert current["stage_evidence_label"] == "held from non-room context"
    assert current["handoff_type"] == "table_cleared"
    assert current["stage_table_track_count"] == 0
    assert current["stage_table_track_ids"] == []
    assert current["effective_table_source"] == "last_observed_room_view"
    assert current["effective_table_track_ids"] == [7, 8]
    assert current["effective_table_canonical_ids"] == [1, 2]
    assert "Current held stage: Closure / finish" in current["operator_packet"]
    assert "stage support held from non-room context" in current["operator_packet"]
    assert "stage roster people none" in current["operator_packet"]
    assert "latest table status last observed room view 2 people Person 1, Person 2" in (
        current["operator_packet"]
    )


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
    deployment_start = next(
        event
        for event in events
        if event["event_type"] == "stage_started"
        and event["stage"] == "valve_deployment"
    )
    assert deployment_start["table_canonical_ids"] == [1]
    assert deployment_start["roster"][0]["canonical_table_id"] == 1
    assert deployment_start["roster"][0]["label"].startswith("Person 1:")
    assert "people Person 1" in deployment_start["label"]
    assert any(
        event["event_type"] == "table_peak"
        and event["stage"] == "valve_deployment"
        and event["table_count"] == 2
        and event["table_canonical_ids"] == [1, 2]
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
    assert deployment["canonical_table_identity_count"] == 2
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
    packet = operator_stage_packet(metrics)[-1]
    milestones = procedure_milestones(metrics)
    closure = next(row for row in milestones if row["stage"] == "closure_finish")

    assert status["current_stage"] == "closure_finish"
    assert status["current_stage_status"] == "current_held_context"
    assert status["current_stage_evidence_status"] == "held_non_room_context"
    assert status["current_stage_evidence_label"] == "held from non-room context"
    assert closure["milestone_status"] == "current_held_context"
    assert packet["stage_status"] == "current_held_context"
    assert status["next_stage"] is None
    assert status["current_view"] == "non_room"
    assert status["tracking_available"] is False
    assert status["current_table_count"] == 0
    assert status["current_table_track_ids"] == []
    assert status["effective_table_source"] == "last_observed_room_view"
    assert status["effective_table_count"] == 2
    assert status["effective_table_track_ids"] == [7, 8]
    assert status["effective_table_age_from_clip_end_s"] == 0.1
    assert status["last_observed_stage"] == "valve_deployment"
    assert status["last_observed_table_count"] == 2
    assert status["last_observed_table_track_ids"] == [7, 8]
    assert status["peak_table_count"] == 2
    assert status["peak_table_track_ids"] == [7, 8]
    assert "Current held stage: Closure / finish" in status["operator_summary"]
    assert "Current held stage: Closure / finish" in packet["operator_packet"]
    assert "table status: last observed room view Person 1: ID 7" in (
        status["operator_summary"]
    )
    assert "last observed table: Person 1: ID 7" in status["operator_summary"]


def test_procedure_status_holds_recent_room_roster_when_current_frame_is_quiet() -> None:
    metrics = [
        _table_metric(0, 0.0, "valve_deployment", [7]),
        _table_metric(1, 0.1, "valve_deployment", [7]),
        _table_metric(2, 0.2, "valve_deployment", []),
    ]

    status = procedure_status_summary(metrics)[0]
    packet = operator_stage_packet(metrics)[-1]

    assert status["current_view"] == "room"
    assert status["tracking_available"] is True
    assert status["current_table_count"] == 0
    assert status["current_stage_evidence_status"] == "strong_visual_support"
    assert status["effective_table_source"] == "recent_room_view_hold"
    assert status["effective_table_count"] == 1
    assert status["effective_table_track_ids"] == [7]
    assert status["effective_table_age_from_clip_end_s"] == 0.1
    assert "table status: recent room view hold Person 1: ID 7" in (
        status["operator_summary"]
    )
    assert packet["effective_table_source"] == "recent_room_view_hold"
    assert packet["stage_evidence_status"] == "strong_visual_support"
    assert packet["effective_table_track_ids"] == [7]
    assert "latest table status recent room view hold 1 people Person 1" in (
        packet["operator_packet"]
    )


def test_procedure_status_uses_stable_recent_room_roster_when_table_drops_out() -> None:
    metrics = [
        _table_metric(0, 0.0, "valve_deployment", [7, 8, 9]),
        _table_metric(1, 0.1, "valve_deployment", [9]),
        _table_metric(
            2,
            0.2,
            "valve_deployment",
            [],
            alert_flags=["non_room_view"],
        ),
    ]

    status = procedure_status_summary(metrics)[0]

    assert status["current_view"] == "non_room"
    assert status["current_table_count"] == 0
    assert status["current_table_track_ids"] == []
    assert status["effective_table_source"] == "last_observed_room_view"
    assert status["effective_table_count"] == 3
    assert status["effective_table_track_ids"] == [7, 8, 9]
    assert status["effective_table_canonical_ids"] == [1, 2, 3]
    assert status["last_observed_table_count"] == 3
    assert status["last_observed_table_track_ids"] == [7, 8, 9]
    assert status["last_observed_table_canonical_ids"] == [1, 2, 3]


def test_effective_table_uses_current_stage_recent_window_for_partial_frame() -> None:
    metrics = [
        _table_metric(0, 0.0, "post_deploy_assessment", [7, 8]),
        _table_metric(1, 1.0, "closure_finish", [9, 10]),
        _table_metric(2, 2.0, "closure_finish", [9]),
    ]

    status = procedure_status_summary(metrics)[0]
    packet = operator_stage_packet(metrics)[-1]

    assert status["current_stage"] == "closure_finish"
    assert status["current_table_count"] == 1
    assert status["current_table_track_ids"] == [9]
    assert status["effective_table_source"] == "current_stage_recent_room_window"
    assert status["effective_table_count"] == 2
    assert status["effective_table_track_ids"] == [9, 10]
    assert len(status["effective_table_canonical_ids"]) == 2
    assert {
        item["track_id"] for item in status["effective_table_roster"]
    } == {9, 10}
    assert packet["effective_table_source"] == "current_stage_recent_room_window"
    assert packet["effective_table_track_ids"] == [9, 10]


def test_effective_table_window_does_not_pull_people_from_previous_stage() -> None:
    metrics = [
        _table_metric(0, 0.0, "post_deploy_assessment", [7, 8]),
        _table_metric(1, 1.0, "closure_finish", [9]),
    ]

    status = procedure_status_summary(metrics)[0]

    assert status["current_stage"] == "closure_finish"
    assert status["current_table_track_ids"] == [9]
    assert status["effective_table_source"] == "current_room_view"
    assert status["effective_table_count"] == 1
    assert status["effective_table_track_ids"] == [9]
    assert {
        item["track_id"] for item in status["effective_table_roster"]
    } == {9}


def test_operator_status_uses_canonical_table_people_for_fragmented_tracks() -> None:
    metrics = [
        _table_metric(
            0,
            0.0,
            "valve_deployment",
            [18],
            centroids_by_track={18: (100, 100)},
        ),
        _table_metric(
            1,
            0.1,
            "valve_deployment",
            [18],
            centroids_by_track={18: (102, 101)},
        ),
        _table_metric(
            2,
            0.2,
            "valve_deployment",
            [],
        ),
        _table_metric(
            3,
            0.3,
            "valve_deployment",
            [21],
            centroids_by_track={21: (106, 103)},
        ),
    ]

    status = procedure_status_summary(metrics)[0]
    packet = operator_stage_packet(metrics)[-1]

    assert status["current_table_track_ids"] == [21]
    assert status["current_table_canonical_ids"] == [1]
    assert status["effective_table_track_ids"] == [21]
    assert status["effective_table_canonical_ids"] == [1]
    assert status["peak_table_canonical_ids"] == [1]
    assert status["current_table_roster"][0]["canonical_table_id"] == 1
    assert status["current_table_roster"][0]["merged_track_ids"] == [18, 21]
    assert "Person 1: ID 21" in status["operator_summary"]
    assert packet["active_table_track_ids"] == [18]
    assert packet["active_table_canonical_ids"] == [1]
    assert packet["stage_table_track_ids"] == [18]
    assert packet["stage_table_canonical_ids"] == [1]
    assert packet["canonical_table_identity_count"] == 1
    assert "stage roster people Person 1 (raw IDs 18)" in packet["operator_packet"]
    assert "active people" not in packet["operator_packet"]
    assert "latest table status current room view 1 people Person 1" in (
        packet["operator_packet"]
    )
    snapshot_rows = summarize_tavr_metrics(metrics)["table_roster_snapshots"]
    assert snapshot_rows
    assert {
        (row["snapshot_type"], row["track_id"], row["canonical_table_id"])
        for row in snapshot_rows
    } == {
        ("current", 21, 1),
        ("last_observed", 21, 1),
        ("peak", 21, 1),
    }
    assert all(row["merged_track_ids"] == [18, 21] for row in snapshot_rows)


def test_operator_snapshot_score_combines_stage_table_and_canonical_people() -> None:
    metrics = [
        _table_metric(
            0,
            0.0,
            "access_sheathing",
            [18],
            centroids_by_track={18: (100, 100)},
        ),
        _table_metric(
            1,
            0.1,
            "valve_deployment",
            [18],
            centroids_by_track={18: (102, 101)},
        ),
        _table_metric(
            2,
            0.2,
            "valve_deployment",
            [],
        ),
        _table_metric(
            3,
            0.3,
            "valve_deployment",
            [21],
            centroids_by_track={21: (106, 103)},
        ),
    ]
    labels = {
        "operator_snapshot_expectations": [
            {
                "timestamp_s": 0.3,
                "tolerance_s": 0.01,
                "stage": "valve_deployment",
                "stage_evidence_status": "strong_visual_support",
                "current_view": "room",
                "tracking_available": True,
                "min_table_count": 1,
                "min_effective_table_count": 1,
                "required_current_canonical_table_ids": [1],
                "required_effective_canonical_table_ids": [1],
            }
        ]
    }

    score = score_tavr_metrics(metrics, labels)

    assert score["operator_snapshot_score"]["pass_rate"] == 1.0
    candidate = score["operator_snapshot_score"]["expectations"][0][
        "matched_candidates"
    ][0]
    assert candidate["current_stage"] == "valve_deployment"
    assert candidate["candidate_source"] == "operator_status_snapshots"
    assert "clip_end" in candidate["snapshot_reason"]
    assert candidate["current_table_canonical_ids"] == [1]
    assert candidate["effective_table_canonical_ids"] == [1]
    assert candidate["checks"]["required_current_canonical_table_ids"] is True


def test_operator_snapshot_score_rejects_unexported_middle_frame() -> None:
    metrics = [
        _table_metric(0, 0.0, "valve_deployment", [7]),
        _table_metric(1, 0.1, "valve_deployment", [7]),
        _table_metric(2, 0.2, "valve_deployment", [7]),
    ]
    assert [row["frame_index"] for row in operator_status_snapshots(metrics)] == [0, 2]

    score = score_tavr_metrics(
        metrics,
        {
            "operator_snapshot_expectations": [
                {
                    "timestamp_s": 0.1,
                    "tolerance_s": 0.01,
                    "stage": "valve_deployment",
                    "current_view": "room",
                    "tracking_available": True,
                    "min_table_count": 1,
                }
            ]
        },
    )

    expectation = score["operator_snapshot_score"]["expectations"][0]
    assert score["operator_snapshot_score"]["pass_rate"] == 0.0
    assert expectation["matched_count"] == 0
    assert expectation["matched_candidates"] == []
    assert expectation["passed"] is False


def test_operator_snapshot_score_can_require_snapshot_reason() -> None:
    metrics = [
        _table_metric(0, 0.0, "valve_deployment", [7]),
        _table_metric(1, 0.1, "valve_deployment", [7]),
        _table_metric(2, 0.2, "valve_deployment", [7]),
    ]

    score = score_tavr_metrics(
        metrics,
        {
            "operator_snapshot_expectations": [
                {
                    "timestamp_s": 0.2,
                    "tolerance_s": 0.01,
                    "stage": "valve_deployment",
                    "current_view": "room",
                    "tracking_available": True,
                    "min_table_count": 1,
                    "required_snapshot_reasons": ["clip_end", "last_observed_table"],
                }
            ]
        },
    )

    candidate = score["operator_snapshot_score"]["expectations"][0][
        "matched_candidates"
    ][0]
    assert score["operator_snapshot_score"]["pass_rate"] == 1.0
    assert candidate["checks"]["required_snapshot_reasons"] is True


def test_exact_procedure_status_canonical_people_rejects_extra_people() -> None:
    metrics = [
        _table_metric(0, 0.0, "valve_deployment", [7, 8]),
        _table_metric(1, 0.1, "valve_deployment", [7, 8]),
    ]
    actual_ids = procedure_status_summary(metrics)[0]["current_table_canonical_ids"]
    assert len(actual_ids) == 2

    score = score_tavr_metrics(
        metrics,
        {
            "procedure_status_expectations": [
                {
                    "current_stage": "valve_deployment",
                    "required_current_canonical_table_ids": [actual_ids[0]],
                    "expected_current_canonical_table_ids": [actual_ids[0]],
                }
            ]
        },
    )

    expectation = score["procedure_status_score"]["expectations"][0]
    candidate = expectation["matched_candidates"][0]
    assert score["procedure_status_score"]["pass_rate"] == 0.0
    assert candidate["checks"]["required_current_canonical_table_ids"] is True
    assert candidate["checks"]["expected_current_canonical_table_ids"] is False
    assert candidate["current_table_canonical_ids"] == actual_ids
    assert candidate["expected_current_canonical_table_ids"] == [actual_ids[0]]


def test_exact_operator_packet_canonical_people_rejects_extra_people() -> None:
    metrics = [
        _table_metric(0, 0.0, "valve_deployment", [7, 8]),
        _table_metric(1, 0.1, "valve_deployment", [7, 8]),
    ]
    actual_ids = operator_stage_packet(metrics)[0]["active_table_canonical_ids"]
    assert len(actual_ids) == 2

    score = score_tavr_metrics(
        metrics,
        {
            "operator_packet_expectations": [
                {
                    "stage": "valve_deployment",
                    "required_stage_table_canonical_ids": [actual_ids[0]],
                    "expected_stage_table_canonical_ids": [actual_ids[0]],
                    "required_active_canonical_table_ids": [actual_ids[0]],
                    "expected_active_canonical_table_ids": [actual_ids[0]],
                }
            ]
        },
    )

    expectation = score["operator_packet_score"]["expectations"][0]
    candidate = expectation["matched_candidates"][0]
    assert score["operator_packet_score"]["pass_rate"] == 0.0
    assert candidate["checks"]["required_active_canonical_table_ids"] is True
    assert candidate["checks"]["expected_active_canonical_table_ids"] is False
    assert candidate["checks"]["required_stage_table_canonical_ids"] is True
    assert candidate["checks"]["expected_stage_table_canonical_ids"] is False
    assert candidate["stage_table_canonical_ids"] == actual_ids
    assert candidate["expected_stage_table_canonical_ids"] == [actual_ids[0]]
    assert candidate["active_table_canonical_ids"] == actual_ids
    assert candidate["expected_active_canonical_table_ids"] == [actual_ids[0]]


def test_exact_roster_snapshot_canonical_people_rejects_extra_people() -> None:
    metrics = [
        _table_metric(0, 0.0, "valve_deployment", [7, 8]),
        _table_metric(1, 0.1, "valve_deployment", [7, 8]),
    ]
    actual_ids = sorted(
        {
            row["canonical_table_id"]
            for row in summarize_tavr_metrics(metrics)["table_roster_snapshots"]
            if row["snapshot_type"] == "current"
        }
    )
    assert len(actual_ids) == 2

    score = score_tavr_metrics(
        metrics,
        {
            "roster_snapshot_expectations": [
                {
                    "snapshot_type": "current",
                    "required_canonical_table_ids": [actual_ids[0]],
                    "expected_canonical_table_ids": [actual_ids[0]],
                }
            ]
        },
    )

    expectation = score["roster_snapshot_score"]["expectations"][0]
    assert score["roster_snapshot_score"]["pass_rate"] == 0.0
    assert expectation["checks"]["required_canonical_table_ids"] is True
    assert expectation["checks"]["expected_canonical_table_ids"] is False
    assert expectation["canonical_table_ids"] == actual_ids
    assert expectation["expected_canonical_table_ids"] == [actual_ids[0]]


def test_exact_stage_handoff_canonical_deltas_reject_wrong_boundary_person() -> None:
    metrics = [
        _table_metric(0, 0.0, "access_sheathing", [7, 8]),
        _table_metric(1, 0.1, "access_sheathing", [7, 8]),
        _table_metric(2, 0.2, "valve_deployment", [7, 9, 10]),
        _table_metric(3, 0.3, "valve_deployment", [7, 9, 10]),
    ]
    handoff = stage_handoff_summary(metrics)[1]
    assert handoff["continued_canonical_table_ids"]
    assert len(handoff["new_canonical_table_ids"]) == 2
    assert handoff["dropped_canonical_table_ids"]

    score = score_tavr_metrics(
        metrics,
        {
            "stage_handoff_expectations": [
                {
                    "stage": "valve_deployment",
                    "handoff_type": handoff["handoff_type"],
                    "expected_active_canonical_table_ids": handoff[
                        "active_table_canonical_ids"
                    ],
                    "expected_continued_canonical_table_ids": handoff[
                        "continued_canonical_table_ids"
                    ],
                    "required_new_canonical_table_ids": [
                        handoff["new_canonical_table_ids"][0]
                    ],
                    "expected_new_canonical_table_ids": handoff[
                        "new_canonical_table_ids"
                    ][:-1],
                    "expected_dropped_canonical_table_ids": handoff[
                        "dropped_canonical_table_ids"
                    ],
                }
            ]
        },
    )

    candidate = score["stage_handoff_score"]["expectations"][0][
        "matched_candidates"
    ][0]
    assert score["stage_handoff_score"]["pass_rate"] == 0.0
    assert candidate["checks"]["required_new_canonical_table_ids"] is True
    assert candidate["checks"]["expected_new_canonical_table_ids"] is False
    assert candidate["new_canonical_table_ids"] == handoff["new_canonical_table_ids"]
    assert candidate["expected_new_canonical_table_ids"] == handoff[
        "new_canonical_table_ids"
    ][:-1]


def test_exact_stage_roster_canonical_deltas_accept_full_boundary_contract() -> None:
    metrics = [
        _table_metric(0, 0.0, "access_sheathing", [7, 8]),
        _table_metric(1, 0.1, "access_sheathing", [7, 8]),
        _table_metric(2, 0.2, "valve_deployment", [7, 9, 10]),
        _table_metric(3, 0.3, "valve_deployment", [7, 9, 10]),
    ]
    roster = stage_roster_summary(metrics)[1]

    score = score_tavr_metrics(
        metrics,
        {
            "stage_roster_expectations": [
                {
                    "stage": "valve_deployment",
                    "handoff_type": roster["handoff_type"],
                    "expected_active_canonical_table_ids": roster[
                        "active_table_canonical_ids"
                    ],
                    "expected_continued_canonical_table_ids": roster[
                        "continued_canonical_table_ids"
                    ],
                    "expected_new_canonical_table_ids": roster[
                        "new_canonical_table_ids"
                    ],
                    "expected_dropped_canonical_table_ids": roster[
                        "dropped_canonical_table_ids"
                    ],
                }
            ]
        },
    )

    candidate = score["stage_roster_score"]["expectations"][0][
        "matched_candidates"
    ][0]
    assert score["stage_roster_score"]["pass_rate"] == 1.0
    assert candidate["checks"]["expected_active_canonical_table_ids"] is True
    assert candidate["checks"]["expected_continued_canonical_table_ids"] is True
    assert candidate["checks"]["expected_new_canonical_table_ids"] is True
    assert candidate["checks"]["expected_dropped_canonical_table_ids"] is True
    assert candidate["active_table_canonical_ids"] == roster[
        "active_table_canonical_ids"
    ]


def test_operator_status_snapshots_capture_critical_replay_points() -> None:
    metrics = [
        _table_metric(0, 0.0, "access_sheathing", [7]),
        _table_metric(1, 0.1, "access_sheathing", [7]),
        _table_metric(
            2,
            0.2,
            "valve_deployment",
            [],
            alert_flags=["non_room_view"],
        ),
        _table_metric(
            3,
            0.3,
            "valve_deployment",
            [],
            alert_flags=["non_room_view"],
        ),
    ]

    snapshots = operator_status_snapshots(metrics)

    assert [row["frame_index"] for row in snapshots] == [0, 1, 2, 3]
    by_frame = {row["frame_index"]: row for row in snapshots}
    assert by_frame[0]["snapshot_reason"] == ["clip_start", "stage_start", "view_start"]
    assert by_frame[1]["snapshot_reason"] == [
        "last_observed_table",
        "peak_table",
        "stage_end",
        "view_end",
    ]
    assert by_frame[2]["snapshot_reason"] == ["stage_start", "view_start"]
    assert by_frame[2]["current_stage"] == "valve_deployment"
    assert by_frame[2]["current_view"] == "non_room"
    assert by_frame[2]["effective_table_source"] == "last_observed_room_view"
    assert by_frame[2]["effective_table_canonical_ids"] == [1]
    assert by_frame[3]["snapshot_reason"] == ["clip_end", "stage_end", "view_end"]
    assert by_frame[3]["effective_table_age_from_clip_end_s"] == 0.2


def test_operator_snapshot_score_enforces_timestamp_tolerance() -> None:
    metrics = [
        _table_metric(0, 0.0, "valve_deployment", [7]),
        _table_metric(1, 0.1, "valve_deployment", [7]),
    ]
    labels = {
        "operator_snapshot_expectations": [
            {
                "timestamp_s": 1.0,
                "tolerance_s": 0.01,
                "stage": "valve_deployment",
                "current_view": "room",
                "tracking_available": True,
                "min_table_count": 1,
            }
        ]
    }

    score = score_tavr_metrics(metrics, labels)

    expectation = score["operator_snapshot_score"]["expectations"][0]
    assert score["operator_snapshot_score"]["pass_rate"] == 0.0
    assert expectation["matched_count"] == 0
    assert expectation["matched_candidates"] == []
    assert expectation["passed"] is False


def test_table_team_summary_reports_active_recent_and_historical_members() -> None:
    non_room_metrics = [
        _table_metric(0, 0.0, "access_sheathing", [7, 8]),
        _table_metric(1, 0.1, "valve_deployment", [7, 8]),
        _table_metric(
            2,
            0.2,
            "closure_finish",
            [],
            alert_flags=["non_room_view"],
        ),
    ]

    non_room_team = table_team_summary(
        non_room_metrics,
        min_observed_table_frames=1,
    )
    non_room_by_id = {item["track_id"]: item for item in non_room_team}

    assert non_room_by_id[7]["team_status"] == "recent_last_observed"
    assert non_room_by_id[7]["table_team_role"] == "table_operator"
    assert non_room_by_id[7]["is_current_table_member"] is False
    assert non_room_by_id[7]["is_effective_table_member"] is True
    assert non_room_by_id[7]["is_last_observed_table_member"] is True
    assert non_room_by_id[7]["age_from_clip_end_s"] == 0.1

    room_metrics = [
        _table_metric(0, 0.0, "access_sheathing", [7, 8]),
        _table_metric(1, 0.1, "valve_deployment", [7]),
        _table_metric(2, 0.2, "closure_finish", [9]),
    ]

    room_team = table_team_summary(room_metrics, min_observed_table_frames=1)
    room_by_id = {item["track_id"]: item for item in room_team}

    assert room_by_id[9]["team_status"] == "active_current"
    assert room_by_id[9]["table_team_role"] == "table_operator"
    assert room_by_id[9]["is_current_table_member"] is True
    assert room_by_id[9]["is_effective_table_member"] is True
    assert room_by_id[9]["age_from_clip_end_s"] == 0.0
    assert room_by_id[8]["team_status"] == "recent_last_observed"
    assert room_by_id[8]["is_current_table_member"] is False
    assert room_by_id[8]["is_effective_table_member"] is False
    assert room_by_id[8]["is_last_observed_table_member"] is True
    assert room_by_id[8]["is_peak_table_member"] is True
    assert room_by_id[8]["dominant_stage"] == "access_sheathing"
    assert "recent last observed" in room_by_id[8]["label"]


def test_table_team_role_promotes_table_facing_role_over_raw_dominant() -> None:
    metrics = [
        _table_metric(
            index,
            index / 10,
            "valve_deployment",
            [13],
            roles_by_track={
                13: "table_operator" if index < 4 else "imaging",
            },
        )
        for index in range(12)
    ]

    team = table_team_summary(metrics, min_observed_table_frames=1)
    row = {item["track_id"]: item for item in team}[13]

    assert row["dominant_role"] == "imaging"
    assert row["table_team_role"] == "table_operator"
    assert row["table_team_role_confidence"] == pytest.approx(0.333)
    assert "table_operator (dominant imaging)" in row["label"]


def test_stage_and_event_surfaces_use_table_facing_role() -> None:
    metrics = [
        _table_metric(
            index,
            index / 10,
            "valve_deployment",
            [13],
            roles_by_track={
                13: "table_operator" if index < 4 else "imaging",
            },
        )
        for index in range(12)
    ]

    coverage = stage_table_coverage(metrics)
    handoffs = stage_handoff_summary(metrics)
    events = procedure_event_timeline(metrics)
    score = score_tavr_metrics(
        metrics,
        {
            "stage_staffing_expectations": [
                {
                    "stage": "valve_deployment",
                    "role": "table_operator",
                    "dominant_role": "imaging",
                    "min_tracks": 1,
                    "min_observed_table_frames": 12,
                }
            ],
            "stage_table_coverage_expectations": [
                {
                    "stage": "valve_deployment",
                    "role": "table_operator",
                    "dominant_role": "imaging",
                    "min_tracks": 1,
                    "min_observed_table_frames": 12,
                    "min_coverage_ratio": 1.0,
                    "min_room_coverage_ratio": 1.0,
                    "required_label_text": "table_operator (dominant imaging)",
                }
            ],
            "stage_handoff_expectations": [
                {
                    "stage": "valve_deployment",
                    "role": "table_operator",
                    "lead_role": "table_operator",
                    "lead_dominant_role": "imaging",
                    "handoff_type": "initial_table_roster",
                    "min_active_tracks": 1,
                }
            ],
            "stage_roster_expectations": [
                {
                    "stage": "valve_deployment",
                    "role": "table_operator",
                    "lead_role": "table_operator",
                    "lead_dominant_role": "imaging",
                    "handoff_type": "initial_table_roster",
                    "min_tracks": 1,
                }
            ],
            "operator_packet_expectations": [
                {
                    "stage": "valve_deployment",
                    "current": True,
                    "stage_status": "current_observed",
                    "lead_role": "table_operator",
                    "handoff_type": "initial_table_roster",
                    "min_active_tracks": 1,
                    "min_peak_table_count": 1,
                    "required_packet_text": [
                        "Current stage: Valve deployment",
                        "stage roster people Person 1 (raw IDs 13)",
                    ],
                    "forbidden_packet_text": ["active people"],
                }
            ],
            "event_timeline_expectations": [
                {
                    "event_type": "table_handoff",
                    "stage": "valve_deployment",
                    "role": "table_operator",
                    "handoff_type": "initial_table_roster",
                    "min_tracks": 1,
                    "required_table_canonical_ids": [1],
                }
            ],
        },
    )

    assert coverage[0]["dominant_role"] == "imaging"
    assert coverage[0]["table_team_role"] == "table_operator"
    assert coverage[0]["table_team_role_confidence"] == pytest.approx(0.333)
    assert "table_operator (dominant imaging)" in coverage[0]["label"]

    assert handoffs[0]["lead_role"] == "table_operator"
    assert handoffs[0]["lead_dominant_role"] == "imaging"
    assert handoffs[0]["lead_table_team_role"] == "table_operator"
    assert "lead ID 13 table_operator" in handoffs[0]["label"]

    handoff_event = next(
        event for event in events if event["event_type"] == "table_handoff"
    )
    assert handoff_event["dominant_role"] == "imaging"
    assert handoff_event["table_team_role"] == "table_operator"
    assert handoff_event["canonical_table_id"] == 1
    assert handoff_event["table_canonical_ids"] == [1]
    assert handoff_event["roster"][0]["dominant_role"] == "imaging"
    assert handoff_event["roster"][0]["table_team_role"] == "table_operator"
    assert handoff_event["roster"][0]["canonical_table_id"] == 1

    assert score["stage_staffing_score"]["pass_rate"] == 1.0
    assert score["stage_table_coverage_score"]["pass_rate"] == 1.0
    assert score["stage_handoff_score"]["pass_rate"] == 1.0
    assert score["stage_roster_score"]["pass_rate"] == 1.0
    assert score["operator_packet_score"]["pass_rate"] == 1.0
    assert score["event_timeline_score"]["pass_rate"] == 1.0


def test_negative_table_presence_staffing_and_handoff_maxima() -> None:
    labels = {
        "table_presence_expectations": [
            {
                "role": "table_operator",
                "max_intervals": 0,
            }
        ],
        "stage_staffing_expectations": [
            {
                "stage": "access_sheathing",
                "role": "table_operator",
                "max_tracks": 0,
                "max_peak_count": 0,
                "max_mean_count": 0,
                "max_table_occupancy_rate": 0,
                "max_room_mean_count": 0,
                "max_room_table_occupancy_rate": 0,
                "max_canonical_table_identity_count": 0,
            }
        ],
        "stage_handoff_expectations": [
            {
                "stage": "access_sheathing",
                "handoff_type": "initial_no_table_evidence",
                "max_active_tracks": 0,
                "max_new_tracks": 0,
                "max_continued_tracks": 0,
                "max_dropped_tracks": 0,
            }
        ],
    }
    no_table_metrics = [
        _table_metric(index, index / 10, "access_sheathing", [])
        for index in range(3)
    ]
    table_metrics = [
        _table_metric(index, index / 10, "access_sheathing", [7])
        for index in range(3)
    ]

    clean_score = score_tavr_metrics(no_table_metrics, labels)
    phantom_score = score_tavr_metrics(table_metrics, labels)

    assert clean_score["table_presence_score"]["pass_rate"] == 1.0
    assert clean_score["stage_staffing_score"]["pass_rate"] == 1.0
    assert clean_score["stage_handoff_score"]["pass_rate"] == 1.0
    assert phantom_score["table_presence_score"]["pass_rate"] == 0.0
    assert phantom_score["table_presence_score"]["expectations"][0]["checks"][
        "max_intervals"
    ] is False
    assert phantom_score["stage_staffing_score"]["pass_rate"] == 0.0
    assert phantom_score["stage_staffing_score"]["expectations"][0]["checks"][
        "max_tracks"
    ] is False
    assert phantom_score["stage_handoff_score"]["pass_rate"] == 0.0
    assert phantom_score["stage_handoff_score"]["expectations"][0][
        "matched_candidates"
    ][0]["checks"]["max_active_tracks"] is False


def test_stage_table_coverage_expectation_requires_match_by_default() -> None:
    metrics = [
        _table_metric(
            index,
            index / 10,
            "valve_deployment",
            [7],
            roles_by_track={7: "imaging"},
        )
        for index in range(3)
    ]

    empty_positive = score_tavr_metrics(
        [],
        {
            "stage_table_coverage_expectations": [
                {"stage": "valve_deployment", "role": "table_operator"}
            ]
        },
    )
    role_mismatch = score_tavr_metrics(
        metrics,
        {
            "stage_table_coverage_expectations": [
                {
                    "stage": "valve_deployment",
                    "role": "table_operator",
                    "min_observed_table_frames": 1,
                }
            ]
        },
    )
    explicit_negative = score_tavr_metrics(
        [],
        {
            "stage_table_coverage_expectations": [
                {"stage": "valve_deployment", "max_tracks": 0}
            ]
        },
    )

    assert empty_positive["stage_table_coverage_score"]["pass_rate"] == 0.0
    assert (
        empty_positive["stage_table_coverage_score"]["expectations"][0][
            "min_tracks"
        ]
        == 1
    )
    assert role_mismatch["stage_table_coverage_score"]["pass_rate"] == 0.0
    mismatch_expectation = role_mismatch["stage_table_coverage_score"][
        "expectations"
    ][0]
    assert mismatch_expectation["candidate_count"] == 1
    assert mismatch_expectation["matched_count"] == 0
    assert mismatch_expectation["passed_candidate_count"] == 0
    assert explicit_negative["stage_table_coverage_score"]["pass_rate"] == 1.0
    assert (
        explicit_negative["stage_table_coverage_score"]["expectations"][0][
            "min_tracks"
        ]
        == 0
    )


def test_table_identity_stitching_merges_sequential_fragmented_tracks() -> None:
    metrics = [
        _table_metric(
            0,
            0.0,
            "valve_deployment",
            [7],
            centroids_by_track={7: (120, 220)},
        ),
        _table_metric(
            1,
            0.1,
            "valve_deployment",
            [7],
            centroids_by_track={7: (123, 222)},
        ),
        _table_metric(
            2,
            0.2,
            "valve_deployment",
            [8],
            centroids_by_track={8: (126, 224)},
        ),
        _table_metric(
            3,
            0.3,
            "valve_deployment",
            [8],
            centroids_by_track={8: (129, 225)},
        ),
        _table_metric(
            4,
            0.4,
            "valve_deployment",
            [9],
            centroids_by_track={9: (132, 227)},
        ),
        _table_metric(
            5,
            0.5,
            "valve_deployment",
            [9],
            centroids_by_track={9: (135, 228)},
        ),
    ]

    identities = summarize_tavr_metrics(metrics)["table_identity_groups"]
    team = table_team_summary(metrics, min_observed_table_frames=1)
    coverage = stage_table_coverage(metrics)
    handoffs = stage_handoff_summary(metrics)
    staffing = stage_staffing_summary(metrics, min_observed_table_frames=1)
    milestones = procedure_milestones(metrics)

    assert len(identities) == 1
    assert identities[0]["merged_track_ids"] == [7, 8, 9]
    assert identities[0]["observed_table_frames"] == 6

    assert len(team) == 1
    assert team[0]["canonical_table_id"] == identities[0]["canonical_table_id"]
    assert team[0]["track_id"] == 7
    assert team[0]["merged_track_ids"] == [7, 8, 9]
    assert team[0]["table_frames"] == 6

    assert len(coverage) == 1
    assert coverage[0]["canonical_table_id"] == identities[0]["canonical_table_id"]
    assert coverage[0]["merged_track_ids"] == [7, 8, 9]
    assert coverage[0]["observed_table_frames"] == 6

    assert handoffs[0]["active_table_track_count"] == 1
    assert handoffs[0]["active_table_roster"][0]["merged_track_ids"] == [7, 8, 9]

    assert staffing[0]["unique_table_track_count"] == 3
    assert staffing[0]["canonical_table_identity_count"] == 1
    deployment = next(item for item in milestones if item["stage"] == "valve_deployment")
    assert deployment["unique_table_track_count"] == 3
    assert deployment["canonical_table_identity_count"] == 1

    score = score_tavr_metrics(
        metrics,
        {
            "table_identity_group_expectations": [
                {
                    "stage": "valve_deployment",
                    "role": "table_operator",
                    "min_groups": 1,
                    "max_groups": 1,
                    "required_merged_track_ids": [7, 8, 9],
                    "min_merged_track_count": 3,
                    "min_observed_table_frames": 6,
                    "min_stage_frames": 6,
                },
                {
                    "role": "anesthesia",
                    "max_groups": 0,
                },
            ]
        },
    )

    assert score["table_identity_group_score"]["pass_rate"] == 1.0
    assert (
        score["table_identity_group_score"]["expectations"][0]["matched_candidates"][0][
            "merged_track_ids"
        ]
        == [7, 8, 9]
    )


def test_exact_merged_track_ids_rejects_overmerged_identity_and_coverage() -> None:
    metrics = [
        _table_metric(
            0,
            0.0,
            "valve_deployment",
            [7],
            centroids_by_track={7: (120, 220)},
        ),
        _table_metric(
            1,
            0.1,
            "valve_deployment",
            [8],
            centroids_by_track={8: (123, 222)},
        ),
        _table_metric(
            2,
            0.2,
            "valve_deployment",
            [9],
            centroids_by_track={9: (126, 224)},
        ),
    ]

    score = score_tavr_metrics(
        metrics,
        {
            "table_identity_group_expectations": [
                {
                    "stage": "valve_deployment",
                    "role": "table_operator",
                    "required_merged_track_ids": [7, 8],
                    "expected_merged_track_ids": [7, 8],
                    "min_groups": 1,
                }
            ],
            "stage_table_coverage_expectations": [
                {
                    "stage": "valve_deployment",
                    "role": "table_operator",
                    "required_merged_track_ids": [7, 8],
                    "expected_merged_track_ids": [7, 8],
                    "min_tracks": 1,
                }
            ],
        },
    )

    identity_candidate = score["table_identity_group_score"]["expectations"][0][
        "candidate_checks"
    ][0]
    coverage_candidate = score["stage_table_coverage_score"]["expectations"][0][
        "candidate_checks"
    ][0]

    assert score["table_identity_group_score"]["pass_rate"] == 0.0
    assert identity_candidate["checks"]["required_merged_track_ids"] is True
    assert identity_candidate["checks"]["expected_merged_track_ids"] is False
    assert identity_candidate["merged_track_ids"] == [7, 8, 9]
    assert identity_candidate["expected_merged_track_ids"] == [7, 8]
    assert score["stage_table_coverage_score"]["pass_rate"] == 0.0
    assert coverage_candidate["checks"]["required_merged_track_ids"] is True
    assert coverage_candidate["checks"]["expected_merged_track_ids"] is False
    assert coverage_candidate["merged_track_ids"] == [7, 8, 9]
    assert coverage_candidate["expected_merged_track_ids"] == [7, 8]


def test_table_identity_stitching_preserves_people_through_crossing_fragments() -> None:
    metrics = [
        _table_metric(
            0,
            0.0,
            "valve_deployment",
            [7, 8],
            centroids_by_track={7: (120, 220), 8: (220, 220)},
        ),
        _table_metric(
            1,
            0.1,
            "valve_deployment",
            [7, 8],
            centroids_by_track={7: (145, 220), 8: (195, 220)},
        ),
        _table_metric(
            2,
            0.2,
            "valve_deployment",
            [7, 8],
            centroids_by_track={7: (170, 220), 8: (170, 222)},
        ),
        _table_metric(
            3,
            0.3,
            "valve_deployment",
            [],
            centroids_by_track={},
        ),
        _table_metric(
            4,
            0.4,
            "valve_deployment",
            [9, 10],
            centroids_by_track={9: (145, 220), 10: (195, 220)},
        ),
        _table_metric(
            5,
            0.5,
            "valve_deployment",
            [9, 10],
            centroids_by_track={9: (120, 220), 10: (220, 220)},
        ),
    ]

    identities = summarize_tavr_metrics(metrics)["table_identity_groups"]
    merged_sets = {tuple(row["merged_track_ids"]) for row in identities}

    assert len(identities) == 2
    assert merged_sets == {(7, 10), (8, 9)}

    score = score_tavr_metrics(
        metrics,
        {
            "table_identity_group_expectations": [
                {
                    "stage": "valve_deployment",
                    "role": "table_operator",
                    "min_groups": 2,
                    "max_groups": 2,
                },
                {
                    "stage": "valve_deployment",
                    "role": "table_operator",
                    "min_groups": 1,
                    "max_groups": 1,
                    "min_merged_track_count": 2,
                    "max_merged_track_count": 2,
                    "min_observed_table_frames": 4,
                    "required_merged_track_ids": [7, 10],
                },
                {
                    "stage": "valve_deployment",
                    "role": "table_operator",
                    "min_groups": 1,
                    "max_groups": 1,
                    "min_merged_track_count": 2,
                    "max_merged_track_count": 2,
                    "min_observed_table_frames": 4,
                    "required_merged_track_ids": [8, 9],
                },
            ]
        },
    )

    assert score["table_identity_group_score"]["pass_rate"] == 1.0
    expectations = score["table_identity_group_score"]["expectations"]
    assert [expectation["matched_count"] for expectation in expectations] == [
        2,
        1,
        1,
    ]


def test_table_identity_stitching_uses_motion_when_centroids_nearly_tie() -> None:
    metrics = [
        _table_metric(
            0,
            0.0,
            "valve_deployment",
            [7, 8],
            centroids_by_track={7: (220, 220), 8: (139.8, 220)},
        ),
        _table_metric(
            1,
            0.1,
            "valve_deployment",
            [7, 8],
            centroids_by_track={7: (170.1, 220), 8: (169.9, 220)},
        ),
        _table_metric(
            2,
            0.2,
            "valve_deployment",
            [9],
            centroids_by_track={9: (200, 220)},
        ),
    ]

    identities = summarize_tavr_metrics(metrics)["table_identity_groups"]
    merged_sets = {tuple(row["merged_track_ids"]) for row in identities}

    assert merged_sets == {(7,), (8, 9)}


def test_table_identity_motion_resets_after_single_frame_fragment() -> None:
    group = {
        "raw_track_ids": set(),
        "first_frame": 0,
        "last_frame": 0,
        "first_s": 0.0,
        "last_s": 0.0,
        "first_clip_s": 0.0,
        "last_clip_s": 0.0,
        "last_cx": None,
        "last_cy": None,
        "last_area": None,
        "observed_table_frames": 0,
        "role_counts": {},
        "stage_counts": {},
    }
    moving_interval = {
        "track_id": 7,
        "start_frame": 0,
        "end_frame": 1,
        "start_s": 0.0,
        "end_s": 0.1,
        "clip_start_s": 0.0,
        "clip_end_s": 0.1,
        "first_cx": 100,
        "first_cy": 220,
        "last_cx": 150,
        "last_cy": 220,
        "last_area": 200,
        "observed_table_frames": 2,
        "role_counts": {"table_operator": 2},
        "stage_counts": {"valve_deployment": 2},
    }
    single_frame_interval = {
        "track_id": 9,
        "start_frame": 2,
        "end_frame": 2,
        "start_s": 0.2,
        "end_s": 0.2,
        "clip_start_s": 0.2,
        "clip_end_s": 0.2,
        "first_cx": 151,
        "first_cy": 220,
        "last_cx": 151,
        "last_cy": 220,
        "last_area": 200,
        "observed_table_frames": 1,
        "role_counts": {"table_operator": 1},
        "stage_counts": {"valve_deployment": 1},
    }
    future_interval = {
        "start_frame": 3,
        "first_cx": 201,
        "first_cy": 220,
    }

    evaluation_module._merge_identity_interval(group, moving_interval)
    assert group["last_velocity_cx"] == 50

    evaluation_module._merge_identity_interval(group, single_frame_interval)

    assert "last_velocity_cx" not in group
    assert "last_velocity_cy" not in group
    assert (
        evaluation_module._identity_projected_centroid_distance(
            group,
            future_interval,
        )
        is None
    )


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


def test_score_tavr_metrics_compares_table_transition_events() -> None:
    metrics = [
        _table_metric(0, 0.0, "access_sheathing", [7]),
        _table_metric(1, 0.1, "access_sheathing", [7]),
        _table_metric(2, 0.2, "valve_deployment", [7]),
        _table_metric(3, 0.3, "valve_deployment", [7, 8]),
        _table_metric(4, 0.4, "valve_deployment", [8]),
    ]

    score = score_tavr_metrics(
        metrics,
        {
            "table_transition_expectations": [
                {
                    "event_type": "table_entry",
                    "stage": "valve_deployment",
                    "role": "table_operator",
                    "min_events": 1,
                    "min_observed_table_frames": 2,
                    "min_coverage_ratio": 0.6,
                    "min_room_coverage_ratio": 0.6,
                    "required_label_text": "table_entry",
                },
                {
                    "event_type": "table_exit",
                    "stage": "valve_deployment",
                    "track_id": 7,
                    "min_events": 1,
                    "min_table_team_role_confidence": 1.0,
                },
                {
                    "event_type": "table_entry",
                    "stage": "closure_finish",
                    "max_events": 0,
                },
            ]
        },
    )

    transition_score = score["table_transition_score"]
    assert transition_score["pass_rate"] == 1.0
    assert transition_score["expectations"][0]["candidate_count"] == 1
    assert transition_score["expectations"][0]["matched_count"] == 1
    assert transition_score["expectations"][2]["min_events"] == 0


def test_table_transition_expectation_requires_event_by_default() -> None:
    score = score_tavr_metrics(
        [],
        {
            "table_transition_expectations": [
                {"event_type": "table_entry", "stage": "valve_deployment"}
            ]
        },
    )

    assert score["table_transition_score"]["pass_rate"] == 0.0
    assert score["table_transition_score"]["expectations"][0]["min_events"] == 1


def test_table_transition_score_enforces_zero_events_and_time_windows() -> None:
    metrics = [
        _table_metric(0, 0.0, "valve_deployment", [7]),
        _table_metric(1, 0.1, "valve_deployment", [7, 8]),
        _table_metric(2, 0.2, "valve_deployment", [8]),
    ]

    score = score_tavr_metrics(
        metrics,
        {
            "table_transition_expectations": [
                {
                    "event_type": "table_entry",
                    "stage": "valve_deployment",
                    "start_s": 0.05,
                    "end_s": 0.15,
                    "min_events": 1,
                },
                {
                    "event_type": "table_entry",
                    "stage": "valve_deployment",
                    "start_s": 0.15,
                    "end_s": 0.25,
                    "max_events": 0,
                },
                {
                    "event_type": "table_entry",
                    "stage": "valve_deployment",
                    "max_events": 0,
                },
            ]
        },
    )

    transition_score = score["table_transition_score"]
    assert transition_score["pass_rate"] == 0.667
    assert transition_score["expectations"][0]["matched_count"] == 1
    assert transition_score["expectations"][1]["matched_count"] == 0
    assert transition_score["expectations"][2]["matched_count"] == 1
    assert transition_score["expectations"][2]["passed"] is False


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
        "stage_roster_summary",
        "operator_stage_packet",
        "operator_status_snapshots",
        "stage_evidence_summary",
        "procedure_status_summary",
        "table_team_summary",
        "table_identity_groups",
        "procedure_milestones",
        "procedure_event_timeline",
        "table_roster_snapshots",
        "table_transition_events",
        "view_segments",
    }.issubset(paths)
    coverage_csv = Path(paths["stage_table_coverage"]).read_text(encoding="utf-8")
    staffing_csv = Path(paths["stage_staffing_summary"]).read_text(encoding="utf-8")
    handoff_csv = Path(paths["stage_handoff_summary"]).read_text(encoding="utf-8")
    roster_csv = Path(paths["stage_roster_summary"]).read_text(encoding="utf-8")
    packet_csv = Path(paths["operator_stage_packet"]).read_text(encoding="utf-8")
    status_snapshots_csv = Path(paths["operator_status_snapshots"]).read_text(
        encoding="utf-8"
    )
    evidence_csv = Path(paths["stage_evidence_summary"]).read_text(encoding="utf-8")
    status_csv = Path(paths["procedure_status_summary"]).read_text(encoding="utf-8")
    team_csv = Path(paths["table_team_summary"]).read_text(encoding="utf-8")
    identities_csv = Path(paths["table_identity_groups"]).read_text(encoding="utf-8")
    milestones_csv = Path(paths["procedure_milestones"]).read_text(encoding="utf-8")
    event_csv = Path(paths["procedure_event_timeline"]).read_text(encoding="utf-8")
    snapshots_csv = Path(paths["table_roster_snapshots"]).read_text(encoding="utf-8")
    assert "track_id" in coverage_csv
    assert "coverage_ratio" in coverage_csv
    assert "table_team_role" in coverage_csv
    assert "room_coverage_ratio" in coverage_csv
    assert "tracking_available_rate" in staffing_csv
    assert "table_operator" in staffing_csv
    assert "canonical_table_identity_count" in staffing_csv
    assert "room_table_occupancy_rate" in staffing_csv
    assert "handoff_type" in handoff_csv
    assert "lead_table_team_role" in handoff_csv
    assert "active_table_canonical_ids" in handoff_csv
    assert "roster_added" in handoff_csv
    assert "roster_summary" in roster_csv
    assert "active_table_track_ids" in roster_csv
    assert "active_table_canonical_ids" in roster_csv
    assert "canonical_table_identity_count" in roster_csv
    assert "Valve deployment: peak table 2" in roster_csv
    assert "operator_packet" in packet_csv
    assert "Current stage: Valve deployment" in packet_csv
    assert "stage_table_track_ids" in packet_csv
    assert "stage_table_canonical_ids" in packet_csv
    assert "stage_table_roster_summary" in packet_csv
    assert "stage roster people Person 1, Person 2 (raw IDs 7, 8)" in packet_csv
    assert "active people" not in packet_csv
    assert "effective_table_canonical_ids" in packet_csv
    assert "snapshot_reason" in status_snapshots_csv
    assert "clip_end" in status_snapshots_csv
    assert "effective_table_canonical_ids" in status_snapshots_csv
    assert "evidence_level" in evidence_csv
    assert "strong_visual_support" in evidence_csv
    assert "operator_summary" in status_csv
    assert "Current observed stage" in status_csv
    assert "effective_table_source" in status_csv
    assert "effective_table_canonical_ids" in status_csv
    assert "team_status" in team_csv
    assert "canonical_table_id" in team_csv
    assert "merged_track_ids" in team_csv
    assert "active_current" in team_csv
    assert "table_team_role" in team_csv
    assert "canonical_table_id" in identities_csv
    assert "merged_track_ids" in identities_csv
    assert "milestone_status" in milestones_csv
    assert "current_observed" in milestones_csv
    assert "canonical_table_identity_count" in milestones_csv
    assert "event_type" in event_csv
    assert "table_handoff" in event_csv
    assert "table_team_role" in event_csv
    assert "canonical_table_id" in event_csv
    assert "table_canonical_ids" in event_csv
    assert "snapshot_type" in snapshots_csv
    assert "canonical_table_id" in snapshots_csv
    assert "merged_track_ids" in snapshots_csv
    assert "last_observed" in snapshots_csv
    assert "table_team_role" in snapshots_csv
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
                "min_canonical_table_identity_count": 2,
                "max_canonical_table_identity_count": 2,
            }
        ],
        "stage_table_coverage_expectations": [
            {
                "stage": "valve_deployment",
                "role": "table_operator",
                "min_tracks": 2,
                "min_observed_table_frames": 2,
                "min_coverage_ratio": 1.0,
                "min_room_coverage_ratio": 1.0,
                "spans_full_stage": True,
            }
        ],
        "table_transition_expectations": [
            {
                "event_type": "table_present_at_stage_start",
                "stage": "valve_deployment",
                "role": "table_operator",
                "min_events": 2,
                "min_observed_table_frames": 2,
                "min_room_coverage_ratio": 1.0,
            },
            {
                "event_type": "table_present_at_stage_start",
                "stage": "closure_finish",
                "role": "table_operator",
                "min_events": 1,
                "min_observed_table_frames": 1,
            },
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
        "stage_roster_expectations": [
            {
                "stage": "valve_deployment",
                "role": "table_operator",
                "handoff_type": "roster_changed",
                "min_tracks": 2,
                "min_peak_table_count": 2,
                "min_canonical_table_identity_count": 2,
                "max_canonical_table_identity_count": 2,
                "min_new_tracks": 2,
                "min_dropped_tracks": 1,
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
                "min_canonical_table_identity_count": 2,
                "max_canonical_table_identity_count": 2,
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
                "current_stage_evidence_status": "strong_visual_support",
                "next_stage": None,
                "current_view": "room",
                "tracking_available": True,
                "effective_table_source": "current_room_view",
                "evidence_level": "strong_visual_support",
                "min_current_table_count": 1,
                "min_effective_table_count": 1,
                "max_effective_table_age_from_clip_end_s": 0.0,
                "min_last_observed_table_count": 1,
                "max_last_observed_age_from_clip_end_s": 0.0,
                "min_peak_table_count": 2,
                "required_quality_flags": ["non_room_view"],
            }
        ],
        "operator_packet_expectations": [
            {
                "stage": "valve_deployment",
                "current": False,
                "stage_status": "observed_prior",
                "stage_evidence_status": "strong_visual_support",
                "handoff_type": "roster_changed",
                "evidence_level": "strong_visual_support",
                "min_peak_table_count": 2,
                "min_active_tracks": 2,
                "min_canonical_table_identity_count": 2,
                "max_canonical_table_identity_count": 2,
                "min_new_tracks": 2,
                "min_dropped_tracks": 1,
                "required_quality_flags": ["non_room_view"],
                    "required_packet_text": [
                        "Observed stage: Valve deployment",
                        "stage roster people Person 2, Person 3 (raw IDs 9, 10)",
                    ],
                    "forbidden_packet_text": ["active people"],
            }
        ],
        "table_team_expectations": [
            {
                "status": "active_current",
                "role": "table_operator",
                "table_team_role": "table_operator",
                "min_tracks": 1,
                "require_in_current_table_roster": True,
                "require_in_effective_table_roster": True,
                "require_in_last_table_roster": True,
                "min_observed_table_frames": 1,
                "max_last_seen_age_from_clip_end_s": 0.0,
            },
            {
                "status": "recent_last_observed",
                "role": "table_operator",
                "table_team_role": "table_operator",
                "min_tracks": 1,
                "require_in_current_table_roster": False,
                "require_in_last_table_roster": True,
                "require_in_peak_table_roster": True,
                "min_observed_table_frames": 2,
                "max_last_seen_age_from_clip_end_s": 0.1,
            },
        ],
        "table_identity_group_expectations": [
            {
                "stage": "valve_deployment",
                "role": "table_operator",
                "min_groups": 2,
                "max_groups": 2,
                "min_observed_table_frames": 2,
                "min_stage_frames": 2,
                "max_merged_track_count": 1,
            },
            {
                "stage": "closure_finish",
                "role": "table_operator",
                "min_groups": 1,
                "min_observed_table_frames": 1,
            },
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
    assert score["stage_table_coverage_score"]["pass_rate"] == 1.0
    assert (
        score["stage_table_coverage_score"]["expectations"][0][
            "passed_candidate_count"
        ]
        == 2
    )
    assert score["table_transition_score"]["pass_rate"] == 1.0
    assert score["table_transition_score"]["expectations"][0]["matched_count"] == 2
    assert score["stage_handoff_score"]["pass_rate"] == 1.0
    assert score["stage_handoff_score"]["expectations"][0]["matched_count"] == 1
    assert score["stage_roster_score"]["pass_rate"] == 1.0
    assert score["stage_roster_score"]["expectations"][0]["matched_count"] == 1
    assert (
        score["stage_roster_score"]["expectations"][0]["matched_candidates"][0][
            "active_match_count"
        ]
        == 2
    )
    assert score["stage_evidence_score"]["pass_rate"] == 1.0
    assert score["stage_evidence_score"]["expectations"][1]["matched_count"] == 1
    assert score["procedure_milestone_score"]["pass_rate"] == 1.0
    assert score["procedure_milestone_score"]["expectations"][2]["matched_count"] == 1
    assert score["procedure_status_score"]["pass_rate"] == 1.0
    assert score["procedure_status_score"]["expectations"][0]["matched_count"] == 1
    assert score["operator_packet_score"]["pass_rate"] == 1.0
    assert score["operator_packet_score"]["expectations"][0]["matched_count"] == 1
    assert score["table_team_score"]["pass_rate"] == 1.0
    assert score["table_team_score"]["expectations"][0]["matched_count"] == 1
    assert score["table_team_score"]["expectations"][1]["matched_count"] == 1
    assert score["table_identity_group_score"]["pass_rate"] == 1.0
    assert score["table_identity_group_score"]["expectations"][0]["matched_count"] == 2
    assert score["event_timeline_score"]["pass_rate"] == 1.0
    assert score["event_timeline_score"]["expectations"][0]["matched_count"] == 1
    assert score["roster_snapshot_score"]["pass_rate"] == 1.0
    assert score["roster_snapshot_score"]["expectations"][0]["matched_count"] == 2
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
    roles_by_track: Optional[dict[int, str]] = None,
    centroids_by_track: Optional[dict[int, tuple[int, int]]] = None,
) -> FrameMetrics:
    role_counts: dict[str, int] = {}
    role_track_ids: dict[str, list[int]] = {}
    for track_id in table_track_ids:
        role = (roles_by_track or {}).get(track_id, "table_operator")
        role_counts[role] = role_counts.get(role, 0) + 1
        role_track_ids.setdefault(role, []).append(track_id)

    return FrameMetrics(
        frame_index=frame_index,
        timestamp_s=timestamp_s,
        detections=[
            Detection(
                track_id=track_id,
                bbox=(cx - 5, cy - 10, 10, 20),
                centroid=(cx, cy),
                area=200,
            )
            for track_id, (cx, cy) in (centroids_by_track or {}).items()
        ],
        alert_flags=alert_flags or [],
        tavr=TAVRFrameState(
            stage=stage,
            stage_label=TAVR_STAGE_LABELS[stage],
            confidence=0.8,
            table_count=len(table_track_ids),
            table_track_ids=table_track_ids,
            role_counts=role_counts,
            role_track_ids=role_track_ids,
            track_role_summaries={
                track_id: _track_summary(
                    track_id,
                    frame_index,
                    role=(roles_by_track or {}).get(track_id, "table_operator"),
                )
                for track_id in table_track_ids
            },
            signals={},
            note=TAVR_STAGE_NOTES[stage],
        ),
    )


def _track_summary(track_id: int, frame_index: int, role: str = "table_operator"):
    from or_tracking.tavr import TrackRoleSummary

    return TrackRoleSummary(
        track_id=track_id,
        dominant_role=role,
        frames_seen=1,
        first_frame=frame_index,
        last_frame=frame_index,
        table_frames=1,
        role_counts={role: 1},
    )
