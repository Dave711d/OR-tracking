"""Export compact public replay artifacts from TAVR suite outputs."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PublicDemoCase:
    source: Path
    target: Path


PUBLIC_DEMO_CASES = (
    PublicDemoCase(
        Path(
            "outputs/tavr_suite_table_presence_identity_verify/"
            "sentara_900_room_to_fluoro_low_motion/result.json"
        ),
        Path("public/demo-data/sentara-900-evaluation.json"),
    ),
    PublicDemoCase(
        Path(
            "outputs/tavr_suite_table_presence_identity_verify/"
            "sentara_1800_mixed_room/result.json"
        ),
        Path("public/demo-data/sentara-1800-evaluation.json"),
    ),
    PublicDemoCase(
        Path(
            "outputs/tavr_suite_table_presence_identity_verify/"
            "sentara_2400_fluoro_negative/result.json"
        ),
        Path("public/demo-data/sentara-2400-evaluation.json"),
    ),
    PublicDemoCase(
        Path(
            "outputs/tavr_suite_table_presence_identity_verify/"
            "sentara_2700_room_post/result.json"
        ),
        Path("public/demo-data/sentara-2700-evaluation.json"),
    ),
    PublicDemoCase(
        Path(
            "outputs/tavr_static_table_presence_identity_verify/"
            "sentara_900_static_table_fallback/result.json"
        ),
        Path("public/demo-data/sentara-900-static-fallback-evaluation.json"),
    ),
    PublicDemoCase(
        Path(
            "outputs/tavr_synthetic_table_presence_identity_verify/"
            "synthetic_full_tavr_workflow/result.json"
        ),
        Path("public/demo-data/synthetic-full-tavr-evaluation.json"),
    ),
)


def summarize_scores(label_score: dict[str, Any]) -> dict[str, float]:
    summary: dict[str, float] = {}
    for key, value in label_score.items():
        if key == "timebase" or not isinstance(value, dict):
            continue
        score = value.get("pass_rate", value.get("accuracy"))
        if isinstance(score, (int, float)):
            summary[key] = float(score)
    return summary


def build_public_payload(
    result_path: Path,
    *,
    generated_from: Path | None = None,
) -> dict[str, Any]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    label_score = result.get("label_score") or {}

    return {
        "case": result["case"],
        "generated_from": str(generated_from or result_path),
        "timebase": result.get("timebase") or {},
        "evaluation_config": result.get("evaluation_config") or {},
        "score_summary": summarize_scores(label_score),
        "label_score_timebase": label_score.get("timebase") or {},
        "tavr": result.get("tavr") or {},
    }


def write_payload(target_path: Path, payload: dict[str, Any], *, check: bool) -> bool:
    serialized = json.dumps(payload, indent=2) + "\n"
    if check:
        return target_path.exists() and target_path.read_text(encoding="utf-8") == serialized

    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(serialized, encoding="utf-8")
    return True


def export_public_demo_data(root: Path, *, check: bool = False) -> list[Path]:
    stale: list[Path] = []
    for demo_case in PUBLIC_DEMO_CASES:
        source_path = root / demo_case.source
        target_path = root / demo_case.target
        payload = build_public_payload(source_path, generated_from=demo_case.source)
        if not write_payload(target_path, payload, check=check):
            stale.append(demo_case.target)
    return stale


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("."),
        help="Repository root. Defaults to the current directory.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if public demo artifacts are missing or stale.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    stale = export_public_demo_data(args.root.resolve(), check=args.check)
    if stale:
        joined = ", ".join(str(path) for path in stale)
        print(f"Stale public demo artifacts: {joined}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
