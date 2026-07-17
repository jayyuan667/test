# -*- coding: utf-8 -*-
"""RapidOCR-based hole annotation extractor for drawing images."""

import logging
import re
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

_OCR_ENABLED = __import__("os").getenv("OCR_HOLE_FIELDS", "1") != "0"

# ── RapidOCR 懒加载 ─────────────────────────────────────────────
_ocr_instance = None
_ocr_available: bool | None = None  # None=未检查, True=可用, False=缺包
_ocr_init_lock = threading.Lock()


def _get_ocr():
    """懒加载 RapidOCR 实例，失败后缓存状态避免重复尝试。"""
    global _ocr_instance, _ocr_available
    if _ocr_available is False:
        raise ImportError("rapidocr unavailable (cached failure)")
    if _ocr_instance is not None:
        return _ocr_instance
    with _ocr_init_lock:
        if _ocr_available is False:
            raise ImportError("rapidocr unavailable (cached failure)")
        if _ocr_instance is None:
            try:
                from rapidocr_onnxruntime import RapidOCR  # noqa: PLC0415
                _ocr_instance = RapidOCR()
                _ocr_available = True
                logger.info("[ocr_feature] RapidOCR initialized OK")
            except ImportError:
                _ocr_available = False
                raise
            except Exception as e:
                _ocr_available = False
                logger.warning("[ocr_feature] RapidOCR init failed: %s", e, exc_info=True)
                raise ImportError(f"rapidocr init failed: {e}") from e
    return _ocr_instance


def run_ocr_on_images(image_paths: list[Path]) -> list[str]:
    """对图片列表跑 RapidOCR，返回所有识别文本行（置信度>=0.6）。"""
    lines: list[str] = []
    ocr = _get_ocr()
    for path in image_paths:
        try:
            # RapidOCR returns (result, elapse); result is list of [bbox, text, score]
            result, _ = ocr(str(path))
            if not result:
                continue
            for item in result:
                if len(item) < 2:
                    continue
                text = item[1]
                conf = float(item[2]) if len(item) > 2 and item[2] is not None else 1.0
                if conf >= 0.6 and isinstance(text, str) and text.strip():
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
                "[ocr_feature] rapidocr-onnxruntime not installed — OCR hole extraction disabled. "
                "Run: pip install rapidocr-onnxruntime"
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
# OCR artifact: Ø读为'0', ×读为'X' → "12X02.705.6X90°" "8X02.3V04.6X90°"
_RE_CHEN_OCR = re.compile(r"\d+[Xx]0\d+(?:\.\d+)?.+[Xx]\d+°")

# 螺纹孔: MN + 含"孔深"/"底孔"/"螺纹孔" 或 NXMd 形式 (OCR artifact)
_RE_LUOWEN = re.compile(
    rf"M{_NUM}.*?(?:孔深|底孔|螺纹孔)", re.IGNORECASE
)
# OCR artifact: "4XM2" → 4×M2
_RE_LUOWEN_OCR = re.compile(r"\d+[Xx]M\d+(?:\.\d+)?(?!\w)", re.IGNORECASE)

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

        if _RE_CHEN.search(line) or _RE_CHEN_OCR.search(line):
            buckets["沉孔沉槽"].append(line)
        elif _RE_LUOWEN.search(line) or _RE_LUOWEN_OCR.search(line):
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
    """规范化孔规格字符串用于去重比较（含 OCR artifact 容错）。"""
    s = s.strip()
    # Unicode phi variants → Ø
    s = re.sub(r"[φ∅]", "Ø", s)
    # OCR artifact: × written as X between digit/phi/M  e.g. 12X0 → 12×0, 4XM → 4×M
    s = re.sub(r"(?<=\d)[Xx](?=[\dØM])", "×", s)
    # OCR artifact: Ø written as 0 after × or ↴/V transition markers  e.g. ×02 → ×Ø2
    s = re.sub(r"(?<=[×↴V])0(?=\d)", "Ø", s)
    # OCR artifact: Ø written as 0 between two decimal dims  e.g. 2.705.6 → 2.7Ø5.6
    s = re.sub(r"(?<=\d\.\d)0(?=\d+\.)", "Ø", s)
    # Strip structural separators that differ between VLM (↴) and OCR (V or absent)
    s = re.sub(r"[↴V]", "", s)
    # Strip category suffixes present in VLM but not OCR  e.g. "沉孔" "沉槽" "埋头"
    s = re.sub(r"沉[孔槽]|埋头", "", s)
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
