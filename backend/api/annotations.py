# -*- coding: utf-8 -*-
"""Annotation API — save/load/export per-task bounding box annotations."""

import io
import json
import os
import threading
import zipfile

from flask import Blueprint, jsonify, request, send_file

try:
    from ..config import OUTPUT_FOLDER
except ImportError:
    from backend.config import OUTPUT_FOLDER

annotations_bp = Blueprint("annotations", __name__)

# Class ID mapping matches augmented_v2/data.yaml order
LABEL_TO_ID = {"threaded_hole": 0, "circle_hole": 1, "chamfer": 2}


def _ann_dir(task_id: str) -> str:
    return os.path.join(OUTPUT_FOLDER, task_id, "annotations")


@annotations_bp.route("/annotations/<task_id>", methods=["GET"])
def get_annotations(task_id):
    """Return all saved annotation JSON files for a task, keyed by page number."""
    ann_dir = _ann_dir(task_id)
    if not os.path.isdir(ann_dir):
        return jsonify({"task_id": task_id, "pages": {}})

    pages = {}
    for fname in sorted(os.listdir(ann_dir)):
        if not fname.endswith(".json"):
            continue
        parts = fname.rsplit("_page_", 1)
        page_n = parts[1].replace(".json", "") if len(parts) == 2 else "1"
        fpath = os.path.join(ann_dir, fname)
        with open(fpath, encoding="utf-8") as fh:
            try:
                pages[page_n] = json.load(fh)
            except json.JSONDecodeError:
                pass

    return jsonify({"task_id": task_id, "pages": pages})


@annotations_bp.route("/annotations/<task_id>/save", methods=["POST"])
def save_annotations(task_id):
    """Save annotations for one page as labelme JSON + YOLO TXT.

    Body: {page, shapes, imageWidth, imageHeight, imagePath}
    """
    data = request.get_json(force=True)
    shapes = data.get("shapes", [])
    img_w = int(data.get("imageWidth", 0))
    img_h = int(data.get("imageHeight", 0))
    img_path = data.get("imagePath", f"page_{data.get('page', 1)}.png")

    stem = os.path.splitext(img_path)[0]

    ann_dir = _ann_dir(task_id)
    os.makedirs(ann_dir, exist_ok=True)

    # ── labelme JSON ──────────────────────────────────────────────────────────
    labelme = {
        "version": "0.4.36",
        "flags": {},
        "shapes": [
            {
                "label": s["label"],
                "text": "",
                "points": s["points"],
                "group_id": None,
                "shape_type": "rectangle",
                "flags": {},
            }
            for s in shapes
        ],
        "imagePath": img_path,
        "imageData": None,
        "imageHeight": img_h,
        "imageWidth": img_w,
        "text": "",
    }
    json_path = os.path.join(ann_dir, f"{stem}.json")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(labelme, fh, ensure_ascii=False, indent=2)

    # ── YOLO TXT ──────────────────────────────────────────────────────────────
    txt_lines = []
    if img_w > 0 and img_h > 0:
        for s in shapes:
            (x1, y1), (x2, y2) = s["points"]
            cx = (x1 + x2) / 2 / img_w
            cy = (y1 + y2) / 2 / img_h
            bw = abs(x2 - x1) / img_w
            bh = abs(y2 - y1) / img_h
            # Clamp to [0, 1]
            cx = max(0.0, min(1.0, cx))
            cy = max(0.0, min(1.0, cy))
            bw = max(0.0, min(1.0, bw))
            bh = max(0.0, min(1.0, bh))
            cls_id = LABEL_TO_ID.get(s["label"], len(LABEL_TO_ID))
            txt_lines.append(f"{cls_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")

    txt_path = os.path.join(ann_dir, f"{stem}.txt")
    with open(txt_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(txt_lines))

    return jsonify({"ok": True, "json_path": json_path, "txt_path": txt_path})


@annotations_bp.route("/annotations/<task_id>/export", methods=["GET"])
def export_annotations(task_id):
    """Return annotation files + source images for a task as a ZIP download."""
    ann_dir  = _ann_dir(task_id)
    task_dir = os.path.join(OUTPUT_FOLDER, task_id)
    buf = io.BytesIO()

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # annotation JSON + TXT
        if os.path.isdir(ann_dir):
            for fname in sorted(os.listdir(ann_dir)):
                fpath = os.path.join(ann_dir, fname)
                if os.path.isfile(fpath):
                    zf.write(fpath, fname)

        # source PNG/JPG images (walk task dir, exclude annotations sub-dir)
        if os.path.isdir(task_dir):
            for dirpath, _dirs, fnames in os.walk(task_dir):
                # skip the annotations folder itself
                rel_dir = os.path.relpath(dirpath, task_dir)
                if rel_dir.startswith("annotations"):
                    continue
                for fname in sorted(fnames):
                    if not fname.lower().endswith((".png", ".jpg", ".jpeg")):
                        continue
                    fpath = os.path.join(dirpath, fname)
                    parts = [] if rel_dir == "." else [rel_dir]
                    arc_name = "/".join(["images"] + parts + [fname])
                    zf.write(fpath, arc_name)

    buf.seek(0)
    return send_file(
        buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"annotations_{task_id}.zip",
    )


@annotations_bp.route("/annotations/<task_id>/finalize", methods=["POST"])
def finalize_annotations(task_id):
    """User confirmed manual annotation; resume the pipeline.

    Two cases:
    - In-flight task: a background thread is blocked on annotation_event.wait();
      we just set the event and the thread continues.
    - Restored task (page refresh / server restart): no live thread. Spawn one
      that runs _resume_from_annotation() — mirrors how /api/review handles
      restored_from_pending tasks.
    """
    # 延迟导入避免循环依赖
    from .upload import tasks, _resume_from_annotation

    task = tasks.get(task_id)
    if not task:
        return jsonify({"ok": False, "error": "task not found"}), 404
    if task.get("status") != "awaiting_annotation":
        return jsonify({
            "ok": False,
            "error": f"task in status {task.get('status')}, not awaiting_annotation",
        }), 409

    # Distinguish in-flight (thread is alive on annotation_event.wait()) from
    # restored (thread is gone — page refresh / server restart). Use the
    # `restored_from_pending` marker set by restore_task_from_pending().
    if task.get("restored_from_pending"):
        threading.Thread(
            target=_resume_from_annotation,
            args=(task_id,),
            daemon=True,
        ).start()
        return jsonify({"ok": True, "task_id": task_id, "mode": "resumed"})

    ann_event = task.get("annotation_event")
    if ann_event:
        ann_event.set()
        return jsonify({"ok": True, "task_id": task_id, "mode": "inflight"})

    # Unexpected: no event, no marker — fall back to resume
    threading.Thread(
        target=_resume_from_annotation,
        args=(task_id,),
        daemon=True,
    ).start()
    return jsonify({"ok": True, "task_id": task_id, "mode": "resumed"})
