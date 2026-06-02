# -*- coding: utf-8 -*-
"""PaddleOCR-based hole annotation extractor for Creo view images."""

import logging
import os
import re
import sys
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

_OCR_ENABLED = os.getenv("OCR_HOLE_FIELDS", "1") != "0"

# Disable OneDNN/MKL-DNN globally before Paddle C++ runtime initializes.
# PaddlePaddle 3.x with PIR dispatches fused_conv2d to the OneDNN kernel by
# default on CPU, which raises "OneDnnContext does not have input Filter".
os.environ["FLAGS_use_mkldnn"] = "0"

# ── PaddleOCR 懒加载 ────────────────────────────────────────────
_ocr_instance = None
_ocr_available: bool | None = None  # None=未检查, True=可用, False=缺包
_ocr_init_lock = threading.Lock()  # 防止多线程并发初始化


def _ensure_lazy_loader():
    """Force the correct lazy_loader (with attach_stub) into sys.modules.

    geometry_analyzer.py imports FreeCAD at startup, which inserts
    D:\\Program Files\\FreeCAD 1.1\\Ext\\ at the FRONT of sys.path.
    That directory ships an old lazy_loader without attach_stub, which
    shadows the venv's version and breaks skimage.__init__.

    Fix: scan ALL sys.path entries for a lazy_loader that actually has
    attach_stub in its source, then load it explicitly via importlib so
    sys.path ordering is irrelevant.
    """
    import importlib.util

    # Fast path: already have the right module cached
    ll = sys.modules.get("lazy_loader")
    if ll is not None and hasattr(ll, "attach_stub"):
        return

    if ll is not None:
        logger.warning(
            "[ocr_feature] lazy_loader in sys.modules missing attach_stub "
            "(file=%s, likely FreeCAD's Ext version) — searching for correct one",
            getattr(ll, "__file__", "?"),
        )

    # Search all sys.path entries for a lazy_loader that has attach_stub
    good_init = None
    for p in sys.path:
        candidate = Path(p) / "lazy_loader" / "__init__.py"
        if candidate.is_file():
            try:
                if "def attach_stub" in candidate.read_text(encoding="utf-8", errors="ignore"):
                    good_init = candidate
                    break
            except OSError:
                continue

    if good_init is None:
        logger.error(
            "[ocr_feature] No lazy_loader with attach_stub found anywhere in sys.path "
            "— OCR will fail. Install lazy_loader>=0.3 in the active venv."
        )
        return

    # Load the correct lazy_loader directly by path, bypassing sys.path order
    sys.modules.pop("lazy_loader", None)
    spec = importlib.util.spec_from_file_location("lazy_loader", good_init)
    module = importlib.util.module_from_spec(spec)
    sys.modules["lazy_loader"] = module  # register before exec (handles self-refs)
    spec.loader.exec_module(module)

    if hasattr(module, "attach_stub"):
        logger.info("[ocr_feature] lazy_loader loaded from %s (attach_stub OK)", good_init)
    else:
        logger.error("[ocr_feature] lazy_loader at %s still has no attach_stub!", good_init)


def _get_ocr():
    """懒加载 PaddleOCR 实例。任何初始化失败都缓存状态，避免重复尝试。"""
    global _ocr_instance, _ocr_available
    if _ocr_available is False:
        raise ImportError("paddleocr unavailable (cached failure)")
    if _ocr_instance is not None:
        return _ocr_instance
    with _ocr_init_lock:
        # Double-checked locking: re-test inside the lock
        if _ocr_available is False:
            raise ImportError("paddleocr unavailable (cached failure)")
        if _ocr_instance is None:
            _ensure_lazy_loader()
            try:
                from paddleocr import PaddleOCR  # noqa: PLC0415
                _ocr_instance = PaddleOCR(use_angle_cls=True, lang="ch")
                _ocr_available = True
            except ImportError:
                _ocr_available = False
                raise
            except Exception as e:
                _ocr_available = False
                logger.warning("[ocr_feature] PaddleOCR init failed: %s", e, exc_info=True)
                raise ImportError(f"paddleocr init failed: {e}") from e
    return _ocr_instance


def run_ocr_on_images(image_paths: list[Path]) -> list[str]:
    """对图片列表跑 PaddleOCR，返回所有识别文本行（置信度>=0.6）。"""
    lines: list[str] = []
    ocr = _get_ocr()
    for path in image_paths:
        try:
            result = ocr.ocr(str(path), cls=True)
            if not result:
                continue
            for page in result:
                if not page:
                    continue
                for item in page:
                    text, conf = item[1][0], item[1][1]
                    if conf >= 0.6 and text.strip():
                        lines.append(text.strip())
        except Exception:
            logger.warning("[ocr_feature] OCR failed on %s", path, exc_info=True)
    return lines


_import_error_warned = False


