from __future__ import annotations

import hashlib
import json
from pathlib import Path

REQUIRED_FIELDS = {
    "name",
    "version",
    "format",
    "sha256",
    "classes",
    "input_size",
    "confidence_threshold",
    "released_at",
}


def load_model_manifest(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    missing = sorted(REQUIRED_FIELDS - payload.keys())
    if missing:
        raise ValueError(f"模型清单缺少字段：{', '.join(missing)}")
    if payload["format"] not in {"onnx", "pt"}:
        raise ValueError("模型清单format必须是onnx或pt")
    return payload


def verify_model_file(model_path: Path, manifest: dict) -> tuple[bool, str]:
    if not model_path.is_file():
        return False, "模型文件不存在"
    expected = str(manifest.get("sha256") or "").lower()
    actual = hashlib.sha256(model_path.read_bytes()).hexdigest()
    if expected and actual != expected:
        return False, "模型SHA-256与清单不一致"
    return True, ""
