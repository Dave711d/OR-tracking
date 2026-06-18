import json
import re
from pathlib import Path

from export_public_demo_data import PUBLIC_DEMO_CASES
from or_tracking.tracker import ROLE_ZONE_PRIORITY
from or_tracking.tavr import TAVR_STAGE_ORDER


PUBLIC_EVALUATION_DEMOS = [
    {
        "file": "sentara-900-evaluation.json",
        "case": "sentara_900_room_to_fluoro_low_motion",
        "stage": "access_sheathing",
        "stage_label": "Access / sheathing",
        "evidence": "weak_visual_support",
        "table_source": "no_room_table_evidence",
        "table_count": 0,
        "current_table_count": 0,
        "required_flags": {
            "low_stage_confidence",
            "non_room_view",
            "low_motion_room_view",
        },
        "min_team_rows": 0,
        "min_identity_groups": 0,
        "min_coverage_rows": 0,
        "min_presence_intervals": 0,
        "table_person_interval_score": 1.0,
        "table_person_status_score": 1.0,
        "min_events": 4,
    },
    {
        "file": "sentara-1800-evaluation.json",
        "case": "sentara_1800_mixed_room",
        "stage": "valve_deployment",
        "stage_label": "Valve deployment",
        "evidence": "strong_visual_support",
        "table_source": "recent_room_view_hold",
        "table_count": 2,
        "current_table_count": 0,
        "required_flags": {
            "rapid_stage_progression",
            "low_stage_confidence",
            "non_room_view",
        },
        "min_team_rows": 8,
        "min_identity_groups": 10,
        "min_coverage_rows": 8,
        "min_presence_intervals": 13,
        "table_person_interval_score": 1.0,
        "table_person_status_score": 1.0,
        "min_events": 12,
    },
    {
        "file": "sentara-2400-evaluation.json",
        "case": "sentara_2400_fluoro_negative",
        "stage": "valve_deployment",
        "stage_label": "Valve deployment",
        "current_stage_status": "current_held_context",
        "packet_stage_status": "current_held_context",
        "evidence": "held_non_room_context",
        "table_source": "no_room_table_evidence",
        "table_count": 0,
        "current_table_count": 0,
        "required_flags": {"low_stage_confidence", "non_room_view"},
        "min_team_rows": 0,
        "min_identity_groups": 0,
        "min_coverage_rows": 0,
        "min_presence_intervals": 0,
        "table_person_interval_score": 1.0,
        "table_person_status_score": 1.0,
        "min_events": 3,
    },
    {
        "file": "sentara-2700-evaluation.json",
        "case": "sentara_2700_room_post",
        "stage": "closure_finish",
        "stage_label": "Closure / finish",
        "evidence": "weak_visual_support",
        "table_source": "last_observed_room_view",
        "table_count": 1,
        "current_table_count": 0,
        "required_flags": {
            "rapid_stage_progression",
            "early_terminal_stage",
            "low_stage_confidence",
            "non_room_view",
        },
        "min_team_rows": 8,
        "min_identity_groups": 9,
        "min_coverage_rows": 8,
        "min_presence_intervals": 8,
        "table_person_interval_score": 1.0,
        "table_person_status_score": 1.0,
        "min_events": 12,
    },
    {
        "file": "sentara-900-static-fallback-evaluation.json",
        "case": "sentara_900_static_table_fallback",
        "stage": "access_sheathing",
        "stage_label": "Access / sheathing",
        "evidence": "weak_visual_support",
        "table_source": "last_observed_room_view",
        "table_count": 3,
        "current_table_count": 0,
        "required_flags": {
            "low_stage_confidence",
            "non_room_view",
        },
        "min_team_rows": 3,
        "min_identity_groups": 3,
        "min_coverage_rows": 3,
        "min_presence_intervals": 3,
        "table_person_interval_score": 1.0,
        "table_person_status_score": 1.0,
        "min_events": 11,
    },
    {
        "file": "synthetic-full-tavr-evaluation.json",
        "case": "synthetic_full_tavr_workflow",
        "stage": "closure_finish",
        "stage_label": "Closure / finish",
        "evidence": "strong_visual_support",
        "table_source": "current_stage_recent_room_window",
        "table_count": 2,
        "current_table_count": 1,
        "required_flags": {"rapid_stage_progression"},
        "min_team_rows": 10,
        "min_identity_groups": 10,
        "min_coverage_rows": 18,
        "min_presence_intervals": 16,
        "table_person_interval_score": 1.0,
        "table_person_status_score": 1.0,
        "min_events": 60,
    },
]