def extract_hole_fields_from_ocr(creo_dir: str) -> dict[str, list[str]]:
    """从 creo_views 目录的图片中提取孔标注，返回分类后的字段桶。

    若 OCR 未启用、目录不存在、或任何异常，返回空 dict。
    """
    global _import_error_warned
    if not _OCR_ENABLED:
        return {}
    try:
        from backend.pipeline.vlm_feature import _select_creo_images  # noqa: PLC0415
        dir_path = Path(creo_dir)
        if not dir_path.exists():
            return {}
        image_paths = _select_creo_images(dir_path, max_n=6)
        if not image_paths:
            return {}
        lines = run_ocr_on_images(image_paths)
        buckets = classify_ocr_tokens(lines)
        non_empty = {k: v for k, v in buckets.items() if v}
        logger.info(
            "[ocr_feature] OCR done: %d images, %d lines recognized, buckets: %s",
            len(image_paths), len(lines),
            {k: len(v) for k, v in non_empty.items()} if non_empty else "none",
        )
        return buckets
    except ImportError:
        if not _import_error_warned:
            _import_error_warned = True
            logger.warning(
                "[ocr_feature] paddleocr not installed — OCR hole extraction disabled. "
                "Start the backend with the Python env that has paddleocr installed, "
                "or set OCR_HOLE_FIELDS=0 to suppress this message."
            )
        return {}
    except Exception:
        logger.warning("[ocr_feature] extract_hole_fields_from_ocr failed", exc_info=True)
        return {}


# ── Regex patterns ──────────────────────────────────────────────
_PHI = r"[Øφ∅]"
_NUM = r"\d+(?:\.\d+)?"

# 沉孔沉槽: φN×角度° 或 含"沉孔"/"沉槽"/"埋头"
_RE_CHEN = re.compile(
    rf"({_PHI}{_NUM}\s*[×x]\s*{_NUM}°|沉孔|沉槽|埋头)", re.IGNORECASE
)

# 螺纹孔: MN + 含"孔深"/"底孔"/"螺纹孔"
_RE_LUOWEN = re.compile(
    rf"M{_NUM}.*?(?:孔深|底孔|螺纹孔)", re.IGNORECASE
)

# 通孔: N-φN 或 含"通孔" (无深度词)
_RE_TONGKONG_PHI = re.compile(rf"\d+-?{_PHI}{_NUM}")
_RE_TONGKONG_KW = re.compile(r"通孔")
_RE_DEPTH_WORD = re.compile(r"孔深|底孔|螺纹孔")

# 特殊孔
_RE_SPECIAL = re.compile(r"锥孔|异形孔|定位孔|销孔")
_RE_SPECIAL_LARGE = re.compile(rf"{_PHI}(\d+(?:\.\d+)?)")


def classify_ocr_tokens(lines: list[str]) -> dict[str, list[str]]:
    """将 OCR 识别文本行分类到4个孔字段桶。

    优先级: 沉孔沉槽 > 螺纹孔 > 通孔 > 特殊孔
    每条文本只归入一个桶。
    """
    buckets: dict[str, list[str]] = {
        "通孔": [], "沉孔沉槽": [], "螺纹孔": [], "特殊孔": []
    }
    for raw in lines:
        if not isinstance(raw, str): continue
        line = raw.strip()
        if not line or not re.search(r"[\dMØφ∅沉槽锥孔通孔螺纹埋异定销]", line):
            continue

        if _RE_CHEN.search(line):
            buckets["沉孔沉槽"].append(line)
        elif _RE_LUOWEN.search(line):
            buckets["螺纹孔"].append(line)
        elif _RE_SPECIAL.search(line):
            buckets["特殊孔"].append(line)
        elif _RE_TONGKONG_KW.search(line) or (
            _RE_TONGKONG_PHI.search(line) and not _RE_DEPTH_WORD.search(line)
        ):
            buckets["通孔"].append(line)
        else:
            m = _RE_SPECIAL_LARGE.search(line)
            if m and float(m.group(1)) > 50:
                buckets["特殊孔"].append(line)
    return buckets


def _normalize_spec(s: str) -> str:
    """规范化孔规格字符串用于去重比较。"""
    s = s.strip()
    s = re.sub(r"[φ∅]", "Ø", s)
    s = re.sub(r"\s+", " ", s)
    s = s.replace("　", " ")
    return s


def merge_ocr_into_field(vlm_val: str, ocr_items: list[str]) -> str:
    """将 OCR 识别项追加到 VLM 字段值，重复项去重。

    Args:
        vlm_val: VLM 字段值，；分隔 或 "无"
        ocr_items: OCR 识别到的同字段条目列表

    Returns:
        合并去重后的字段值字符串
    """
    if not ocr_items:
        return vlm_val

    vlm_parts = [p.strip() for p in vlm_val.split("；") if p.strip() and p.strip() != "无"]
    vlm_norms = [_normalize_spec(p) for p in vlm_parts]

    for item in ocr_items:
        norm = _normalize_spec(item)
        if any(norm == v or norm in v or v in norm for v in vlm_norms):
            continue
        vlm_parts.append(item.strip())
        vlm_norms.append(norm)

    return "；".join(vlm_parts) if vlm_parts else "无"
