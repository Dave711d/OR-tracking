import json
import re
from pathlib import Path

from or_tracking.tracker import ROLE_ZONE_PRIORITY
from or_tracking.tavr import TAVR_STAGE_ORDER


def test_vercel_static_demo_files_are_present() -> None:
    public = Path("public")

    assert (public / "index.html").exists()
    assert (public / "app.js").exists()
    assert (public / "styles.css").exists()
    assert (public / "demo-data" / "sentara-1800-evaluation.json").exists()


def test_vercel_config_builds_public_assets() -> None:
    config = json.loads(Path("vercel.json").read_text(encoding="utf-8"))

    assert config["framework"] is None
    assert config["buildCommand"] == "npm run build"
    assert config["outputDirectory"] == "dist"


def test_vercel_deploy_ignores_streamlit_entrypoint() -> None:
    ignore_rules = Path(".vercelignore").read_text(encoding="utf-8").splitlines()

    assert "app.py" in ignore_rules
    assert "or_tracking/" in ignore_rules
    assert "public/" not in ignore_rules


def test_static_demo_stage_keys_match_backend_tavr_order() -> None:
    app_js = Path("public/app.js").read_text(encoding="utf-8")
    stage_block_match = re.search(
        r"const TAVR_STAGES = \[(?P<body>.*?)\];",
        app_js,
        flags=re.DOTALL,
    )

    assert stage_block_match is not None
    stage_keys = re.findall(r'key: "([^"]+)"', stage_block_match.group("body"))
    assert stage_keys == TAVR_STAGE_ORDER


def test_static_demo_role_zone_priority_matches_backend() -> None:
    app_js = Path("public/app.js").read_text(encoding="utf-8")
    priority_block_match = re.search(
        r"const ROLE_ZONE_PRIORITY = \[(?P<body>.*?)\];",
        app_js,
        flags=re.DOTALL,
    )

    assert priority_block_match is not None
    role_zone_priority = re.findall(
        r'"([^"]+)"',
        priority_block_match.group("body"),
    )
    assert role_zone_priority == list(ROLE_ZONE_PRIORITY)


def test_static_demo_exposes_static_table_fallback_review_mode() -> None:
    index_html = Path("public/index.html").read_text(encoding="utf-8")
    app_js = Path("public/app.js").read_text(encoding="utf-8")

    assert 'id="staticFallback"' in index_html
    assert "Static table fallback" in index_html
    assert "collectStaticTableBoxes" in app_js
    assert "staticFallbackInput.checked" in app_js


def test_static_demo_estimates_tavr_stage_for_uploaded_video() -> None:
    index_html = Path("public/index.html").read_text(encoding="utf-8")
    app_js = Path("public/app.js").read_text(encoding="utf-8")
    analyze_frame_match = re.search(
        r"function analyzeFrame\(\) \{(?P<body>.*?)\nfunction analyzeSyntheticFrame",
        app_js,
        flags=re.DOTALL,
    )

    assert 'id="initialStage"' in index_html
    assert "populateInitialStageOptions" in app_js
    assert "selectedInitialStageIndex" in app_js
    assert analyze_frame_match is not None
    assert "estimateUploadedTavrStage(boxes, activity, video.currentTime)" in app_js
    assert "function estimateUploadedTavrStage" in app_js
    assert "function scoreTavrStages" in app_js
    assert "function chooseTavrStageIndex" in app_js
    assert "Uploaded review" not in analyze_frame_match.group("body")


def test_static_demo_surfaces_stage_roster_summary() -> None:
    index_html = Path("public/index.html").read_text(encoding="utf-8")
    app_js = Path("public/app.js").read_text(encoding="utf-8")
    styles = Path("public/styles.css").read_text(encoding="utf-8")

    assert 'id="stageRosterList"' in index_html
    assert "Stage roster" in index_html
    assert "updateStageRoster(stage, summary.tableRoster, elapsedSeconds)" in app_js
    assert "function renderStageRosterSummary" in app_js
    assert "function classifyStageRosterHandoff" in app_js
    assert "stageRosterSegments = []" in app_js
    assert ".stage-roster-list" in styles


def test_static_demo_surfaces_operator_stage_packet() -> None:
    index_html = Path("public/index.html").read_text(encoding="utf-8")
    app_js = Path("public/app.js").read_text(encoding="utf-8")
    styles = Path("public/styles.css").read_text(encoding="utf-8")

    assert 'id="operatorPacket"' in index_html
    assert "Operator packet" in index_html
    assert "renderOperatorPacket(stage, summary, elapsedSeconds)" in app_js
    assert "function renderOperatorPacket" in app_js
    assert "function operatorEvidenceLevel" in app_js
    assert "function operatorQualityFlags" in app_js
    assert "currentStageRosterSegment" in app_js
    assert "nextTavrStage(stage.key)" in app_js
    assert "static_table_fallback" in app_js
    assert ".operator-packet" in styles


