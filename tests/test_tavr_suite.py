import json
import sys
from pathlib import Path

import pytest

from evaluate_tavr_suite import DEFAULT_THRESHOLDS, _score_summary, run_suite
from or_tracking.synthetic import generate_synthetic_tavr_video
from or_tracking.tavr import TAVR_STAGE_ORDER


def test_score_summary_ignores_unscored_sections_and_fails_bad_scores() -> None:
    label_score = {
        "stage_score": {"accuracy": None},
        "table_count_score": {"pass_rate": 1.0},
        "table_presence_score": {"pass_rate": None},
        "table_person_interval_score": {"pass_rate": None},
        "table_person_status_score": {"pass_rate": None},
        "stage_staffing_score": {"pass_rate": 0.5},
        "stage_table_coverage_score": {"pass_rate": None},
        "table_transition_score": {"pass_rate": None},
        "stage_handoff_score": {"pass_rate": None},
        "stage_roster_score": {"pass_rate": None},
        "stage_evidence_score": {"pass_rate": None},
        "procedure_milestone_score": {"pass_rate": None},
        "procedure_status_score": {"pass_rate": None},
        "operator_snapshot_score": {"pass_rate": None},
        "operator_packet_score": {"pass_rate": None},
        "table_team_score": {"pass_rate": None},
        "table_identity_group_score": {"pass_rate": None},
        "event_timeline_score": {"pass_rate": None},
        "roster_snapshot_score": {"pass_rate": None},
        "quality_flag_score": {"pass_rate": None},
    }
    thresholds = {
        "stage_accuracy": 1.0,
        "table_count_pass_rate": 1.0,
        "table_presence_pass_rate": 1.0,
        "table_person_interval_pass_rate": 1.0,
        "table_person_status_pass_rate": 1.0,
        "stage_staffing_pass_rate": 1.0,
        "stage_table_coverage_pass_rate": 1.0,
        "table_transition_pass_rate": 1.0,
        "stage_handoff_pass_rate": 1.0,
        "stage_roster_pass_rate": 1.0,
        "stage_evidence_pass_rate": 1.0,
        "procedure_milestone_pass_rate": 1.0,
        "procedure_status_pass_rate": 1.0,
        "operator_snapshot_pass_rate": 1.0,
        "operator_packet_pass_rate": 1.0,
        "table_team_pass_rate": 1.0,
        "table_identity_group_pass_rate": 1.0,
        "event_timeline_pass_rate": 1.0,
        "roster_snapshot_pass_rate": 1.0,
        "quality_flag_pass_rate": 1.0,
    }

    summary = _score_summary(label_score, thresholds)

    assert summary["passed"] is False
    assert [check["scored"] for check in summary["checks"]] == [
        False,
        True,
        False,
        False,
        False,
        True,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
    ]
    assert all(check["required"] is False for check in summary["checks"])


