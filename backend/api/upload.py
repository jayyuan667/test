# -*- coding: utf-8 -*-
"""Upload endpoint for single PRT files."""

import os
import re
import uuid
import json
import time
import hashlib
import threading
import logging
import traceback
from datetime import datetime
from pathlib import Path

import cv2
from flask import Blueprint, request, jsonify
from PIL import Image

from ..config import UPLOAD_FOLDER, OUTPUT_FOLDER, validate_vision_config
from ..feature_report import build_feature_report, write_feature_report_json, cleanup_feature_text
from ..history import add_history_entry
from ..prt_pipeline import prepare_prt_artifacts, export_gltf
from ..pipeline.vlm_feature import build_vlm_feature_text
from ..pipeline.geometry_analyzer import analyze_step_geometry
from ..pipeline.expert_judge import ExpertJudge
from ..pipeline.process_gen import ProcessGenerator
from ..pipeline.pdf_converter import convert_pdf_to_images
from ..services.event_emitter import (
    emit_step_start,
    emit_step_complete,
    emit_complete,
    emit_error,
    emit_image_ready,
    emit_log,
    emit_custom,
)
from ..services.upload_pipeline import process_prt_pipeline
from ..services.review_session import (
    persist_review_payload,
    clear_pending_review,
    restore_task_from_pending,
    restore_task_from_result,
)
from ..vision_utils import split_vision_results, format_vision_failure_message
from ..task_store import insert_task, update_task_status, save_result, get_prt_cache, save_prt_cache
from ._response import fail, ERR_FILE_MISSING, ERR_FILE_TYPE, ERR_CONFIG, ERR_CAPABILITY
from ..auth_utils import login_required, require_quota
from ..services.capabilities import inspect_pdf_capability
from ._utils import PRT_FILE_RE, extract_prefix_from_filename, get_enterprise_scope, assert_task_access
from ..services.observability import time_block
from ..library_scope import PUBLIC_LIBRARY_KEY

upload_bp = Blueprint("upload", __name__)
logger = logging.getLogger(__name__)

# Shared state (will be injected from app.py)
tasks = {}
event_data = {}
event_locks = {}


def set_shared_state(tasks_dict, event_data_dict, event_locks_dict):
    """Inject shared state from app.py."""
    global tasks, event_data, event_locks
    tasks = tasks_dict
    event_data = event_data_dict
    event_locks = event_locks_dict


_extract_prefix_from_filename = extract_prefix_from_filename


def _request_retrieval_library_key() -> str:
    """Resolve the RAG retrieval library key from new and legacy request fields."""
    return (
        request.form.get("retrieval_library_key")
        or request.args.get("retrieval_library_key")
        or request.form.get("library_key")
        or request.args.get("library_key")
        or PUBLIC_LIBRARY_KEY
    )


DRAWING_FILE_RE = re.compile(r'\.(pdf|png|jpg|jpeg|dxf|dwg)$', re.IGNORECASE)


def _is_image_file(filename: str) -> bool:
    return filename.lower().endswith((".png", ".jpg", ".jpeg"))


def _is_drawing_file(filename: str) -> bool:
    return bool(DRAWING_FILE_RE.search(filename or ""))


def _get_vision_analyzer():
    vision_mode = os.getenv("VISION_MODE", "doubao").lower()
    if vision_mode == "local" or not all(
        os.getenv(n) for n in ("VISION_API_KEY", "VISION_API_BASE", "VISION_MODEL_ID")
    ):
        from ..pipeline.local_vision_analyzer import LocalVisionAnalyzer
        return LocalVisionAnalyzer()
    from ..pipeline.vision_analyzer import VisionAnalyzer
    return VisionAnalyzer()


def _save_image_as_png(source_path: str, output_path: str):
    """Normalize an uploaded image to PNG for preview/result consistency."""
    with Image.open(source_path) as img:
        rgb_img = img.convert("RGB") if img.mode not in ("RGB", "RGBA") else img
        rgb_img.save(output_path, format="PNG")


def _build_preview_urls(task_id: str, png_paths: list[str]):
    urls = []
    seen = set()
    task_dir = os.path.join(OUTPUT_FOLDER, task_id)
    for path in png_paths or []:
        if not path:
            continue
        rel = os.path.relpath(path, task_dir)
        if rel in seen:
            continue
        seen.add(rel)
        urls.append(f"/api/result/{task_id}/asset/{rel.replace(os.sep, '/')}")
    return urls


def _build_degraded_feature_text(
    annotation_text: str,
    failure_details: list[dict],
    prefix_hint: str = "",
) -> str:
    lines = [
        "【系统提示】视觉分析已降级，本次报告未使用远程视觉模型输出，请人工核对后继续。",
        f"【降级原因】{format_vision_failure_message(failure_details, prefix='视觉分析失败')}",
    ]
    if prefix_hint:
        lines.append(f"【图号提示】{prefix_hint}")

    annotated = (annotation_text or "").strip()
    if annotated:
        lines.append("【标注文本】")
        lines.append(annotated)
    else:
        lines.append("【标注文本】无可用标注文本，请结合预览图人工补全。")

    return cleanup_feature_text("\n".join(lines)).strip()


def _store_degraded_feature_report(task: dict, feature_text: str, failure_details: list[dict]) -> None:
    task["vision_degraded"] = True
    task["vision_failure_details"] = failure_details
    task["review_text"] = feature_text
    task["raw_review_text"] = feature_text
    task["feature_report_json"] = {
        "report_text": feature_text,
        "pages": [],
        "degraded": True,
        "failure_details": failure_details,
    }
    task["feature_report_text"] = feature_text



def _build_upload_mode_meta(file_count: int, page_count: int):
    file_count = max(int(file_count or 0), 0)
    page_count = max(int(page_count or 0), 0)

    if file_count <= 1:
        if page_count <= 1:
            mode = "single_pdf_single_page"
            label = "单个 PDF · 单页"
            can_paginate = False
        else:
            mode = "single_pdf_multi_page"
            label = "单个 PDF · 多页"
            can_paginate = True
    else:
        if page_count <= file_count:
            mode = "multi_pdf_single_page"
            label = f"{file_count} 个 PDF · 单页"
        else:
            mode = "multi_pdf_multi_page"
            label = f"{file_count} 个 PDF · 多页"
        can_paginate = True

    return {
        "upload_mode": mode,
        "upload_mode_label": label,
        "file_count": file_count,
        "page_count": page_count,
        "can_paginate": can_paginate,
    }


def _build_review_message(success_count: int, failure_count: int) -> str:
    if failure_count <= 0:
        return "请核对或修改综合特征报告后继续"
    return f"已有 {success_count} 页提取成功，另有 {failure_count} 页视觉分析失败，请补全后再继续。"


def _parse_process_markdown(raw_text: str):
    process_data = []
    normalized_text = (raw_text or "").replace("ENDD$$", " ")
    for line in normalized_text.strip().splitlines():
        current = line.strip()
        if not current:
            continue
        if current.startswith(("#", "|", "---", "===")):
            continue
        content = current[2:].strip() if current.startswith(("- ", "* ")) else current
        match = re.match(r"^(\d{4})\s*[@:：\-\|,，;；\s]*\s*(.+)$", content)
        if match:
            process_data.append([match.group(1), match.group(2).strip()])
    return process_data


