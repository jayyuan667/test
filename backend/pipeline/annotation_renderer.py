# -*- coding: utf-8 -*-
"""Render annotations/*.json into a Chinese structured text block for the VLM prompt.

Output is concatenated to the visual-analysis prompt as a "known features" prefix,
not used for text-extraction prompt (text extraction does not need bbox info).
"""

import json
import os
from collections import defaultdict
from typing import Dict, List

LABEL_TO_ZH = {
    "chamfer":       "倒角",
    "threaded_hole": "螺纹孔",
    "circle_hole":   "圆孔",
}


def _page_block(page_num: int, shapes: List[dict]) -> str:
    if not shapes:
        return f"=== 第 {page_num} 页 ===\n[此页无已知特征位置]\n"

    groups: Dict[str, List] = defaultdict(list)
    for s in shapes:
        label = s.get("label", "")
        pts = s.get("points") or []
        if label and len(pts) == 2:
            groups[label].append(pts)

    lines = [
        f"=== 第 {page_num} 页 ===",
        "[已人工核对的特征位置]",
    ]
    for label, boxes in groups.items():
        zh = LABEL_TO_ZH.get(label, label)
        lines.append(f"- {zh} ({label})：{len(boxes)} 处")
        for i, ((x1, y1), (x2, y2)) in enumerate(boxes, 1):
            lines.append(f"  · 框 {i}: 左上 ({int(x1)}, {int(y1)}) 右下 ({int(x2)}, {int(y2)})")
    return "\n".join(lines) + "\n"


def render_annotation_text(ann_dir: str) -> str:
    """Read all `*_page_N.json` files in ann_dir and produce a single Chinese text block.

    Returns empty string if directory is missing or contains no JSONs.
    """
    if not os.path.isdir(ann_dir):
        return ""

    pages: Dict[int, List[dict]] = {}
    for fname in sorted(os.listdir(ann_dir)):
        if not fname.endswith(".json"):
            continue
        parts = fname.rsplit("_page_", 1)
        try:
            page_n = int(parts[1].replace(".json", "")) if len(parts) == 2 else 1
        except ValueError:
            page_n = 1
        fpath = os.path.join(ann_dir, fname)
        try:
            with open(fpath, encoding="utf-8") as f:
                data = json.load(f)
            pages[page_n] = data.get("shapes", []) or []
        except (OSError, json.JSONDecodeError):
            continue

    if not pages:
        return ""

    blocks = [_page_block(n, pages[n]) for n in sorted(pages)]
    return (
        "\n".join(blocks)
        + "\n请基于上述特征位置（图纸像素坐标），结合图纸本身进行精确分析。\n"
    )
