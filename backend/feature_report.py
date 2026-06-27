# -*- coding: utf-8 -*-
"""Helpers for building and persisting feature-extraction reports."""

import json
import os
import re
from typing import Dict, Iterable, List

# ── Thickness depth-conflict post-check ──────────────────────────────────────
_OUTER_DIM_RE = re.compile(
    r'(\d+(?:\.\d+)?)(?:[±+\-]\d+(?:\.\d+)?)?\s*[×xX*]\s*'
    r'(\d+(?:\.\d+)?)(?:[±+\-]\d+(?:\.\d+)?)?\s*[×xX*]\s*'
    r'(\d+(?:\.\d+)?)(?:[±+\-]\d+(?:\.\d+)?)?'
)
_PHI_DEPTH_RE    = re.compile(r'φ\d+(?:\.\d+)?\s*[×xX]\s*(\d+(?:\.\d+)?)')
_EXPLICIT_DEPTH_RE = re.compile(r'(?:深|孔深)\s*(\d+(?:\.\d+)?)')
_KD_NUM_RE       = re.compile(r'\b(\d+(?:\.\d+)?)\b')


def _max_annotated_depth(merged_fields: dict) -> float:
    """Extract the maximum annotated hole/slot depth from parsed fields."""
    text = "；".join(
        v
        for field in ("外圆与内孔", "沉孔沉槽", "关键尺寸", "精度与检测特征")
        for v in merged_fields.get(field, [])
    )
    depths = (
        [float(m.group(1)) for m in _PHI_DEPTH_RE.finditer(text)]
        + [float(m.group(1)) for m in _EXPLICIT_DEPTH_RE.finditer(text)]
    )
    return max(depths) if depths else 0.0


def _replace_outer_thickness(merged_fields: dict, new_T: float, correction_key: str,
                            correction_msg: str) -> dict:
    """Apply a corrected thickness value to the 外形尺寸 field.

    Returns a new merged_fields dict with the corrected dimension string and a
    private logging key (_thickness_correction or _outer_key_correction).
    """
    outer_list = merged_fields.get("外形尺寸", [])
    m = _OUTER_DIM_RE.search(outer_list[0])
    a, b, c = float(m.group(1)), float(m.group(2)), float(m.group(3))
    T = min(a, b, c)
    grp_idx = next(
        (i for i, v in enumerate([a, b, c], start=1) if abs(v - T) < 0.001), None
    )
    if grp_idx is None:
        return merged_fields

    new_T_str = str(int(new_T)) if new_T == int(new_T) else str(round(new_T, 3))
    new_dim = outer_list[0][: m.start(grp_idx)] + new_T_str + outer_list[0][m.end(grp_idx):]

    result = dict(merged_fields)
    result["外形尺寸"] = [new_dim] + outer_list[1:]
    result[correction_key] = correction_msg
    return result


def _fix_thickness_by_depth_check(merged_fields: dict) -> dict:
    """Post-validate 外形尺寸: if min dim < deepest hole depth, attempt fix.

    Trigger: deepest annotated depth > thickness × 3 (conservative).
    Correction source: smallest value in 关键尺寸 that is > depth and < longest dim.
    """
    outer_list = merged_fields.get("外形尺寸", [])
    if not outer_list:
        return merged_fields

    m = _OUTER_DIM_RE.search(outer_list[0])
    if not m:
        return merged_fields

    a, b, c = float(m.group(1)), float(m.group(2)), float(m.group(3))
    T = min(a, b, c)
    L = max(a, b, c)

    max_depth = _max_annotated_depth(merged_fields)
    if max_depth <= 0 or max_depth < T * 3:
        return merged_fields

    key_text = "；".join(merged_fields.get("关键尺寸", []))
    candidates = sorted(
        float(v) for v in _KD_NUM_RE.findall(key_text)
        if float(v) > max_depth
        and float(v) < L
        and all(abs(float(v) - x) > 0.01 for x in (a, b, c))
    )
    if not candidates:
        return merged_fields

    new_T = candidates[0]
    return _replace_outer_thickness(
        merged_fields, new_T,
        correction_key="_thickness_correction",
        correction_msg=f"{outer_list[0]} → （孔深{max_depth}mm > 原厚{T}mm，取{new_T}mm）",
    )


