"""Operating room video tracking prototype."""

from .tracker import MotionTrackerConfig, ORActivityTracker
from .tavr import TAVR_STAGE_LABELS, TAVR_STAGE_ORDER, TAVRFrameState
from .evaluation import (
    score_tavr_metrics,
    procedure_event_timeline,
    procedure_milestones,
    procedure_status_summary,
    stage_evidence_summary,
    stage_handoff_summary,
    stage_table_coverage,
    summarize_tavr_metrics,
    table_transition_events,
    view_segments,
    write_tavr_summary_csvs,
)
from .video import TrackingRunResult, process_video_file

__all__ = [
    "MotionTrackerConfig",
    "ORActivityTracker",
    "TAVRFrameState",
    "TAVR_STAGE_LABELS",
    "TAVR_STAGE_ORDER",
    "TrackingRunResult",
    "process_video_file",
    "procedure_event_timeline",
    "procedure_milestones",
    "procedure_status_summary",
    "score_tavr_metrics",
    "stage_evidence_summary",
    "stage_handoff_summary",
    "stage_table_coverage",
    "summarize_tavr_metrics",
    "table_transition_events",
    "view_segments",
    "write_tavr_summary_csvs",
]
