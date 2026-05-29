# -*- coding: utf-8 -*-
"""Helpers for building and persisting feature-extraction reports."""

import json
import os
import re
from typing import Dict, Iterable, List


REPORT_FIELD_ORDER = [
    "图号",
    "零件名称",
    "形态",
    "类型",
    "技术要求",
    "关键尺寸",
    "外圆与内孔",
    "螺纹与螺孔",
    "倒角",
    "热处理与探伤",
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
    "线切": "线切割",
    "线割": "线切割",
    "精度": "精度与检测特征",
    "检测": "精度与检测特征",
    "表面处理": "表面处理与镀层特征",
    "镀层": "表面处理与镀层特征",
    "过渡": "过渡特征",
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

    lines = [
        "【报告名称】多页特征提取报告",
        f"【页数】{page_count}",
        f"【图号】{';'.join(merged_fields.get('图号', [])) if merged_fields.get('图号') else ''}",
    ]

    for field in REPORT_FIELD_ORDER:
        values = merged_fields.get(field, [])
        lines.append(f"【{field}】{'；'.join(values) if values else ''}")

    extra_fields = [field for field in merged_fields.keys() if field not in REPORT_FIELD_ORDER]
    for field in extra_fields:
        values = merged_fields.get(field, [])
        lines.append(f"【{field}】{'；'.join(values) if values else ''}")

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