def _fix_outer_by_key_dims_order(merged_fields: dict) -> dict:
    """Fix 外形尺寸 when VLM picks a wrong feature-dim as thickness.

    Two independent trigger paths (either is sufficient):

    Path A — T is late in 关键尺寸:
      T does NOT appear in the first 3 plain numbers, but a smaller value
      does appear in those first 3. Example: key_dims=[293, 51.3, 10, …, 36]
      → 36 is at position 17, 10 is at position 2 → replace 36 with 10.

    Path B — T is 3rd in 关键尺寸 but immediately followed by a much smaller value:
      T appears at position 2 (3rd token), AND the very next token (position 3)
      is < T/3 and ≥ 3 mm. Example: key_dims=[293, 51.3, 36, 10, …]
      → 36/10 = 3.6 > 3 → replace 36 with 10.

    Guards:
    - new_T must be ≥ 3 mm (skip cosmetic / tolerance numbers)
    - Stores _outer_key_correction for logging; '_'-prefixed keys never appear in report_text.
    """
    outer_list = merged_fields.get("外形尺寸", [])
    key_list = merged_fields.get("关键尺寸", [])
    if not outer_list or not key_list:
        return merged_fields

    m = _OUTER_DIM_RE.search(outer_list[0])
    if not m:
        return merged_fields

    a, b, c = float(m.group(1)), float(m.group(2)), float(m.group(3))
    T = min(a, b, c)

    # Build ordered list of plain numeric tokens from 关键尺寸 (skip unit-prefixed like φ/M/R/×)
    key_text = "；".join(key_list)
    plain_nums: list = []
    for token in re.split(r'[；;,，\s]+', key_text):
        token = token.strip()
        if not token or re.match(r'^[φøΦMRm×xX±]', token):
            continue
        nm = re.match(r'^(\d+(?:\.\d+)?)', token)
        if nm:
            plain_nums.append(float(nm.group(1)))

    if len(plain_nums) < 3:
        return merged_fields

    first3 = plain_nums[:3]
    T_pos = next((i for i, k in enumerate(plain_nums) if abs(k - T) < 0.5), None)

    new_T = None
    reason = ""

    # Path A: T is late (position > 2), candidate is among the first 3
    if T_pos is not None and T_pos > 2 and not any(abs(T - k) < 0.5 for k in first3):
        candidates = sorted(k for k in first3 if k < T and k >= 3.0)
        if candidates:
            new_T = candidates[0]
            reason = f"T={T}在关键尺寸位置{T_pos}，早期主尺寸{new_T}更可能是真实厚度"

    # Path B: T is exactly at position 2 and the next value is < T/3
    if new_T is None and T_pos == 2 and len(plain_nums) > 3:
        next_val = plain_nums[3]
        if next_val >= 3.0 and T > 0 and next_val < T / 3:
            new_T = next_val
            reason = f"T={T}在关键尺寸位置2，紧邻值{new_T}仅为T的{next_val/T:.0%}，可能是真实厚度"

    if new_T is None:
        return merged_fields

    return _replace_outer_thickness(
        merged_fields, new_T,
        correction_key="_outer_key_correction",
        correction_msg=f"{outer_list[0]} → （{reason}）",
    )


REPORT_FIELD_ORDER = [
    "图号",
    "零件名称",
    "外形尺寸",
    "毛坯类型",
    "技术要求",
    "形态",
    "类型",
    "关键尺寸",
    "弧段与齿形",
    "端面与平面",
    "外圆与内孔",
    "螺纹与螺孔",
    "倒角",
    "热处理与探伤",
    "标识与检验",
    "线切割",
    "精度与检测特征",
    "表面处理与镀层特征",
    "过渡特征",
    "其他特征",
]

FEATURE_SYNONYMS = {
    "图纸编号": "图号",
    "零件号": "图号",
    "零件图号": "图号",
    "产品名称": "零件名称",
    "部件名称": "零件名称",
    "毛坯": "毛坯类型",
    "材料": "毛坯类型",
    "物料": "毛坯类型",
    "物料形态": "毛坯类型",
    "技术条件": "技术要求",
    "加工要求": "技术要求",
    "外形": "形态",
    "工件形态": "形态",
    "类别": "类型",
    "规格": "关键尺寸",
    "尺寸": "关键尺寸",
    "弧段": "弧段与齿形",
    "齿形": "弧段与齿形",
    "端面": "端面与平面",
    "平面": "端面与平面",
    "外圆": "外圆与内孔",
    "内孔": "外圆与内孔",
    "孔": "外圆与内孔",
    "螺纹": "螺纹与螺孔",
    "螺孔": "螺纹与螺孔",
    "倒角要求": "倒角",
    "热处理": "热处理与探伤",
    "探伤": "热处理与探伤",
    "标识": "标识与检验",
    "检验": "标识与检验",
    "刻字": "标识与检验",
    "刻字要求": "标识与检验",
    "标记": "标识与检验",
    "线切": "线切割",
    "线割": "线切割",
    "精度": "精度与检测特征",
    "检测": "精度与检测特征",
    "表面处理": "表面处理与镀层特征",
    "镀层": "表面处理与镀层特征",
    "过渡": "过渡特征",
    "翻面": "过渡特征",
    "吊面": "过渡特征",
    "吊面/翻面": "过渡特征",
    "吊面/翻面特征": "过渡特征",
    "翻面特征": "过渡特征",
}