def test_score_summary_fails_required_unscored_sections() -> None:
    label_score = {
        "stage_score": {"accuracy": None},
        "table_count_score": {"pass_rate": 1.0},
        "table_presence_score": {"pass_rate": None},
        "table_person_interval_score": {"pass_rate": None},
        "table_person_status_score": {"pass_rate": None},
        "stage_staffing_score": {"pass_rate": None},
        "stage_table_coverage_score": {"pass_rate": None},
        "table_transition_score": {"pass_rate": None},
        "stage_handoff_score": {"pass_rate": None},
        "stage_roster_score": {"pass_rate": None},
        "stage_evidence_score": {"pass_rate": None},
        "procedure_milestone_score": {"pass_rate": None},
        "procedure_status_score": {"pass_rate": None},
        "operator_snapshot_score": {"pass_rate": None},
        "operator_packet_score": {"pass_rate": None},
        "table_team_score": {"pass_rate": None},
        "table_identity_group_score": {"pass_rate": None},
        "event_timeline_score": {"pass_rate": None},
        "roster_snapshot_score": {"pass_rate": None},
        "quality_flag_score": {"pass_rate": None},
    }
    thresholds = {
        "stage_accuracy": 1.0,
        "table_count_pass_rate": 1.0,
        "table_presence_pass_rate": 1.0,
        "table_person_interval_pass_rate": 1.0,
        "table_person_status_pass_rate": 1.0,
        "stage_staffing_pass_rate": 1.0,
        "stage_table_coverage_pass_rate": 1.0,
        "table_transition_pass_rate": 1.0,
        "stage_handoff_pass_rate": 1.0,
        "stage_roster_pass_rate": 1.0,
        "stage_evidence_pass_rate": 1.0,
        "procedure_milestone_pass_rate": 1.0,
        "procedure_status_pass_rate": 1.0,
        "operator_snapshot_pass_rate": 1.0,
        "operator_packet_pass_rate": 1.0,
        "table_team_pass_rate": 1.0,
        "table_identity_group_pass_rate": 1.0,
        "event_timeline_pass_rate": 1.0,
        "roster_snapshot_pass_rate": 1.0,
        "quality_flag_pass_rate": 1.0,
    }

    summary = _score_summary(
        label_score,
        thresholds,
        required_checks=["stage_accuracy", "table_count_pass_rate"],
    )

    stage_check = next(
        check for check in summary["checks"] if check["name"] == "stage_accuracy"
    )
    table_check = next(
        check for check in summary["checks"] if check["name"] == "table_count_pass_rate"
    )
    assert summary["passed"] is False
    assert stage_check["required"] is True
    assert stage_check["scored"] is False
    assert stage_check["passed"] is False
    assert stage_check["failure_reason"] == "required_check_unscored"
    assert table_check["required"] is True
    assert table_check["passed"] is True


def test_score_summary_rejects_unknown_required_score_checks() -> None:
    label_score = {
        "stage_score": {"accuracy": 1.0},
        "table_count_score": {"pass_rate": None},
        "table_presence_score": {"pass_rate": None},
        "table_person_interval_score": {"pass_rate": None},
        "table_person_status_score": {"pass_rate": None},
        "stage_staffing_score": {"pass_rate": None},
        "stage_table_coverage_score": {"pass_rate": None},
        "table_transition_score": {"pass_rate": None},
        "stage_handoff_score": {"pass_rate": None},
        "stage_roster_score": {"pass_rate": None},
        "stage_evidence_score": {"pass_rate": None},
        "procedure_milestone_score": {"pass_rate": None},
        "procedure_status_score": {"pass_rate": None},
        "operator_snapshot_score": {"pass_rate": None},
        "operator_packet_score": {"pass_rate": None},
        "table_team_score": {"pass_rate": None},
        "table_identity_group_score": {"pass_rate": None},
        "event_timeline_score": {"pass_rate": None},
        "roster_snapshot_score": {"pass_rate": None},
        "quality_flag_score": {"pass_rate": None},
    }
    thresholds = {
        "stage_accuracy": 1.0,
        "table_count_pass_rate": 1.0,
        "table_presence_pass_rate": 1.0,
        "table_person_interval_pass_rate": 1.0,
        "table_person_status_pass_rate": 1.0,
        "stage_staffing_pass_rate": 1.0,
        "stage_table_coverage_pass_rate": 1.0,
        "table_transition_pass_rate": 1.0,
        "stage_handoff_pass_rate": 1.0,
        "stage_roster_pass_rate": 1.0,
        "stage_evidence_pass_rate": 1.0,
        "procedure_milestone_pass_rate": 1.0,
        "procedure_status_pass_rate": 1.0,
        "operator_snapshot_pass_rate": 1.0,
        "operator_packet_pass_rate": 1.0,
        "table_team_pass_rate": 1.0,
        "table_identity_group_pass_rate": 1.0,
        "event_timeline_pass_rate": 1.0,
        "roster_snapshot_pass_rate": 1.0,
        "quality_flag_pass_rate": 1.0,
    }

    with pytest.raises(ValueError, match="not_a_real_check"):
        _score_summary(
            label_score,
            thresholds,
            required_checks=["not_a_real_check"],
        )


