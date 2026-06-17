"""Synthetic OR-like video fixtures for demos and tests."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Tuple

import cv2
import numpy as np


def generate_synthetic_or_video(
    output_path: str | Path,
    frames: int = 96,
    width: int = 640,
    height: int = 360,
    fps: float = 24.0,
) -> Path:
    """Create a small deterministic video with staff-like moving shapes."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        raise ValueError(f"Could not create synthetic video at {path}")

    try:
        for index in range(frames):
            frame = _base_or_frame(width, height)
            for x, y, color in _staff_positions(index, width, height):
                cv2.ellipse(frame, (x, y), (18, 32), 0, 0, 360, color, -1)
                cv2.circle(frame, (x, y - 34), 10, (230, 235, 245), -1)
            writer.write(frame)
    finally:
        writer.release()

    return path


def _base_or_frame(width: int, height: int) -> np.ndarray:
    frame = np.full((height, width, 3), (32, 38, 44), dtype=np.uint8)
    cv2.rectangle(
        frame,
        (int(width * 0.33), int(height * 0.33)),
        (int(width * 0.68), int(height * 0.70)),
        (58, 72, 84),
        -1,
    )
    cv2.rectangle(
        frame,
        (int(width * 0.39), int(height * 0.40)),
        (int(width * 0.61), int(height * 0.60)),
        (96, 116, 132),
        -1,
    )
    cv2.line(frame, (0, int(height * 0.83)), (width, int(height * 0.83)), (70, 75, 80), 2)
    return frame


def _staff_positions(
    frame_index: int, width: int, height: int
) -> Iterable[Tuple[int, int, Tuple[int, int, int]]]:
    x1 = int(width * 0.14 + frame_index * 2.8) % width
    y1 = int(height * 0.56)
    x2 = int(width * 0.76 - frame_index * 1.7)
    y2 = int(height * 0.42 + 28 * np.sin(frame_index / 14))
    x3 = int(width * 0.49 + 44 * np.sin(frame_index / 9))
    y3 = int(height * 0.76)
    return (
        (max(24, min(width - 24, x1)), y1, (88, 212, 255)),
        (max(24, min(width - 24, x2)), y2, (82, 190, 132)),
        (max(24, min(width - 24, x3)), y3, (210, 170, 92)),
    )