def load_public_demo_payload(file_name: str) -> dict:
    return json.loads(
        Path("public/demo-data", file_name).read_text(encoding="utf-8")
    )


def test_vercel_static_demo_files_are_present() -> None:
    public = Path("public")

    assert (public / "index.html").exists()
    assert (public / "app.js").exists()
    assert (public / "browser_identity.mjs").exists()
    assert (public / "replay_view.mjs").exists()
    assert (public / "styles.css").exists()
    for demo in PUBLIC_EVALUATION_DEMOS:
        assert (public / "demo-data" / demo["file"]).exists()


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
    replay_js = Path("public/replay_view.mjs").read_text(encoding="utf-8")
    stage_block_match = re.search(
        r"const TAVR_STAGES = \[(?P<body>.*?)\];",
        app_js,
        flags=re.DOTALL,
    )
    replay_stage_block_match = re.search(
        r"export const TAVR_STAGE_PROGRESS = \[(?P<body>.*?)\];",
        replay_js,
        flags=re.DOTALL,
    )

    assert stage_block_match is not None
    stage_keys = re.findall(r'key: "([^"]+)"', stage_block_match.group("body"))
    assert stage_keys == TAVR_STAGE_ORDER
    assert replay_stage_block_match is not None
    replay_stage_keys = re.findall(
        r'key: "([^"]+)"',
        replay_stage_block_match.group("body"),
    )
    assert replay_stage_keys == TAVR_STAGE_ORDER


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
    assert "const viewColorfulness = frameColorfulness(image)" in app_js
    assert "const nonRoomView = viewColorfulness < BROWSER_NON_ROOM_COLORFULNESS_THRESHOLD" in app_js
    assert "if (nonRoomView) {" in app_js
    assert "boxes = []" in app_js
    assert "let staticTableUsed = false" in app_js
    assert "stageHoldReason: nonRoomView" in app_js
    assert "? \"non_room_view\"" in app_js
    assert ": (staticTableUsed ? \"static_table_fallback\" : null)" in app_js
    assert "viewColorfulness," in app_js
    assert "const tableSnapshot = updateBrowserTableSnapshot(summary, elapsedSeconds, stage)" in app_js
    assert "const currentTable = currentBrowserTableSnapshot(summary, elapsedSeconds)" in app_js
    assert "tableSideMetric.textContent = String(currentTable.count)" in app_js
    assert "renderTableRoster(currentTable, tableSnapshot)" in app_js
    assert "renderOperatorPacket(stage, summary, elapsedSeconds, tableSnapshot)" in app_js
    assert "estimateUploadedTavrStage(boxes, activity, video.currentTime, {" in app_js
    assert "function estimateUploadedTavrStage" in app_js
    assert "function scoreTavrStages" in app_js
    assert "function chooseTavrStageIndex" in app_js
    assert "function frameColorfulness" in app_js
    assert "const stageObservable = !stageHoldReason" in app_js
    assert "if (stageObservable) {" in app_js
    assert "stage_hold_non_room_view" in app_js
    assert "stage_hold_static_table_fallback" in app_js
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


def test_static_demo_canonicalizes_browser_table_identities() -> None:
    index_html = Path("public/index.html").read_text(encoding="utf-8")
    app_js = Path("public/app.js").read_text(encoding="utf-8")
    identity_js = Path("public/browser_identity.mjs").read_text(encoding="utf-8")

    assert 'type="module" src="/app.js"' in index_html
    assert 'import { BrowserTableIdentityTracker } from "./browser_identity.mjs";' in app_js
    assert "browserIdentityTracker.update(summary.tableRoster, elapsedSeconds)" in app_js
    assert "renderBrowserTableIdentities()" in app_js
    assert "canonicalizeBrowserSummary(summarizeBoxes(boxes), elapsedSeconds)" in app_js
    assert "class BrowserTableIdentityTracker" in identity_js
    assert "projectedCentroidDistance" in identity_js


