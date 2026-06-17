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
