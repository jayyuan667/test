#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Release stale ZIP import workflow locks.

This script is intended for a systemd timer. It does not import or start the
web application, so it does not add work to gunicorn workers.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from backend.workflow_harness import cleanup_stale_workflow_runs


def main() -> int:
    ttl_seconds = int(
        os.getenv(
            "ZIP_IMPORT_STALE_CLEANUP_SECONDS",
            os.getenv("ZIP_IMPORT_RUNNING_TTL_SECONDS", "3600"),
        )
    )
    cleaned = cleanup_stale_workflow_runs(
        "zip_import",
        stale_after_seconds=ttl_seconds,
    )
    print(f"cleanup_stale_zip_imports ttl_seconds={ttl_seconds} cleaned={cleaned}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
