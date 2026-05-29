# -*- coding: utf-8 -*-
"""Shared utilities for API blueprints."""

import os
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
