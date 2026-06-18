import json
from pathlib import Path

from evaluate_tavr_suite import _score_summary, run_suite
from or_tracking.synthetic import generate_synthetic_tavr_video


def test_score_summary_ignores_unscored_sections_and_fails_bad_scores() -> None:
    label_score = {
        "stage_score": {"accuracy": None},
        "table_count_score": {"pass_rate": 1.0},
        "table_presence_score": {"pass_rate": None},
        "stage_staffing_score": {"pass_rate": 0.5},
        "stage_table_coverage_score": {"pass_rate": None},
        "table_transition_score": {"pass_rate": None},
        "stage_handoff_score": {"pass_rate": None},
        "stage_roster_score": {"pass_rate": None},
        "stage_evidence_score": {"pass_rate": None},
        "procedure_milestone_score": {"pass_rate": None},
        "procedure_status_score": {"pass_rate": None},
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
        "stage_staffing_pass_rate": 1.0,
        "stage_table_coverage_pass_rate": 1.0,
        "table_transition_pass_rate": 1.0,
        "stage_handoff_pass_rate": 1.0,
        "stage_roster_pass_rate": 1.0,
        "stage_evidence_pass_rate": 1.0,
        "procedure_milestone_pass_rate": 1.0,
        "procedure_status_pass_rate": 1.0,
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
    ]


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
