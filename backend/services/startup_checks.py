from __future__ import annotations

import sys
from pathlib import Path

from backend.config import OUTPUT_FOLDER, UPLOAD_FOLDER
from backend.library_scope import initialize_library_storage

REQUIRED_PYTHON = (3, 11, 15)
RUNTIME_DIRECTORIES = [
    Path(OUTPUT_FOLDER),
    Path(UPLOAD_FOLDER),
    Path(OUTPUT_FOLDER).parent / "db_data",
]


def _version_tuple(version_info) -> tuple[int, int, int]:
    if isinstance(version_info, tuple):
        return tuple(version_info[:3])
    return version_info.major, version_info.minor, version_info.micro


def run_startup_checks(version_info=None) -> dict:
    current = _version_tuple(version_info or sys.version_info)
    if current != REQUIRED_PYTHON:
        found = ".".join(str(part) for part in current)
        raise RuntimeError(
            f"需要Python 3.11.15，当前为{found}。"
            "请执行 uv python install 3.11.15 && uv sync。"
        )

    for directory in RUNTIME_DIRECTORIES:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()

    try:
        initialize_library_storage()
    except Exception as exc:
        raise RuntimeError(f"数据库初始化失败：{exc}") from exc

    return {
        "python": {"available": True, "version": "3.11.15"},
        "database": {"available": True},
    }
