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


def generate_synthetic_tavr_video(
    output_path: str | Path,
    frames: int = 320,
    width: int = 720,
    height: int = 420,
    fps: float = 24.0,
) -> Path:
    """Create deterministic TAVR-room footage for stage-inference tests."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        raise ValueError(f"Could not create synthetic TAVR video at {path}")

    try:
        for index in range(frames):
            frame = _base_tavr_frame(width, height)
            stage = _synthetic_tavr_stage(index, frames)
            _draw_stage_equipment(frame, stage, index, width, height)
            for x, y, color in _tavr_staff_positions(stage, index, width, height):
                cv2.ellipse(frame, (x, y), (17, 30), 0, 0, 360, color, -1)
                cv2.circle(frame, (x, y - 32), 9, (230, 235, 245), -1)
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


def _base_tavr_frame(width: int, height: int) -> np.ndarray:
    frame = np.full((height, width, 3), (28, 34, 40), dtype=np.uint8)
    cv2.rectangle(
        frame,
        (int(width * 0.32), int(height * 0.30)),
        (int(width * 0.70), int(height * 0.74)),
        (55, 70, 82),
        -1,
    )
    cv2.rectangle(
        frame,
        (int(width * 0.40), int(height * 0.40)),
        (int(width * 0.62), int(height * 0.60)),
        (92, 112, 130),
        -1,
    )
    cv2.rectangle(
        frame,
        (int(width * 0.04), int(height * 0.08)),
        (int(width * 0.25), int(height * 0.30)),
        (44, 54, 62),
        -1,
    )
    cv2.putText(
        frame,
        "device table",
        (int(width * 0.06), int(height * 0.18)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        (110, 128, 140),
        1,
        cv2.LINE_AA,
    )
    cv2.rectangle(
        frame,
        (int(width * 0.73), int(height * 0.04)),
        (int(width * 0.96), int(height * 0.27)),
        (38, 46, 52),
        -1,
    )
    cv2.putText(
        frame,
        "anesthesia",
        (int(width * 0.75), int(height * 0.16)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        (110, 128, 140),
        1,
        cv2.LINE_AA,
    )
    return frame


def _synthetic_tavr_stage(frame_index: int, total_frames: int) -> str:
    progress = frame_index / max(total_frames, 1)
    if progress < 0.13:
        return "room_prep_drape"
    if progress < 0.26:
        return "access_sheathing"
    if progress < 0.39:
        return "angio_alignment_crossing"
    if progress < 0.51:
        return "bav_optional"
    if progress < 0.64:
        return "valve_delivery_positioning"
    if progress < 0.75:
        return "valve_deployment"
    if progress < 0.87:
        return "post_deploy_assessment"
    return "closure_finish"


def _draw_stage_equipment(
    frame: np.ndarray,
    stage: str,
    frame_index: int,
    width: int,
    height: int,
) -> None:
    if stage in {
        "angio_alignment_crossing",
        "bav_optional",
        "valve_delivery_positioning",
        "valve_deployment",
        "post_deploy_assessment",
    }:
        c_arm_x = int(width * (0.50 + 0.04 * np.sin(frame_index / 11)))
        cv2.circle(frame, (c_arm_x, int(height * 0.15)), 34, (82, 92, 102), 5)
        cv2.line(
            frame,
            (c_arm_x, int(height * 0.18)),
            (int(width * 0.52), int(height * 0.39)),
            (82, 92, 102),
            7,
        )
    if stage in {"bav_optional", "valve_deployment"}:
        pulse = int(20 + 18 * np.sin(frame_index / 3))
        cv2.circle(
            frame,
            (int(width * 0.52), int(height * 0.49)),
            max(8, pulse),
            (72, 128, 210),
            2,
        )
    if stage == "valve_delivery_positioning":
        cv2.rectangle(
            frame,
            (int(width * 0.18), int(height * 0.18)),
            (int(width * 0.32), int(height * 0.25)),
            (88, 170, 210),
            -1,
        )
    if stage == "closure_finish":
        cv2.line(
            frame,
            (int(width * 0.28), int(height * 0.78)),
            (int(width * 0.48), int(height * 0.78)),
            (130, 95, 95),
            8,
        )


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


def _tavr_staff_positions(
    stage: str,
    frame_index: int,
    width: int,
    height: int,
) -> Iterable[Tuple[int, int, Tuple[int, int, int]]]:
    jitter = lambda scale, speed=8: int(scale * np.sin(frame_index / speed))
    normalized_positions = {
        "room_prep_drape": (
            (0.16, 0.24, (88, 212, 255)),
            (0.84, 0.20, (82, 190, 132)),
            (0.10, 0.70, (210, 170, 92)),
        ),
        "access_sheathing": (
            (0.35, 0.80, (88, 212, 255)),
            (0.42, 0.66, (82, 190, 132)),
            (0.83, 0.18, (210, 170, 92)),
        ),
        "angio_alignment_crossing": (
            (0.34, 0.56, (88, 212, 255)),
            (0.64, 0.48, (82, 190, 132)),
            (0.55, 0.18, (210, 170, 92)),
        ),
        "bav_optional": (
            (0.35, 0.54, (88, 212, 255)),
            (0.65, 0.52, (82, 190, 132)),
            (0.55, 0.17, (210, 170, 92)),
        ),
        "valve_delivery_positioning": (
            (0.18, 0.22, (88, 212, 255)),
            (0.36, 0.55, (82, 190, 132)),
            (0.64, 0.50, (210, 170, 92)),
            (0.56, 0.18, (190, 110, 210)),
        ),
        "valve_deployment": (
            (0.35, 0.52, (88, 212, 255)),
            (0.65, 0.52, (82, 190, 132)),
            (0.55, 0.16, (210, 170, 92)),
        ),
        "post_deploy_assessment": (
            (0.56, 0.18, (88, 212, 255)),
            (0.64, 0.48, (82, 190, 132)),
            (0.84, 0.20, (210, 170, 92)),
        ),
        "closure_finish": (
            (0.34, 0.80, (88, 212, 255)),
            (0.45, 0.70, (82, 190, 132)),
            (0.12, 0.72, (210, 170, 92)),
        ),
    }
    for x_norm, y_norm, color in normalized_positions[stage]:
        x = int(width * x_norm) + jitter(6)
        y = int(height * y_norm) + jitter(4, speed=10)
        yield max(24, min(width - 24, x)), max(42, min(height - 24, y)), color
