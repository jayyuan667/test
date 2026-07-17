# -*- coding: utf-8 -*-
"""Configuration management for the PDF Process Analysis System."""

import os
import json
from typing import Dict, Any
from urllib.parse import urlparse

import httpx
from openai import OpenAI
from dotenv import load_dotenv

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
DIRECT_OPENAI_HOSTS = {"ark.cn-beijing.volces.com"}


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
            if "KEY" in key:
                display = "configured=true"
            else:
                display = val[:20] + "..." if len(val) > 20 else val
            print(f"  {key}: {display}")

    config = load_config()
    if config:
        for key in env_keys:
            config_key = key.lower()
            if not os.getenv(key) and config_key in config:
                value = config[config_key]
                if isinstance(value, str):
                    os.environ[key] = value
                    if "KEY" in key:
                        preview = "configured=true"
                    else:
                        preview = value[:20] + "..." if len(value) > 20 else value
                    print(f"  [from config.json] {key}: {preview}")


def create_openai_client(api_key: str | None, base_url: str | None) -> OpenAI:
    """Build an OpenAI-compatible client.

    Some vision/embedding providers are unstable behind the user's local proxy.
    For known direct-connect hosts, bypass environment proxy settings explicitly
    while keeping the default behavior for all other providers.
    """
    host = ""
    if base_url:
        try:
            host = (urlparse(base_url).hostname or "").lower()
        except ValueError:
            host = ""

    if host in DIRECT_OPENAI_HOSTS:
        return OpenAI(
            api_key=api_key,
            base_url=base_url,
            http_client=httpx.Client(trust_env=False),
        )

    return OpenAI(api_key=api_key, base_url=base_url)


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


BASE_DIR = _PROJECT_ROOT


def _env_path(name: str, default: str) -> str:
    value = os.getenv(name, "").strip()
    return os.path.abspath(os.path.expanduser(value)) if value else default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


_runtime_data_dir_configured = bool(os.getenv("RUNTIME_DATA_DIR", "").strip())
RUNTIME_DATA_DIR = _env_path("RUNTIME_DATA_DIR", BASE_DIR)
DB_DATA_FOLDER = _env_path("DB_DATA_FOLDER", os.path.join(RUNTIME_DATA_DIR, "db_data"))
UPLOAD_FOLDER = _env_path("UPLOAD_FOLDER", os.path.join(RUNTIME_DATA_DIR, "uploads"))
OUTPUT_FOLDER = _env_path("OUTPUT_FOLDER", os.path.join(RUNTIME_DATA_DIR, "output"))
KB_PREVIEW_FOLDER = _env_path("KB_PREVIEW_FOLDER", os.path.join(DB_DATA_FOLDER, "kb_previews"))
_default_state_dir = RUNTIME_DATA_DIR if _runtime_data_dir_configured else os.path.join(BASE_DIR, "backend")
AUTH_DB_FILE = _env_path("AUTH_DB_FILE", os.path.join(_default_state_dir, "auth.db"))
TASK_STORE_DB_FILE = _env_path("TASK_STORE_DB_FILE", os.path.join(_default_state_dir, "task_store.db"))
AUTH_COOKIE_NAME = os.getenv("AUTH_COOKIE_NAME", "gn_token").strip() or "gn_token"
VECTOR_DB_PATH = _env_path("VECTOR_DB_PATH", os.path.join(DB_DATA_FOLDER, "2d-v.db"))
MAX_CONTENT_LENGTH = 50 * 1024 * 1024
MAX_HISTORY_COUNT = 50

# ============ YOLO 预标注配置 ============
YOLO_WEIGHT_PATH = _env_path("YOLO_WEIGHT_PATH", os.path.join(DB_DATA_FOLDER, "best.pt"))
YOLO_ONNX_PATH   = _env_path("YOLO_ONNX_PATH",   os.path.join(DB_DATA_FOLDER, "best.onnx"))
YOLO_CONF        = float(os.getenv("YOLO_CONF", "0.25"))
YOLO_IOU         = float(os.getenv("YOLO_IOU",  "0.45"))
YOLO_IMG_SIZE    = int(os.getenv("YOLO_IMG_SIZE", "1280"))
YOLO_DEVICE      = os.getenv("YOLO_DEVICE", "cpu")

# ============ YOLO GPU 服务配置 ============
YOLO_SERVICE_URL       = os.getenv("YOLO_SERVICE_URL", "").strip()
YOLO_SERVICE_TOKEN     = os.getenv("YOLO_SERVICE_TOKEN", "")
YOLO_SERVICE_TIMEOUT   = float(os.getenv("YOLO_SERVICE_TIMEOUT", "15"))


def get_backend_bind_config() -> tuple[str, int]:
    return os.getenv("BACKEND_HOST", "0.0.0.0").strip() or "0.0.0.0", _env_int("BACKEND_PORT", 5190)

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


import secrets


def get_jwt_secret() -> str:
    """Return a stable JWT secret key.

    Gunicorn workers run in separate processes. If each worker generates its own
    key, a token issued by one worker fails validation on another.
    """
    secret = os.getenv("JWT_SECRET_KEY", "").strip()
    if secret:
        return secret

    secret_file = os.path.join(RUNTIME_DATA_DIR, "jwt_secret.key")
    try:
        if os.path.exists(secret_file):
            persisted = open(secret_file, "r", encoding="utf-8").read().strip()
            if persisted:
                os.environ["JWT_SECRET_KEY"] = persisted
                return persisted
    except OSError:
        pass

    generated = secrets.token_hex(32)
    try:
        os.makedirs(os.path.dirname(secret_file), exist_ok=True)
        with open(secret_file, "x", encoding="utf-8") as f:
            f.write(generated)
        try:
            os.chmod(secret_file, 0o600)
        except OSError:
            pass
    except FileExistsError:
        persisted = open(secret_file, "r", encoding="utf-8").read().strip()
        if persisted:
            generated = persisted
    except OSError:
        pass

    os.environ["JWT_SECRET_KEY"] = generated
    return generated