def test_static_demo_bundles_evaluated_tavr_replay_artifact() -> None:
    payload = json.loads(
        Path("public/demo-data/sentara-1800-evaluation.json").read_text(
            encoding="utf-8"
        )
    )
    tavr = payload["tavr"]

    assert payload["case"] == "sentara_1800_mixed_room"
    assert payload["timebase"]["timebase"] in {"clip", "source"}
    assert tavr["timebase_summary"]
    for key in [
        "timebase_summary",
        "procedure_status_summary",
        "operator_stage_packet",
        "table_team_summary",
        "table_identity_groups",
        "stage_roster_summary",
        "stage_table_coverage",
        "procedure_event_timeline",
        "table_transition_events",
        "quality_flags",
    ]:
        assert tavr[key]

    status = tavr["procedure_status_summary"][0]
    packet = tavr["operator_stage_packet"][-1]
    assert "source_start_s" in status
    assert "clip_start_s" in status
    assert "clip_end_s" in packet
    assert "effective_table_source" in status
    assert status["effective_table_source"] == "recent_room_view_hold"
    assert status["effective_table_count"] == 1
    assert status["effective_table_track_ids"]
    assert packet["effective_table_source"] == "recent_room_view_hold"
    assert packet["effective_table_count"] == 1
    assert "canonical_table_identity_count" in packet
    assert "quality_flag_codes" in packet
    assert payload["score_summary"]["table_identity_group_score"] == 1.0
    assert len(tavr["table_team_summary"]) > 8
    assert len(tavr["table_identity_groups"]) >= 10
    assert any(
        len(row["merged_track_ids"]) > 1
        for row in tavr["table_identity_groups"]
    )
    assert len(tavr["stage_table_coverage"]) > 8
    assert (
        len(tavr["procedure_event_timeline"]) + len(tavr["table_transition_events"])
    ) > 12


def test_static_demo_loads_backend_evaluation_replay() -> None:
    index_html = Path("public/index.html").read_text(encoding="utf-8")
    app_js = Path("public/app.js").read_text(encoding="utf-8")
    styles = Path("public/styles.css").read_text(encoding="utf-8")

    assert 'id="evaluationDemoButton"' in index_html
    assert 'id="procedureStatus"' in index_html
    assert 'id="tableIdentityList"' in index_html
    assert 'id="eventTimelineList"' in index_html
    assert 'id="qualityFlagList"' in index_html
    assert "Evaluated demo" in index_html
    assert "EVALUATION_DEMO_URL" in app_js
    assert "function loadEvaluationDemo" in app_js
    assert "function normalizeEvaluationPayload" in app_js
    assert "function renderEvaluationReplay" in app_js
    assert "function renderProcedureStatus" in app_js
    assert "function renderBackendOperatorPacket" in app_js
    assert "function renderBackendTableTeam" in app_js
    assert "function renderBackendTableIdentities" in app_js
    assert "function renderBackendStageCoverage" in app_js
    assert "function renderBackendStageRoster" in app_js
    assert "function renderBackendProcedureEvents" in app_js
    assert "function renderBackendQualityFlags" in app_js
    assert "function formatClockRange" in app_js
    assert "function formatClockPoint" in app_js
    assert "function tableSourceLabel" in app_js
    assert "recent room-view hold" in app_js
    assert "evaluationReplayRequestId" in app_js
    assert "keepEvaluationReplayRequest" in app_js
    assert "requestId !== evaluationReplayRequestId" in app_js
    assert "function appendOverflowRow" in app_js
    assert "function syncEmptyStateToVideoSource" in app_js
    assert "function summarizeStageCounts" in app_js
    assert "emptyState.hidden = Boolean(video.src)" in app_js
    assert "effective_table_source" in app_js
    assert "tracking_available_rate" in app_js
    assert "canonical_table_identity_count" in app_js
    assert "timebase_summary" in app_js
    assert "clip_timestamp_s" in app_js
    assert "table_identity_groups" in app_js
    assert "merged_track_ids" in app_js
    assert "quality_flag_codes" in app_js
    assert "procedure_event_timeline" in app_js
    assert ".procedure-status-list" in styles
    assert ".identity-list" in styles
    assert ".event-list" in styles
    assert ".quality-list" in styles
