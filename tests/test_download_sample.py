import sys
from pathlib import Path

import download_sample
from download_sample import build_ytdlp_options


def test_build_ytdlp_options_targets_requested_output() -> None:
    output = Path("samples/or_sample.mp4")

    options = build_ytdlp_options(output)

    assert options["outtmpl"] == str(output)
    assert options["merge_output_format"] == "mp4"
    assert options["noplaylist"] is True


def test_main_falls_back_to_fixture_when_download_fails(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    output = tmp_path / "fallback.mp4"

    def blocked_download(url: str, output_path: Path) -> Path:
        raise RuntimeError("blocked")

    monkeypatch.setattr(download_sample, "download_video", blocked_download)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "download_sample.py",
            "--url",
            "https://example.test/video",
            "--output",
            str(output),
        ],
    )

    download_sample.main()

    assert output.exists()
    assert "Download failed" in capsys.readouterr().out


def test_main_can_generate_tavr_fixture(monkeypatch, tmp_path: Path) -> None:
    output = tmp_path / "tavr.mp4"
    monkeypatch.setattr(
        sys,
        "argv",
        ["download_sample.py", "--tavr-fixture", "--output", str(output)],
    )

    download_sample.main()

    assert output.exists()
    assert output.stat().st_size > 0
