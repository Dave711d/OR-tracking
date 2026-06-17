import json
from pathlib import Path


def test_vercel_static_demo_files_are_present() -> None:
    public = Path("public")

    assert (public / "index.html").exists()
    assert (public / "app.js").exists()
    assert (public / "styles.css").exists()


def test_vercel_config_builds_public_assets() -> None:
    config = json.loads(Path("vercel.json").read_text(encoding="utf-8"))

    assert config["buildCommand"] == "npm run build"
    assert config["outputDirectory"] == "dist"


def test_vercel_deploy_ignores_streamlit_entrypoint() -> None:
    ignore_rules = Path(".vercelignore").read_text(encoding="utf-8").splitlines()

    assert "app.py" in ignore_rules
    assert "or_tracking/" in ignore_rules
    assert "public/" not in ignore_rules
