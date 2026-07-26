# -*- coding: utf-8 -*-
"""Shared utilities for API blueprints."""

import os
import json
import re

# Matches .prt and .prt.N (e.g. .prt.1, .prt.12)
PRT_FILE_RE = re.compile(r'\.prt(\.\d+)?$', re.IGNORECASE)

# Drawing number pattern: starts with digit, followed by uppercase letter, then 4-6 digits
_DRAWING_PREFIX_RE = re.compile(r'([1-9][A-Z]\d{4,6})', re.IGNORECASE)


def is_prt_file(filename: str) -> bool:
    """Return True if filename matches the PRT file pattern."""
    return bool(PRT_FILE_RE.search(filename or ""))


def extract_prefix_from_filename(filename: str) -> str | None:
    """Extract drawing number prefix from a filename stem.

    Returns the first match (uppercased) or None.
    """
    stem = os.path.splitext(os.path.basename(filename or ""))[0].strip()
    m = _DRAWING_PREFIX_RE.search(stem)
    return m.group(1).upper() if m else None


def get_enterprise_scope():
    """
    Return (enterprise_id, is_super_admin) for the current request.

    Rules:
      - super_admin       -> (None, True)    no filtering
      - enterprise_admin  -> (user.enterprise_id, False)
      - user (assigned)   -> (user.enterprise_id, False)
      - user (unassigned) -> (None, False)   only public data
    """
    from flask import g

    user = g.current_user if hasattr(g, 'current_user') else None
    if not user:
        return None, False

    role = user.get('role', 'user')
    if role == 'super_admin':
        return None, True

    enterprise_id = user.get('enterprise_id')
    if enterprise_id is None:
        return None, False

    return int(enterprise_id), False


def assert_task_access(task_id):
    """
    Verify the current user can access the given task.

    Returns (True, None) if access is granted.
    Returns (False, (error_response, status_code)) if denied.

    Rules:
      - super_admin: always allowed.
      - enterprise_admin / user: task.enterprise_id must match user.enterprise_id.
      - unassigned user: denied for business tasks.
      - task not found: 404.
    """
    from flask import jsonify

    ent_id, is_super = get_enterprise_scope()
    if is_super:
        return True, None

    task = None
    task_ent = None

    # Try in-memory tasks dict
    try:
        from .status import tasks as _status_tasks
        task = _status_tasks.get(task_id)
        if task:
            task_ent = task.get("enterprise_id")
    except Exception:
        pass

    # Try SQLite task_store
    if task is None:
        try:
            from ..task_store import get_task
            task_row = get_task(task_id)
            if task_row:
                task = task_row
                task_ent = task_row.get("enterprise_id")
        except Exception:
            pass

    # Try file-based result/pending snapshots for legacy restored tasks.
    if task is None:
        try:
            from ..config import OUTPUT_FOLDER

            for filename in ("result.json", "pending_review.json"):
                path = os.path.join(OUTPUT_FOLDER, task_id, filename)
                if not os.path.exists(path):
                    continue
                with open(path, "r", encoding="utf-8") as f:
                    task = json.load(f)
                task_ent = task.get("enterprise_id")
                break
        except Exception:
            pass

    if task is None:
        return False, (jsonify({"error": "Task not found"}), 404)

    # Public-library-only legacy tasks are readable by authenticated users.
    # Enterprise tasks may use the public library for retrieval, but still
    # belong to their enterprise and must pass the enterprise check below.
    task_lib = task.get("library_key") if isinstance(task, dict) else None
    from ..library_scope import is_public_library
    if task_ent is None and is_public_library(task_lib):
        return True, None

    if ent_id is None:
        return False, (jsonify({"error": "未分配企业，无权访问"}), 403)

    if task_ent is None:
        return False, (jsonify({"error": "Task not found"}), 404)

    if task_ent != ent_id:
        return False, (jsonify({"error": "Task not found"}), 404)

    return True, None