def normalize_feature_label(label: str) -> str:
    cleaned = re.sub(r"[\s\-—_（）()【】\[\]：:]+$", "", (label or "").strip())
    cleaned = cleaned.replace(" ", "")
    if cleaned in FEATURE_SYNONYMS:
        return FEATURE_SYNONYMS[cleaned]
    if cleaned.startswith("图号"):
        return "图号"
    if cleaned.startswith("零件名称") or cleaned.startswith("产品名称"):
        return "零件名称"
    return cleaned


def cleanup_feature_text(text: str) -> str:
    cleaned = (text or "").strip().replace("\ufeff", "")
    cleaned = re.sub(r"^\[Pasted", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\n[=\-]{10,}\n", "\n", cleaned)
    cleaned = re.sub(r"^[=\-]{10,}\n", "", cleaned)
    return cleaned.strip()


def extract_feature_pairs(text: str):
    cleaned = cleanup_feature_text(text)
    if not cleaned or "【" not in cleaned:
        return []

    pairs = []
    token_pattern = re.compile(r"【([^】]+)】")
    matches = list(token_pattern.finditer(cleaned))
    if not matches:
        return []

    leading_text = cleaned[: matches[0].start()].strip(" ：:\n\r\t-—[]")
    if leading_text:
        pairs.append(("图号", leading_text))

    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(cleaned)
        label = normalize_feature_label((match.group(1) or "").strip())
        value = cleaned[start:end].strip()
        if label:
            pairs.append((label, value))

    return pairs


def build_feature_report(descriptions: Iterable[Dict], prefix_hint: str | None = None, total_pages: int | None = None) -> Dict:
    pages = list(descriptions or [])
    page_count = len(pages) if total_pages is None else max(int(total_pages or 0), 0)
    merged_fields: Dict[str, List[str]] = {}
    page_summaries = []
    page_reports = []

    for index, item in enumerate(pages, start=1):
        raw_text = (
            item.get("description")
            or item.get("text")
            or "\n\n".join(item.get("rows") or [])
            or ""
        ).strip()
        pairs = extract_feature_pairs(raw_text)
        page_number = int(item.get("_page_number") or index)
        image_path = item.get("image_path") or item.get("source_path") or ""
        if not image_path:
            png_paths = item.get("png_paths") or []
            if isinstance(png_paths, list) and png_paths:
                image_path = png_paths[0]

        page_feature_map = {}
        for label, value in pairs:
            if value and value not in page_feature_map.get(label, []):
                page_feature_map.setdefault(label, []).append(value)
            merged_fields.setdefault(label, [])
            if value and value not in merged_fields[label]:
                merged_fields[label].append(value)

        if pairs:
            summary_values = [f"{label}：{value or '未识别'}" for label, value in pairs[:6]]
            summary_text = "；".join(summary_values) if summary_values else raw_text.replace("\n", "；")
        else:
            summary_text = raw_text.replace("\n", "；") if raw_text else "未识别"

        page_summaries.append({"page": page_number, "summary": summary_text})
        page_reports.append(
            {
                "page": page_number,
                "image_path": image_path,
                "description": raw_text,
                "features": page_feature_map,
                "summary": summary_text,
            }
        )

    merged_fields = _fix_thickness_by_depth_check(merged_fields)
    merged_fields = _fix_outer_by_key_dims_order(merged_fields)

    lines = [
        "【报告名称】多页特征提取报告",
        f"【页数】{page_count}",
        f"【图号】{';'.join(merged_fields.get('图号', [])) if merged_fields.get('图号') else ''}",
    ]

    for field in REPORT_FIELD_ORDER:
        values = merged_fields.get(field, [])
        lines.append(f"【{field}】{'；'.join(values) if values else '无'}")

    extra_fields = [
        field for field in merged_fields.keys()
        if field not in REPORT_FIELD_ORDER and not field.startswith("_")
    ]
    for field in extra_fields:
        values = merged_fields.get(field, [])
        lines.append(f"【{field}】{'；'.join(values) if values else '无'}")

    for item in page_summaries:
        lines.append(f"【第{item['page']}页摘要】{item['summary'] or '未识别'}")

    report_text = "\n".join(lines).strip()
    return {
        "report_name": "多页特征提取报告",
        "prefix_hint": prefix_hint or "",
        "page_count": page_count,
        "pages": page_reports,
        "merged_fields": merged_fields,
        "report_text": report_text,
    }


def write_feature_report_json(output_dir: str, payload: Dict, filename: str = "feature_report.json") -> str:
    os.makedirs(output_dir, exist_ok=True)
    file_path = os.path.join(output_dir, filename)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return file_path