def test_run_suite_with_synthetic_tavr_case(tmp_path: Path) -> None:
    video_path = generate_synthetic_tavr_video(tmp_path / "tavr.mp4", frames=180)
    labels_path = tmp_path / "labels.json"
    labels_path.write_text(
        json.dumps(
            {
                "table_count_segments": [
                    {"start_s": 0.0, "end_s": 7.0, "min_peak_count": 1}
                ]
            }
        ),
        encoding="utf-8",
    )
    manifest_path = tmp_path / "suite.json"
    manifest_path.write_text(
        json.dumps(
            {
                "name": "synthetic suite",
                "cases": [
                    {
                        "name": "synthetic_tavr",
                        "video_path": str(video_path),
                        "labels_path": str(labels_path),
                        "config": {
                            "max_frames": 180,
                            "min_area": 180,
                            "static_table_fallback": True,
                            "initial_stage": "room_prep_drape",
                            "source_start_s": 42.0,
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    summary = run_suite(manifest_path, tmp_path / "outputs")

    assert summary["passed"] is True
    assert summary["case_count"] == 1
    assert summary["passed_count"] == 1
    result_path = Path(summary["cases"][0]["result_path"])
    assert result_path.exists()
    result_payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert result_payload["evaluation_config"]["static_table_fallback"] is True
    assert result_payload["evaluation_config"]["source_start_s"] == 42.0
    assert result_payload["timebase"]["timebase"] == "source"
    assert result_payload["timebase"]["source_start_s"] == 42.0
    assert result_payload["tavr"]["timebase_summary"][0]["source_start_s"] == 42.0
    assert summary["cases"][0]["tavr_csv_paths"]["stage_timeline"]
    assert Path(summary["cases"][0]["tavr_csv_paths"]["stage_timeline"]).exists()
    assert Path(summary["summary_path"]).exists()


def test_synthetic_full_tavr_labels_cover_all_canonical_stages() -> None:
    labels = json.loads(
        Path("docs/evaluation/synthetic_tavr_full.labels.json").read_text(
            encoding="utf-8"
        )
    )
    manifest = json.loads(
        Path("docs/evaluation/tavr_synthetic_suite.json").read_text(
            encoding="utf-8"
        )
    )

    assert [row["stage"] for row in labels["stage_segments"]] == TAVR_STAGE_ORDER
    assert [
        row["stage"] for row in labels["procedure_milestone_expectations"]
    ] == TAVR_STAGE_ORDER
    assert {row["stage"] for row in labels["stage_roster_expectations"]} == set(
        TAVR_STAGE_ORDER
    )
    assert {row["stage"] for row in labels["stage_evidence_expectations"]} == set(
        TAVR_STAGE_ORDER
    )
    assert Path(manifest["cases"][0]["video_path"]).exists()
    assert manifest["cases"][0]["labels_path"] == (
        "docs/evaluation/synthetic_tavr_full.labels.json"
    )


@pytest.mark.skipif(
    sys.platform.startswith("linux"),
    reason="Linux OpenCV decodes the mp4v fixture differently enough to shift the strict visual oracle.",
)
def test_synthetic_full_tavr_suite_scores_all_canonical_stages(
    tmp_path: Path,
) -> None:
    manifest = json.loads(
        Path("docs/evaluation/tavr_synthetic_suite.json").read_text(
            encoding="utf-8"
        )
    )
    assert Path(manifest["cases"][0]["video_path"]).exists()
    manifest_path = tmp_path / "suite.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    summary = run_suite(manifest_path, tmp_path / "outputs")

    assert summary["passed"] is True, json.dumps(
        summary["cases"][0]["score_summary"],
        indent=2,
    )
    assert summary["case_count"] == 1
    result = json.loads(
        Path(summary["cases"][0]["result_path"]).read_text(encoding="utf-8")
    )
    milestone_stages = [
        row["stage"] for row in result["tavr"]["procedure_milestones"]
    ]
    assert milestone_stages == TAVR_STAGE_ORDER
    assert all(
        row["observed_in_clip"]
        for row in result["tavr"]["procedure_milestones"]
    )
    assert (
        result["label_score"]["operator_packet_score"]["pass_rate"] == 1.0
    )
    assert (
        result["label_score"]["table_identity_group_score"]["pass_rate"]
        == 1.0
    )
    assert (
        result["label_score"]["quality_flag_score"]["expectations"][0][
            "checks"
        ]["min_stage_count"]
        is True
    )


def test_static_table_fallback_suite_manifest_is_explicitly_opt_in() -> None:
    manifest = json.loads(
        Path("docs/evaluation/tavr_static_table_fallback_suite.json").read_text(
            encoding="utf-8"
        )
    )

    assert manifest["cases"]
    case = manifest["cases"][0]
    assert case["config"]["static_table_fallback"] is True

    labels = json.loads(Path(case["labels_path"]).read_text(encoding="utf-8"))
    assert "--static-table-fallback" in labels["command_hint"]
    assert labels["procedure_status_expectations"][0]["effective_table_source"] == (
        "last_observed_room_view"
    )


def test_public_tavr_manifests_declare_required_score_checks() -> None:
    manifest_paths = [
        Path("docs/evaluation/tavr_suite.json"),
        Path("docs/evaluation/tavr_static_table_fallback_suite.json"),
        Path("docs/evaluation/tavr_synthetic_suite.json"),
    ]
    core_required = {
        "table_count_pass_rate",
        "stage_table_coverage_pass_rate",
        "table_transition_pass_rate",
        "stage_roster_pass_rate",
        "stage_evidence_pass_rate",
        "procedure_milestone_pass_rate",
        "procedure_status_pass_rate",
        "operator_packet_pass_rate",
        "table_team_pass_rate",
        "table_identity_group_pass_rate",
        "event_timeline_pass_rate",
        "quality_flag_pass_rate",
    }
    five_section_contract_cases = {
        "sentara_900_room_to_fluoro_low_motion",
        "sentara_1800_mixed_room",
        "sentara_2700_room_post",
        "sentara_900_static_table_fallback",
    }
    five_section_required = {
        "table_presence_pass_rate",
        "stage_staffing_pass_rate",
        "stage_handoff_pass_rate",
        "operator_snapshot_pass_rate",
        "roster_snapshot_pass_rate",
    }
    stage_labelled_cases = {
        "sentara_900_room_to_fluoro_low_motion",
        "sentara_1800_mixed_room",
        "sentara_2700_room_post",
        "sentara_900_static_table_fallback",
        "synthetic_full_tavr_workflow",
    }
    full_procedure_cases = {"synthetic_full_tavr_workflow"}
    full_procedure_required = {
        "table_presence_pass_rate",
        "stage_staffing_pass_rate",
        "stage_handoff_pass_rate",
        "operator_snapshot_pass_rate",
        "roster_snapshot_pass_rate",
    }
    person_interval_cases = {
        "sentara_1800_mixed_room",
        "sentara_2700_room_post",
        "sentara_900_static_table_fallback",
    }

    for manifest_path in manifest_paths:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["cases"]
        for case in manifest["cases"]:
            required = set(case.get("required_score_checks", []))
            assert core_required <= required, case["name"]
            assert required <= set(DEFAULT_THRESHOLDS), case["name"]
            if case["name"] in stage_labelled_cases:
                assert "stage_accuracy" in required, case["name"]
            if case["name"] in five_section_contract_cases:
                assert five_section_required <= required, case["name"]
            if case["name"] in full_procedure_cases:
                assert full_procedure_required <= required, case["name"]
            if case["name"] in person_interval_cases:
                assert "table_person_interval_pass_rate" in required, case["name"]
                assert "table_person_status_pass_rate" in required, case["name"]
