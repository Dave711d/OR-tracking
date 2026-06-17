"""Shared data models for OR tracking runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


BBox = Tuple[int, int, int, int]
Point = Tuple[int, int]


@dataclass(frozen=True)
class Detection:
    """A tracked detection in one frame."""

    track_id: int
    bbox: BBox
    centroid: Point
    area: float
    confidence: float = 1.0

    def to_compact_dict(self) -> Dict[str, object]:
        x, y, w, h = self.bbox
        cx, cy = self.centroid
        return {
            "track_id": self.track_id,
            "x": x,
            "y": y,
            "w": w,
            "h": h,
            "cx": cx,
            "cy": cy,
            "area": round(float(self.area), 2),
            "confidence": round(float(self.confidence), 3),
        }


@dataclass
class FrameMetrics:
    """Per-frame analytics emitted by the tracker."""

    frame_index: int
    timestamp_s: float
    detections: List[Detection] = field(default_factory=list)
    movement_px: float = 0.0
    zone_counts: Dict[str, int] = field(default_factory=dict)
    alert_flags: List[str] = field(default_factory=list)
    view_colorfulness: float = 0.0
    tavr: Optional[Any] = None

    @property
    def people_count(self) -> int:
        return len(self.detections)

    @property
    def active_track_ids(self) -> List[int]:
        return sorted(detection.track_id for detection in self.detections)

    def to_row(self) -> Dict[str, object]:
        """Return a flat row suitable for CSV and DataFrame display."""

        zone_counts = ",".join(
            f"{zone}:{count}" for zone, count in sorted(self.zone_counts.items())
        )
        alerts = ",".join(sorted(self.alert_flags))
        tracks = ",".join(str(track_id) for track_id in self.active_track_ids)
        row = {
            "frame_index": self.frame_index,
            "timestamp_s": round(float(self.timestamp_s), 3),
            "people_count": self.people_count,
            "active_track_ids": tracks,
            "movement_px": round(float(self.movement_px), 2),
            "view_colorfulness": round(float(self.view_colorfulness), 2),
            "zone_counts": zone_counts,
            "alert_flags": alerts,
        }
        if self.tavr is not None:
            row.update(self.tavr.to_row_fields())
        return row


@dataclass
class TrackingSummary:
    """Compact run summary for UI cards and API-like output."""

    frames_processed: int
    duration_s: float
    average_people_count: float
    peak_people_count: int
    total_unique_tracks: int
    activity_score: float
    alert_count: int
    dominant_tavr_stage: str = ""
    peak_table_count: int = 0

    @classmethod
    def from_metrics(cls, metrics: Sequence[FrameMetrics]) -> "TrackingSummary":
        if not metrics:
            return cls(
                frames_processed=0,
                duration_s=0.0,
                average_people_count=0.0,
                peak_people_count=0,
                total_unique_tracks=0,
                activity_score=0.0,
                alert_count=0,
                dominant_tavr_stage="",
                peak_table_count=0,
            )

        counts = [metric.people_count for metric in metrics]
        track_ids = {
            detection.track_id for metric in metrics for detection in metric.detections
        }
        duration = max(metric.timestamp_s for metric in metrics)
        movement = sum(metric.movement_px for metric in metrics)
        alert_count = sum(len(metric.alert_flags) for metric in metrics)
        tavr_states = [metric.tavr for metric in metrics if metric.tavr is not None]
        dominant_tavr_stage = _dominant_stage(tavr_states)
        peak_table_count = max((state.table_count for state in tavr_states), default=0)
        return cls(
            frames_processed=len(metrics),
            duration_s=round(float(duration), 3),
            average_people_count=round(sum(counts) / len(counts), 2),
            peak_people_count=max(counts),
            total_unique_tracks=len(track_ids),
            activity_score=round(movement / max(len(metrics), 1), 2),
            alert_count=alert_count,
            dominant_tavr_stage=dominant_tavr_stage,
            peak_table_count=peak_table_count,
        )

    def to_dict(self) -> Dict[str, object]:
        return {
            "frames_processed": self.frames_processed,
            "duration_s": self.duration_s,
            "average_people_count": self.average_people_count,
            "peak_people_count": self.peak_people_count,
            "total_unique_tracks": self.total_unique_tracks,
            "activity_score": self.activity_score,
            "alert_count": self.alert_count,
            "dominant_tavr_stage": self.dominant_tavr_stage,
            "peak_table_count": self.peak_table_count,
        }


def rows_from_metrics(metrics: Iterable[FrameMetrics]) -> List[Dict[str, object]]:
    return [metric.to_row() for metric in metrics]


def _dominant_stage(states: Sequence[Any]) -> str:
    counts: Dict[str, int] = {}
    for state in states:
        counts[state.stage] = counts.get(state.stage, 0) + 1
    if not counts:
        return ""
    return max(counts.items(), key=lambda item: item[1])[0]