def _finalize_processing(task_id, file_name, output_dir, reviewed_text, prefix_hint, source_descriptions=None, library_key=None, force_llm=False):
    logger.info("[_finalize_processing] START task_id=%s", task_id)
    task = tasks[task_id]
    if task.get("status") == "cancelled":
        return

    descriptions = source_descriptions or [{"description": reviewed_text}]
    task["status"] = "processing"
    update_task_status(task_id, "processing", task.get("progress", 0))

    emit_step_start(
        task_id,
        event_data,
        event_locks,
        3,
        "专家判断",
        "正在分析工艺特征",
    )
    emit_log(task_id, event_data, event_locks, 3, "开始专家判断分析...")

    judge = ExpertJudge()
    expert_judgment_obj = judge.analyze(descriptions)
    # 序列化为结构化文本供 ProcessGenerator 消费（Step B 完成后改用结构化对象）
    expert_judgment = ExpertJudge.to_str(expert_judgment_obj)
    emit_step_complete(task_id, event_data, event_locks, 3, "专家判断", "分析完成")
    emit_log(task_id, event_data, event_locks, 3,
             f"专家判断完成（置信度 {expert_judgment_obj.confidence:.2f}）")
    task["progress"] = 75
    task["expert_judgment"] = expert_judgment
    task["expert_judgment_structured"] = expert_judgment_obj.model_dump()

    emit_step_start(
        task_id,
        event_data,
        event_locks,
        4,
        "工艺生成",
        "正在生成工艺规程",
    )
    emit_log(task_id, event_data, event_locks, 4, "开始RAG检索...")

    def rag_log_callback(msg):
        emit_log(task_id, event_data, event_locks, 4, msg)

    # Rate-limit process_stream SSE events so the frontend typewriter can
    # keep up.  Without throttling the LLM sends dozens of deltas per
    # second and the browser receives them all in one burst, making the
    # "streaming" output appear instant instead of character-by-character.
    _stream_buf = ""
    _stream_last = 0.0
    _STREAM_INTERVAL = 0.04  # emit at most every 40 ms (~25 chunks/s)
    _stream_emit_count = 0

    def stream_callback(chunk):
        nonlocal _stream_buf, _stream_last, _stream_emit_count
        _stream_buf += chunk
        now = time.monotonic()
        if now - _stream_last >= _STREAM_INTERVAL:
            _stream_emit_count += 1
            logger.info("[StreamThrottle] emit #%d len=%d", _stream_emit_count, len(_stream_buf))
            emit_custom(task_id, event_data, event_locks,
                        "process_stream", {"chunk": _stream_buf})
            _stream_buf = ""
            _stream_last = now

    # Flush any remaining buffer after generate() returns

    # ── Geometry constraints for process generation ──
    # Fast path: use geo_data pre-computed during Step 1.
    # Fallback: compute now (covers /rerun and /review paths where Step 1 was skipped).
    geo_data = task.get("geo_data")
    if geo_data is None:
        _step_path = task.get("step_path", "")
        if _step_path and os.path.exists(_step_path):
            try:
                _geo = analyze_step_geometry(_step_path)
                if "error" not in _geo:
                    geo_data = _geo
            except Exception as _geo_err:
                emit_log(task_id, event_data, event_locks, 4, f"[几何约束] 跳过: {_geo_err}")

    generator = ProcessGenerator()
    with time_block("process_generation"):
        process_flow_raw, process_data, rag_results = generator.generate(
            descriptions,
            expert_judgment_obj,
            prefix_hint=prefix_hint,
            log_callback=rag_log_callback,
            stream_callback=stream_callback,
            library_key=library_key,
            geo_data=geo_data,
            force_llm=force_llm,
        )

    logger.info("[_finalize_processing] generate() done, stream_emit_count=%d, buf_len=%d", _stream_emit_count, len(_stream_buf))
    # Flush any remaining buffered stream chunks
    if _stream_buf:
        emit_custom(task_id, event_data, event_locks,
                    "process_stream", {"chunk": _stream_buf})

    emit_log(task_id, event_data, event_locks, 4, "工艺生成完成，正在保存...")
    task["progress"] = 100
    task["status"] = "completed"
    update_task_status(task_id, "completed", 100)
    task["process_flow"] = {
        "data": process_data,
        "raw": process_flow_raw,
        "columns": ["标签编码", "工序内容"],
        "format": "markdown",
    }
    task["rag_results"] = rag_results

    result = {
        "task_id": task_id,
        "pdf_name": file_name,
        "source_name": file_name,
        "file_count": 1,
        "total_pages": len(task.get("png_paths", []) or []),
        **_build_upload_mode_meta(1, len(task.get("png_paths", []) or [])),
        "png_count": len(task.get("png_paths", []) or []),
        "expert_judgment": expert_judgment,
        "process_flow": task["process_flow"],
        "process_flow_raw": process_flow_raw,
        "vision_descriptions": task.get("vision_descriptions", []),
        "vision_failures": task.get("vision_failures", []),
        "raw_review_text": task.get("raw_review_text", ""),
        "review_text": task.get("review_text", reviewed_text),
        "feature_report": task.get("feature_report_text", task.get("review_text", reviewed_text)),
        "feature_report_json": task.get("feature_report_json", {}),
        "feature_report_text": task.get("feature_report_text", task.get("review_text", reviewed_text)),
        "feature_report_path": task.get("feature_report_path", ""),
    }
    preview_image_urls = _build_preview_urls(task_id, task.get("png_paths", []) or [])
    gltf_path = task.get("gltf_path", "")
    if gltf_path and os.path.isfile(gltf_path):
        result["gltf_url"] = f"/api/result/{task_id}/asset/{os.path.basename(gltf_path)}"
    result["preview_image_urls"] = preview_image_urls
    result["preview_images"] = [os.path.basename(url) for url in preview_image_urls]
    result["image_url"] = preview_image_urls[0] if preview_image_urls else ""
    task["result"] = result
    save_result(task_id, result)

    result_file = os.path.join(output_dir, "result.json")
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    clear_pending_review(task_id, output_dir)

    emit_complete(task_id, event_data, event_locks, "处理完成！")
    _history_ent_id = task.get("enterprise_id")
    add_history_entry(
        task_id=task_id,
        pdf_name=file_name,
        progress=100,
        created_at=task.get("created_at", ""),
        enterprise_id=_history_ent_id,
    )


def _run_yolo_prelabel(task_id: str, png_paths: list, output_dir: str) -> dict:
    """Run YOLO via GPU service on each page, write labelme JSON, emit per-page SSE.

    When GPU service is unavailable, writes empty LabelMe JSONs so manual
    annotation fallback works without frontend changes.

    Returns aggregate detection counts {class_name: count}.
    """
    import logging
    from ..config import YOLO_SERVICE_URL, YOLO_SERVICE_TOKEN, YOLO_SERVICE_TIMEOUT
    from ..pipeline.yolo_service_client import YOLOServiceClient
    from ..pipeline.yolo_to_labelme import write_labelme
    from ..pipeline.yolo_labels import YOLO_CLASSES

    logger = logging.getLogger(__name__)
    ann_dir = os.path.join(output_dir, "annotations")
    summary: dict[str, int] = {}

    client = None
    if YOLO_SERVICE_URL:
        try:
            client = YOLOServiceClient(YOLO_SERVICE_URL, YOLO_SERVICE_TOKEN, YOLO_SERVICE_TIMEOUT)
            client.health()  # fast check
        except Exception as e:
            logger.warning("[%s] YOLO GPU 服务不可用: %s", task_id, e)
    else:
        logger.info("[%s] YOLO_SERVICE_URL 未配置，跳过 GPU 预标注", task_id)

    total = len(png_paths)
    for i, png_path in enumerate(png_paths, 1):
        dets: list[dict] = []

        if client is not None:
            try:
                result = client.detect(png_path)
                dets = result.get("detections", [])
                # GPU service returns key "class"; write_labelme expects "cls_name"
                for d in dets:
                    d["cls_name"] = d.pop("class")
            except Exception as e:
                logger.warning("[%s] 第 %d 页 YOLO 推理失败: %s", task_id, i, e)
                # Fall through — write empty LabelMe for this page
                dets = []

        # Per-class count dict (match old yolo_progress format)
        page_count = {cls: 0 for cls in YOLO_CLASSES}
        for d in dets:
            cls_name = d["cls_name"]
            if cls_name in page_count:
                page_count[cls_name] += 1
            summary[cls_name] = summary.get(cls_name, 0) + 1

        stem = os.path.splitext(os.path.basename(png_path))[0]
        json_path = os.path.join(ann_dir, f"{stem}_page_{i}.json")
        write_labelme(png_path, dets, json_path)

        emit_custom(task_id, event_data, event_locks, "yolo_progress",
                    {"page": i, "total": total, "detections": page_count})

    # Emit step completion with summary for frontend/logger
    summary_lines = [f"{cls}: {summary.get(cls, 0)}" for cls in YOLO_CLASSES if summary.get(cls, 0)]
    summary_text = "YOLO 检测完成：" + ("；".join(summary_lines) if summary_lines else "未检测到特征")
    emit_step_complete(
        task_id, event_data, event_locks, 2, "YOLO 检测", summary_text
    )

    return summary


