import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_start_backend_uses_module_entrypoint_and_project_python():
    script = (ROOT / "start-backend.sh").read_text(encoding="utf-8")

    assert "python app.py" not in script
    assert "-m backend.app" in script
    assert ".venv/bin/python" in script


def test_start_backend_defaults_to_5390_and_checks_port_conflict():
    script = (ROOT / "start-backend.sh").read_text(encoding="utf-8")

    assert "BACKEND_PORT=${BACKEND_PORT:-5390}" in script
    assert "lsof -tiTCP:${BACKEND_PORT}" in script
    assert "kill ${PORT_PID}" in script


def test_package_scripts_expose_stable_startup_commands():
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    scripts = package["scripts"]

    assert scripts["dev:frontend"] == "next dev --webpack -p 3002"
    assert scripts["start:frontend"] == "next start -p 3002"
    assert scripts["start:backend"] == "./start-backend.sh"
