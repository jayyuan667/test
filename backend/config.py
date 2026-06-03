# -*- coding: utf-8 -*-
"""Configuration management for the PDF Process Analysis System."""

import os
import json
from typing import Dict, Any

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def load_config() -> Dict[str, Any]:
    """Load configuration from config.json file."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Failed to load config: {e}")
    return {}


def save_config(config: Dict[str, Any]) -> None:
    """Save configuration to config.json file."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error: Failed to save config: {e}")


def get_config() -> Dict[str, Any]:
    """Get full configuration, environment variables take priority over file config."""
    env_config = {
        "vision_api_key": os.getenv("VISION_API_KEY", ""),
        "vision_api_base": os.getenv("VISION_API_BASE", ""),
        "vision_model_id": os.getenv("VISION_MODEL_ID", ""),
        "llm_api_key": os.getenv("LLM_API_KEY", ""),
        "llm_base_url": os.getenv("LLM_BASE_URL", ""),
        "llm_model": os.getenv("LLM_MODEL", ""),
        "vision_mode": os.getenv("VISION_MODE", "doubao"),
        "poppler_path": os.getenv("POPPLER_PATH", ""),
        "creo_exe": os.getenv("CREO_EXE", ""),
        "creo_base_dir": os.getenv("CREO_BASE_DIR", ""),
        "creo_out_dir": os.getenv("CREO_OUT_DIR", ""),
    }

    file_config = load_config()
    for key in env_config:
        if not env_config[key] and key in file_config:
            env_config[key] = file_config[key]

    return env_config


def update_config_from_request(data: Dict[str, Any]) -> Dict[str, Any]:
    """Update configuration from API request data."""
    config = load_config()

    key_mapping = {
        "vision_api_key": "VISION_API_KEY",
        "vision_api_base": "VISION_API_BASE",
        "vision_model_id": "VISION_MODEL_ID",
        "llm_api_key": "LLM_API_KEY",
        "llm_base_url": "LLM_BASE_URL",
        "llm_model": "LLM_MODEL",
        "vision_mode": "VISION_MODE",
        "poppler_path": "POPPLER_PATH",
        "creo_exe": "CREO_EXE",
        "creo_base_dir": "CREO_BASE_DIR",
        "creo_out_dir": "CREO_OUT_DIR",
    }

    for api_key, env_key in key_mapping.items():
        if api_key in data:
            value = (data[api_key] or "").strip() if isinstance(data[api_key], str) else data[api_key]
            config[api_key] = value
            if isinstance(value, str):
                os.environ[env_key] = value

    save_config(config)
    return config


def validate_vision_config(vision_mode: str | None = None) -> str | None:
    """Validate required runtime configuration for vision analysis."""
    mode = (vision_mode or os.getenv("VISION_MODE", "doubao") or "doubao").strip().lower()
    if mode == "local":
        return None

    required = {
        "VISION_API_KEY": "vision_api_key",
        "VISION_API_BASE": "vision_api_base",
        "VISION_MODEL_ID": "vision_model_id",
    }
    missing = [label for env_key, label in required.items() if not (os.getenv(env_key, "") or "").strip()]
    if missing:
        return f"视觉模型配置不完整：缺少 {', '.join(missing)}，请先在系统设置中补全。"
    return None


def init_config() -> None:
    """Initialize configuration - environment variables take priority."""
    env_keys = [
        "VISION_API_KEY",
        "VISION_API_BASE",
        "VISION_MODEL_ID",
        "LLM_API_KEY",
        "LLM_BASE_URL",
        "LLM_MODEL",
        "VISION_MODE",
        "POPPLER_PATH",
        "CREO_EXE",
        "CREO_BASE_DIR",
        "CREO_OUT_DIR",
    ]

    print("Loading configuration:")
    for key in env_keys:
        val = os.getenv(key, "")
        if val:
            display = val[:20] + "..." if len(val) > 20 else val
            if "KEY" in key:
                display = val[:8] + "..." if len(val) > 8 else val
            print(f"  {key}: {display}")

    config = load_config()
    if config:
        for key in env_keys:
            config_key = key.lower()
            if not os.getenv(key) and config_key in config:
                value = config[config_key]
                if isinstance(value, str):
                    os.environ[key] = value
                    preview = value[:20] + "..." if len(value) > 20 else value
                    if "KEY" in key:
                        preview = value[:8] + "..." if len(value) > 8 else value
                    print(f"  [from config.json] {key}: {preview}")


def _iter_extra_paths(raw_value: str):
    """Split POPPLER_PATH or similar env values into individual existing paths."""
    if not raw_value:
        return []

    normalized = raw_value.replace("\n", os.pathsep).replace(";", os.pathsep)
    candidates = []
    for part in normalized.split(os.pathsep):
        cleaned = part.strip().strip('"')
        if cleaned and cleaned not in candidates:
            candidates.append(cleaned)
    return candidates


def ensure_poppler_path() -> None:
    """Ensure Poppler is in PATH for PDF conversion when explicitly configured."""
    configured_paths = _iter_extra_paths(os.getenv("POPPLER_PATH", ""))
    if not configured_paths:
        return

    current_path = os.environ.get("PATH", "")
    existing_entries = current_path.split(os.pathsep) if current_path else []
    missing_entries = [path for path in configured_paths if path not in existing_entries and os.path.exists(path)]

    if missing_entries:
        os.environ["PATH"] = os.pathsep.join(missing_entries + existing_entries)


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
OUTPUT_FOLDER = os.path.join(BASE_DIR, "output")
KB_PREVIEW_FOLDER = os.path.join(BASE_DIR, "db_data", "kb_previews")
MAX_CONTENT_LENGTH = 50 * 1024 * 1024
MAX_HISTORY_COUNT = 50

# ============ FreeCAD / OnShape 配置 ============

def get_freecad_paths() -> list[str]:
    """Return ordered FreeCAD library paths, configurable via env."""
    candidates = [
        os.getenv("FREECAD_BIN"),
        os.getenv("FREECAD_LIB"),
        r"D:\Program Files\FreeCAD 1.1\bin",
        r"D:\Program Files\FreeCAD 1.1\lib",
        r"C:\Program Files\FreeCAD 1.1\bin",
        r"C:\Program Files\FreeCAD 1.1\lib",
        "/usr/lib/freecad/lib",
        "/usr/lib/freecad-python3/lib",
    ]
    return [p for p in candidates if p and os.path.exists(p)]


def get_freecad_qt_plugin_paths() -> list[str]:
    """Return ordered Qt plugin root directories for FreeCAD GUI."""
    candidates = [
        r"D:\Program Files\FreeCAD 1.1\lib\qt6\plugins",
        r"C:\Program Files\FreeCAD 1.1\lib\qt6\plugins",
        r"D:\Program Files\FreeCAD 1.1\bin\Lib\site-packages\PySide6\plugins",
        r"C:\Program Files\FreeCAD 1.1\bin\Lib\site-packages\PySide6\plugins",
    ]
    return [p for p in candidates if p and os.path.exists(os.path.join(p, "platforms"))]