def _resume_from_annotation(task_id):
    """Resume a restored-from-pending task that paused at awaiting_annotation.

    Only used when the original processing thread is gone (page refresh, restart).
    For in-flight tasks the annotation_event.set() in finalize_annotations is enough.
    """
    from ..pipeline.annotation_renderer import (
        render_annotation_text, render_annotated_images,
    )
    task = tasks.get(task_id)
    if not task:
        return
    if task.get("status") == "cancelled":
        return

    output_dir = task.get("output_dir") or os.path.join(OUTPUT_FOLDER, task_id)
    # Prefer the original png paths if we already swapped to annotated in a prior run
    png_paths = task.get("original_png_paths") or task.get("png_paths", []) or []
    if not png_paths:
        emit_error(task_id, event_data, event_locks, "无法恢复：缺少 PNG 路径")
        return

    ann_dir       = os.path.join(output_dir, "annotations")
    annotated_dir = os.path.join(output_dir, "annotated_pages")
    annotated_paths = render_annotated_images(ann_dir, png_paths, annotated_dir)
    task["original_png_paths"] = list(png_paths)
    task["png_paths"] = annotated_paths
    png_paths = annotated_paths
    preview_image_urls = _build_preview_urls(task_id, annotated_paths)
    emit_custom(
        task_id, event_data, event_locks,
        "preview_updated",
        {"preview_image_urls": preview_image_urls},
    )

    annotation_text = render_annotation_text(ann_dir)
    task["annotation_text"] = annotation_text
    task["status"]   = "processing"
    task["progress"] = 40
    update_task_status(task_id, "processing", 40)
    emit_log(task_id, event_data, event_locks, 2, "标注已确认，开始视觉分析（恢复任务）")

    # Run VLM + feature extract + review pause inline. We mirror the original
    # _process_uploaded_file_task body from the cache-check section onward.
    try:
        analyzer = _get_vision_analyzer()
        emit_step_start(task_id, event_data, event_locks, 2, "特征提取", "正在分析图纸特征")
        merged = analyzer.analyze_drawing(png_paths, annotation_text)
        merged["_page_number"] = 1
        all_descriptions = [merged]
        successful, failure_details = split_vision_results(all_descriptions)
        failures = failure_details
        if not successful:
            feature_text = _build_degraded_feature_text(
                annotation_text,
                failure_details,
                prefix_hint=task.get("prefix_hint", ""),
            )
            task["vision_descriptions"] = []
            task["vision_failures"] = [d.get("image_path", "") for d in failure_details if d.get("image_path")]
            _store_degraded_feature_report(task, feature_text, failure_details)
            emit_log(
                task_id,
                event_data,
                event_locks,
                2,
                format_vision_failure_message(failure_details, prefix="视觉分析失败，已降级为标注文本"),
                level="warn",
            )
        else:
            task["vision_degraded"] = False

            vision_descriptions = [
                {"description": d.get("description", ""), "_page_number": d.get("_page_number", i)}
                for i, d in enumerate(all_descriptions, 1)
            ]
            task["vision_descriptions"] = vision_descriptions
            task["vision_failures"] = [d.get("image_path", "") for d in failures if d.get("image_path")]
            task["vision_failure_details"] = failure_details

            report_inputs = [
                {"description": d.get("description", ""), "_page_number": d.get("_page_number", i)}
                for i, d in enumerate(all_descriptions, 1)
                if d.get("ok") and d.get("description", "").strip()
            ]
            feature_text = build_feature_report(
                report_inputs,
                prefix_hint=task.get("prefix_hint", ""),
                total_pages=len(png_paths),
            )["report_text"]
            task["review_text"] = feature_text
            task["raw_review_text"] = feature_text
            task["feature_report_json"] = {"report_text": feature_text, "pages": []}
            task["feature_report_text"] = feature_text

        emit_step_complete(task_id, event_data, event_locks, 2, "特征提取",
                           "视觉分析降级完成" if not successful else f"{len(successful)} 页提取成功")
        task["status"] = "awaiting_review"
        task["progress"] = 50
        update_task_status(task_id, "awaiting_review", 50)
        persist_review_payload(task)
        emit_custom(
            task_id, event_data, event_locks,
            "review_required",
            {
                "step": 2, "title": "图纸特征报告",
                "content": feature_text, "raw_content": feature_text,
                "failures": task["vision_failures"], "can_continue": True,
                "gltf_url": "",
                "message": (
                    "视觉分析失败，已退回标注文本，请核对补全后继续。"
                    if not successful else
                    _build_review_message(len(successful), len(failures))
                ),
            },
        )
    except Exception as e:
        logger.exception("[%s] resume_from_annotation failed", task_id)
        task["status"] = "error"
        task["error"] = f"恢复任务视觉分析失败: {e}"
        emit_error(task_id, event_data, event_locks, task["error"])
        update_task_status(task_id, "error", task.get("progress", 0), task["error"])


def _resume_from_review(task_id):
    """Resume processing a restored-from-pending task after review."""
    task = tasks.get(task_id)
    if not task:
        return
    reviewed_text = (task.get("review_text") or "").strip()
    if not reviewed_text:
        emit_error(task_id, event_data, event_locks, "审阅文本为空，无法继续")
        return
    _finalize_processing(
        task_id=task_id,
        file_name=task.get("pdf_name", task_id),
        output_dir=task.get("output_dir", os.path.join(OUTPUT_FOLDER, task_id)),
        reviewed_text=reviewed_text,
        prefix_hint=task.get("prefix_hint", ""),
        source_descriptions=[{"description": reviewed_text}],
        library_key=task.get("retrieval_library_key") or task.get("library_key") or PUBLIC_LIBRARY_KEY,
    )


def _rerun_from_review(task_id):
    task = tasks.get(task_id)
    if not task:
        raise ValueError("Task not found")

    try:
        if task.get("status") == "cancelled":
            return

        reviewed_text = (task.get("review_text") or "").strip()
        if not reviewed_text:
            raise ValueError("No review text available")

        with event_locks.get(task_id, threading.Lock()):
            event_data[task_id] = []

        # Clear old DB events so _db_event_generator doesn't replay them
        try:
            from ..task_store import clear_task_events
            clear_task_events(task_id)
        except Exception:
            pass

        task["status"] = "processing"
        task["progress"] = 50
        task.pop("error", None)
        emit_log(task_id, event_data, event_locks, 2, "收到重新生成请求，开始重新分析")

        _finalize_processing(
            task_id=task_id,
            file_name=task.get("pdf_name", "历史文件"),
            output_dir=task.get("output_dir", os.path.join(OUTPUT_FOLDER, task_id)),
            reviewed_text=reviewed_text,
            prefix_hint=task.get("prefix_hint"),
            source_descriptions=[{"description": reviewed_text}],
            library_key=task.get("retrieval_library_key") or task.get("library_key"),
            force_llm=True,
        )
    except Exception as e:
        logger.error("[%s] RERUN ERROR: %s", task_id, e, exc_info=True)
        task["status"] = "error"
        task["error"] = str(e)
        emit_error(task_id, event_data, event_locks, str(e))


def _is_upload_template_ready(task: dict) -> bool:
    """Check whether a completed upload task meets the rollout template gate.

    A task is "template-ready" when it has a recognised VLM mode, a STEP
    artifact path, and reached a terminal review or completed state.
    """
    vlm_mode = task.get("vlm_mode")
    return bool(
        vlm_mode in {"creo-primary", "freecad-geo", "dual", "freecad", "creo", "none"}
        and task.get("step_path")
        and task.get("status") in {"awaiting_review", "completed"}
    )