def test_static_demo_surfaces_operator_stage_packet() -> None:
    index_html = Path("public/index.html").read_text(encoding="utf-8")
    app_js = Path("public/app.js").read_text(encoding="utf-8")
    styles = Path("public/styles.css").read_text(encoding="utf-8")

    assert 'id="operatorPacket"' in index_html
    assert "Operator packet" in index_html
    assert "renderOperatorPacket(stage, summary, elapsedSeconds, tableSnapshot)" in app_js
    assert "function renderOperatorPacket" in app_js
    assert "function operatorEvidenceLevel" in app_js
    assert "function operatorQualityFlags" in app_js
    assert "function updateBrowserTableSnapshot" in app_js
    assert "function currentBrowserTableSnapshot" in app_js
    assert "function hasDistinctBrowserTable" in app_js
    assert "lastObservedTableSnapshot" in app_js
    assert "BROWSER_RECENT_TABLE_HOLD_SECONDS" in app_js
    assert 'label: "Current table"' in app_js
    assert "label: \"Effective table\"" in app_js
    assert '"Stage roster"' in app_js
    assert "stage_table_track_count" in app_js
    assert "stage_table_canonical_ids" in app_js
    assert "stage_table_track_ids" in app_js
    assert "Active table" not in app_js
    assert "table_roster_held_from_room_view" in app_js
    assert "tableSnapshot?.rows?.some(({ staticFallback }) => staticFallback)" in app_js
    assert "currentStageRosterSegment" in app_js
    assert "nextTavrStage(stage.key)" in app_js
    assert "static_table_fallback" in app_js
    assert "non_room_view" in app_js
    assert ".operator-packet" in styles


def test_static_demo_exporter_covers_all_public_tavr_replays() -> None:
    exporter = Path("export_public_demo_data.py").read_text(encoding="utf-8")

    assert "PUBLIC_DEMO_CASES" in exporter
    assert "summarize_scores" in exporter
    for demo in PUBLIC_EVALUATION_DEMOS:
        assert demo["file"] in exporter


def test_static_demo_exporter_uses_status_verified_suite_outputs() -> None:
    source_paths = {str(demo_case.source) for demo_case in PUBLIC_DEMO_CASES}

    assert any("outputs/tavr_suite_person_status_verify/" in path for path in source_paths)
    assert any(
        "outputs/tavr_static_person_status_verify/" in path
        for path in source_paths
    )
    assert any(
        "outputs/tavr_synthetic_person_status_verify/" in path
        for path in source_paths
    )
    assert not any("person_interval_verify" in path for path in source_paths)


