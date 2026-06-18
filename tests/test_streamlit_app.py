from app import (
    _current_operator_packet,
    _current_stage_roster,
    _operator_answer_rows,
    _operator_stage_packet_rows,
    _operator_status_snapshot_rows,
    _stage_roster_rows,
)


def test_operator_answer_preserves_effective_table_when_current_view_is_empty() -> None:
    status = {
        "current_stage": "valve_deployment",
        "current_stage_label": "Valve deployment",
        "current_stage_status": "current_held_context",
        "evidence_level": "strong_visual_support",
        "observable_rate": 0.75,
        "current_view": "non_room",
        "tracking_available": False,
        "current_table_count": 0,
        "current_table_roster": [],
        "current_table_track_ids": [],
        "current_table_canonical_ids": [],
        "effective_table_source": "last_observed_room_view",
        "effective_table_age_from_clip_end_s": 1.2,
        "effective_table_stage_label": "Valve deployment",
        "effective_table_count": 2,
        "effective_table_track_ids": [7, 8],
        "effective_table_canonical_ids": [1, 2],
        "effective_table_roster": [
            {"label": "Person 1: ID 7 table_operator 2 frames 0.0-0.4s"},
            {"label": "Person 2: ID 8 table_operator 1 frames 0.2-0.4s"},
        ],
        "quality_flag_codes": ["non_room_view"],
        "peak_table_count": 2,
        "next_stage_label": "Closure / finish",
    }
    packet = {
        "stage_segment_index": 2,
        "stage_label": "Valve deployment",
        "handoff_type": "roster_added",
        "stage_table_track_ids": [7, 8],
        "stage_table_canonical_ids": [1, 2],
        "stage_table_roster_summary": "Person 1 table_operator; Person 2 table_operator",
        "new_canonical_table_ids": [2],
        "dropped_canonical_table_ids": [],
        "within_stage_entry_track_ids": [8],
        "within_stage_entry_canonical_table_ids": [2],
        "within_stage_exit_track_ids": [7],
        "within_stage_exit_canonical_table_ids": [1],
    }

    rows = {row["answer"]: row for row in _operator_answer_rows(status, packet, None)}

    assert rows["Current visible table"]["value"] == "0 people visible"
    assert rows["Current visible table"]["canonical_people"] == "none"
    assert rows["Effective table handoff"]["value"] == "2 people"
    assert rows["Effective table handoff"]["canonical_people"] == "Person 1, Person 2"
    assert rows["Effective table handoff"]["raw_track_ids"] == "7, 8"
    assert rows["Stage roster"]["canonical_people"] == "Person 1, Person 2"
    assert rows["Stage roster"]["evidence"] == "new Person 2; dropped none"
    assert rows["Within-stage movement"]["value"] == "entered Person 2; exited Person 1"
    assert rows["Quality"]["value"] == "non_room_view"


def test_operator_packet_and_stage_roster_rows_expose_canonical_mid_stage_changes() -> None:
    packet = {
        "stage_label": "Valve deployment",
        "stage_status": "current_observed",
        "is_current_stage": True,
        "start_s": 10.0,
        "end_s": 18.0,
        "evidence_level": "strong_visual_support",
        "mean_confidence": 0.82,
        "handoff_type": "roster_changed",
        "peak_table_count": 2,
        "active_table_track_ids": [7, 8],
        "active_table_canonical_ids": [1, 2],
        "new_track_ids": [8],
        "new_canonical_table_ids": [2],
        "dropped_track_ids": [],
        "dropped_canonical_table_ids": [],
        "within_stage_entry_track_ids": [8],
        "within_stage_entry_canonical_table_ids": [2],
        "within_stage_exit_track_ids": [7],
        "within_stage_exit_canonical_table_ids": [1],
        "effective_table_source": "current_room_view",
        "effective_table_track_ids": [8],
        "effective_table_canonical_ids": [2],
        "quality_flag_codes": [],
        "operator_packet": "Current stage: Valve deployment",
    }
    roster = {
        "stage_label": "Valve deployment",
        "start_s": 10.0,
        "end_s": 18.0,
        "evidence_level": "strong_visual_support",
        "tracking_available_rate": 1.0,
        "peak_table_count": 2,
        "canonical_table_identity_count": 2,
        "lead_track_id": 8,
        "lead_table_team_role": "table_operator",
        "handoff_type": "roster_changed",
        "active_table_track_ids": [7, 8],
        "active_table_canonical_ids": [1, 2],
        "new_track_ids": [8],
        "new_canonical_table_ids": [2],
        "dropped_track_ids": [],
        "dropped_canonical_table_ids": [],
        "within_stage_entry_track_ids": [8],
        "within_stage_entry_canonical_table_ids": [2],
        "within_stage_exit_track_ids": [7],
        "within_stage_exit_canonical_table_ids": [1],
        "active_table_roster": [{"label": "Person 2: ID 8 table_operator"}],
    }

    packet_row = _operator_stage_packet_rows([packet])[0]
    roster_row = _stage_roster_rows([roster])[0]

    assert packet_row["active_people"] == "Person 1, Person 2"
    assert packet_row["within_stage_entry_people"] == "Person 2"
    assert packet_row["within_stage_exit_people"] == "Person 1"
    assert packet_row["effective_people"] == "Person 2"
    assert roster_row["new_people"] == "Person 2"
    assert roster_row["within_stage_entry_people"] == "Person 2"
    assert roster_row["within_stage_exit_people"] == "Person 1"


def test_operator_status_snapshot_rows_surface_current_and_effective_people() -> None:
    rows = _operator_status_snapshot_rows(
        [
            {
                "snapshot_index": 4,
                "snapshot_reason": ["stage_start", "view_start"],
                "clip_timestamp_s": 12.4,
                "current_stage_label": "Valve deployment",
                "current_stage_status": "current_held_context",
                "evidence_level": "strong_visual_support",
                "current_table_count": 0,
                "current_table_canonical_ids": [],
                "effective_table_count": 2,
                "effective_table_canonical_ids": [1, 2],
                "effective_table_source": "last_observed_room_view",
                "effective_table_age_from_clip_end_s": 0.8,
                "quality_flag_codes": ["non_room_view"],
            }
        ]
    )

    assert rows == [
        {
            "snapshot": 4,
            "reason": "stage_start, view_start",
            "clip_s": 12.4,
            "stage": "Valve deployment",
            "status": "current held context",
            "evidence": "strong visual support",
            "current_visible_count": 0,
            "current_visible_people": "none",
            "effective_table_count": 2,
            "effective_people": "Person 1, Person 2",
            "effective_source": "last observed room view",
            "effective_age_s": 0.8,
            "quality_flags": "non_room_view",
        }
    ]


def test_current_packet_and_roster_select_current_stage_segment() -> None:
    packets = [
        {"stage_segment_index": 1, "is_current_stage": False},
        {"stage_segment_index": 3, "is_current_stage": True},
    ]
    rosters = [
        {"stage_segment_index": 1, "stage": "access_sheathing"},
        {"stage_segment_index": 3, "stage": "valve_deployment"},
    ]

    packet = _current_operator_packet(packets)
    roster = _current_stage_roster(
        rosters,
        packet,
        {"current_stage": "valve_deployment"},
    )

    assert packet == packets[1]
    assert roster == rosters[1]