@upload_bp.route("/upload", methods=["POST"])
@login_required
@require_quota
def upload():
    if "file" not in request.files:
        return fail(ERR_FILE_MISSING, "No file provided")

    file = request.files["file"]
    if not PRT_FILE_RE.search(file.filename or ""):
        return fail(ERR_FILE_TYPE, "Only PRT files (including .prt.N) allowed")

    # Preflight: reject if VLM config is incomplete
    config_error = validate_vision_config()
    if config_error:
        return fail(ERR_CONFIG, config_error, 400)

    task_id = str(uuid.uuid4())
    logger.info("[%s] /upload received file=%s", task_id, file.filename)
    filename = f"{task_id}_{file.filename}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    # ── PRT 文件缓存：同文件重传直接跳到审阅步骤 ──
    prefix_hint = _extract_prefix_from_filename(file.filename) or os.path.splitext(os.path.basename(file.filename))[0].strip() or None
    _ent_id, _ = get_enterprise_scope()
    _prt_hash = hashlib.sha256()
    with open(filepath, "rb") as _f:
        while True:
            _chunk = _f.read(65536)
            if not _chunk:
                break
            _prt_hash.update(_chunk)
    _prt_hash_hex = _prt_hash.hexdigest()
    _cached = get_prt_cache(_prt_hash_hex)
    if _cached:
        logger.info("[%s] cache hit, hash=%s, source_task=%s", task_id, _prt_hash_hex, _cached["task_id"])
        # Use cached prefix_hint if extracted from filename is empty
        prefix_hint = prefix_hint or _cached.get("prefix_hint", "")
        output_dir = os.path.join(OUTPUT_FOLDER, task_id)
        os.makedirs(output_dir, exist_ok=True)

        # ── 从缓存源任务复制 3D 预览文件 + creo_views 图片 ──
        import shutil
        _src_task_dir = os.path.join(OUTPUT_FOLDER, _cached["task_id"])
        _src_glb = os.path.join(_src_task_dir, "model.glb")
        _dst_glb = os.path.join(output_dir, "model.glb")
        _gltf_url = ""
        if os.path.isfile(_src_glb):
            try:
                shutil.copy2(_src_glb, _dst_glb)
                _gltf_url = f"/api/result/{task_id}/asset/model.glb"
                logger.info("[%s] copied cached glb from %s", task_id, _src_glb)
            except Exception:
                logger.warning("[%s] failed to copy cached glb", task_id, exc_info=True)
        else:
            logger.info("[%s] source task %s has no model.glb", task_id, _cached["task_id"])

        _src_creo = os.path.join(_src_task_dir, "creo_views")
        _dst_creo = os.path.join(output_dir, "creo_views")
        if os.path.isdir(_src_creo) and not os.path.exists(_dst_creo):
            try:
                shutil.copytree(_src_creo, _dst_creo)
                logger.info("[%s] copied cached creo_views from %s", task_id, _src_creo)
            except Exception:
                logger.warning("[%s] failed to copy cached creo_views", task_id, exc_info=True)

        tasks[task_id] = {
            "task_id": task_id,
            "pdf_name": file.filename,
            "prt_name": file.filename,
            "prt_path": filepath,
            "output_dir": output_dir,
            "prefix_hint": prefix_hint,
            "source_kind": "prt",
            "status": "awaiting_review",
            "progress": 50,
            "created_at": datetime.now().isoformat(),
            "review_event": threading.Event(),
            "review_text": _cached["feature_text"],
            "vision_descriptions": [{"description": _cached["feature_text"]}],
            "feature_report_json": {"report_text": _cached["feature_text"], "pages": []},
            "feature_report_text": _cached["feature_text"],
            "vision_failures": [],
            "keep_after_complete": True,
            "source_name": file.filename,
            "library_key": request.form.get("library_key") or request.args.get("library_key") or PUBLIC_LIBRARY_KEY,
            "retrieval_library_key": _request_retrieval_library_key(),
            "enterprise_id": _ent_id,
            "_from_cache": True,
            **({"gltf_path": _dst_glb} if os.path.isfile(_dst_glb) else {}),
        }
        insert_task(task_id=task_id, pdf_name=file.filename, prt_name=file.filename,
                     output_dir=output_dir, prefix_hint=prefix_hint,
                     library_key=tasks[task_id]["library_key"], source_kind="prt",
                     enterprise_id=_ent_id)
        update_task_status(task_id, "awaiting_review", 50)
        if task_id not in event_data:
            event_data[task_id] = []
        if task_id not in event_locks:
            event_locks[task_id] = threading.Lock()
        persist_review_payload(tasks[task_id])
        emit_custom(
            task_id, event_data, event_locks,
            "review_required",
            {
                "step": 2,
                "title": "PRT 几何特征报告（缓存）",
                "content": _cached["feature_text"],
                "raw_content": _cached["feature_text"],
                "failures": [],
                "can_continue": True,
                "gltf_url": _gltf_url,
                "message": (
                    "📦 缓存命中 — 该文件之前已处理过，直接使用缓存特征。\n"
                    "请核对或修改几何特征后确认继续生成工艺。"
                ),
            },
        )

        def _cached_review_worker():
            task = tasks[task_id]
            review_event = task.get("review_event")
            if review_event:
                confirmed = review_event.wait(timeout=1800)
                if not confirmed:
                    task["status"] = "error"
                    task["error"] = "审阅等待超时（30分钟无操作），任务已超时终止"
                    emit_error(task_id, event_data, event_locks, task["error"])
                    update_task_status(task_id, "error", task.get("progress", 0), task["error"])
                    return
            if task.get("status") == "cancelled":
                return
            reviewed_text = (task.get("review_text") or _cached["feature_text"]).strip()
            emit_log(task_id, event_data, event_locks, 2, "审阅确认，开始生成工艺规程...")
            _finalize_processing(
                task_id=task_id,
                file_name=file.filename,
                output_dir=output_dir,
                reviewed_text=reviewed_text,
                prefix_hint=prefix_hint,
                source_descriptions=[{"description": reviewed_text}],
                library_key=tasks[task_id].get("retrieval_library_key") or tasks[task_id]["library_key"],
            )

        threading.Thread(target=_cached_review_worker, daemon=True).start()
        return jsonify({"task_id": task_id, "status": "awaiting_review", "cached": True, "message": "缓存命中，进入审阅"})

    logger.info("[UPLOAD] Task %s, prefix_hint: %s", task_id, prefix_hint)

    output_dir = os.path.join(OUTPUT_FOLDER, task_id)
    os.makedirs(output_dir, exist_ok=True)

    tasks[task_id] = {
        "task_id": task_id,
        "pdf_name": file.filename,
        "prt_name": file.filename,
        "prt_path": filepath,
        "output_dir": output_dir,
        "prefix_hint": prefix_hint,
        "source_kind": "prt",
        "status": "pending",
        "progress": 0,
        "created_at": datetime.now().isoformat(),
        "review_event": threading.Event(),
        "review_text": None,
        "vision_descriptions": None,
        "vision_failures": [],
        "keep_after_complete": True,
        "source_name": file.filename,
        "library_key": request.form.get("library_key") or request.args.get("library_key") or PUBLIC_LIBRARY_KEY,
        "retrieval_library_key": _request_retrieval_library_key(),
        "enterprise_id": _ent_id,
    }
    insert_task(task_id=task_id, pdf_name=file.filename, prt_name=file.filename, output_dir=output_dir, prefix_hint=prefix_hint, library_key=tasks[task_id]["library_key"], source_kind="prt", enterprise_id=_ent_id)
    if task_id not in event_data:
        event_data[task_id] = []
    if task_id not in event_locks:
        event_locks[task_id] = threading.Lock()

    def process_task(task_id, filepath):
        task = tasks[task_id]
        try:
            task["status"] = "processing"
            update_task_status(task_id, "processing", task.get("progress", 0))
            logger.info("[%s] starting PRT processing pipeline", task_id)

            # Step 1: PRT to STEP + three-view images
            emit_step_start(task_id, event_data, event_locks, 1, "PRT转换", "正在转换PRT文件")
            emit_log(task_id, event_data, event_locks, 1, "开始PRT转换...")
            logger.info("[%s] Step 1: Converting PRT...", task_id)

            task["current_stage"] = "artifact_preparation"
            artifacts = prepare_prt_artifacts(filepath, output_dir)

            if task.get("status") == "cancelled":
                return

            view_paths = artifacts["view_paths"]
            task["step_path"] = artifacts["step_path"]
            task["png_paths"] = view_paths
            if artifacts.get("geo_data") is not None:
                task["geo_data"] = artifacts["geo_data"]

            # Export 3D model as glTF in background — overlaps with VLM call below
            _gltf_result: dict = {}

            def _run_gltf():
                try:
                    _gltf_result["path"] = export_gltf(artifacts["step_path"], output_dir)
                except Exception as _e:
                    logger.warning("[%s] glTF export failed: %s", task_id, _e)

            _gltf_thread = threading.Thread(target=_run_gltf, daemon=True, name=f"gltf-export-{task_id[:8]}")
            _gltf_thread.start()

            if task.get("status") == "cancelled":
                return

            for index, image_path in enumerate(view_paths, start=1):
                emit_image_ready(task_id, event_data, event_locks, index, len(view_paths), image_path)
                emit_log(task_id, event_data, event_locks, 1, f"第 {index}/{len(view_paths)} 张视图已生成")

            creo_views_generated = artifacts.get("creo_views_generated", False)
            if creo_views_generated:
                emit_log(task_id, event_data, event_locks, 1, "Creo 截图与注释已采集")
            else:
                emit_log(task_id, event_data, event_locks, 1, "Creo 截图未生成，将按降级路径继续", level="warn")

            emit_step_complete(task_id, event_data, event_locks, 1, "PRT转换", f"共生成 {len(view_paths)} 张视图")
            emit_log(task_id, event_data, event_locks, 1, f"PRT转换完成，共 {len(view_paths)} 张视图")
            task["progress"] = 25
            logger.info("[%s] Step 1 done: %d views", task_id, len(view_paths))

            # VLM-only feature extraction with Creo-primary / freecad-geo / FreeCAD fallback
            task["current_stage"] = "vlm_feature_extraction"
            vlm_text = ""
            vlm_mode = "none"
            if artifacts.get("views_generated") or artifacts.get("creo_views_generated"):
                emit_log(task_id, event_data, event_locks, 2, "正在调用VLM提取视觉特征（Creo主路径 / FreeCAD降级）...")
                vlm_text, vlm_mode = build_vlm_feature_text(
                    freecad_views_dir=artifacts.get("views_dir", ""),
                    creo_views_dir=artifacts.get("creo_views_dir", ""),
                    creo_txt_path=artifacts.get("creo_zhushi_path", ""),
                    step_path=artifacts.get("step_path", ""),
                )
                if vlm_text:
                    _MODE_LABELS = {"creo-primary": "Creo主路径", "freecad-geo": "FreeCAD+几何约束", "freecad": "FreeCAD-only"}
                    label = _MODE_LABELS.get(vlm_mode, vlm_mode)
                    emit_log(task_id, event_data, event_locks, 2, f"VLM {label} 特征提取完成: {vlm_text[:80]}...")
                else:
                    emit_log(task_id, event_data, event_locks, 2, "VLM特征提取跳过（无图或API失败）", level="warn")
            else:
                emit_log(task_id, event_data, event_locks, 2, "FreeCAD 与 Creo 图片都不可用，跳过VLM特征提取", level="warn")

            if artifacts.get("creo_zhushi_text"):
                task["creo_zhushi_text"] = artifacts["creo_zhushi_text"]
                task["creo_zhushi_path"] = artifacts.get("creo_zhushi_path", "")
                task["creo_views_dir"] = artifacts.get("creo_views_dir", "")
                task["vlm_mode"] = vlm_mode

                emit_log(task_id, event_data, event_locks, 2, "Creo 注释文本已注入 VLM 上下文")
            else:
                task["vlm_mode"] = vlm_mode

            if artifacts.get("creo_views_generated") and artifacts.get("creo_views_dir"):
                creo_dir = artifacts["creo_views_dir"]
                for name in sorted(os.listdir(creo_dir)):
                    image_path = os.path.join(creo_dir, name)
                    if os.path.isfile(image_path) and name.lower().endswith((".png", ".jpg", ".jpeg")):
                        task["png_paths"].append(image_path)
                        emit_image_ready(task_id, event_data, event_locks, len(task["png_paths"]), len(task["png_paths"]), image_path)
                        emit_log(task_id, event_data, event_locks, 2, f"Creo 图已加入结果预览: {name}")
                        break

            logger.info("[%s] VLM mode: %s", task_id, vlm_mode)

            if task.get("status") == "cancelled":
                return

            # Merge: vlm (VLM output) + drawing number (geo data is embedded in VLM prompt, not output)
            parts = []
            if vlm_text:
                parts.append(vlm_text)
            _fig_name = prefix_hint or PRT_FILE_RE.sub("", os.path.basename(file.filename))
            parts.append(f"【图号】{_fig_name}")
            full_feature_text = cleanup_feature_text("\n".join(parts))

            # Collect GLB result (should be done while VLM was running)
            _gltf_thread.join(timeout=320)  # _run_freecad_worker subprocess limit is 300s
            task["gltf_path"] = _gltf_result.get("path", "")
            task["review_text"] = full_feature_text
            task["vision_descriptions"] = [{"description": full_feature_text}]
            task["feature_report_json"] = {"report_text": full_feature_text, "pages": []}
            task["feature_report_text"] = full_feature_text
            task["progress"] = 50
            emit_step_complete(task_id, event_data, event_locks, 2, "特征提取", "特征提取完成")

            # ── 特征审阅暂停（与 PDF 流程对齐）──
            task["status"] = "awaiting_review"
            update_task_status(task_id, "awaiting_review", 50)
            persist_review_payload(task)

            # ── 保存 PRT 缓存（供后续重传命中）──
            _cached_text = task.get("feature_report_text") or full_feature_text
            try:
                save_prt_cache(_prt_hash_hex, task_id, _cached_text, prefix_hint or "")
                logger.info("[%s] cached feature result, hash=%s", task_id, _prt_hash_hex)
            except Exception:
                logger.warning("[%s] failed to save prt_cache", task_id, exc_info=True)

            gltf_path = task.get("gltf_path", "")
            gltf_url_for_review = (
                f"/api/result/{task_id}/asset/model.glb"
                if gltf_path and os.path.isfile(gltf_path)
                else ""
            )
            emit_custom(
                task_id, event_data, event_locks,
                "review_required",
                {
                    "step": 2,
                    "title": "PRT 几何特征报告",
                    "content": full_feature_text,
                    "raw_content": full_feature_text,
                    "failures": [],
                    "can_continue": True,
                    "gltf_url": gltf_url_for_review,
                    "message": (
                        "请核对或修改几何特征后确认继续生成工艺。\n"
                        "💡 提示：若该零件在知识库中无高相似匹配，可在下方文本中补充"
                        "【零件名称】【形态】【材料】等字段以提高工艺生成质量。"
                    ),
                },
            )

            review_event = task.get("review_event")
            if review_event:
                confirmed = review_event.wait(timeout=1800)
                if not confirmed:
                    task["status"] = "error"
                    task["error"] = "审阅等待超时（30分钟无操作），任务已超时终止"
                    emit_error(task_id, event_data, event_locks, task["error"])
                    update_task_status(task_id, "error", task.get("progress", 0), task["error"])
                    return

            if task.get("status") == "cancelled":
                return

            reviewed_text = (task.get("review_text") or full_feature_text).strip()
            emit_log(task_id, event_data, event_locks, 2, "审阅确认，开始生成工艺规程...")
            _finalize_processing(
                task_id=task_id,
                file_name=file.filename,
                output_dir=output_dir,
                reviewed_text=reviewed_text,
                prefix_hint=prefix_hint,
                source_descriptions=[{"description": reviewed_text}],
                library_key=task.get("retrieval_library_key") or task.get("library_key"),
            )
        except Exception as e:
            import traceback
            logger.error("[%s] ERROR: %s", task_id, e)
            traceback.print_exc()
            stage = task.get("current_stage", "unknown")
            task["status"] = "error"
            task["error"] = str(e)
            task["error_stage"] = stage
            task["retryable"] = getattr(e, "retryable", False)
            emit_error(task_id, event_data, event_locks, str(e))
            update_task_status(task_id, "error", task.get("progress", 0), f"[{stage}] {e}")
        finally:
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except Exception as e:
                logger.warning("[%s] Failed to delete upload file %s: %s", task_id, filepath, e)

    thread = threading.Thread(target=process_task, args=(task_id, filepath), daemon=True)
    thread.start()
    logger.info("[UPLOAD] Started task %s", task_id)

    return jsonify(
        {"task_id": task_id, "pdf_name": file.filename, "prt_name": file.filename, "message": "File uploaded"}
    )


