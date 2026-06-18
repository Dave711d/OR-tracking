"""CPU-friendly video tracking primitives.

This module intentionally starts with deterministic motion tracking rather than a
heavy model download. It makes the prototype deployable on Streamlit Cloud,
Hugging Face Spaces, and Vercel's static hosting path today.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import hypot
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import cv2
import numpy as np

from .models import BBox, Detection, FrameMetrics, Point
from .tavr import ROLE_ZONE_MAP, TABLE_ZONES, TAVRWorkflowAnalyzer, tavr_default_zones


ZoneMap = Mapping[str, Tuple[float, float, float, float]]
ROLE_ZONE_PRIORITY = (
    "access",
    "device_table",
    "imaging",
    "anesthesia",
    "table_left",
    "table_right",
    "table",
    "entry",
)


def _default_zones() -> Dict[str, Tuple[float, float, float, float]]:
    return tavr_default_zones()


@dataclass
class MotionTrackerConfig:
    """Configuration for the OpenCV motion tracker."""

    min_area: int = 700
    history: int = 300
    var_threshold: float = 24.0
    learning_rate: float = -1.0
    blur_kernel: int = 5
    morphology_kernel: int = 5
    max_match_distance: float = 90.0
    max_disappeared: int = 12
    crowding_threshold: int = 4
    zones: ZoneMap = field(default_factory=_default_zones)
    suppress_non_room_tracking: bool = True
    freeze_non_room_tavr_stage: bool = True
    non_room_colorfulness_threshold: float = 8.0
    enable_static_table_fallback: bool = False
    static_table_min_area: int = 240
    static_table_max_zone_area_ratio: float = 0.38
    static_table_min_aspect_ratio: float = 0.18
    static_table_max_aspect_ratio: float = 2.25
    static_table_min_saturation: int = 28
    static_table_max_value: int = 238
    enable_tavr: bool = True
    tavr_initial_stage: str = "room_prep_drape"
    tavr_min_confidence_to_advance: float = 0.42
    tavr_advance_margin: float = 0.06
    tavr_min_stage_frames: int = 30


@dataclass
class _TrackState:
    track_id: int
    bbox: BBox
    centroid: Point
    area: float
    disappeared: int = 0
    total_distance: float = 0.0
    last_frame_index: int = 0


class _CentroidTracker:
    """Small centroid tracker with greedy nearest-neighbor assignment."""

    def __init__(self, max_distance: float, max_disappeared: int) -> None:
        self.max_distance = max_distance
        self.max_disappeared = max_disappeared
        self._next_id = 1
        self._tracks: Dict[int, _TrackState] = {}

    @property
    def track_count(self) -> int:
        return self._next_id - 1

    def update(
        self, candidates: Sequence[Tuple[BBox, Point, float]], frame_index: int
    ) -> Tuple[List[Detection], float]:
        if not candidates:
            self._age_unmatched(set())
            return [], 0.0

        if not self._tracks:
            detections = [
                self._register(bbox, centroid, area, frame_index)
                for bbox, centroid, area in candidates
            ]
            return detections, 0.0

        unmatched_tracks = set(self._tracks)
        unmatched_detections = set(range(len(candidates)))
        assignments: List[Tuple[int, int, float]] = []

        for track_id, track in self._tracks.items():
            for detection_index, (_, centroid, _) in enumerate(candidates):
                distance = _distance(track.centroid, centroid)
                if distance <= self.max_distance:
                    assignments.append((track_id, detection_index, distance))

        assignments.sort(key=lambda item: item[2])
        chosen: List[Tuple[int, int, float]] = []
        for track_id, detection_index, distance in assignments:
            if track_id in unmatched_tracks and detection_index in unmatched_detections:
                chosen.append((track_id, detection_index, distance))
                unmatched_tracks.remove(track_id)
                unmatched_detections.remove(detection_index)

        detections: List[Detection] = []
        movement_px = 0.0
        for track_id, detection_index, distance in chosen:
            bbox, centroid, area = candidates[detection_index]
            track = self._tracks[track_id]
            track.bbox = bbox
            track.centroid = centroid
            track.area = area
            track.disappeared = 0
            track.total_distance += distance
            track.last_frame_index = frame_index
            movement_px += distance
            detections.append(
                Detection(track_id=track_id, bbox=bbox, centroid=centroid, area=area)
            )

        for detection_index in sorted(unmatched_detections):
            bbox, centroid, area = candidates[detection_index]
            detections.append(self._register(bbox, centroid, area, frame_index))

        self._age_unmatched(unmatched_tracks)
        detections.sort(key=lambda detection: detection.track_id)
        return detections, movement_px

    def _register(
        self, bbox: BBox, centroid: Point, area: float, frame_index: int
    ) -> Detection:
        track_id = self._next_id
        self._next_id += 1
        self._tracks[track_id] = _TrackState(
            track_id=track_id,
            bbox=bbox,
            centroid=centroid,
            area=area,
            last_frame_index=frame_index,
        )
        return Detection(track_id=track_id, bbox=bbox, centroid=centroid, area=area)

    def _age_unmatched(self, unmatched_track_ids: Iterable[int]) -> None:
        expired: List[int] = []
        for track_id in unmatched_track_ids:
            track = self._tracks.get(track_id)
            if track is None:
                continue
            track.disappeared += 1
            if track.disappeared > self.max_disappeared:
                expired.append(track_id)
        for track_id in expired:
            del self._tracks[track_id]


class ORActivityTracker:
    """Detect and track moving staff-like objects in OR video frames."""

    def __init__(self, config: Optional[MotionTrackerConfig] = None) -> None:
        self.config = config or MotionTrackerConfig()
        self._background = cv2.createBackgroundSubtractorMOG2(
            history=self.config.history,
            varThreshold=self.config.var_threshold,
            detectShadows=True,
        )
        self._tracker = _CentroidTracker(
            max_distance=self.config.max_match_distance,
            max_disappeared=self.config.max_disappeared,
        )
        self._tavr = (
            TAVRWorkflowAnalyzer(
                initial_stage=self.config.tavr_initial_stage,
                min_confidence_to_advance=self.config.tavr_min_confidence_to_advance,
                advance_margin=self.config.tavr_advance_margin,
                min_stage_frames=self.config.tavr_min_stage_frames,
            )
            if self.config.enable_tavr
            else None
        )

    @property
    def total_tracks_seen(self) -> int:
        return self._tracker.track_count

    def process_frame(
        self,
        frame: np.ndarray,
        frame_index: int,
        timestamp_s: float,
        *,
        clip_frame_index: Optional[int] = None,
        clip_timestamp_s: Optional[float] = None,
    ) -> FrameMetrics:
        view_colorfulness = _colorfulness(frame)
        view_flags = self._view_quality_flags(view_colorfulness)
        candidates = self._detect_motion_candidates(frame)
        static_table_used = False
        if view_flags and self.config.suppress_non_room_tracking:
            candidates = []
        elif self.config.enable_static_table_fallback and not self._has_table_candidate(
            candidates,
            frame.shape[1],
            frame.shape[0],
        ):
            static_candidates = self._detect_static_table_candidates(frame)
            if static_candidates:
                candidates = list(candidates) + static_candidates
                static_table_used = True
        detections, movement_px = self._tracker.update(candidates, frame_index)
        zone_counts = self._zone_counts(detections, frame.shape[1], frame.shape[0])
        alert_flags = view_flags + self._alert_flags(detections, zone_counts)
        if static_table_used:
            alert_flags.append("static_table_fallback")
        tavr = None
        if self._tavr is not None:
            table_track_ids = self._track_ids_in_zones(
                detections,
                frame.shape[1],
                frame.shape[0],
                TABLE_ZONES,
            )
            role_track_ids = self._role_track_ids(
                detections,
                frame.shape[1],
                frame.shape[0],
            )
            stage_observable = not (
                self.config.freeze_non_room_tavr_stage
                and "non_room_view" in view_flags
            )
            tavr = self._tavr.update(
                detections=detections,
                zone_counts=zone_counts,
                table_track_ids=table_track_ids,
                role_track_ids=role_track_ids,
                frame_index=frame_index,
                movement_px=movement_px,
                stage_observable=stage_observable,
                stage_frame_index=clip_frame_index,
            )
        return FrameMetrics(
            frame_index=frame_index,
            timestamp_s=timestamp_s,
            clip_frame_index=clip_frame_index,
            clip_timestamp_s=clip_timestamp_s,
            detections=detections,
            movement_px=movement_px,
            zone_counts=zone_counts,
            alert_flags=alert_flags,
            view_colorfulness=view_colorfulness,
            tavr=tavr,
        )

    def annotate_frame(
        self,
        frame: np.ndarray,
        metrics: FrameMetrics,
    ) -> np.ndarray:
        annotated = frame.copy()
        height, width = annotated.shape[:2]
        self._draw_zones(annotated, width, height)

        for detection in metrics.detections:
            x, y, w, h = detection.bbox
            color = (32, 190, 255)
            cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 2)
            cv2.circle(annotated, detection.centroid, 4, (20, 255, 120), -1)
            cv2.putText(
                annotated,
                f"ID {detection.track_id}",
                (x, max(20, y - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                color,
                2,
                cv2.LINE_AA,
            )

        status = (
            f"People {metrics.people_count} | Move {metrics.movement_px:.0f}px"
        )
        if metrics.tavr is not None:
            status = (
                f"{metrics.tavr.stage_label} | Table {metrics.tavr.table_count} | "
                f"Conf {metrics.tavr.confidence:.2f}"
            )
        if "non_room_view" in metrics.alert_flags:
            status = "Non-room / fluoroscopy view | staff tracking suppressed"
        cv2.rectangle(annotated, (10, 10), (520, 46), (12, 18, 28), -1)
        cv2.putText(
            annotated,
            status,
            (20, 34),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            (245, 248, 255),
            2,
            cv2.LINE_AA,
        )
        return annotated

    def _detect_motion_candidates(
        self, frame: np.ndarray
    ) -> List[Tuple[BBox, Point, float]]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blur_kernel = _odd_kernel(self.config.blur_kernel)
        if blur_kernel > 1:
            gray = cv2.GaussianBlur(gray, (blur_kernel, blur_kernel), 0)

        mask = self._background.apply(gray, learningRate=self.config.learning_rate)
        _, mask = cv2.threshold(mask, 200, 255, cv2.THRESH_BINARY)

        morph_kernel = _odd_kernel(self.config.morphology_kernel)
        if morph_kernel > 1:
            kernel = np.ones((morph_kernel, morph_kernel), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates: List[Tuple[BBox, Point, float]] = []
        for contour in contours:
            area = float(cv2.contourArea(contour))
            if area < self.config.min_area:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            if w < 8 or h < 12:
                continue
            candidates.append(((x, y, w, h), (x + w // 2, y + h // 2), area))

        candidates.sort(key=lambda item: item[2], reverse=True)
        return candidates

    def _detect_static_table_candidates(
        self, frame: np.ndarray
    ) -> List[Tuple[BBox, Point, float]]:
        """Return conservative static table-zone silhouettes in room views."""

        height, width = frame.shape[:2]
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        candidates: List[Tuple[BBox, Point, float]] = []
        for zone_name in TABLE_ZONES:
            zone = self.config.zones.get(zone_name)
            if zone is None:
                continue
            x0, y0, x1, y1 = _zone_pixels(zone, width, height)
            if x1 <= x0 or y1 <= y0:
                continue
            crop = hsv[y0:y1, x0:x1]
            if crop.size == 0:
                continue

            saturation = crop[:, :, 1]
            value = crop[:, :, 2]
            mask = (
                (saturation >= self.config.static_table_min_saturation)
                & (value <= self.config.static_table_max_value)
            ).astype("uint8") * 255
            kernel = np.ones((3, 3), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            contours, _ = cv2.findContours(
                mask,
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE,
            )
            zone_area = max((x1 - x0) * (y1 - y0), 1)
            max_area = zone_area * self.config.static_table_max_zone_area_ratio
            for contour in contours:
                area = float(cv2.contourArea(contour))
                if area < self.config.static_table_min_area or area > max_area:
                    continue
                bx, by, bw, bh = cv2.boundingRect(contour)
                if bw < 8 or bh < 16:
                    continue
                aspect_ratio = bw / max(float(bh), 1.0)
                if not (
                    self.config.static_table_min_aspect_ratio
                    <= aspect_ratio
                    <= self.config.static_table_max_aspect_ratio
                ):
                    continue
                bbox = (x0 + bx, y0 + by, bw, bh)
                centroid = (bbox[0] + bw // 2, bbox[1] + bh // 2)
                candidates.append((bbox, centroid, area))

        return _dedupe_candidates(candidates)

    def _has_table_candidate(
        self,
        candidates: Sequence[Tuple[BBox, Point, float]],
        width: int,
        height: int,
    ) -> bool:
        for _, centroid, _ in candidates:
            cx = centroid[0] / max(width, 1)
            cy = centroid[1] / max(height, 1)
            for zone_name in TABLE_ZONES:
                zone = self.config.zones.get(zone_name)
                if zone is None:
                    continue
                x0, y0, x1, y1 = zone
                if x0 <= cx <= x1 and y0 <= cy <= y1:
                    return True
        return False

    def _zone_counts(
        self,
        detections: Sequence[Detection],
        width: int,
        height: int,
    ) -> Dict[str, int]:
        counts = {name: 0 for name in self.config.zones}
        for detection in detections:
            cx = detection.centroid[0] / max(width, 1)
            cy = detection.centroid[1] / max(height, 1)
            for zone_name, (x0, y0, x1, y1) in self.config.zones.items():
                if x0 <= cx <= x1 and y0 <= cy <= y1:
                    counts[zone_name] += 1
        return counts

    def _track_ids_in_zones(
        self,
        detections: Sequence[Detection],
        width: int,
        height: int,
        zone_names: Sequence[str],
    ) -> List[int]:
        track_ids: List[int] = []
        for detection in detections:
            cx = detection.centroid[0] / max(width, 1)
            cy = detection.centroid[1] / max(height, 1)
            for zone_name in zone_names:
                zone = self.config.zones.get(zone_name)
                if zone is None:
                    continue
                x0, y0, x1, y1 = zone
                if x0 <= cx <= x1 and y0 <= cy <= y1:
                    track_ids.append(detection.track_id)
                    break
        return sorted(set(track_ids))

    def _role_track_ids(
        self,
        detections: Sequence[Detection],
        width: int,
        height: int,
    ) -> Dict[str, List[int]]:
        role_track_ids: Dict[str, List[int]] = {
            role: [] for role in sorted(set(ROLE_ZONE_MAP.values()))
        }
        for detection in detections:
            zone_name = self._primary_role_zone(detection, width, height)
            if zone_name is None:
                continue
            role_track_ids[ROLE_ZONE_MAP[zone_name]].append(detection.track_id)

        return {
            role: sorted(set(track_ids))
            for role, track_ids in role_track_ids.items()
        }

    def _primary_role_zone(
        self,
        detection: Detection,
        width: int,
        height: int,
    ) -> Optional[str]:
        cx = detection.centroid[0] / max(width, 1)
        cy = detection.centroid[1] / max(height, 1)
        for zone_name in ROLE_ZONE_PRIORITY:
            zone = self.config.zones.get(zone_name)
            if zone is None:
                continue
            x0, y0, x1, y1 = zone
            if x0 <= cx <= x1 and y0 <= cy <= y1:
                return zone_name
        return None

    def _alert_flags(
        self, detections: Sequence[Detection], zone_counts: Mapping[str, int]
    ) -> List[str]:
        flags: List[str] = []
        if len(detections) >= self.config.crowding_threshold:
            flags.append("crowding")
        if zone_counts.get("entry", 0) > 0:
            flags.append("entry_activity")
        return flags

    def _view_quality_flags(self, view_colorfulness: float) -> List[str]:
        if view_colorfulness < self.config.non_room_colorfulness_threshold:
            return ["non_room_view"]
        return []

    def _draw_zones(self, frame: np.ndarray, width: int, height: int) -> None:
        for zone_name, (x0, y0, x1, y1) in self.config.zones.items():
            pt1 = (int(x0 * width), int(y0 * height))
            pt2 = (int(x1 * width), int(y1 * height))
            cv2.rectangle(frame, pt1, pt2, (92, 118, 255), 1)
            cv2.putText(
                frame,
                zone_name,
                (pt1[0] + 6, pt1[1] + 18),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (190, 205, 255),
                1,
                cv2.LINE_AA,
            )


def _distance(a: Point, b: Point) -> float:
    return hypot(a[0] - b[0], a[1] - b[1])


def _odd_kernel(value: int) -> int:
    value = max(int(value), 1)
    return value if value % 2 == 1 else value + 1


def _zone_pixels(
    zone: Tuple[float, float, float, float],
    width: int,
    height: int,
) -> Tuple[int, int, int, int]:
    x0, y0, x1, y1 = zone
    return (
        max(0, min(width, int(round(x0 * width)))),
        max(0, min(height, int(round(y0 * height)))),
        max(0, min(width, int(round(x1 * width)))),
        max(0, min(height, int(round(y1 * height)))),
    )


def _dedupe_candidates(
    candidates: Sequence[Tuple[BBox, Point, float]],
) -> List[Tuple[BBox, Point, float]]:
    deduped: List[Tuple[BBox, Point, float]] = []
    for candidate in sorted(candidates, key=lambda item: item[2], reverse=True):
        bbox, centroid, _ = candidate
        if any(
            _distance(centroid, kept_centroid) < 32
            or _bbox_iou(bbox, kept_bbox) > 0.18
            for kept_bbox, kept_centroid, _ in deduped
        ):
            continue
        deduped.append(candidate)
    return deduped


def _bbox_iou(a: BBox, b: BBox) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    left = max(ax, bx)
    top = max(ay, by)
    right = min(ax + aw, bx + bw)
    bottom = min(ay + ah, by + bh)
    if right <= left or bottom <= top:
        return 0.0
    intersection = float((right - left) * (bottom - top))
    union = float(aw * ah + bw * bh) - intersection
    if union <= 0:
        return 0.0
    return intersection / union


def _colorfulness(frame: np.ndarray) -> float:
    """Return a simple color-opponent score for room-vs-fluoroscopy gating."""

    if frame.size == 0:
        return 0.0
    bgr = frame.astype("float32")
    red_green = np.abs(bgr[:, :, 2] - bgr[:, :, 1]).mean()
    yellow_blue = np.abs(0.5 * (bgr[:, :, 2] + bgr[:, :, 1]) - bgr[:, :, 0]).mean()
    return float((red_green**2 + yellow_blue**2) ** 0.5)
