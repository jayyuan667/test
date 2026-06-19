from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_install_scripts_use_uv_and_fixed_python():
    for path in ("setup.sh", "setup.bat"):
        text = _read(path).lower()
        assert "uv" in text
        assert "3.11.15" in text
        assert "backend/requirements.txt" not in text
        assert "backend\\requirements.txt" not in text


def test_start_scripts_use_supported_launcher():
    for path in ("start.sh", "start.ps1"):
        text = _read(path).lower()
        assert "backend.run" in text
        assert "uv" in text


def test_node_version_contract():
    assert _read(".nvmrc").strip() == "20"