@upload_bp.route("/review/<task_id>", methods=["POST"])
@login_required
def review_visual_features(task_id):
    ok, err = assert_task_access(task_id)
    if not ok:
        return err
    task = tasks.get(task_id)
    if not task:
        task = restore_task_from_pending(task_id, tasks, event_data, event_locks)
    payload = request.get_json(silent=True) or {}
    action = payload.get("action") or "continue"
    if not task:
        if action == "rerun":
            task = restore_task_from_result(task_id, tasks, event_data, event_locks)
        if not task:
            # Task might have already completed (pending cleared, result.json exists)
            result_file = os.path.join(OUTPUT_FOLDER, task_id, "result.json")
            if os.path.exists(result_file):
                return jsonify({"error": "Task already completed", "message": "This task has already finished processing", "task_id": task_id}), 409
            return jsonify({"error": "Task not found"}), 404

    review_text = (payload.get("review_text") or "").strip()

    if not review_text:
        review_text = task.get("review_text") or ""

    task["review_text"] = review_text
    task["review_action"] = action

    new_retrieval_library_key = (
        payload.get("retrieval_library_key")
        or payload.get("library_key")
        or ""
    ).strip()
    if new_retrieval_library_key:
        task["retrieval_library_key"] = new_retrieval_library_key

    if action == "rerun":
        allowed = {"completed", "error", "processing", "awaiting_review"}
        if task.get("status") not in allowed:
            return jsonify({"error": f"Task is not ready to rerun (status={task.get('status')})"}), 400

        # Reset status synchronously BEFORE starting the thread.
        # Without this, the frontend poll fires immediately after this response
        # returns and still sees status='completed', causing it to close SSE and
        # render the stale result — the new rerun then runs silently with no listeners.
        task["status"] = "processing"
        task["progress"] = 50
        task.pop("error", None)

        rerun_thread = threading.Thread(target=_rerun_from_review, args=(task_id,), daemon=True)
        rerun_thread.start()
        return jsonify({"message": "Rerun started", "task_id": task_id, "action": action})

    if task.get("status") == "completed":
        return jsonify({"message": "Task already completed", "task_id": task_id, "action": action})

    if task.get("status") != "awaiting_review":
        # Worker in-memory state may be stale (gunicorn multi-worker mismatch).
        # Try restoring from the pending file for a fresh view of the task.
        pending_restored = restore_task_from_pending(task_id, tasks, event_data, event_locks)
        if pending_restored:
            task = pending_restored
        else:
            return jsonify({"error": "Task is not waiting for review"}), 400

    if task.get("restored_from_pending"):
        # Clear the pending file BEFORE starting processing to prevent duplicate
        # threads when a retry hits a different gunicorn worker.
        clear_pending_review(task_id, task.get("output_dir", os.path.join(OUTPUT_FOLDER, task_id)))
        resume_thread = threading.Thread(target=_resume_from_review, args=(task_id,), daemon=True)
        resume_thread.start()
        return jsonify({"message": "Review restored and processing resumed", "task_id": task_id, "action": action})

    review_event = task.get("review_event")
    if review_event:
        # Clear pending file on the same-worker path too, for consistency.
        clear_pending_review(task_id, task.get("output_dir", os.path.join(OUTPUT_FOLDER, task_id)))
        review_event.set()

    return jsonify({"message": "Review accepted", "task_id": task_id, "action": action})


