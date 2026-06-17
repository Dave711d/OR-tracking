"""Download a sample OR video or generate a deterministic local fixture."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict

from or_tracking.synthetic import generate_synthetic_or_video


DEFAULT_OUTPUT = Path("samples/or_sample.mp4")


def build_ytdlp_options(output_path: Path) -> Dict[str, object]:
    return {
        "format": "bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4][height<=720]/best",
        "merge_output_format": "mp4",
        "outtmpl": str(output_path),
        "quiet": False,
        "noplaylist": True,
    }


def download_video(url: str, output_path: Path) -> Path:
    try:
        import yt_dlp
    except ImportError as exc:
        raise SystemExit("yt-dlp is required. Run: pip install -r requirements.txt") from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)
    options = build_ytdlp_options(output_path)
    with yt_dlp.YoutubeDL(options) as ydl:
        ydl.download([url])
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", help="Video URL to download")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output path. Default: {DEFAULT_OUTPUT}",
    )
    parser.add_argument(
        "--fixture",
        action="store_true",
        help="Generate a deterministic synthetic OR fixture instead of downloading",
    )
    parser.add_argument(
        "--no-fallback",
        action="store_true",
        help="Fail if the remote download is blocked instead of generating a fixture",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.fixture:
        path = generate_synthetic_or_video(args.output)
        print(path)
        return
    if not args.url:
        raise SystemExit("Provide --url or use --fixture")
    try:
        path = download_video(args.url, args.output)
    except Exception as exc:
        if args.no_fallback:
            raise
        print(f"Download failed ({exc}). Generating fixture at {args.output}.")
        path = generate_synthetic_or_video(args.output)
    print(path)


if __name__ == "__main__":
    main()
