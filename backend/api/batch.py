# -*- coding: utf-8 -*-
"""Batch upload endpoint for multiple PRT files."""

import os
import re
import uuid
import json
import threading
import logging
from datetime import datetime
from flask import Blueprint, jsonify, request, g

from ..config import UPLOAD_FOLDER, OUTPUT_FOLDER, validate_vision_config
from ..feature_report import build_feature_report, write_feature_report_json
from ..history import add_history_entry
from ._response import fail, ERR_FILE_MISSING, ERR_FILE_TYPE
from ..auth_utils import login_required, require_quota
from ..task_store import insert_task, update_task_status, save_result
from ..services.event_emitter import (
    emit_step_start,
    emit_step_complete,
    emit_complete,
    emit_error,
    emit_image_ready,
    emit_log,
)
from ..vision_utils import split_vision_results, format_vision_failure_message
from ._utils import PRT_FILE_RE, extract_prefix_from_filename, get_enterprise_scope
from ..library_scope import PUBLIC_LIBRARY_KEY
from ..services.process_rollout import resolve_generation_library_key

batch_bp = Blueprint("batch", __name__)
logger = logging.getLogger(__name__)

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


def _raw_request_retrieval_library_key() -> str:
    """Read the RAG retrieval library key from new and legacy request fields."""
    return (
        request.form.get("retrieval_library_key")
        or request.args.get("retrieval_library_key")
        or request.form.get("library_key")
        or request.args.get("library_key")
        or ""
    )


def _request_retrieval_library_key() -> tuple[str, dict]:
    """Resolve the RAG retrieval library key for the current user."""
    user = getattr(g, "current_user", None)
    return resolve_generation_library_key(_raw_request_retrieval_library_key(), user)


def _build_upload_mode_meta(file_count: int, page_count: int):
    file_count = max(int(file_count or 0), 0)
    page_count = max(int(page_count or 0), 0)

    if file_count <= 1:
        if page_count <= 1:
            mode = "single_prt_single_page"
            label = "单个 PRT · 单页"
            can_paginate = False
        else:
            mode = "single_prt_multi_page"
            label = "单个 PRT · 多页"
            can_paginate = True
    else:
        if page_count <= file_count:
            mode = "multi_prt_single_page"
            label = f"{file_count} 个 PRT · 单页"
        else:
            mode = "multi_prt_multi_page"
            label = f"{file_count} 个 PRT · 多页"
        can_paginate = True

    return {
        "upload_mode": mode,
        "upload_mode_label": label,
        "file_count": file_count,
        "page_count": page_count,
        "can_paginate": can_paginate,
    }