@upload_bp.route("/rerun/<task_id>", methods=["POST"])
@login_required
def rerun_task(task_id):
    """Dedicated rerun endpoint - uses stored review_text, no status restriction."""
    ok, err = assert_task_access(task_id)
    if not ok:
        return err
    task = tasks.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    stored = (task.get("review_text") or "").strip()
    if not stored:
        return jsonify({"error": "No review text stored"}), 400

    payload = request.get_json(silent=True) or {}
    override = (payload.get("review_text") or "").strip()
    if override:
        task["review_text"] = override

    rerun_thread = threading.Thread(target=_rerun_from_review, args=(task_id,), daemon=True)
    rerun_thread.start()
    return jsonify({"message": "Rerun started", "task_id": task_id})


@upload_bp.route("/process/<task_id>", methods=["POST"])
@login_required
def update_process_flow(task_id):
    ok, err = assert_task_access(task_id)
    if not ok:
        return err
    task = tasks.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    payload = request.get_json(silent=True) or {}
    process_text = (payload.get("process_text") or "").strip()
    if not process_text:
        return jsonify({"error": "No process text provided"}), 400

    process_flow = {
        "data": _parse_process_markdown(process_text),
        "columns": ["标签编码", "工序内容"],
        "format": "markdown",
    }
    task["process_flow"] = process_flow

    result = dict(task.get("result") or {})
    result["process_flow"] = process_flow
    task["result"] = result

    output_dir = task.get("output_dir")
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        result_file = os.path.join(output_dir, "result.json")
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    return jsonify(result)


@upload_bp.route("/cancel/<task_id>", methods=["POST"])
@login_required
def cancel_task_route(task_id):
    ok, err = assert_task_access(task_id)
    if not ok:
        return err
    task = tasks.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    task["status"] = "cancelled"
    review_event = task.get("review_event")
    if review_event:
        review_event.set()
    update_task_status(task_id, "cancelled", progress=task.get("progress", 0))
    return jsonify({"message": "Task cancelled", "task_id": task_id})


