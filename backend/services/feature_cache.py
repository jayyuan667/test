# -*- coding: utf-8 -*-
"""Feature extraction result cache — keyed by SHA-256 of the source file."""

import hashlib
import json
import logging
import os

logger = logging.getLogger(__name__)

_CACHE_SUBDIR = "_feature_cache"


def _cache_dir(output_folder: str) -> str:
    d = os.path.join(output_folder, _CACHE_SUBDIR)
    os.makedirs(d, exist_ok=True)
    return d


def compute_file_hash(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def get_cached(output_folder: str, file_hash: str) -> dict | None:
    path = os.path.join(_cache_dir(output_folder), f"{file_hash}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        logger.warning("Feature cache read failed for %s", file_hash, exc_info=True)
        return None


def put_cache(output_folder: str, file_hash: str, payload: dict) -> None:
    path = os.path.join(_cache_dir(output_folder), f"{file_hash}.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        logger.info("Feature cache written: %s", file_hash[:12])
    except Exception:
        logger.warning("Feature cache write failed for %s", file_hash, exc_info=True)
