from pathlib import Path

import pytest

from backend.services import startup_checks


def test_wrong_python_version_is_blocking():
    with pytest.raises(RuntimeError, match="Python 3.11.15"):
        startup_checks.run_startup_checks(version_info=(3, 11, 14))


def test_runtime_directories_are_created(monkeypatch, tmp_path):
    monkeypatch.setattr(startup_checks, "RUNTIME_DIRECTORIES", [tmp_path / "a", tmp_path / "b"])
    monkeypatch.setattr(startup_checks, "initialize_library_storage", lambda: None)
    result = startup_checks.run_startup_checks(version_info=(3, 11, 15))
    assert result["database"]["available"] is True
    assert all(path.is_dir() for path in startup_checks.RUNTIME_DIRECTORIES)


def test_database_initialization_failure_is_blocking(monkeypatch, tmp_path):
    monkeypatch.setattr(startup_checks, "RUNTIME_DIRECTORIES", [tmp_path])
    monkeypatch.setattr(
        startup_checks,
        "initialize_library_storage",
        lambda: (_ for _ in ()).throw(RuntimeError("schema failed")),
    )
    with pytest.raises(RuntimeError, match="schema failed"):
        startup_checks.run_startup_checks(version_info=(3, 11, 15))