@upload_bp.route("/upload_drawing", methods=["POST"])
@login_required
@require_quota
def upload_drawing():
    """Upload a 2D drawing file (PDF, PNG, JPG) for feature extraction and process generation."""
    if "file" not in request.files:
        return fail(ERR_FILE_MISSING, "No file provided")

    file = request.files["file"]
    filename = file.filename or ""
    if not _is_drawing_file(filename):
        return fail(ERR_FILE_TYPE, "Only PDF, PNG, JPG files allowed")

    if filename.lower().endswith(".pdf"):
        pdf_capability = inspect_pdf_capability()
        if not pdf_capability["available"]:
            return fail(
                ERR_CAPABILITY,
                pdf_capability["reason"],
                422,
                {"capability": "pdf"},
            )

    config_error = validate_vision_config()
    if config_error:
        return fail(ERR_CONFIG, config_error, 400)

    task_id = str(uuid.uuid4())
    logger.info("[%s] /upload_drawing received file=%s", task_id, filename)

    saved_filename = f"{task_id}_{filename}"
    filepath = os.path.join(UPLOAD_FOLDER, saved_filename)
    file.save(filepath)

    use_cache = request.form.get("feature_cache", request.form.get("use_cache", "0")) in ("1", "true")
    file_hash = None
    if use_cache:
        try:
            from ..services.feature_cache import compute_file_hash as _compute_hash
            file_hash = _compute_hash(filepath)
            logger.info("[%s] file_hash=%s…", task_id, file_hash[:12])
        except Exception:
            logger.warning("[%s] Failed to compute file hash", task_id, exc_info=True)

    prefix_hint = (
        _extract_prefix_from_filename(filename)
        or os.path.splitext(os.path.basename(filename))[0].strip()
        or None
    )

    output_dir = os.path.join(OUTPUT_FOLDER, task_id)
    os.makedirs(output_dir, exist_ok=True)

    is_pdf = filename.lower().endswith(".pdf")
    is_dxf = filename.lower().endswith(".dxf")
    is_dwg = filename.lower().endswith(".dwg")

    _ent_id_drawing, _ = get_enterprise_scope()
    tasks[task_id] = {
        "task_id": task_id,
        "pdf_name": filename,
        "prt_name": None,
        "prt_path": None,
        "output_dir": output_dir,
        "prefix_hint": prefix_hint,
        "source_kind": "drawing",
        "source_name": filename,
        "status": "pending",
        "progress": 0,
        "created_at": datetime.now().isoformat(),
        "review_event": threading.Event(),
        "annotation_event": threading.Event(),
        "review_text": None,
        "vision_descriptions": None,
        "vision_failures": [],
        "keep_after_complete": True,
        "library_key": request.form.get("library_key") or request.args.get("library_key") or PUBLIC_LIBRARY_KEY,
        "retrieval_library_key": _request_retrieval_library_key(),
        "enterprise_id": _ent_id_drawing,
    }
    insert_task(
        task_id=task_id,
        pdf_name=filename,
        prt_name=filename,
        output_dir=output_dir,
        prefix_hint=prefix_hint,
        library_key=tasks[task_id]["library_key"],
        source_kind="drawing",
        enterprise_id=_ent_id_drawing,
    )
    if task_id not in event_data:
        event_data[task_id] = []
    if task_id not in event_locks:
        event_locks[task_id] = threading.Lock()

    def process_drawing(task_id, filepath):
        task = tasks[task_id]
        try:
            task["status"] = "processing"
            update_task_status(task_id, "processing", 0)

            # Step 1: Convert file to PNG pages
            emit_step_start(task_id, event_data, event_locks, 1, "图纸解析", "正在解析图纸文件")
            emit_log(task_id, event_data, event_locks, 1, "开始图纸页面解析...")

            pages_dir = os.path.join(output_dir, "pages")
            os.makedirs(pages_dir, exist_ok=True)

            if is_pdf:
                def _on_page(page_num, total, path):
                    emit_image_ready(task_id, event_data, event_locks, page_num, total, path)
                    emit_log(task_id, event_data, event_locks, 1, f"第 {page_num}/{total} 页已转换")
                png_paths = convert_pdf_to_images(filepath, pages_dir, dpi=300, on_image_ready=_on_page)
            elif is_dxf:
                from ..pipeline.dxf_converter import convert_dxf_to_images
                def _on_dxf_page(page_num, total, path):
                    emit_image_ready(task_id, event_data, event_locks, page_num, total, path)
                    emit_log(task_id, event_data, event_locks, 1, f"DXF 第 {page_num}/{total} 张布局已转换")
                emit_log(task_id, event_data, event_locks, 1, "正在解析 DXF 文件...")
                png_paths = convert_dxf_to_images(filepath, pages_dir, on_image_ready=_on_dxf_page)
                if not png_paths:
                    raise RuntimeError("DXF 文件解析失败，未生成任何图片（可能是空图纸）")
            elif is_dwg:
                from ..pipeline.dwg_converter import convert_dwg_to_images
                def _on_dwg_page(page_num, total, path):
                    emit_image_ready(task_id, event_data, event_locks, page_num, total, path)
                    emit_log(task_id, event_data, event_locks, 1, f"DWG 第 {page_num}/{total} 张布局已转换")
                emit_log(task_id, event_data, event_locks, 1, "正在解析 DWG 文件...")
                png_paths = convert_dwg_to_images(filepath, pages_dir, on_image_ready=_on_dwg_page)
                if not png_paths:
                    raise RuntimeError("DWG 文件解析失败，未生成任何图片")
            else:
                stem = os.path.splitext(os.path.basename(filename))[0]
                out_png = os.path.join(pages_dir, f"{stem}.png")
                _save_image_as_png(filepath, out_png)
                png_paths = [out_png]
                emit_image_ready(task_id, event_data, event_locks, 1, 1, out_png)

            task["png_paths"] = png_paths
            emit_step_complete(task_id, event_data, event_locks, 1, "图纸解析", f"共 {len(png_paths)} 页")
            task["progress"] = 25

            if task.get("status") == "cancelled":
                return

            # ── Feature cache check (early — before YOLO) ─────────────
            _cache_entry = None
            if use_cache and file_hash:
                from ..services.feature_cache import get_cached as _fc_get
                _cache_entry = _fc_get(OUTPUT_FOLDER, file_hash)
                if _cache_entry:
                    logger.info("[%s] Feature cache HIT (early) hash=%s", task_id, file_hash[:12])

            # ── Step 1.5: YOLO 预标注 + 暂停等人工补全 ────────────────
            emit_step_start(task_id, event_data, event_locks, 2, "YOLO 检测", "正在自动标注特征")
            yolo_summary = _run_yolo_prelabel(task_id, png_paths, output_dir)
            task["yolo_summary"] = yolo_summary
            task["progress"] = 35

            task["status"] = "awaiting_annotation"
            update_task_status(task_id, "awaiting_annotation", 35)
            persist_review_payload(task)
            preview_image_urls = _build_preview_urls(task_id, png_paths)
            emit_custom(
                task_id, event_data, event_locks,
                "annotation_required",
                {
                    "task_id": task_id,
                    "summary": yolo_summary,
                    "pages":   len(png_paths),
                    "preview_image_urls": preview_image_urls,
                },
            )
            annotation_event = task.get("annotation_event")
            if annotation_event:
                confirmed = annotation_event.wait(timeout=1800)
                if not confirmed:
                    task["status"] = "error"
                    task["error"] = "标注等待超时（30分钟无操作），任务已终止"
                    emit_error(task_id, event_data, event_locks, task["error"])
                    update_task_status(task_id, "error", task.get("progress", 0), task["error"])
                    return

            if task.get("status") == "cancelled":
                return

            # ── 加载人工核对后的标注 → 渲染带框图 + VLM 文本 ─────────────
            from ..pipeline.annotation_renderer import (
                render_annotation_text, render_annotated_images,
            )
            ann_dir       = os.path.join(output_dir, "annotations")
            annotated_dir = os.path.join(output_dir, "annotated_pages")
            annotated_paths = render_annotated_images(ann_dir, png_paths, annotated_dir)
            # Replace png_paths so VLM sees boxed images; preview URLs follow
            task["original_png_paths"] = list(png_paths)
            task["png_paths"] = annotated_paths
            png_paths = annotated_paths
            preview_image_urls = _build_preview_urls(task_id, annotated_paths)
            emit_custom(
                task_id, event_data, event_locks,
                "preview_updated",
                {"preview_image_urls": preview_image_urls},
            )

            annotation_text = render_annotation_text(ann_dir)
            task["annotation_text"] = annotation_text
            emit_log(task_id, event_data, event_locks, 2, "标注已确认，开始视觉分析")
            task["progress"] = 40
            update_task_status(task_id, "processing", 40)

            # ── Feature cache: use entry from early check (or re-read if restarted)
            if _cache_entry is None and use_cache and file_hash:
                from ..services.feature_cache import get_cached as _fc_get2
                _cache_entry = _fc_get2(OUTPUT_FOLDER, file_hash)
                if _cache_entry:
                    logger.info("[%s] Feature cache re-read after restart hash=%s", task_id, file_hash[:12])
            if _cache_entry:
                # Step 2 (cache hit): skip VLM, restore from cache
                emit_step_start(task_id, event_data, event_locks, 2, "特征提取", "缓存命中，恢复上次分析结果")
                feature_text = _cache_entry["feature_text"]
                vision_descriptions = _cache_entry.get("vision_descriptions", [])
                task["vision_descriptions"] = vision_descriptions
                task["vision_failures"] = []
                successful = vision_descriptions
                failures = []
                task["review_text"] = feature_text
                task["raw_review_text"] = feature_text
                task["feature_report_json"] = {"report_text": feature_text, "pages": []}
                task["feature_report_text"] = feature_text
                emit_log(task_id, event_data, event_locks, 2,
                         f"缓存命中（来源：{_cache_entry.get('source_filename', '')}），跳过 VLM 分析")
                emit_step_complete(task_id, event_data, event_locks, 2, "特征提取", "缓存恢复完成")
                task["progress"] = 50
            else:
                # Step 2 (normal): VLM feature extraction
                emit_step_start(task_id, event_data, event_locks, 2, "特征提取", "正在分析图纸特征")
                emit_log(task_id, event_data, event_locks, 2, "开始VLM特征提取...")

                analyzer = _get_vision_analyzer()
                emit_log(task_id, event_data, event_locks, 2,
                         f"双模并行分析（共 {len(png_paths)} 页）...")
                if task.get("status") == "cancelled":
                    return
                # analyze_drawing 发出两路并行 VLM 调用，返回合并后的单条结果
                merged = analyzer.analyze_drawing(png_paths, task.get("annotation_text", ""))
                merged["_page_number"] = 1
                all_descriptions = [merged]

                successful, failure_details = split_vision_results(all_descriptions)
                failures = failure_details

                vision_descriptions = [
                    {"description": d.get("description", ""), "_page_number": d.get("_page_number", i)}
                    for i, d in enumerate(all_descriptions, 1)
                ]
                task["vision_descriptions"] = vision_descriptions
                task["vision_failures"] = [d.get("image_path", "") for d in failures if d.get("image_path")]
                task["vision_failure_details"] = failure_details

                if not successful:
                    feature_text = _build_degraded_feature_text(
                        task.get("annotation_text", ""),
                        failure_details,
                        prefix_hint=prefix_hint,
                    )
                    _store_degraded_feature_report(task, feature_text, failure_details)
                    emit_log(
                        task_id,
                        event_data,
                        event_locks,
                        2,
                        format_vision_failure_message(failure_details, prefix="视觉分析失败，已降级为标注文本"),
                        level="warn",
                    )
                else:
                    task["vision_degraded"] = False
                    report_inputs = [
                        {"description": d.get("description", ""), "_page_number": d.get("_page_number", i)}
                        for i, d in enumerate(all_descriptions, 1)
                        if d.get("ok") and d.get("description", "").strip()
                    ]
                    feature_text = build_feature_report(
                        report_inputs, prefix_hint=prefix_hint, total_pages=len(png_paths)
                    )["report_text"]
                    task["review_text"] = feature_text
                    task["raw_review_text"] = feature_text
                    task["feature_report_json"] = {"report_text": feature_text, "pages": []}
                    task["feature_report_text"] = feature_text

                # ── OCR 厚度交叉校验（非阻断）──
                if successful and os.getenv("OCR_THICKNESS_CHECK", "1") != "0":
                    try:
                        from ..pipeline.ocr_thickness import verify_drawing_thickness
                        _thickness_flag = verify_drawing_thickness(
                            feature_text=feature_text,
                            image_paths=[Path(p) for p in png_paths],
                            drawing_id=prefix_hint or os.path.splitext(os.path.basename(filename))[0],
                        )
                        if _thickness_flag:
                            task.setdefault("flags", {})["thickness_conflict"] = _thickness_flag
                            logger.warning("[%s] OCR thickness conflict detected: %s", task_id, _thickness_flag)
                            # 自动修正 feature_text 中的厚度值（替换最后一个 × 后的数字）
                            _vlm_dim = _thickness_flag.get("thickness_candidates_vlm", "")
                            _ocr_t = _thickness_flag.get("thickness_recommended")
                            _vlm_t = _thickness_flag.get("thickness_vlm")
                            if _vlm_dim and _ocr_t and _vlm_t and _ocr_t != _vlm_t:
                                # 合理性检查：如果 VLM 是 L×W×T 三部分格式且第三维远小于前两维（板料），
                                # 检查 OCR 推荐值是否合理（厚度不应超过长宽的 50%）
                                _should_skip = False
                                _parts = [p.strip() for p in _vlm_dim.replace('Ø', '').split('×') if p.strip()]
                                if len(_parts) >= 3:
                                    _nums = []
                                    for p in _parts:
                                        _m = re.search(r'\d+(?:\.\d+)?', p)
                                        if _m:
                                            _nums.append(float(_m.group()))
                                    if len(_nums) >= 3:
                                        _a, _b, _t = _nums[0], _nums[1], _nums[2]
                                        # VLM 厚度是最小值且远小于另两维 → 板料，OCR 不应推荐 > 较小长宽的一半
                                        if _t < _a * 0.5 and _t < _b * 0.5 and _ocr_t > min(_a, _b) * 0.5:
                                            _should_skip = True
                                if _should_skip:
                                    logger.info(
                                        "[%s] Skipped OCR auto-correction: VLM=%s is a thin plate (%.1f×%.1f×%.1f), OCR=%d would make it a cube",
                                        task_id, _vlm_dim, _nums[0], _nums[1], _nums[2], _ocr_t,
                                    )
                                else:
                                    _dim_new = re.sub(r'(×)[^×]+$', r'\g<1>' + str(_ocr_t), _vlm_dim.strip())
                                    if _dim_new != _vlm_dim:
                                        feature_text = re.sub(
                                            r'(【外形尺寸】[：:\s]*)[^\n]+',
                                            r'\g<1>' + _dim_new,
                                            feature_text
                                        )
                                        task["feature_report_text"] = feature_text
                                        if task.get("review_text"):
                                            task["review_text"] = re.sub(
                                                r'(【外形尺寸】[：:\s]*)[^\n]+',
                                                r'\g<1>' + _dim_new,
                                                task["review_text"]
                                            )
                                        logger.info(
                                            "[%s] Auto-corrected feature_text thickness: %s → %s",
                                            task_id, _vlm_dim, _dim_new,
                                        )
                    except Exception:
                        logger.warning("[%s] OCR thickness check failed", task_id, exc_info=True)

                emit_step_complete(task_id, event_data, event_locks, 2, "特征提取", f"{len(successful)} 页提取成功")
                task["progress"] = 50

                # 始终写缓存（仅特征报告，不缓存 YOLO 标注）
                if file_hash and feature_text:
                    try:
                        from ..services.feature_cache import put_cache as _fc_put
                        _fc_put(OUTPUT_FOLDER, file_hash, {
                            "source_filename": filename,
                            "feature_text": feature_text,
                            "vision_descriptions": vision_descriptions,
                        })
                    except Exception:
                        logger.warning("[%s] Feature cache write failed", task_id, exc_info=True)

            # Pause for human review
            task["status"] = "awaiting_review"
            update_task_status(task_id, "awaiting_review", 50)
            persist_review_payload(task)
            emit_custom(
                task_id, event_data, event_locks,
                "review_required",
                {
                    "step": 2,
                    "title": "图纸特征报告",
                    "content": feature_text,
                    "raw_content": feature_text,
                    "failures": task["vision_failures"],
                    "can_continue": True,
                    "gltf_url": "",
                    "message": (
                        "视觉分析失败，已退回标注文本，请核对补全后继续。"
                        if not successful else
                        _build_review_message(len(successful), len(failures))
                    ),
                },
            )

            review_event = task.get("review_event")
            if review_event:
                confirmed = review_event.wait(timeout=1800)
                if not confirmed:
                    task["status"] = "error"
                    task["error"] = "审阅等待超时（30分钟无操作），任务已超时终止"
                    emit_error(task_id, event_data, event_locks, task["error"])
                    update_task_status(task_id, "error", task.get("progress", 0), task["error"])
                    return

            if task.get("status") == "cancelled":
                return

            reviewed_text = (task.get("review_text") or feature_text).strip()
            emit_log(task_id, event_data, event_locks, 2, "审阅确认，开始生成工艺规程...")
            _finalize_processing(
                task_id=task_id,
                file_name=filename,
                output_dir=output_dir,
                reviewed_text=reviewed_text,
                prefix_hint=prefix_hint,
                source_descriptions=[{"description": reviewed_text}],
                library_key=task.get("retrieval_library_key") or task.get("library_key"),
            )

        except Exception as e:
            traceback.print_exc()
            task["status"] = "error"
            task["error"] = str(e)
            emit_error(task_id, event_data, event_locks, str(e))
            update_task_status(task_id, "error", task.get("progress", 0), str(e))
        finally:
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except Exception as _del_err:
                logger.warning("[%s] Failed to delete upload file: %s", task_id, _del_err)

    thread = threading.Thread(target=process_drawing, args=(task_id, filepath), daemon=True)
    thread.start()
    logger.info("[UPLOAD_DRAWING] Started task %s", task_id)

    return jsonify({"task_id": task_id, "pdf_name": filename, "message": "File uploaded"})
