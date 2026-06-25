# -*- coding: utf-8 -*-
"""Export endpoint for downloading task results as Excel or PDF."""

import json
import os
from io import BytesIO
from typing import List, Dict, Any, Tuple

from flask import Blueprint, jsonify, request, send_file

from ..config import OUTPUT_FOLDER
from ..auth_utils import login_required
from ._utils import assert_task_access

export_bp = Blueprint("export", __name__)

tasks = {}

PDF_PAGE_SIZE = (1654, 2339)  # A4 @ ~150 DPI
PDF_MARGIN = 72
PDF_HEADER_GAP = 18
PDF_TABLE_ROW_GAP = 12
PDF_FIRST_IMAGE_MAX_H = 720
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simsun.ttc",
]


def set_tasks(tasks_dict):
    """Inject tasks dictionary from app.py."""
    global tasks
    tasks = tasks_dict


def _load_result_data(task_id: str) -> Dict[str, Any] | None:
    if task_id in tasks:
        task = tasks[task_id]
        result = task.get("result")
        if result:
            return result

    result_file = os.path.join(OUTPUT_FOLDER, task_id, "result.json")
    if os.path.exists(result_file):
        with open(result_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _task_image_path(task_id: str) -> str:
    """Return the preview image path for a task, matching the preview modal logic."""
    output_dir = os.path.join(OUTPUT_FOLDER, task_id)
    if not os.path.isdir(output_dir):
        return ""
    creo_default = os.path.join(output_dir, "creo_views", "全部默认.jpg")
    if os.path.exists(creo_default):
        return creo_default
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        files = sorted(
            [n for n in os.listdir(output_dir) if n.lower().endswith(ext)]
        )
        if files:
            return os.path.join(output_dir, files[0])
    pages_dir = os.path.join(output_dir, "pages")
    if os.path.isdir(pages_dir):
        for ext in (".png", ".jpg", ".jpeg", ".webp"):
            files = sorted(
                [n for n in os.listdir(pages_dir) if n.lower().endswith(ext)]
            )
            if files:
                return os.path.join(pages_dir, files[0])
    creo_dir = os.path.join(output_dir, "creo_views")
    if os.path.isdir(creo_dir):
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            files = sorted(
                [n for n in os.listdir(creo_dir) if n.lower().endswith(ext)]
            )
            if files:
                return os.path.join(creo_dir, files[0])
    return ""


INFO_KEEP_FIELDS = ["零件名称", "形态", "类型", "技术要求"]


def _filter_info_fields(text: str) -> str:
    """Keep only the wanted 【field】 sections from feature_report_text."""
    import re

    sections = re.split(r"(?=【)", text.strip())
    kept = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        for field in INFO_KEEP_FIELDS:
            if section.startswith(f"【{field}】"):
                kept.append(section)
                break
    return "\n".join(kept)


def parse_process_table(raw_text: str) -> List[List[str]]:
    rows = []
    for line in raw_text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("=") or "---" in line or ":---" in line:
            continue
        cells = [c.strip() for c in line.split("|")]
        cells = [c for c in cells if c]
        if len(cells) >= 2:
            rows.append(cells)

    header_keywords = ["label", "fen", "process", "workcenter", "time", "status"]
    if rows:
        first_row = rows[0]
        if any(kw in "".join(first_row).lower() for kw in header_keywords):
            return rows[1:] if len(rows) > 1 else []
    return rows


def _normalize_rows(result_data: Dict[str, Any]) -> List[List[str]]:
    process_flow = result_data.get("process_flow", {})
    if isinstance(process_flow, str):
        data = parse_process_table(process_flow)
    else:
        data = process_flow.get("data", []) or []

    normalized = []
    for row in data:
        if isinstance(row, (list, tuple)):
            code = str(row[0]).strip() if len(row) > 0 else ""
            if len(row) >= 3:
                trade = str(row[1]).strip()
                content = str(row[2]).strip()
            elif len(row) == 2:
                trade = ""
                content = str(row[1]).strip()
            else:
                trade = ""
                content = ""
            normalized.append([code, trade, content])
            continue
        if isinstance(row, dict):
            normalized.append([
                str(row.get("processNo") or row.get("stepNo") or row.get("code") or "").strip(),
                str(row.get("trade") or row.get("tradeType") or row.get("workCenter") or "").strip(),
                str(row.get("stepContent") or row.get("content") or row.get("description") or "").strip(),
            ])
            continue
        normalized.append(["", "", str(row or "").strip()])
    return normalized


def _excel_response(task_id: str, result_data: Dict[str, Any]):
    columns = ["标签编码", "工种", "工序内容"]
    process_flow = result_data.get("process_flow", {})

    if isinstance(process_flow, dict) and process_flow.get("tables"):
        tables = process_flow.get("tables", {})
        if not tables:
            return jsonify({"error": "No data"}), 404
        try:
            import pandas as pd

            output = BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                for table_name, data in tables.items():
                    if not data:
                        continue
                    normalized_data = []
                    for row in data:
                        normalized_row = list(row) + [""] * (len(columns) - len(row))
                        normalized_data.append(normalized_row[: len(columns)])
                    df = pd.DataFrame(normalized_data, columns=columns)
                    df.to_excel(writer, sheet_name=table_name[:31] or "Process", index=False)
            output.seek(0)
            return send_file(
                output,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                as_attachment=True,
                download_name=f"Process_{task_id[:8]}.xlsx",
            )
        except Exception as e:
            return jsonify({"error": f"Export failed: {str(e)}"}), 500

    data = _normalize_rows(result_data)
    if not data:
        return jsonify({"error": "No data"}), 404

    try:
        import pandas as pd

        output = BytesIO()
        df = pd.DataFrame(data, columns=columns)
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Process", index=False)
        output.seek(0)
        return send_file(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=f"Process_{task_id[:8]}.xlsx",
        )
    except Exception as e:
        return jsonify({"error": f"Export failed: {str(e)}"}), 500


def _load_font(size: int):
    from PIL import ImageFont

    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def _text_width(draw, text: str, font) -> int:
    bbox = draw.textbbox((0, 0), text or "", font=font)
    return max(0, bbox[2] - bbox[0])


def _wrap_text(draw, text: str, font, max_width: int) -> List[str]:
    raw = str(text or "").replace("\r", "")
    wrapped = []
    for paragraph in raw.split("\n"):
        current = paragraph.strip() or ""
        if not current:
            wrapped.append("")
            continue
        line = ""
        for ch in current:
            candidate = f"{line}{ch}"
            if line and _text_width(draw, candidate, font) > max_width:
                wrapped.append(line)
                line = ch
            else:
                line = candidate
        if line:
            wrapped.append(line)
    return wrapped or [""]


def _line_height(font) -> int:
    try:
        ascent, descent = font.getmetrics()
        return ascent + descent + 6
    except Exception:
        return font.size + 8


def _draw_multiline(draw, xy: Tuple[int, int], lines: List[str], font, fill) -> int:
    x, y = xy
    step = _line_height(font)
    for index, line in enumerate(lines):
        draw.text((x, y + index * step), line, font=font, fill=fill)
    return len(lines) * step


def _render_pdf_pages(task_id: str, result_data: Dict[str, Any]) -> List[Any]:
    from PIL import Image, ImageDraw

    title_font = _load_font(38)
    meta_font = _load_font(24)
    header_font = _load_font(22)
    body_font = _load_font(20)
    small_font = _load_font(18)

    rows = _normalize_rows(result_data)
    if not rows:
        raise ValueError("No data")

    page_w, page_h = PDF_PAGE_SIZE
    margin = PDF_MARGIN
    cw = page_w - margin * 2  # content width
    lh = _line_height(body_font)

    page = Image.new("RGB", (page_w, page_h), "white")
    draw = ImageDraw.Draw(page)
    pages = [page]
    y = margin

    # ── Title + meta ──
    draw.text((margin, y), "工艺工程卡", font=title_font, fill="#172334")
    y += _line_height(title_font) + 8
    pdf_name = result_data.get("pdf_name") or task_id
    draw.text((margin, y), f"任务ID：{task_id}    文件名称：{pdf_name}", font=meta_font, fill="#4d6580")
    y += _line_height(meta_font) + 24

    # ── Two-column: image + info ──
    image_path = _task_image_path(task_id)
    has_image = image_path and os.path.exists(image_path)
    feature_text = result_data.get("feature_report_text") or result_data.get("expert_judgment") or ""
    if feature_text and result_data.get("feature_report_text"):
        feature_text = _filter_info_fields(feature_text)

    if has_image or feature_text:
        col_gap = 20
        card_pad = 16
        has_both = has_image and bool(feature_text)

        if has_both:
            left_w = int(cw * 0.46)
            right_w = cw - left_w - col_gap
        elif has_image:
            left_w = cw
            right_w = 0
        else:
            left_w = 0
            right_w = cw

        # Measure feature text height to balance columns
        feature_lines = []
        if feature_text:
            text_wrap_w = right_w - card_pad * 2
            feature_lines = _wrap_text(draw, feature_text, body_font, text_wrap_w)

        info_inner_h = 0
        if feature_lines:
            for line in feature_lines:
                info_inner_h += _line_height(header_font) if line.startswith("## ") else lh
            info_inner_h += _line_height(header_font)  # "图纸信息" title
        info_card_h = max(200, info_inner_h + card_pad * 2 + 12) if feature_text else 0

        # Size image to match card height
        img_draw_h = 0
        img_to_paste = None
        if has_image:
            with Image.open(image_path) as raw:
                raw = raw.convert("RGB")
                avail_w = (left_w - card_pad * 2) if has_both else (left_w - card_pad * 2)
                avail_h = max(info_card_h, 200) - card_pad * 2
                ratio = min(avail_w / raw.width, avail_h / raw.height, 1.0)
                img_draw_w = max(1, int(raw.width * ratio))
                img_draw_h = max(1, int(raw.height * ratio))
                img_to_paste = raw.resize((img_draw_w, img_draw_h))
            image_card_h = max(200, img_draw_h + card_pad * 2)
        else:
            image_card_h = 0

        card_h = max(image_card_h, info_card_h)

        if card_h + y + margin > page_h:
            page = Image.new("RGB", (page_w, page_h), "white")
            draw = ImageDraw.Draw(page)
            pages.append(page)
            y = margin

        # Left card – image
        if has_image and img_to_paste:
            draw.rounded_rectangle(
                (margin, y, margin + left_w, y + card_h),
                radius=14, fill="#f7fbff", outline="#d7e1eb", width=1,
            )
            px = margin + (left_w - img_draw_w) // 2
            py = y + (card_h - img_draw_h) // 2
            page.paste(img_to_paste, (px, py))

        # Right card – info
        if feature_text:
            rx = margin + left_w + col_gap if has_image else margin
            rw = right_w if has_image else cw
            draw.rounded_rectangle(
                (rx, y, rx + rw, y + card_h),
                radius=14, fill="#ffffff", outline="#e0e8f0", width=1,
            )
            iy = y + card_pad
            draw.text((rx + card_pad, iy), "图纸信息", font=header_font, fill="#172334")
            iy += _line_height(header_font) + 6
            for line in feature_lines:
                if iy + lh > y + card_h - card_pad:
                    break
                if line.startswith("## "):
                    draw.text((rx + card_pad, iy), line[3:], font=header_font, fill="#172334")
                elif line.startswith("- "):
                    draw.text((rx + card_pad + 16, iy), line, font=body_font, fill="#20354f")
                else:
                    draw.text((rx + card_pad, iy), line, font=body_font, fill="#4d6580")
                iy += lh

        y += card_h + 20

    # ── Process table ──
    code_col_w = 100
    trade_col_w = 80
    divider1_x = margin + code_col_w
    divider2_x = divider1_x + trade_col_w
    content_x = divider2_x
    content_w = page_w - margin - content_x - 36
    border_color = "#d8e2ec"

    # Section header "工艺规程"
    draw.text((margin, y), "工艺规程", font=header_font, fill="#172334")
    y += _line_height(header_font) + 10

    def _draw_table_header(draw_obj, y_pos):
        draw_obj.rounded_rectangle(
            (margin, y_pos, page_w - margin, y_pos + 50),
            radius=12,
            fill="#eef5fc",
            outline="#d6e1ee",
            width=2,
        )
        draw_obj.text((margin + 28, y_pos + 12), "工序号", font=header_font, fill="#35506b")
        trade_hdr_w = _text_width(draw_obj, "工种", header_font)
        draw_obj.text((divider1_x + (trade_col_w - trade_hdr_w) // 2, y_pos + 12), "工种", font=header_font, fill="#35506b")
        draw_obj.text((divider2_x + 24, y_pos + 12), "工序名称及内容", font=header_font, fill="#35506b")

    _draw_table_header(draw, y)
    y += 50

    for code, trade, content in rows:
        content_lines = _wrap_text(draw, content, body_font, content_w)
        content_text_h = len(content_lines) * lh
        row_h = max(56, content_text_h + 24)

        if y + row_h + margin > page_h:
            page = Image.new("RGB", (page_w, page_h), "white")
            draw = ImageDraw.Draw(page)
            pages.append(page)
            y = margin
            _draw_table_header(draw, y)
            y += 50

        draw.rectangle((margin, y, page_w - margin, y + row_h), outline=border_color, width=1)
        draw.line((divider1_x, y, divider1_x, y + row_h), fill=border_color, width=1)
        draw.line((divider2_x, y, divider2_x, y + row_h), fill=border_color, width=1)

        code_y = y + (row_h - _line_height(header_font)) // 2
        draw.text((margin + 28, code_y), code or "----", font=header_font, fill="#ff6528")

        trade_w = _text_width(draw, trade or "", header_font)
        trade_x = divider1_x + (trade_col_w - trade_w) // 2
        trade_y = y + (row_h - _line_height(header_font)) // 2
        draw.text((max(divider1_x + 4, trade_x), trade_y), trade or "", font=header_font, fill="#35506b")

        content_y = y + (row_h - content_text_h) // 2
        _draw_multiline(draw, (content_x + 24, content_y), content_lines, body_font, "#20354f")

        y += row_h + PDF_TABLE_ROW_GAP

    # ── Footer ──
    page = pages[-1]
    draw = ImageDraw.Draw(page)
    footer = f"导出时间：{result_data.get('completed_at') or ''}"
    draw.text((margin, page_h - margin + 8), footer, font=small_font, fill="#6b7f93")
    return pages


def _pdf_response(task_id: str, result_data: Dict[str, Any]):
    try:
        pages = _render_pdf_pages(task_id, result_data)
        if not pages:
            return jsonify({"error": "No data"}), 404
        output = BytesIO()
        first, rest = pages[0], pages[1:]
        first.save(output, format="PDF", save_all=True, append_images=rest, resolution=150.0)
        output.seek(0)
        return send_file(
            output,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"Process_{task_id[:8]}.pdf",
        )
    except Exception as e:
        return jsonify({"error": f"Export failed: {str(e)}"}), 500


@export_bp.route("/export/<task_id>", methods=["GET", "POST"])
@login_required
def export_result(task_id):
    ok, err = assert_task_access(task_id)
    if not ok:
        return err

    try:
        result_data = _load_result_data(task_id)
    except Exception as e:
        return jsonify({"error": f"Failed to read result: {str(e)}"}), 500

    if not result_data:
        return jsonify({"error": "Task not found"}), 404

    # POST body may carry user-edited rows — override process_flow with them
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        rows = body.get("rows")
        if rows and isinstance(rows, list):
            result_data = dict(result_data)
            result_data["process_flow"] = {"data": rows}

    export_format = (request.args.get("format") or "xlsx").strip().lower()
    if export_format == "pdf":
        return _pdf_response(task_id, result_data)
    if export_format == "xlsx":
        return _excel_response(task_id, result_data)
    return jsonify({"error": f"Unsupported format: {export_format}"}), 400