def test_static_demo_bundles_evaluated_tavr_replay_artifacts() -> None:
    for demo in PUBLIC_EVALUATION_DEMOS:
        payload = load_public_demo_payload(demo["file"])
        tavr = payload["tavr"]

        assert payload["case"] == demo["case"]
        assert payload["timebase"]["timebase"] in {"clip", "source"}
        assert payload["score_summary"]["procedure_status_score"] == 1.0
        assert payload["score_summary"]["stage_evidence_score"] == 1.0
        if "table_person_interval_score" in demo:
            assert payload["score_summary"]["table_person_interval_score"] == demo[
                "table_person_interval_score"
            ]
        if "table_person_status_score" in demo:
            assert payload["score_summary"]["table_person_status_score"] == demo[
                "table_person_status_score"
            ]
        assert tavr["timebase_summary"]
        for key in [
            "timebase_summary",
            "procedure_status_summary",
            "operator_stage_packet",
            "table_team_summary",
            "table_identity_groups",
            "stage_roster_summary",
            "stage_table_coverage",
            "procedure_milestones",
            "operator_status_snapshots",
            "procedure_event_timeline",
            "table_transition_events",
            "quality_flags",
        ]:
            assert key in tavr

        status = tavr["procedure_status_summary"][0]
        status_snapshots = tavr["operator_status_snapshots"]
        packet = tavr["operator_stage_packet"][-1]
        event_count = (
            len(tavr["procedure_event_timeline"])
            + len(tavr["table_transition_events"])
        )
        assert "source_start_s" in status
        assert "clip_start_s" in status
        assert "clip_start_s" in packet
        assert "clip_end_s" in packet
        assert status["current_stage"] in TAVR_STAGE_ORDER
        assert status["current_stage"] == demo["stage"]
        assert status["current_stage_label"] == demo["stage_label"]
        assert status["current_stage_status"] == demo.get(
            "current_stage_status", "current_observed"
        )
        assert status["current_stage_evidence_status"] == demo["evidence"]
        assert status["current_table_count"] == demo["current_table_count"]
        assert status["effective_table_source"] == demo["table_source"]
        assert status["effective_table_count"] == demo["table_count"]
        assert "effective_table_canonical_ids" in status
        assert "last_observed_table_canonical_ids" in status
        assert "peak_table_canonical_ids" in status
        assert status_snapshots
        assert status_snapshots[-1]["current_stage"] == status["current_stage"]
        assert "snapshot_reason" in status_snapshots[-1]
        assert "effective_table_canonical_ids" in status_snapshots[-1]
        assert set(status["quality_flag_codes"]) >= demo["required_flags"]
        assert packet["stage_status"] == demo.get(
            "packet_stage_status", "current_observed"
        )
        assert packet["stage_evidence_status"] == demo["evidence"]
        assert packet["effective_table_source"] == demo["table_source"]
        assert packet["effective_table_count"] == demo["table_count"]
        assert "active_table_canonical_ids" in packet
        assert "effective_table_canonical_ids" in packet
        assert "lead_canonical_table_id" in packet
        assert "canonical_table_identity_count" in packet
        assert "within_stage_entry_canonical_table_ids" in packet
        assert "within_stage_exit_canonical_table_ids" in packet
        assert "quality_flag_codes" in packet
        assert tavr["stage_roster_summary"]
        assert tavr["procedure_milestones"]
        assert len(tavr["table_team_summary"]) >= demo["min_team_rows"]
        assert len(tavr["table_identity_groups"]) >= demo["min_identity_groups"]
        assert len(tavr["stage_table_coverage"]) >= demo["min_coverage_rows"]
        assert (
            len(tavr["table_presence_intervals"])
            >= demo["min_presence_intervals"]
        )
        assert all(
            "active_table_canonical_ids" in row
            for row in tavr["stage_roster_summary"]
        )
        assert all(
            "within_stage_entry_canonical_table_ids" in row
            for row in tavr["stage_roster_summary"]
        )
        assert all(
            "within_stage_exit_canonical_table_ids" in row
            for row in tavr["stage_roster_summary"]
        )
        assert all(
            "canonical_table_id" in row
            for row in tavr["stage_table_coverage"]
        )
        assert all(
            "canonical_table_id" in row and "merged_track_ids" in row
            for row in tavr["table_presence_intervals"]
        )
        assert all(
            "table_canonical_ids" in row
            for row in tavr["procedure_event_timeline"]
        )
        assert event_count >= demo["min_events"]

    strong_payload = load_public_demo_payload("sentara-1800-evaluation.json")
    strong_identities = strong_payload["tavr"]["table_identity_groups"]
    assert any(len(row["merged_track_ids"]) > 1 for row in strong_identities)
    strong_rosters = strong_payload["tavr"]["stage_roster_summary"]
    assert any(8 in row["active_table_canonical_ids"] for row in strong_rosters)
    strong_current_roster = strong_rosters[-1]
    assert strong_current_roster["active_table_roster"]
    assert {
        "canonical_table_id",
        "merged_track_ids",
        "observed_table_frames",
        "first_seen_clip_s",
        "last_seen_clip_s",
        "room_coverage_ratio",
    } <= set(strong_current_roster["active_table_roster"][0])
    fallback_payload = load_public_demo_payload(
        "sentara-900-static-fallback-evaluation.json"
    )
    stage_start = next(
        row
        for row in fallback_payload["tavr"]["procedure_event_timeline"]
        if row["event_type"] == "stage_started"
    )
    assert stage_start["table_canonical_ids"] == [1, 2]
    assert "Person 1" in stage_start["roster"][0]["label"]
    fallback_snapshots = fallback_payload["tavr"]["operator_status_snapshots"]
    view_snapshot = next(
        row
        for row in fallback_snapshots
        if "view_start" in row["snapshot_reason"]
        and row["current_view"] == "non_room"
    )
    assert view_snapshot["current_stage"] == "access_sheathing"
    assert view_snapshot["effective_table_source"] == "last_observed_room_view"
    assert view_snapshot["effective_table_canonical_ids"] == [1, 2, 3]
    fallback_packet = fallback_payload["tavr"]["operator_stage_packet"][0]
    assert fallback_packet["within_stage_entry_canonical_table_ids"] == [3]
    assert fallback_packet["within_stage_exit_canonical_table_ids"] == [1, 2, 3]
    fallback_roster = fallback_payload["tavr"]["stage_roster_summary"][0]
    assert fallback_roster["within_stage_entry_canonical_table_ids"] == [3]
    assert fallback_roster["within_stage_exit_canonical_table_ids"] == [1, 2, 3]
    synthetic_payload = load_public_demo_payload(
        "synthetic-full-tavr-evaluation.json"
    )
    synthetic_milestones = synthetic_payload["tavr"]["procedure_milestones"]
    assert [row["stage"] for row in synthetic_milestones] == TAVR_STAGE_ORDER
    assert all(row["observed_in_clip"] for row in synthetic_milestones)
    assert len(synthetic_payload["tavr"]["operator_stage_packet"]) == 8
    synthetic_presence = synthetic_payload["tavr"]["table_presence_intervals"]
    assert any(
        row["dominant_stage"] == "valve_deployment"
        and row["canonical_table_id"] == 7
        and row["merged_track_ids"] == [19]
        for row in synthetic_presence
    )
    assert [
        row["canonical_table_id"]
        for row in synthetic_presence
        if row["dominant_stage"] == "closure_finish"
    ] == [9, 10]
    assert any(
        len(row["merged_track_ids"]) > 1
        for row in synthetic_payload["tavr"]["table_identity_groups"]
    )


