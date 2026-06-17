"""Evaluation helpers for TAVR tracking runs."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence

from .models import FrameMetrics
from .tavr import TAVRFrameState, TrackRoleSummary


def summarize_tavr_metrics(
    metrics: Sequence[FrameMetrics],
    confidence_threshold: float = 0.45,
) -> Dict[str, Any]:
    """Return an auditable TAVR summary for one processed video."""

    tavr_metrics = [metric for metric in metrics if metric.tavr is not None]
    return {
        "stage_timeline": tavr_stage_timeline(tavr_metrics),
        "track_role_report": tavr_track_role_report(tavr_metrics),
        "current_table_roster": current_table_roster(tavr_metrics),
        "peak_table_roster": peak_table_roster(tavr_metrics),
        "table_presence_roster": table_presence_roster(tavr_metrics),
        "table_presence_intervals": table_presence_intervals(
            tavr_metrics,
            min_observed_table_frames=3,
        ),
        "low_confidence_segments": low_confidence_segments(
            tavr_metrics,
            threshold=confidence_threshold,
        ),
        "quality_flags": tavr_quality_flags(tavr_metrics),
    }


def score_tavr_metrics(
    metrics: Sequence[FrameMetrics],
    labels: Dict[str, Any],
) -> Dict[str, Any]:
    """Score tracker output against lightweight human/test labels."""

    tavr_metrics = [metric for metric in metrics if metric.tavr is not None]
    return {
        "stage_score": _stage_score(tavr_metrics, labels.get("stage_segments", [])),
        "table_count_score": _table_count_score(
            tavr_metrics,
            labels.get("table_count_segments", []),
        ),
        "table_presence_score": _table_presence_score(
            tavr_metrics,
            labels.get("table_presence_expectations", []),
        ),
    }


def tavr_stage_timeline(metrics: Sequence[FrameMetrics]) -> List[Dict[str, Any]]:
    """Group contiguous TAVR stage estimates with table-roster context."""

    if not metrics:
        return []

    timeline: List[Dict[str, Any]] = []
    active_metric = metrics[0]
    active_state = _tavr_state(active_metric)
    start_index = 0

    for index, metric in enumerate(metrics[1:], start=1):
        state = _tavr_state(metric)
        if state.stage != active_state.stage:
            timeline.append(
                _timeline_item(metrics, start_index, index - 1, active_state)
            )
            active_state = state
            start_index = index

    timeline.append(_timeline_item(metrics, start_index, len(metrics) - 1, active_state))
    return timeline


def tavr_track_role_report(metrics: Sequence[FrameMetrics]) -> List[Dict[str, Any]]:
    """Return the latest persistent role summary for every seen track."""

    latest: Dict[int, TrackRoleSummary] = {}
    for metric in metrics:
        state = _tavr_state(metric)
        for track_id, summary in state.track_role_summaries.items():
            previous = latest.get(track_id)
            if previous is None or summary.last_frame >= previous.last_frame:
                latest[track_id] = summary

    return [
        {
            "track_id": summary.track_id,
            "dominant_role": summary.dominant_role,
            "frames_seen": summary.frames_seen,
            "first_frame": summary.first_frame,
            "last_frame": summary.last_frame,
            "table_frames": summary.table_frames,
            "table_presence_ratio": round(summary.table_presence_ratio, 3),
            "role_counts": summary.role_counts,
        }
        for summary in sorted(
            latest.values(),
            key=lambda item: (-item.table_presence_ratio, -item.frames_seen, item.track_id),
        )
    ]


def current_table_roster(metrics: Sequence[FrameMetrics]) -> List[Dict[str, Any]]:
    """Return the most recent table-side roster, including role dwell."""

    if not metrics:
        return []

    state = _tavr_state(metrics[-1])
    return _roster_from_state(state)


def peak_table_roster(metrics: Sequence[FrameMetrics]) -> Dict[str, Any]:
    """Return the roster from the frame with the largest table-side count."""

    if not metrics:
        return {
            "frame_index": None,
            "timestamp_s": None,
            "table_count": 0,
            "roster": [],
        }

    peak_metric = max(
        metrics,
        key=lambda metric: (_tavr_state(metric).table_count, metric.frame_index),
    )
    peak_state = _tavr_state(peak_metric)
    return {
        "frame_index": peak_metric.frame_index,
        "timestamp_s": peak_metric.timestamp_s,
        "table_count": peak_state.table_count,
        "roster": _roster_from_state(peak_state),
    }


def table_presence_roster(
    metrics: Sequence[FrameMetrics],
    min_table_frames: int = 3,
) -> List[Dict[str, Any]]:
    """Return tracks that spent meaningful time at the table during the clip."""

    roster = []
    for summary in tavr_track_role_report(metrics):
        if summary["table_frames"] < min_table_frames:
            continue
        roster.append(
            {
                "track_id": summary["track_id"],
                "dominant_role": summary["dominant_role"],
                "frames_seen": summary["frames_seen"],
                "table_frames": summary["table_frames"],
                "table_presence_ratio": summary["table_presence_ratio"],
                "first_frame": summary["first_frame"],
                "last_frame": summary["last_frame"],
                "label": (
                    f"ID {summary['track_id']} {summary['dominant_role']} "
                    f"table={summary['table_presence_ratio']:.0%}"
                ),
            }
        )
    return roster


def table_presence_intervals(
    metrics: Sequence[FrameMetrics],
    max_gap_frames: int = 12,
    max_gap_s: float = 1.0,
    min_observed_table_frames: int = 1,
) -> List[Dict[str, Any]]:
    """Return contiguous table-side intervals for each tracked ID."""

    if not metrics:
        return []

    observations = _table_observations(metrics)
    sample_period_s = _sample_period_s(metrics)
    intervals: List[Dict[str, Any]] = []
    for track_id in sorted(observations):
        active: List[Dict[str, Any]] = []
        for observation in observations[track_id]:
            if active and _observation_gap_exceeded(
                active[-1],
                observation,
                max_gap_frames=max_gap_frames,
                max_gap_s=max_gap_s,
            ):
                if len(active) >= min_observed_table_frames:
                    intervals.append(_table_interval_item(track_id, active, sample_period_s))
                active = []
            active.append(observation)
        if len(active) >= min_observed_table_frames:
            intervals.append(_table_interval_item(track_id, active, sample_period_s))

    intervals.sort(
        key=lambda item: (
            item["start_s"],
            item["track_id"],
            -item["observed_table_frames"],
        )
    )
    return intervals


def _roster_from_state(state: TAVRFrameState) -> List[Dict[str, Any]]:
    roster = []
    for track_id in state.table_track_ids:
        summary = state.track_role_summaries.get(track_id)
        if summary is None:
            continue
        roster.append(
            {
                "track_id": track_id,
                "dominant_role": summary.dominant_role,
                "frames_seen": summary.frames_seen,
                "table_presence_ratio": round(summary.table_presence_ratio, 3),
                "label": summary.to_who_at_table(),
            }
        )
    return roster


def low_confidence_segments(
    metrics: Sequence[FrameMetrics],
    threshold: float = 0.45,
) -> List[Dict[str, Any]]:
    """Group contiguous frames where TAVR stage confidence is weak."""

    segments: List[Dict[str, Any]] = []
    active_start: Optional[int] = None
    active_end: Optional[int] = None

    for index, metric in enumerate(metrics):
        state = _tavr_state(metric)
        if state.confidence < threshold:
            if active_start is None:
                active_start = index
            active_end = index
            continue
        if active_start is not None and active_end is not None:
            segments.append(_confidence_item(metrics, active_start, active_end))
            active_start = None
            active_end = None

    if active_start is not None and active_end is not None:
        segments.append(_confidence_item(metrics, active_start, active_end))

    return segments


def tavr_quality_flags(metrics: Sequence[FrameMetrics]) -> List[Dict[str, Any]]:
    """Flag clips that are likely poor chronology or tracking evidence."""

    if not metrics:
        return []

    flags: List[Dict[str, Any]] = []
    timeline = tavr_stage_timeline(metrics)
    duration_s = max(metrics[-1].timestamp_s - metrics[0].timestamp_s, 0.0)
    if duration_s > 0 and len(timeline) / duration_s > 0.06:
        flags.append(
            {
                "code": "rapid_stage_progression",
                "message": (
                    "Stage changes are dense for the clip duration; this may be "
                    "edited footage or an unseeded slice rather than a continuous case."
                ),
                "stage_count": len(timeline),
                "duration_s": round(duration_s, 3),
            }
        )
    terminal_stage = next(
        (item for item in timeline if item["stage"] == "closure_finish"),
        None,
    )
    if (
        terminal_stage is not None
        and duration_s > 0
        and terminal_stage["start_s"] - metrics[0].timestamp_s < duration_s * 0.5
    ):
        flags.append(
            {
                "code": "early_terminal_stage",
                "message": (
                    "The timeline reached closure early in the clip; the footage may "
                    "be edited, montage-like, or too visually ambiguous for procedure chronology."
                ),
                "closure_start_s": round(terminal_stage["start_s"], 3),
                "duration_s": round(duration_s, 3),
            }
        )

    track_report = tavr_track_role_report(metrics)
    if len(track_report) > max(80, len(metrics) * 0.08):
        flags.append(
            {
                "code": "fragmented_tracks",
                "message": (
                    "Many short-lived track IDs were created; raise min-area, use a "
                    "cleaner view, or inspect the annotated video before trusting roster dwell."
                ),
                "track_count": len(track_report),
                "frames_processed": len(metrics),
            }
        )

    peak_people_count = max((metric.people_count for metric in metrics), default=0)
    if peak_people_count >= 25:
        flags.append(
            {
                "code": "high_motion_noise",
                "message": (
                    "A frame had unusually many detections for OR staff tracking; "
                    "graphics, camera motion, or montage edits may be included."
                ),
                "peak_people_count": peak_people_count,
            }
        )

    return flags


def _timeline_item(
    metrics: Sequence[FrameMetrics],
    start_index: int,
    end_index: int,
    state: TAVRFrameState,
) -> Dict[str, Any]:
    end_state = _tavr_state(metrics[end_index])
    segment_metrics = metrics[start_index : end_index + 1]
    return {
        "stage": state.stage,
        "stage_label": state.stage_label,
        "start_frame": metrics[start_index].frame_index,
        "end_frame": metrics[end_index].frame_index,
        "start_s": metrics[start_index].timestamp_s,
        "end_s": metrics[end_index].timestamp_s,
        "peak_table_count": max(
            _tavr_state(metric).table_count
            for metric in segment_metrics
        ),
        "peak_table_roster": peak_table_roster(segment_metrics),
        "table_presence_roster": _interval_roster(segment_metrics),
        "table_roster": [
            end_state.track_role_summaries[track_id].to_who_at_table()
            for track_id in end_state.table_track_ids
            if track_id in end_state.track_role_summaries
        ],
        "note": state.note,
    }


def _confidence_item(
    metrics: Sequence[FrameMetrics],
    start_index: int,
    end_index: int,
) -> Dict[str, Any]:
    confidences = [
        _tavr_state(metric).confidence for metric in metrics[start_index : end_index + 1]
    ]
    return {
        "start_frame": metrics[start_index].frame_index,
        "end_frame": metrics[end_index].frame_index,
        "start_s": metrics[start_index].timestamp_s,
        "end_s": metrics[end_index].timestamp_s,
        "min_confidence": round(min(confidences), 3),
        "max_confidence": round(max(confidences), 3),
    }


def _tavr_state(metric: FrameMetrics) -> TAVRFrameState:
    if metric.tavr is None:
        raise ValueError("TAVR evaluation requires metrics with TAVR state")
    return metric.tavr


def _stage_score(
    metrics: Sequence[FrameMetrics],
    stage_segments: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    if not stage_segments:
        return {"covered_frames": 0, "accuracy": None, "segments": [], "confusion": {}}

    correct = 0
    covered = 0
    confusion: Dict[str, Dict[str, int]] = {}
    segment_scores = []
    for segment in stage_segments:
        expected_stage = str(segment["stage"])
        segment_metrics = _metrics_in_window(metrics, segment)
        segment_correct = 0
        for metric in segment_metrics:
            predicted_stage = _tavr_state(metric).stage
            if predicted_stage == expected_stage:
                correct += 1
                segment_correct += 1
            covered += 1
            confusion.setdefault(expected_stage, {})
            confusion[expected_stage][predicted_stage] = (
                confusion[expected_stage].get(predicted_stage, 0) + 1
            )
        segment_scores.append(
            {
                "stage": expected_stage,
                "start_s": segment.get("start_s"),
                "end_s": segment.get("end_s"),
                "frames": len(segment_metrics),
                "accuracy": _ratio(segment_correct, len(segment_metrics)),
            }
        )

    return {
        "covered_frames": covered,
        "accuracy": _ratio(correct, covered),
        "segments": segment_scores,
        "confusion": confusion,
    }


def _table_count_score(
    metrics: Sequence[FrameMetrics],
    count_segments: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    if not count_segments:
        return {"segments": [], "pass_rate": None}

    passed = 0
    segment_scores = []
    for segment in count_segments:
        segment_metrics = _metrics_in_window(metrics, segment)
        counts = [_tavr_state(metric).table_count for metric in segment_metrics]
        min_count = segment.get("min_count")
        max_count = segment.get("max_count")
        min_peak_count = segment.get("min_peak_count")
        min_within_range_rate = float(segment.get("min_within_range_rate", 1.0))
        within = [
            count
            for count in counts
            if (min_count is None or count >= min_count)
            and (max_count is None or count <= max_count)
        ]
        within_rate = _ratio(len(within), len(counts))
        peak_table_count = max(counts) if counts else 0
        range_pass = (
            within_rate is not None
            and (min_count is not None or max_count is not None)
            and within_rate >= min_within_range_rate
        )
        if min_count is None and max_count is None:
            range_pass = True
        peak_pass = min_peak_count is None or peak_table_count >= min_peak_count
        segment_pass = bool(counts) and range_pass and peak_pass
        if segment_pass:
            passed += 1
        segment_scores.append(
            {
                "start_s": segment.get("start_s"),
                "end_s": segment.get("end_s"),
                "min_count": min_count,
                "max_count": max_count,
                "min_peak_count": min_peak_count,
                "min_within_range_rate": min_within_range_rate,
                "frames": len(counts),
                "mean_table_count": round(sum(counts) / len(counts), 3) if counts else None,
                "peak_table_count": peak_table_count,
                "within_range_rate": within_rate,
                "passed": segment_pass,
            }
        )

    return {
        "segments": segment_scores,
        "pass_rate": _ratio(passed, len(count_segments)),
    }


def _table_presence_score(
    metrics: Sequence[FrameMetrics],
    expectations: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    if not expectations:
        return {"expectations": [], "pass_rate": None}

    intervals = table_presence_intervals(metrics, min_observed_table_frames=3)
    passed = 0
    scored_expectations = []
    for expectation in expectations:
        role = expectation.get("role")
        min_intervals = int(expectation.get("min_intervals", 1))
        min_observed_table_frames = int(expectation.get("min_observed_table_frames", 3))
        overlapping = [
            interval
            for interval in intervals
            if _interval_overlaps_expectation(interval, expectation)
            and (role is None or interval["dominant_role"] == role)
            and interval["observed_table_frames"] >= min_observed_table_frames
        ]
        expectation_pass = len(overlapping) >= min_intervals
        if expectation_pass:
            passed += 1
        scored_expectations.append(
            {
                "start_s": expectation.get("start_s"),
                "end_s": expectation.get("end_s"),
                "role": role,
                "min_intervals": min_intervals,
                "min_observed_table_frames": min_observed_table_frames,
                "matched_intervals": overlapping,
                "matched_count": len(overlapping),
                "passed": expectation_pass,
            }
        )

    return {
        "expectations": scored_expectations,
        "pass_rate": _ratio(passed, len(expectations)),
    }


def _table_observations(
    metrics: Sequence[FrameMetrics],
) -> Dict[int, List[Dict[str, Any]]]:
    observations: Dict[int, List[Dict[str, Any]]] = {}
    for metric in metrics:
        state = _tavr_state(metric)
        for track_id in state.table_track_ids:
            summary = state.track_role_summaries.get(track_id)
            observations.setdefault(track_id, []).append(
                {
                    "frame_index": metric.frame_index,
                    "timestamp_s": metric.timestamp_s,
                    "stage": state.stage,
                    "role": summary.dominant_role if summary else "unassigned",
                }
            )
    return observations


def _observation_gap_exceeded(
    previous: Dict[str, Any],
    current: Dict[str, Any],
    max_gap_frames: int,
    max_gap_s: float,
) -> bool:
    frame_gap = current["frame_index"] - previous["frame_index"]
    time_gap = current["timestamp_s"] - previous["timestamp_s"]
    return frame_gap > max_gap_frames or time_gap > max_gap_s


def _table_interval_item(
    track_id: int,
    observations: Sequence[Dict[str, Any]],
    sample_period_s: float,
) -> Dict[str, Any]:
    start = observations[0]
    end = observations[-1]
    role_counts = _counts(item["role"] for item in observations)
    stage_counts = _counts(item["stage"] for item in observations)
    dominant_role = _dominant_from_counts(role_counts)
    dominant_stage = _dominant_from_counts(stage_counts)
    duration_s = max(0.0, end["timestamp_s"] - start["timestamp_s"] + sample_period_s)
    return {
        "track_id": track_id,
        "dominant_role": dominant_role,
        "dominant_stage": dominant_stage,
        "start_frame": start["frame_index"],
        "end_frame": end["frame_index"],
        "start_s": round(float(start["timestamp_s"]), 3),
        "end_s": round(float(end["timestamp_s"]), 3),
        "observed_table_frames": len(observations),
        "interval_duration_s": round(float(duration_s), 3),
        "role_counts": role_counts,
        "stage_counts": stage_counts,
        "label": (
            f"ID {track_id} {dominant_role} "
            f"{start['timestamp_s']:.1f}-{end['timestamp_s']:.1f}s"
        ),
    }


def _interval_roster(metrics: Sequence[FrameMetrics]) -> List[Dict[str, Any]]:
    roster = []
    for interval in table_presence_intervals(metrics):
        roster.append(
            {
                "track_id": interval["track_id"],
                "dominant_role": interval["dominant_role"],
                "observed_table_frames": interval["observed_table_frames"],
                "interval_duration_s": interval["interval_duration_s"],
                "start_s": interval["start_s"],
                "end_s": interval["end_s"],
                "label": interval["label"],
            }
        )
    roster.sort(
        key=lambda item: (
            -item["observed_table_frames"],
            item["start_s"],
            item["track_id"],
        )
    )
    return roster


def _counts(values: Iterable[str]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _dominant_from_counts(counts: Dict[str, int]) -> str:
    if not counts:
        return "unassigned"
    return max(counts.items(), key=lambda item: (item[1], item[0]))[0]


def _sample_period_s(metrics: Sequence[FrameMetrics]) -> float:
    deltas = [
        current.timestamp_s - previous.timestamp_s
        for previous, current in zip(metrics, metrics[1:])
        if current.timestamp_s > previous.timestamp_s
    ]
    if not deltas:
        return 0.0
    deltas.sort()
    return deltas[len(deltas) // 2]


def _metrics_in_window(
    metrics: Sequence[FrameMetrics],
    window: Dict[str, Any],
) -> List[FrameMetrics]:
    start_s = float(window.get("start_s", float("-inf")))
    end_s = float(window.get("end_s", float("inf")))
    return [
        metric
        for metric in metrics
        if start_s <= metric.timestamp_s <= end_s
    ]


def _interval_overlaps_expectation(
    interval: Dict[str, Any],
    expectation: Dict[str, Any],
) -> bool:
    start_s = float(expectation.get("start_s", float("-inf")))
    end_s = float(expectation.get("end_s", float("inf")))
    return interval["start_s"] <= end_s and interval["end_s"] >= start_s


def _ratio(numerator: int, denominator: int) -> Optional[float]:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 3)
