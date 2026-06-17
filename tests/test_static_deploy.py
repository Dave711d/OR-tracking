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
