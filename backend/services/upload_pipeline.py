# -*- coding: utf-8 -*-
"""PRT upload pipeline orchestration — core processing between route and domain.

Extracted from backend/api/upload.py to keep route handlers thin while
preserving all existing event emission and state-update behaviour.
"""
import os
import logging

from ..prt_pipeline import prepare_prt_artifacts, export_gltf
from ..pipeline.vlm_feature import build_vlm_feature_text
from ..services.event_emitter import (
    emit_step_start,
    emit_step_complete,
    emit_image_ready,
    emit_log,
    emit_custom,
)

logger = logging.getLogger(__name__)


def process_prt_pipeline(filepath, output_dir, prefix_hint, filename, task, task_id,
                          event_data, event_locks):
    """Run the core PRT processing pipeline: conversion, views, geometry, VLM.

    This function does NOT manage task status, review flow, or finalization.
    The caller (route handler) is responsible for those.

    Returns:
        dict with keys: artifacts, geo_text, vlm_text, vlm_mode, full_feature_text
    """
    # Step 1: PRT to STEP + three-view images
    emit_step_start(task_id, event_data, event_locks, 1, "PRT转换", "正在转换PRT文件")
    emit_log(task_id, event_data, event_locks, 1, "开始PRT转换...")

    task["current_stage"] = "artifact_preparation"
    artifacts = prepare_prt_artifacts(filepath, output_dir)

    view_paths = artifacts["view_paths"]
    task["step_path"] = artifacts["step_path"]
    task["png_paths"] = view_paths

    # Export 3D model as glTF — screenshots first, FreeCAD STEP as fallback
    gltf_path = None
    try:
        gltf_path = export_gltf(
            artifacts["step_path"], output_dir,
            creo_views_dir=artifacts.get("creo_views_dir", ""),
        )
        task["gltf_path"] = gltf_path
    except Exception as e:
        logger.info("[%s] glTF export failed: %s", task_id, e)

    for idx, image_path in enumerate(view_paths, start=1):
        emit_image_ready(task_id, event_data, event_locks, idx, len(view_paths), image_path)
        emit_log(task_id, event_data, event_locks, 1, f"第 {idx}/{len(view_paths)} 张视图已生成")

    creo_views_generated = artifacts.get("creo_views_generated", False)
    if creo_views_generated:
        emit_log(task_id, event_data, event_locks, 1, "Creo 截图与注释已采集")
    else:
        emit_log(task_id, event_data, event_locks, 1, "Creo 截图未生成，将按降级路径继续", level="warn")

    emit_step_complete(task_id, event_data, event_locks, 1, "PRT转换", f"共生成 {len(view_paths)} 张视图")
    emit_log(task_id, event_data, event_locks, 1, f"PRT转换完成，共 {len(view_paths)} 张视图")

    # Step 2: VLM-only feature extraction (Creo-primary / freecad-geo / FreeCAD fallback)
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
            mode_label = {"creo-primary": "Creo主路径", "freecad-geo": "FreeCAD+几何约束", "freecad": "FreeCAD-only"}.get(vlm_mode, vlm_mode)
            emit_log(task_id, event_data, event_locks, 2, f"VLM {mode_label} 特征提取完成: {vlm_text[:80]}...")
        else:
            emit_log(task_id, event_data, event_locks, 2, "VLM特征提取跳过（无图或API失败）", level="warn")
    else:
        emit_log(task_id, event_data, event_locks, 2, "FreeCAD 与 Creo 图片都不可用，跳过VLM特征提取", level="warn")

    # Merge: vlm (VLM output) + drawing number (geo data is embedded in VLM prompt, not output)
    parts = []
    if vlm_text:
        parts.append(vlm_text)
    parts.append(f"【图号】{prefix_hint or os.path.basename(filename)}")
    full_feature_text = "\n".join(parts)

    return {
        "artifacts": artifacts,
        "vlm_text": vlm_text,
        "vlm_mode": vlm_mode,
        "full_feature_text": full_feature_text,
        "gltf_path": gltf_path,
    }
