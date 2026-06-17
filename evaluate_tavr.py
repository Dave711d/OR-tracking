"""Process a test clip and print an auditable TAVR tracking summary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Tuple

from or_tracking import (
    MotionTrackerConfig,
    TAVR_STAGE_ORDER,
    process_video_file,
    score_tavr_metrics,
    write_tavr_summary_csvs,
)
from or_tracking.evaluation import summarize_tavr_metrics


NormalizedROI = Tuple[float, float, float, float]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path, help="Video file to evaluate")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--max-frames", type=int, default=360)
    parser.add_argument("--start-frame", type=int, default=0)
    parser.add_argument("--start-s", type=float)
    parser.add_argument(
        "--roi",
        type=parse_roi,
        help="Normalized crop x0,y0,x1,y1 for room-camera insets in broadcast footage",
    )
    parser.add_argument("--min-area", type=int, default=200)
    parser.add_argument("--crowding-threshold", type=int, default=4)
    parser.add_argument(
        "--static-table-fallback",
        action="store_true",
        help=(
            "Opt into conservative static table-zone silhouette detection for "
            "low-motion room-view review. Defaults off to avoid overcounting equipment."
        ),
    )
    parser.add_argument(
        "--initial-stage",
        choices=TAVR_STAGE_ORDER,
        default="room_prep_drape",
        help="Seed the sequential TAVR estimator for targeted case slices",
    )
    parser.add_argument(
        "--stage-dwell-frames",
        type=int,
        default=30,
        help="Minimum frames before the seeded/sequential stage can advance",
    )
    parser.add_argument(
        "--stage-advance-margin",
        type=float,
        default=0.06,
        help="Required score margin for advancing to the next TAVR stage",
    )
    parser.add_argument(
        "--min-stage-confidence",
        type=float,
        default=0.42,
        help="Minimum next-stage score needed before stage advancement",
    )
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.45,
        help="Flag stage estimates below this confidence",
    )
    parser.add_argument(
        "--labels",
        type=Path,
        help="Optional JSON labels file for stage/table scoring",
    )
    parser.add_argument(
        "--no-annotated-video",
        action="store_true",
        help="Skip annotated MP4 generation",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = process_video_file(
        args.video,
        output_dir=args.output_dir,
        config=MotionTrackerConfig(
            min_area=args.min_area,
            crowding_threshold=args.crowding_threshold,
            enable_static_table_fallback=args.static_table_fallback,
            tavr_initial_stage=args.initial_stage,
            tavr_min_confidence_to_advance=args.min_stage_confidence,
            tavr_advance_margin=args.stage_advance_margin,
            tavr_min_stage_frames=args.stage_dwell_frames,
        ),
        max_frames=args.max_frames,
        start_frame=args.start_frame,
        start_s=args.start_s,
        roi=args.roi,
        write_annotated_video=not args.no_annotated_video,
    )
    tavr_summary = summarize_tavr_metrics(
        result.metrics,
        confidence_threshold=args.confidence_threshold,
    )
    run_stem = result.csv_path.name.replace("_metrics.csv", "")
    tavr_csv_paths = write_tavr_summary_csvs(
        args.output_dir,
        run_stem,
        tavr_summary,
    )
    payload = {
        "input_path": str(result.input_path),
        "csv_path": str(result.csv_path),
        "tavr_csv_paths": tavr_csv_paths,
        "annotated_video_path": (
            str(result.annotated_video_path) if result.annotated_video_path else None
        ),
        "tracking_summary": result.summary.to_dict(),
        "evaluation_config": {
            "max_frames": args.max_frames,
            "start_frame": args.start_frame,
            "start_s": args.start_s,
            "roi": args.roi,
            "min_area": args.min_area,
            "crowding_threshold": args.crowding_threshold,
            "static_table_fallback": args.static_table_fallback,
            "initial_stage": args.initial_stage,
            "stage_dwell_frames": args.stage_dwell_frames,
            "stage_advance_margin": args.stage_advance_margin,
            "min_stage_confidence": args.min_stage_confidence,
            "confidence_threshold": args.confidence_threshold,
        },
        "tavr": tavr_summary,
    }
    if args.labels:
        labels = json.loads(args.labels.read_text(encoding="utf-8"))
        payload["label_path"] = str(args.labels)
        payload["label_score"] = score_tavr_metrics(result.metrics, labels)
    print(json.dumps(payload, indent=2))


def parse_roi(value: str) -> NormalizedROI:
    parts = value.split(",")
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("ROI must be x0,y0,x1,y1")
    try:
        x0, y0, x1, y1 = (float(part) for part in parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("ROI values must be numbers") from exc
    if not (0.0 <= x0 < x1 <= 1.0 and 0.0 <= y0 < y1 <= 1.0):
        raise argparse.ArgumentTypeError("ROI values must be normalized within 0..1")
    return x0, y0, x1, y1


if __name__ == "__main__":
    main()
