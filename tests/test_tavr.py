from or_tracking.models import Detection
from or_tracking.tavr import (
    TAVR_STAGE_ORDER,
    TAVRWorkflowAnalyzer,
    role_counts_from_zones,
    stage_timeline,
    tavr_default_zones,
)


def test_tavr_default_zones_are_normalized() -> None:
    zones = tavr_default_zones()

    assert {"access", "table", "anesthesia", "imaging", "device_table"} <= set(zones)
    for rect in zones.values():
        x0, y0, x1, y1 = rect
        assert 0.0 <= x0 < x1 <= 1.0
        assert 0.0 <= y0 < y1 <= 1.0


def test_role_counts_from_zones_maps_known_tavr_roles() -> None:
    counts = role_counts_from_zones(
        {
            "access": 2,
            "table_left": 1,
            "table_right": 1,
            "imaging": 1,
            "device_table": 1,
            "anesthesia": 1,
            "entry": 1,
            "unknown": 9,
        }
    )

    assert counts["access_operator"] == 2
    assert counts["table_operator"] == 2
    assert counts["imaging"] == 1
    assert counts["device_prep"] == 1
    assert counts["anesthesia"] == 1
    assert counts["entry_supply"] == 1
    assert "unknown" not in counts


def test_tavr_workflow_can_skip_optional_bav_when_delivery_signal_is_stronger() -> None:
    analyzer = TAVRWorkflowAnalyzer(min_stage_frames=0)
    detections = [Detection(1, (10, 10, 20, 40), (20, 30), 700)]
    empty_roles = {
        "access_operator": [],
        "anesthesia": [],
        "device_prep": [],
        "entry_supply": [],
        "imaging": [],
        "table_operator": [1],
    }

    analyzer.update(detections, {"device_table": 2, "table": 0}, [], empty_roles, 0, 20)
    analyzer.update(detections, {"access": 2, "table": 1}, [1], empty_roles, 1, 20)
    analyzer.update(detections, {"imaging": 2, "table": 1}, [1], empty_roles, 2, 20)
    state = analyzer.update(
        detections,
        {"device_table": 2, "table": 2, "imaging": 1},
        [1],
        {"device_prep": [1], "table_operator": [1], "imaging": [1]},
        3,
        80,
    )

    assert state.stage == "valve_delivery_positioning"
    assert state.stage in TAVR_STAGE_ORDER


def test_tavr_workflow_remembers_track_role_history() -> None:
    analyzer = TAVRWorkflowAnalyzer(min_stage_frames=0)
    detections = [Detection(7, (10, 10, 20, 40), (20, 30), 700)]

    analyzer.update(
        detections,
        {"table": 1},
        [7],
        {"table_operator": [7]},
        0,
        10,
    )
    analyzer.update(
        detections,
        {"table": 1},
        [7],
        {"table_operator": [7]},
        1,
        10,
    )
    state = analyzer.update(
        detections,
        {"access": 1, "table": 1},
        [7],
        {"access_operator": [7]},
        2,
        10,
    )

    summary = state.track_role_summaries[7]
    assert summary.dominant_role == "table_operator"
    assert summary.frames_seen == 3
    assert summary.table_frames == 3
    assert summary.table_presence_ratio == 1

    row = state.to_row_fields()
    assert row["who_at_table"] == "ID 7 table_operator table=100%"
    assert "7:table_operator:frames=3" in row["track_role_summary"]


def test_tavr_workflow_keeps_separate_recent_table_roster_for_dropouts() -> None:
    analyzer = TAVRWorkflowAnalyzer(min_stage_frames=0, recent_table_hold_frames=2)
    detection = Detection(7, (10, 10, 20, 40), (20, 30), 700)

    current = analyzer.update(
        [detection],
        {"table": 1},
        [7],
        {"table_operator": [7]},
        0,
        10,
    )
    dropped = analyzer.update([], {}, [], {}, 1, 0)
    reappeared_away = analyzer.update(
        [detection],
        {"entry": 1},
        [],
        {"entry_supply": [7]},
        2,
        10,
    )
    aged_out = analyzer.update([], {}, [], {}, 5, 0)

    assert current.table_track_ids == [7]
    assert current.recent_table_track_ids == [7]
    assert dropped.table_track_ids == []
    assert dropped.recent_table_track_ids == [7]
    assert dropped.to_row_fields()["who_at_table"] == ""
    assert dropped.to_row_fields()["recent_who_at_table"] == (
        "ID 7 table_operator table=100%"
    )
    assert reappeared_away.recent_table_track_ids == []
    assert aged_out.recent_table_track_ids == []


