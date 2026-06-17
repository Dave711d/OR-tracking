"""Process a test clip and print an auditable TAVR tracking summary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from or_tracking import MotionTrackerConfig, process_video_file
from or_tracking.evaluation import summarize_tavr_metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path, help="Video file to evaluate")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--max-frames", type=int, default=360)
    parser.add_argument("--start-frame", type=int, default=0)
    parser.add_argument("--start-s", type=float)
    parser.add_argument("--min-area", type=int, default=200)
    parser.add_argument("--crowding-threshold", type=int, default=4)
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.45,
        help="Flag stage estimates below this confidence",
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
        ),
        max_frames=args.max_frames,
        start_frame=args.start_frame,
        start_s=args.start_s,
        write_annotated_video=not args.no_annotated_video,
    )
    payload = {
        "input_path": str(result.input_path),
        "csv_path": str(result.csv_path),
        "annotated_video_path": (
            str(result.annotated_video_path) if result.annotated_video_path else None
        ),
        "tracking_summary": result.summary.to_dict(),
        "tavr": summarize_tavr_metrics(
            result.metrics,
            confidence_threshold=args.confidence_threshold,
        ),
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
