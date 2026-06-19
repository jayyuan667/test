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


def test_docs_use_only_the_uv_install_contract():
    for path in ("README.md", "INSTALL.md", "START.md"):
        text = _read(path)
        assert "backend/requirements.txt" not in text
        assert "python3 -m venv" not in text
        assert "python -m venv" not in text
        assert "uv sync" in text


def test_docs_explain_optional_yolo_and_capabilities():
    combined = "\n".join(_read(path) for path in ("README.md", "INSTALL.md", "START.md"))
    assert "uv sync --extra yolo" in combined
    assert "/api/system/capabilities" in combined