@batch_bp.route("/batch_upload", methods=["POST"])
@login_required
@require_quota
def batch_upload():
    if "files" not in request.files:
        return fail(ERR_FILE_MISSING, "No files provided")

    files = request.files.getlist("files")
    if not files or len(files) == 0:
        return fail(ERR_FILE_MISSING, "No files provided")

    prt_files = [f for f in files if PRT_FILE_RE.search(f.filename or "")]
    if not prt_files:
        return fail(ERR_FILE_TYPE, "Only PRT files (including .prt.N) allowed")

    batch_task_id = str(uuid.uuid4())
    logger.info("[%s] /batch_upload received %d prt file(s)", batch_task_id, len(prt_files))
    print(f"[{batch_task_id}] /batch_upload received {len(prt_files)} prt file(s)")
    enterprise_id, _ = get_enterprise_scope()
    _resolved_retrieval_key, _resolution_meta = _request_retrieval_library_key()

    tasks[batch_task_id] = {
        "task_id": batch_task_id,
        "files": [],
        "status": "processing",
        "progress": 0,
        "created_at": datetime.now().isoformat(),
        "library_key": request.form.get("library_key") or request.args.get("library_key") or PUBLIC_LIBRARY_KEY,
        "retrieval_library_key": _resolved_retrieval_key,
        "retrieval_library_resolution": _resolution_meta,
        "enterprise_id": enterprise_id,
    }
    insert_task(task_id=batch_task_id, pdf_name=f"Batch ({len(prt_files)} files)", prt_name=f"Batch ({len(prt_files)} files)", output_dir=os.path.join(OUTPUT_FOLDER, batch_task_id), prefix_hint="batch", library_key=tasks[batch_task_id]["library_key"], source_kind="prt", enterprise_id=enterprise_id)
    event_data[batch_task_id] = []
    event_locks[batch_task_id] = threading.Lock()

    saved_files = []
    for file in prt_files:
        task_id = str(uuid.uuid4())
        filename = f"{task_id}_{file.filename}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        prefix_hint = _extract_prefix_from_filename(file.filename) or os.path.splitext(os.path.basename(file.filename))[0].strip() or None

        saved_files.append(
            {
                "task_id": task_id,
                "pdf_name": file.filename,
                "prt_name": file.filename,
                "prt_path": filepath,
                "status": "pending",
                "prefix_hint": prefix_hint,
                "enterprise_id": enterprise_id,
            }
        )
        tasks[task_id] = {
            "task_id": task_id,
            "pdf_name": file.filename,
            "prt_name": file.filename,
            "prt_path": filepath,
            "status": "pending",
            "progress": 0,
            "created_at": datetime.now().isoformat(),
            "enterprise_id": enterprise_id,
        }
        event_data[task_id] = []
        event_locks[task_id] = threading.Lock()

    tasks[batch_task_id]["files"] = saved_files

    def process_batch(batch_task_id, files):
        from ..pipeline.expert_judge import ExpertJudge
        from ..pipeline.process_gen import ProcessGenerator

        try:
            logger.info("[%s] starting batch processing pipeline", batch_task_id)
            print(f"[{batch_task_id}] starting batch processing pipeline")
            emit_step_start(
                batch_task_id,
                event_data,
                event_locks,
                1,
                "PRT to Views",
                "Converting all PRT files",
            )

            # Convert all PRTs first
            all_png_paths = []
            processed_files = []
            global_page = 0  # 全局页码计数器

            for idx, file_info in enumerate(files):
                if tasks.get(batch_task_id, {}).get("status") == "cancelled":
                    return

                task_id = file_info["task_id"]
                prt_path = file_info["prt_path"]
                prt_name = file_info["prt_name"]

                output_dir = os.path.join(OUTPUT_FOLDER, task_id)
                os.makedirs(output_dir, exist_ok=True)

                try:
                    from ..prt_pipeline import prepare_prt_artifacts
                    artifacts = prepare_prt_artifacts(prt_path, output_dir)
                    png_paths = artifacts["view_paths"]
                except ModuleNotFoundError:
                    logger.warning("[%s] prt_pipeline not available, skipping PRT", task_id)
                    continue
                all_png_paths.extend(png_paths)

                # 计算当前总页数（在extend之后）
                current_total = len(all_png_paths)

                # 发送每个PRT的image_ready事件
                for page_idx, png_path in enumerate(png_paths, 1):
                    global_page += 1
                    emit_image_ready(
                        batch_task_id,
                        event_data,
                        event_locks,
                        global_page,  # 全局页码
                        current_total,  # 当前总页数
                        png_path,
                    )

                processed_files.append(
                    {
                        "task_id": task_id,
                        "pdf_name": prt_name,
                        "png_paths": png_paths,
                        "png_count": len(png_paths),
                        "prefix_hint": file_info.get("prefix_hint"),
                        **_build_upload_mode_meta(1, len(png_paths)),
                    }
                )
                tasks[task_id]["status"] = "processing"
                tasks[task_id]["progress"] = 25

            emit_step_complete(
                batch_task_id,
                event_data,
                event_locks,
                1,
                "PRT to Views",
                f"Converted {len(files)} files",
            )
            tasks[batch_task_id]["progress"] = 20

            if tasks.get(batch_task_id, {}).get("status") == "cancelled":
                return

            # Vision analysis
            emit_step_start(
                batch_task_id,
                event_data,
                event_locks,
                2,
                "Vision Analysis",
                "Analyzing all drawings",
            )
            print(f"[{batch_task_id}] Step 2: Batch vision analysis...")

            # 根据 VISION_MODE 选择视觉分析器
            vision_mode = os.getenv("VISION_MODE", "doubao")
            config_error = validate_vision_config(vision_mode)
            if config_error:
                print(f"[{batch_task_id}] 视觉配置不可用，自动降级到本地视觉分析器：{config_error}")
                vision_mode = "local"

            if vision_mode == "local":
                from ..pipeline.local_vision_analyzer import LocalVisionAnalyzer
                batch_analyzer = LocalVisionAnalyzer()
                print(f"[{batch_task_id}] 使用本地视觉分析器 (EasyOCR + RuleEngine + Qwen3-VL-8B)")
            else:
                from ..pipeline.vision_analyzer import VisionAnalyzer
                batch_analyzer = VisionAnalyzer()
                print(f"[{batch_task_id}] 使用 Doubao 视觉分析器")

            all_descriptions = []
            for file_info in processed_files:
                for page_index, png_path in enumerate(file_info["png_paths"], start=1):
                    print(f"[{batch_task_id}] Analyzing: {png_path}")
                    description = batch_analyzer.analyze_image(png_path)
                    all_descriptions.append(
                        {
                            "file": file_info["pdf_name"],
                            "page": page_index,
                            "image_path": png_path,
                            "description": description.get("description", ""),
                            "error": description.get("error", ""),
                        }
                    )
                tasks[file_info["task_id"]]["progress"] = 50

            successful_descriptions, vision_failures = split_vision_results(all_descriptions)
            if vision_failures:
                emit_log(
                    batch_task_id,
                    event_data,
                    event_locks,
                    2,
                    format_vision_failure_message(
                        vision_failures,
                        prefix=f"批量视觉分析：{len(vision_failures)} 页失败，已跳过",
                    ),
                    level="warn",
                )
            if not successful_descriptions:
                raise RuntimeError("所有页面视觉分析均失败，无法继续处理")

            emit_step_complete(
                batch_task_id,
                event_data,
                event_locks,
                2,
                "Vision Analysis",
                f"Analyzed {len(successful_descriptions)} pages",
            )
            tasks[batch_task_id]["progress"] = 40

            if tasks.get(batch_task_id, {}).get("status") == "cancelled":
                return

            # Expert judgment
            emit_step_start(
                batch_task_id,
                event_data,
                event_locks,
                3,
                "Expert Judgment",
                "Analyzing documents",
            )
            print(f"[{batch_task_id}] Step 3: Batch expert judgment...")

            judge = ExpertJudge()
            individual_judgments = []
            for file_info in processed_files:
                file_descriptions = [
                    d for d in successful_descriptions if d["file"] == file_info["pdf_name"]
                ]
                judgment = judge.analyze(file_descriptions)
                individual_judgments.append(
                    {
                        "file": file_info["pdf_name"],
                        "judgment": judgment,
                        "png_count": file_info["png_count"],
                    }
                )
                tasks[file_info["task_id"]]["expert_judgment"] = judgment

            comprehensive = judge.analyze(successful_descriptions)
            tasks[batch_task_id]["expert_judgment"] = comprehensive
            emit_step_complete(
                batch_task_id,
                event_data,
                event_locks,
                3,
                "Expert Judgment",
                "Analysis complete",
            )
            tasks[batch_task_id]["progress"] = 60

            if tasks.get(batch_task_id, {}).get("status") == "cancelled":
                return

            # Process generation
            emit_step_start(
                batch_task_id,
                event_data,
                event_locks,
                4,
                "Process Planning",
                "Generating process specifications",
            )
            print(f"[{batch_task_id}] Step 4: Comprehensive process flow...")

            generator = ProcessGenerator()
            fused_descriptions = [
                {"description": d["description"]} for d in successful_descriptions
            ]

            # Use first file's prefix_hint for batch
            batch_prefix_hint = (
                processed_files[0].get("prefix_hint") if processed_files else None
            )

            feature_report_json = build_feature_report(successful_descriptions, prefix_hint=batch_prefix_hint, total_pages=len(successful_descriptions))

            process_flow_raw, process_data, rag_results = generator.generate(
                fused_descriptions,
                comprehensive,
                prefix_hint=batch_prefix_hint,
                library_key=tasks[batch_task_id].get("retrieval_library_key") or tasks[batch_task_id].get("library_key"),
            )

            tasks[batch_task_id]["progress"] = 100
            tasks[batch_task_id]["status"] = "completed"
            tasks[batch_task_id]["process_flow"] = {
                "raw": process_flow_raw,
                "data": process_data,
                "columns": ["标签编码", "工序内容"],
                "format": "markdown",
            }
            tasks[batch_task_id]["rag_results"] = rag_results
            tasks[batch_task_id]["feature_report_json"] = feature_report_json
            tasks[batch_task_id]["feature_report_text"] = feature_report_json.get("report_text", "")

            # Save result
            result = {
                "task_id": batch_task_id,
                "file_count": len(files),
                "total_pages": len(all_png_paths),
                **_build_upload_mode_meta(len(files), len(all_png_paths)),
                "files": processed_files,
                "comprehensive_judgment": comprehensive,
                "individual_judgments": individual_judgments,
                "process_flow": tasks[batch_task_id]["process_flow"],
                "feature_report_json": feature_report_json,
                "feature_report_text": feature_report_json.get("report_text", ""),
                "completed_at": datetime.now().isoformat(),
                "enterprise_id": tasks[batch_task_id].get("enterprise_id"),
            }

            output_dir = os.path.join(OUTPUT_FOLDER, batch_task_id)
            os.makedirs(output_dir, exist_ok=True)
            result["feature_report_path"] = write_feature_report_json(output_dir, feature_report_json)
            result_file = os.path.join(output_dir, "result.json")
            with open(result_file, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            tasks[batch_task_id]["result"] = result

            emit_complete(
                batch_task_id, event_data, event_locks, "Batch processing complete!"
            )
            print(f"[{batch_task_id}] All steps done!")

            add_history_entry(
                task_id=batch_task_id,
                pdf_name=f"Batch ({len(files)} PRT files)",
                progress=100,
                created_at=tasks[batch_task_id].get("created_at", ""),
                file_count=len(files),
                enterprise_id=tasks[batch_task_id].get("enterprise_id"),
            )

        except Exception as e:
            import traceback

            print(f"[{batch_task_id}] ERROR: {e}")
            traceback.print_exc()
            tasks[batch_task_id]["status"] = "error"
            tasks[batch_task_id]["error"] = str(e)
            emit_error(batch_task_id, event_data, event_locks, str(e))
            update_task_status(batch_task_id, "error", tasks[batch_task_id].get("progress", 0), str(e))
        finally:
            # Persist cancelled status if thread was stopped by /cancel
            batch_status = tasks.get(batch_task_id, {}).get("status")
            if batch_status == "cancelled":
                update_task_status(batch_task_id, "cancelled", tasks.get(batch_task_id, {}).get("progress", 0))
            # Clean up sub-task entries and uploaded files
            for file_info in files:
                sub_id = file_info["task_id"]
                lock = event_locks.get(sub_id)
                if lock is None:
                    event_data.pop(sub_id, None)
                    event_locks.pop(sub_id, None)
                else:
                    with lock:
                        event_data.pop(sub_id, None)
                        event_locks.pop(sub_id, None)
                tasks.pop(sub_id, None)
                prt_path = file_info.get("prt_path")
                if prt_path:
                    try:
                        if os.path.exists(prt_path):
                            os.remove(prt_path)
                    except Exception as e:
                        logger.warning("[%s] Failed to delete upload file %s: %s", batch_task_id, prt_path, e)

    thread = threading.Thread(
        target=process_batch, args=(batch_task_id, saved_files), daemon=True
    )
    thread.start()
    print(f"[BATCH] Started batch task {batch_task_id} with {len(saved_files)} files")

    return jsonify(
        {
            "batch_task_id": batch_task_id,
            "file_count": len(saved_files),
            "files": [
                {"task_id": f["task_id"], "pdf_name": f["pdf_name"], "prt_name": f["prt_name"]}
                for f in saved_files
            ],
            "message": "Files uploaded",
        }
    )