def test_static_demo_loads_backend_evaluation_replay() -> None:
    index_html = Path("public/index.html").read_text(encoding="utf-8")
    app_js = Path("public/app.js").read_text(encoding="utf-8")
    replay_js = Path("public/replay_view.mjs").read_text(encoding="utf-8")
    styles = Path("public/styles.css").read_text(encoding="utf-8")
    catalog_block_match = re.search(
        r"const EVALUATION_DEMOS = \[(?P<body>.*?)\];",
        app_js,
        flags=re.DOTALL,
    )

    assert 'id="evaluationDemoButton"' in index_html
    assert 'id="evaluationDemoSelect"' in index_html
    assert 'id="evaluationSnapshotRange"' in index_html
    assert 'id="evaluationSnapshotLabel"' in index_html
    assert 'id="procedureStatus"' in index_html
    assert 'id="statusSnapshotList"' in index_html
    assert 'id="tableIdentityList"' in index_html
    assert 'id="milestoneList"' in index_html
    assert 'id="eventTimelineList"' in index_html
    assert 'id="qualityFlagList"' in index_html
    assert 'id="operatorAnswer"' in index_html
    assert "Current operator answer" in index_html
    assert "Evaluated demo" in index_html
    assert "Replay" in index_html
    assert "At table now" in index_html
    assert 'id="stageTableBrief"' in index_html
    assert "Stage table brief" in index_html
    assert "Table presence" in index_html
    assert 'id="tablePresenceSummary"' in index_html
    assert "Current room view" in index_html
    assert "Stage table context" in index_html
    assert "Table status" not in index_html
    assert "Table-side count" not in index_html
    assert "Status snapshots" in index_html
    assert catalog_block_match is not None
    catalog_block = catalog_block_match.group("body")
    case_ids = re.findall(r'id: "([^"]+)"', catalog_block)
    labels = re.findall(r'label: "([^"]+)"', catalog_block)
    urls = re.findall(r'url: "([^"]+)"', catalog_block)
    assert len(case_ids) >= 2
    assert len(case_ids) == len(set(case_ids))
    assert len(labels) == len(set(labels)) == len(case_ids)
    assert len(urls) == len(set(urls)) == len(case_ids)
    assert all(url.startswith("/demo-data/") for url in urls)
    for demo in PUBLIC_EVALUATION_DEMOS:
        assert demo["case"] in case_ids
        assert f'/demo-data/{demo["file"]}' in urls
    assert "EVALUATION_DEMOS" in app_js
    assert "EVALUATION_DEMO_URL" not in app_js
    assert 'from "./replay_view.mjs"' in app_js
    assert "function populateEvaluationDemoOptions" in app_js
    assert "function selectedEvaluationDemo" in app_js
    assert "function loadEvaluationDemo" in app_js
    assert "function setupEvaluationScrubber" in app_js
    assert "function renderEvaluationReplaySnapshot" in app_js
    assert "function visibleSnapshotRows" in app_js
    assert "evaluationSnapshotRange.addEventListener" in app_js
    assert "replaySnapshotAt" in app_js
    assert "packetForStatus" in app_js
    assert "replaySnapshotLabel" in app_js
    assert "export function replaySnapshotAt" in replay_js
    assert "export function replaySnapshotIndexForTime" in replay_js
    assert "export function replaySnapshotLabel" in replay_js
    assert "export function packetForStatus" in replay_js
    assert "normalizeEvaluationPayload" in app_js
    assert "export function normalizeEvaluationPayload" in replay_js
    assert "export function replayOperatorProjection" in replay_js
    assert "operatorAnswerRows" in app_js
    assert "operatorAnswerRowsFromSnapshots" in app_js
    assert "export function operatorAnswerRows" in replay_js
    assert "export function operatorAnswerRowsFromSnapshots" in replay_js
    assert "operator_summary" in replay_js
    assert "operatorSummary" in replay_js
    assert "Readout" in replay_js
    assert "function renderOperatorAnswer" in app_js
    assert "scoreVerificationRows" in app_js
    assert "export function scoreVerificationRows" in replay_js
    assert "Stage verification" in replay_js
    assert "Table person verification" in replay_js
    assert "No-table verification" in replay_js
    assert "Label gates" not in app_js
    assert "function renderEvaluationReplay" in app_js
    assert "function renderProcedureStatus" in app_js
    assert "function renderBackendStatusSnapshots" in app_js
    assert "function renderBackendOperatorPacket" in app_js
    assert "function currentStageStatusLabel" in app_js
    assert "function backendPacketStageLabel" in app_js
    assert "current_held_context" in app_js
    assert "Current held stage" in app_js
    assert "Replay stage" in app_js
    assert "function renderBackendTableTeam" in app_js
    assert "function renderBackendTableIdentities" in app_js
    assert "function appendPresenceIntervalRows" in app_js
    assert "function presenceIntervalsForStatus" in app_js
    assert "Presence interval" in app_js
    assert "function renderBackendStageCoverage" in app_js
    assert "function renderBackendStageRoster" in app_js
    assert "function renderBackendProcedureMilestones" in app_js
    assert "function renderBackendProcedureEvents" in app_js
    assert "function renderBackendQualityFlags" in app_js
    assert "function formatClockRange" in app_js
    assert "function formatClockPoint" in app_js
    assert "tableSourceLabel" in app_js
    assert "export function tableSourceLabel" in replay_js
    assert "effectiveTableSnapshot" in app_js
    assert "export function effectiveTableSnapshot" in replay_js
    assert "At table for stage" in app_js
    assert "item.dataset.context = context" in app_js
    assert "function stageEvidenceLabel" in app_js
    assert "function evidenceLevelLabel" in app_js
    assert "function evidenceSupportLabel" in app_js
    assert "held from non-room context" in app_js
    assert "recent room-view hold" in replay_js
    assert "evaluationReplayRequestId" in app_js
    assert "keepEvaluationReplayRequest" in app_js
    assert "requestId !== evaluationReplayRequestId" in app_js
    assert "eventTimeSeconds" in app_js
    assert "export function eventTimeSeconds" in replay_js
    assert "focusedReplayEvents" in app_js
    assert "export function focusedReplayEvents" in replay_js
    assert "export function statusTimeSeconds" in replay_js
    assert "event.clip_timestamp_s" in replay_js
    assert "event.clip_start_s" in replay_js
    assert "Sentara TAVR backend artifact" not in app_js
    assert "function appendOverflowRow" in app_js
    assert "function syncEmptyStateToVideoSource" in app_js
    assert "function summarizeStageCounts" in app_js
    assert "currentTableSnapshot" in app_js
    assert "export function currentTableSnapshot" in replay_js
    assert "presenceIntervals" in replay_js
    assert "stageTableBriefRows" in app_js
    assert "export function stageTableBriefRows" in replay_js
    assert "stageTableBriefRowsFromSnapshots" in app_js
    assert "export function stageTableBriefRowsFromSnapshots" in replay_js
    assert ".operator-answer" in styles
    assert 'data-kind="readout"' in styles
    assert "Procedure progress" in replay_js
    assert "export function procedureProgressBrief" in replay_js
    assert "export function stageTableBriefProgressRows" in replay_js
    assert "export function stageRosterForStatus" in replay_js
    assert "export function stageRosterBriefRows" in replay_js
    assert "stageRosterForStatus(demo.stageRosters, status, packet)" in app_js
    assert "renderBackendStageRoster(demo.stageRosters, stageRoster);" in app_js
    assert "renderBackendProcedureEvents(demo.events, status);" in app_js
    assert "function sameStageRosterRow" in app_js
    assert "Earlier selected-stage events" in app_js
    assert "Stage roster" in replay_js
    assert "stage roster people" in app_js
    assert "Stage handoff" in replay_js
    assert "export function stageTableBriefHandoffRows" in replay_js
    assert "function browserStageHandoffBrief" in app_js
    assert "function browserProcedureProgressBrief" in app_js
    assert "const progress = browserProcedureProgressBrief(stage.key)" in app_js
    assert "progress," in app_js
    assert "const handoff = browserStageHandoffBrief(currentStageRosterSegment)" in app_js
    assert "handoff," in app_js
    assert "function renderStageTableBrief" in app_js
    assert ".stage-table-brief" in styles
    assert "position: sticky" in styles
    assert "tableSnapshotSummary" in app_js
    assert "export function tableSnapshotSummary" in replay_js
    assert "function renderTablePresenceSummary" in app_js
    assert "function appendTablePresenceRow" in app_js
    assert "const tableSnapshot = currentTableSnapshot(status);" in app_js
    assert "const tableSnapshot = effectiveTableSnapshot(status);" not in app_js
    assert "emptyState.hidden = Boolean(video.src)" in app_js
    assert "effective_table_source" in app_js
    assert "current_table_count ?? rows.length" in replay_js
    assert "status.current_table_count ?? status.effective_table_count" not in app_js
    assert "last_observed_age_from_clip_end_s" in app_js
    assert "tracking_available_rate" in app_js
    assert "canonical_table_identity_count" in app_js
    assert "effective_table_canonical_ids" in app_js
    assert "active_table_canonical_ids" in app_js
    assert "lead_canonical_table_id" in app_js
    assert "formatPersonId" in app_js
    assert "formatPersonIds" in app_js
    assert "rosterPersonLabel" in app_js
    assert "export function formatPersonId" in replay_js
    assert "export function formatPersonIds" in replay_js
    assert "export function rosterPersonLabel" in replay_js
    assert "function formatPersonIds" not in app_js
    assert "function rosterPersonLabel" not in app_js
    assert "function formatRosterPeople" in app_js
    assert "function eventTableDetail" in app_js
    assert "function snapshotReasonLabel" in app_js
    assert "${rosterPersonLabel(row)}" in app_js
    assert "stage roster people" in app_js
    assert "active people" not in app_js
    assert "new people" in app_js
    assert "continued people" in app_js
    assert "Within-stage movement" in app_js
    assert "entered people" in app_js
    assert "exited people" in app_js
    assert "raw entry IDs" in app_js
    assert "raw exit IDs" in app_js
    assert "timebase_summary" in replay_js
    assert "clip_timestamp_s" in replay_js
    assert "table_identity_groups" in replay_js
    assert "merged_track_ids" in app_js
    assert "quality_flag_codes" in app_js
    assert "operator_status_snapshots" in replay_js
    assert "procedure_event_timeline" in replay_js
    assert ".procedure-status-list" in styles
    assert ".replay-control" in styles
    assert ".replay-scrub-control" in styles
    assert "overflow-wrap: anywhere" in styles
    assert "grid-template-columns: minmax(0, 1fr)" in styles
    assert ".identity-list" in styles
    assert ".milestone-list" in styles
    assert ".event-list" in styles
    assert ".quality-list" in styles
    assert '.roster-card li[data-context="effective"]' in styles
    assert '.roster-card li[data-context="empty"]' in styles
