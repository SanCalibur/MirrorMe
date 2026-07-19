from pathlib import Path


def test_windows_launcher_starts_the_local_service_and_opens_capture() -> None:
    root = Path(__file__).resolve().parents[1]
    launcher = (root / "启动MirrorMe.bat").read_text(encoding="utf-8")

    assert ".venv\\Scripts\\python.exe" in launcher
    assert "mirrorme.cli','serve" in launcher
    assert "Get-NetTCPConnection -LocalPort 8765" in launcher
    assert "http://127.0.0.1:8765/capture" in launcher