def test_tavr_workflow_can_start_from_seeded_stage() -> None:
    analyzer = TAVRWorkflowAnalyzer(
        initial_stage="valve_deployment",
        min_stage_frames=30,
    )
    state = analyzer.update(
        [],
        {"table": 1, "imaging": 1},
        [],
        {},
        900,
        0,
    )

    assert state.stage == "valve_deployment"
    assert state.stage_label == "Valve deployment"


def test_tavr_workflow_holds_stage_when_room_view_unavailable() -> None:
    analyzer = TAVRWorkflowAnalyzer(
        initial_stage="access_sheathing",
        min_stage_frames=0,
    )
    detection = Detection(1, (10, 10, 20, 40), (20, 30), 700)

    held = analyzer.update(
        [detection],
        {"imaging": 2, "table": 2},
        [1],
        {"imaging": [1], "table_operator": [1]},
        0,
        0,
        stage_observable=False,
        stage_hold_reason="non_room_view",
    )
    advanced = analyzer.update(
        [detection],
        {"imaging": 2, "table": 2},
        [1],
        {"imaging": [1], "table_operator": [1]},
        1,
        0,
        stage_observable=True,
    )

    assert held.stage == "access_sheathing"
    assert held.confidence == 0.2
    assert held.signals["stage_observable"] == 0.0
    assert held.signals["stage_hold_non_room_view"] == 1.0
    assert "room view is unavailable" in held.note
    assert advanced.stage == "angio_alignment_crossing"
    assert advanced.signals["stage_observable"] == 1.0


def test_tavr_workflow_holds_stage_for_static_table_fallback_evidence() -> None:
    analyzer = TAVRWorkflowAnalyzer(
        initial_stage="access_sheathing",
        min_stage_frames=0,
    )
    detection = Detection(1, (10, 10, 20, 40), (20, 30), 700)

    held = analyzer.update(
        [detection],
        {"imaging": 2, "table": 2},
        [1],
        {"imaging": [1], "table_operator": [1]},
        0,
        0,
        stage_observable=False,
        stage_hold_reason="static_table_fallback",
    )
    advanced = analyzer.update(
        [detection],
        {"imaging": 2, "table": 2},
        [1],
        {"imaging": [1], "table_operator": [1]},
        1,
        0,
        stage_observable=True,
    )

    assert held.stage == "access_sheathing"
    assert held.table_count == 1
    assert held.table_track_ids == [1]
    assert held.signals["stage_observable"] == 0.0
    assert held.signals["stage_hold_static_table_fallback"] == 1.0
    assert "static table fallback" in held.note
    assert advanced.stage == "angio_alignment_crossing"
    assert advanced.signals["stage_observable"] == 1.0


def test_tavr_workflow_rejects_unknown_initial_stage() -> None:
    try:
        TAVRWorkflowAnalyzer(initial_stage="not_a_tavr_stage")
    except ValueError as exc:
        assert "Unknown TAVR stage" in str(exc)
    else:
        raise AssertionError("Expected invalid initial stage to raise ValueError")


def test_tavr_stage_dwell_uses_first_observed_frame_for_offset_slices() -> None:
    analyzer = TAVRWorkflowAnalyzer(min_stage_frames=30)
    detections = [Detection(1, (10, 10, 20, 40), (20, 30), 700)]

    first = analyzer.update(
        detections,
        {"access": 2, "table": 1},
        [1],
        {"access_operator": [1]},
        1800,
        10,
    )
    second = analyzer.update(
        detections,
        {"access": 2, "table": 1},
        [1],
        {"access_operator": [1]},
        1801,
        10,
    )

    assert first.stage == "room_prep_drape"
    assert second.stage == "room_prep_drape"


def test_stage_timeline_groups_contiguous_states() -> None:
    analyzer = TAVRWorkflowAnalyzer(min_stage_frames=0)
    state_a = analyzer.update([], {}, [], {}, 0, 0)
    state_b = analyzer.update([], {"access": 2, "table": 1}, [2], {}, 1, 10)
    state_c = analyzer.update([], {"access": 2, "table": 1}, [2], {}, 2, 10)

    timeline = stage_timeline([state_a, state_b, state_c])

    assert timeline[0]["stage"] == "room_prep_drape"
    assert timeline[0]["start_frame"] == 0
    assert timeline[0]["end_frame"] == 0
    assert timeline[1]["stage"] == "access_sheathing"
    assert timeline[1]["start_frame"] == 1
    assert timeline[1]["end_frame"] == 2
