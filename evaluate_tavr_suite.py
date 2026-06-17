"""Run a manifest-driven TAVR evaluation suite."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from or_tracking import (
    MotionTrackerConfig,
    process_video_file,
    score_tavr_metrics,
    write_tavr_summary_csvs,
)
from or_tracking.evaluation import summarize_tavr_metrics


NormalizedROI = Tuple[float, float, float, float]

DEFAULT_MANIFEST = Path("docs/evaluation/tavr_suite.json")
DEFAULT_THRESHOLDS = {
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
    "event_timeline_pass_rate": 1.0,
    "roster_snapshot_pass_rate": 1.0,
    "quality_flag_pass_rate": 1.0,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "manifest",
        type=Path,
        nargs="?",
        default=DEFAULT_MANIFEST,
        help="Evaluation suite manifest JSON",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/tavr_suite"),
        help="Directory for aggregate and per-case JSON outputs",
    )
    parser.add_argument(
        "--write-annotated-video",
        action="store_true",
        help="Write annotated videos for suite cases",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = run_suite(
        args.manifest,
        output_dir=args.output_dir,
        write_annotated_video=args.write_annotated_video,
    )
    print(json.dumps(summary, indent=2))
    raise SystemExit(0 if summary["passed"] else 1)


def run_suite(
    manifest_path: str | Path,
    output_dir: str | Path,
    write_annotated_video: bool = False,
) -> Dict[str, Any]:
    manifest_path = Path(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    suite_output_dir = Path(output_dir)
    suite_output_dir.mkdir(parents=True, exist_ok=True)

    cases = manifest.get("cases", [])
    case_results = [
        _run_case(
            case,
            manifest_path=manifest_path,
            suite_output_dir=suite_output_dir,
            write_annotated_video=write_annotated_video,
            suite_thresholds=manifest.get("thresholds", {}),
        )
        for case in cases
    ]
    passed_count = sum(1 for case in case_results if case["passed"])
    summary = {
        "suite": manifest.get("name", manifest_path.stem),
        "manifest_path": str(manifest_path),
        "output_dir": str(suite_output_dir),
        "case_count": len(case_results),
        "passed_count": passed_count,
        "failed_count": len(case_results) - passed_count,
        "passed": bool(case_results) and passed_count == len(case_results),
        "cases": case_results,
    }
    summary_path = suite_output_dir / "suite_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    summary["summary_path"] = str(summary_path)
    return summary


def _run_case(
    case: Dict[str, Any],
    manifest_path: Path,
    suite_output_dir: Path,
    write_annotated_video: bool,
    suite_thresholds: Dict[str, Any],
) -> Dict[str, Any]:
    name = str(case["name"])
    case_output_dir = suite_output_dir / _slug(name)
    case_output_dir.mkdir(parents=True, exist_ok=True)
    output_path = case_output_dir / "result.json"

    try:
        video_path = _resolve_path(case["video_path"], manifest_path)
        labels_path = _resolve_path(case["labels_path"], manifest_path)
        labels = json.loads(labels_path.read_text(encoding="utf-8"))
        config = case.get("config", {})
        result = process_video_file(
            video_path,
            output_dir=case_output_dir,
            config=MotionTrackerConfig(
                min_area=int(config.get("min_area", 200)),
                crowding_threshold=int(config.get("crowding_threshold", 4)),
                enable_static_table_fallback=bool(
                    config.get("static_table_fallback", False)
                ),
                tavr_initial_stage=str(config.get("initial_stage", "room_prep_drape")),
                tavr_min_confidence_to_advance=float(
                    config.get("min_stage_confidence", 0.42)
                ),
                tavr_advance_margin=float(config.get("stage_advance_margin", 0.06)),
                tavr_min_stage_frames=int(config.get("stage_dwell_frames", 30)),
            ),
            max_frames=_optional_int(config.get("max_frames")),
            start_frame=int(config.get("start_frame", 0)),
            start_s=_optional_float(config.get("start_s")),
            roi=_optional_roi(config.get("roi")),
            write_annotated_video=write_annotated_video,
        )
        tavr_summary = summarize_tavr_metrics(result.metrics)
        run_stem = result.csv_path.name.replace("_metrics.csv", "")
        tavr_csv_paths = write_tavr_summary_csvs(
            case_output_dir,
            run_stem,
            tavr_summary,
        )
        label_score = score_tavr_metrics(result.metrics, labels)
        payload = {
            "case": name,
            "input_path": str(result.input_path),
            "label_path": str(labels_path),
            "csv_path": str(result.csv_path),
            "tavr_csv_paths": tavr_csv_paths,
            "annotated_video_path": (
                str(result.annotated_video_path) if result.annotated_video_path else None
            ),
            "tracking_summary": result.summary.to_dict(),
            "evaluation_config": config,
            "tavr": tavr_summary,
            "label_score": label_score,
        }
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        thresholds = {
            **DEFAULT_THRESHOLDS,
            **suite_thresholds,
            **case.get("thresholds", {}),
        }
        score_summary = _score_summary(label_score, thresholds)
        return {
            "name": name,
            "passed": score_summary["passed"],
            "result_path": str(output_path),
            "tavr_csv_paths": tavr_csv_paths,
            "score_summary": score_summary,
            "quality_flags": tavr_summary.get("quality_flags", []),
        }
    except Exception as exc:  # pragma: no cover - exact errors vary by host
        error_payload = {"case": name, "error": f"{type(exc).__name__}: {exc}"}
        output_path.write_text(json.dumps(error_payload, indent=2), encoding="utf-8")
        return {
            "name": name,
            "passed": False,
            "result_path": str(output_path),
            "error": error_payload["error"],
            "score_summary": {"passed": False, "checks": []},
            "quality_flags": [],
        }


def _score_summary(
    label_score: Dict[str, Any],
    thresholds: Dict[str, Any],
) -> Dict[str, Any]:
    checks = [
        _threshold_check(
            "stage_accuracy",
            label_score["stage_score"]["accuracy"],
            thresholds["stage_accuracy"],
        ),
        _threshold_check(
            "table_count_pass_rate",
            label_score["table_count_score"]["pass_rate"],
            thresholds["table_count_pass_rate"],
        ),
        _threshold_check(
            "table_presence_pass_rate",
            label_score["table_presence_score"]["pass_rate"],
            thresholds["table_presence_pass_rate"],
        ),
        _threshold_check(
            "stage_staffing_pass_rate",
            label_score["stage_staffing_score"]["pass_rate"],
            thresholds["stage_staffing_pass_rate"],
        ),
        _threshold_check(
            "stage_table_coverage_pass_rate",
            label_score["stage_table_coverage_score"]["pass_rate"],
            thresholds["stage_table_coverage_pass_rate"],
        ),
        _threshold_check(
            "table_transition_pass_rate",
            label_score["table_transition_score"]["pass_rate"],
            thresholds["table_transition_pass_rate"],
        ),
        _threshold_check(
            "stage_handoff_pass_rate",
            label_score["stage_handoff_score"]["pass_rate"],
            thresholds["stage_handoff_pass_rate"],
        ),
        _threshold_check(
            "stage_roster_pass_rate",
            label_score["stage_roster_score"]["pass_rate"],
            thresholds["stage_roster_pass_rate"],
        ),
        _threshold_check(
            "stage_evidence_pass_rate",
            label_score["stage_evidence_score"]["pass_rate"],
            thresholds["stage_evidence_pass_rate"],
        ),
        _threshold_check(
            "procedure_milestone_pass_rate",
            label_score["procedure_milestone_score"]["pass_rate"],
            thresholds["procedure_milestone_pass_rate"],
        ),
        _threshold_check(
            "procedure_status_pass_rate",
            label_score["procedure_status_score"]["pass_rate"],
            thresholds["procedure_status_pass_rate"],
        ),
        _threshold_check(
            "operator_packet_pass_rate",
            label_score["operator_packet_score"]["pass_rate"],
            thresholds["operator_packet_pass_rate"],
        ),
        _threshold_check(
            "table_team_pass_rate",
            label_score["table_team_score"]["pass_rate"],
            thresholds["table_team_pass_rate"],
        ),
        _threshold_check(
            "event_timeline_pass_rate",
            label_score["event_timeline_score"]["pass_rate"],
            thresholds["event_timeline_pass_rate"],
        ),
        _threshold_check(
            "roster_snapshot_pass_rate",
            label_score["roster_snapshot_score"]["pass_rate"],
            thresholds["roster_snapshot_pass_rate"],
        ),
        _threshold_check(
            "quality_flag_pass_rate",
            label_score["quality_flag_score"]["pass_rate"],
            thresholds["quality_flag_pass_rate"],
        ),
    ]
    scored = [check for check in checks if check["scored"]]
    return {
        "passed": bool(scored) and all(check["passed"] for check in scored),
        "checks": checks,
    }


def _threshold_check(
    name: str,
    value: Optional[float],
    threshold: float,
) -> Dict[str, Any]:
    if value is None:
        return {
            "name": name,
            "scored": False,
            "passed": None,
            "value": None,
            "threshold": threshold,
        }
    return {
        "name": name,
        "scored": True,
        "passed": value >= threshold,
        "value": value,
        "threshold": threshold,
    }


def _resolve_path(value: str, manifest_path: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    if path.exists():
        return path
    for parent in manifest_path.resolve().parents:
        candidate = parent / path
        if candidate.exists():
            return candidate
    return manifest_path.parent / path


def _optional_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    return int(value)


def _optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    return float(value)


def _optional_roi(value: Any) -> Optional[NormalizedROI]:
    if value is None:
        return None
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError("ROI must be a four-number list")
    x0, y0, x1, y1 = (float(part) for part in value)
    if not (0.0 <= x0 < x1 <= 1.0 and 0.0 <= y0 < y1 <= 1.0):
        raise ValueError("ROI values must be normalized within 0..1")
    return x0, y0, x1, y1


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip().lower()).strip("-")
    return slug or "case"


if __name__ == "__main__":
    main()
