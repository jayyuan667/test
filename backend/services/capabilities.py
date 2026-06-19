from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from pathlib import Path

from backend.config import (
    YOLO_ONNX_PATH,
    YOLO_WEIGHT_PATH,
    get_freecad_paths,
    get_config,
)

REQUIRED_PYTHON = (3, 11, 15)


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def inspect_python_capability(version_info=None) -> dict:
    info = version_info or sys.version_info
    version = f"{info.major}.{info.minor}.{info.micro}"
    available = (info.major, info.minor, info.micro) == REQUIRED_PYTHON
    return {
        "available": available,
        "version": version,
        "required": "3.11.15",
        "reason": "" if available else "需要Python 3.11.15，请执行 uv python install 3.11.15 && uv sync",
    }


def inspect_pdf_capability() -> dict:
    if _module_available("fitz"):
        return {"available": True, "provider": "pymupdf", "reason": ""}
    if shutil.which("pdfinfo") and shutil.which("pdftoppm"):
        return {"available": True, "provider": "poppler", "reason": ""}
    return {
        "available": False,
        "provider": None,
        "reason": "PDF转换不可用，请执行 uv sync 安装PyMuPDF，或安装Poppler兼容工具。",
    }


def inspect_yolo_capability() -> dict:
    onnx = Path(YOLO_ONNX_PATH)
    pt = Path(YOLO_WEIGHT_PATH)
    if onnx.is_file() and _module_available("onnxruntime"):
        return {"available": True, "provider": "onnx", "reason": ""}
    if pt.is_file() and _module_available("ultralytics") and _module_available("torch"):
        return {"available": True, "provider": "ultralytics", "reason": ""}
    missing = []
    if not onnx.is_file() and not pt.is_file():
        missing.append("模型文件不存在")
    elif onnx.is_file() and not _module_available("onnxruntime"):
        missing.append("onnxruntime未安装")
    elif pt.is_file():
        missing.append("ultralytics或torch未安装，请执行 uv sync --extra yolo")
    return {"available": False, "provider": None, "reason": "；".join(missing)}


def inspect_vision_api_capability() -> dict:
    config = get_config()
    mode = str(config.get("vision_mode") or "doubao").lower()
    if mode == "local":
        local_module_dir = Path(__file__).resolve().parents[2] / "v_model_test"
        available = all(
            (local_module_dir / f"{name}.py").is_file()
            for name in ("ppstructure_extractor", "rule_engine", "semantic_enhancer")
        )
        return {
            "available": available,
            "provider": "local",
            "reason": "" if available else "本地视觉分析依赖不完整",
        }
    available = all(
        str(config.get(name) or "").strip()
        for name in ("vision_api_key", "vision_api_base", "vision_model_id")
    )
    return {
        "available": available,
        "provider": mode,
        "reason": "" if available else "视觉模型配置不完整",
    }


def inspect_creo_capability() -> dict:
    if sys.platform != "win32":
        return {
            "available": False,
            "applicable": False,
            "reason": "当前平台不支持Creo自动化",
        }
    config = get_config()
    exe = Path(str(config.get("creo_exe") or ""))
    available = exe.is_file() and _module_available("pywinauto")
    return {
        "available": available,
        "applicable": True,
        "reason": "" if available else "Creo路径或Windows自动化依赖不完整",
    }


def inspect_freecad_capability() -> dict:
    paths = get_freecad_paths()
    available = bool(paths)
    return {
        "available": available,
        "reason": "" if available else "未检测到FreeCAD",
    }


def inspect_database_capability() -> dict:
    from backend.library_scope import DB_PATH

    db_path = Path(DB_PATH)
    existing_parent = db_path.parent
    while not existing_parent.exists() and existing_parent != existing_parent.parent:
        existing_parent = existing_parent.parent
    writable = os.access(existing_parent, os.W_OK)
    return {
        "available": writable,
        "schema_ready": db_path.exists(),
        "reason": "" if writable else f"数据库目录不可写：{existing_parent}",
    }


def collect_capabilities() -> dict:
    return {
        "ok": True,
        "python": inspect_python_capability(),
        "database": inspect_database_capability(),
        "pdf": inspect_pdf_capability(),
        "vision_api": inspect_vision_api_capability(),
        "yolo": inspect_yolo_capability(),
        "creo": inspect_creo_capability(),
        "freecad": inspect_freecad_capability(),
    }
