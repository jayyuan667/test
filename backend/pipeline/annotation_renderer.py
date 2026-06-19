# -*- coding: utf-8 -*-
"""Render annotations/*.json into a Chinese structured text block for the VLM prompt.

Output is concatenated to the visual-analysis prompt as a "known features" prefix,
not used for text-extraction prompt (text extraction does not need bbox info).
"""

import json
import os
from collections import defaultdict
from typing import Dict, List, Tuple

LABEL_TO_ZH = {
    "chamfer":       "倒角",
    "threaded_hole": "螺纹孔",
    "circle_hole":   "圆孔",
}

# RGB colors matching the frontend SVG palette
LABEL_TO_RGB: Dict[str, Tuple[int, int, int]] = {
    "chamfer":       (245, 158, 11),   # #f59e0b orange
    "threaded_hole": (99,  102, 241),  # #6366f1 indigo
    "circle_hole":   (16,  185, 129),  # #10b981 green
}
LABEL_DASHED = {"threaded_hole"}      # threaded_hole rendered as dashed stroke


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


def _draw_dashed_rect(draw, xy, color, width, dash_len=12, gap_len=6):
    """Draw a dashed rectangle by stitching short line segments."""
    x1, y1, x2, y2 = xy

    def _dashed_line(p1, p2):
        from math import hypot
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        length = hypot(dx, dy)
        if length == 0:
            return
        ux, uy = dx / length, dy / length
        seg = 0.0
        while seg < length:
            sx, sy = p1[0] + ux * seg, p1[1] + uy * seg
            seg2 = min(seg + dash_len, length)
            ex, ey = p1[0] + ux * seg2, p1[1] + uy * seg2
            draw.line([(sx, sy), (ex, ey)], fill=color, width=width)
            seg = seg2 + gap_len

    _dashed_line((x1, y1), (x2, y1))
    _dashed_line((x2, y1), (x2, y2))
    _dashed_line((x2, y2), (x1, y2))
    _dashed_line((x1, y2), (x1, y1))


def draw_boxes_on_image(image_path: str, shapes: List[dict], out_path: str,
                        stroke_width: int = 4) -> None:
    """Render bounding boxes onto a copy of the image (annotated PNG).

    - Solid border for chamfer / circle_hole, dashed for threaded_hole
    - Semi-transparent fill (RGBA composite)
    - No text labels drawn (occlusion-free — VLM and viewer rely on color)
    """
    from PIL import Image, ImageDraw
    with Image.open(image_path) as src:
        base = src.convert("RGBA")

    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    for s in shapes:
        label = s.get("label", "")
        pts   = s.get("points") or []
        if len(pts) != 2:
            continue
        (x1, y1), (x2, y2) = pts
        x1, y1, x2, y2 = int(min(x1, x2)), int(min(y1, y2)), int(max(x1, x2)), int(max(y1, y2))
        rgb = LABEL_TO_RGB.get(label, (156, 163, 175))  # default gray
        fill = (*rgb, 34)    # ~0x22 alpha — soft tint
        edge = (*rgb, 255)

        # tinted fill
        draw.rectangle([x1, y1, x2, y2], fill=fill)
        # stroke
        if label in LABEL_DASHED:
            _draw_dashed_rect(draw, (x1, y1, x2, y2), edge, stroke_width)
        else:
            draw.rectangle([x1, y1, x2, y2], outline=edge, width=stroke_width)

    composed = Image.alpha_composite(base, overlay).convert("RGB")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    composed.save(out_path, "PNG")


def render_annotated_images(ann_dir: str, png_paths: List[str], out_dir: str) -> List[str]:
    """For each PNG, find its labelme JSON in ann_dir and write an annotated copy.

    Returns the list of annotated output paths in the same order as png_paths.
    Pages with no JSON (or empty shapes) still get written (a clean copy of the original).
    """
    os.makedirs(out_dir, exist_ok=True)
    # Index ann_dir by stem prefix so we don't repeatedly listdir
    ann_files = {f for f in os.listdir(ann_dir) if f.endswith(".json")} if os.path.isdir(ann_dir) else set()

    annotated_paths: List[str] = []
    for i, p in enumerate(png_paths, 1):
        stem = os.path.splitext(os.path.basename(p))[0]
        candidate = f"{stem}_page_{i}.json"
        shapes: List[dict] = []
        if candidate in ann_files:
            try:
                with open(os.path.join(ann_dir, candidate), encoding="utf-8") as f:
                    shapes = (json.load(f).get("shapes") or [])
            except (OSError, json.JSONDecodeError):
                shapes = []
        out_path = os.path.join(out_dir, f"{stem}_annotated.png")
        try:
            draw_boxes_on_image(p, shapes, out_path)
            annotated_paths.append(out_path)
        except Exception:
            # On any failure, fall back to the original PNG path
            annotated_paths.append(p)
    return annotated_paths
