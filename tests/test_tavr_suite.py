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
        "stage_handoff_score": {"pass_rate": None},
        "event_timeline_score": {"pass_rate": None},
        "roster_snapshot_score": {"pass_rate": None},
        "quality_flag_score": {"pass_rate": None},
    }
    thresholds = {
        "stage_accuracy": 1.0,
        "table_count_pass_rate": 1.0,
        "table_presence_pass_rate": 1.0,
        "stage_staffing_pass_rate": 1.0,
        "stage_handoff_pass_rate": 1.0,
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
                            "initial_stage": "room_prep_drape",
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
    assert Path(summary["cases"][0]["result_path"]).exists()
    assert summary["cases"][0]["tavr_csv_paths"]["stage_timeline"]
    assert Path(summary["cases"][0]["tavr_csv_paths"]["stage_timeline"]).exists()
    assert Path(summary["summary_path"]).exists()
