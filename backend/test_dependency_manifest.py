from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]


def _pyproject():
    with (ROOT / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)


def test_python_version_is_pinned():
    assert (ROOT / ".python-version").read_text(encoding="utf-8").strip() == "3.11.15"
    assert _pyproject()["project"]["requires-python"] == ">=3.11,<3.12"


def test_core_and_optional_dependencies_are_separated():
    project = _pyproject()["project"]
    core = "\n".join(project["dependencies"]).lower()
    extras = project["optional-dependencies"]

    assert "pymupdf" in core
    assert "onnxruntime" in core
    assert "opencv-python" in core
    assert "ultralytics" not in core
    assert "torch" not in core
    assert any(item.startswith("ultralytics") for item in extras["yolo"])
    assert any("sys_platform == 'win32'" in item for item in extras["windows-creo"])


def test_only_one_hand_maintained_dependency_manifest_exists():
    assert not (ROOT / "backend" / "requirements.txt").exists()
    exported = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    assert "pymupdf==" in exported
    assert "ultralytics==" not in exported
