#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Smoke test for vlm_feature.py — covers all 4 VLM routing modes.

Usage:
    pytest backend/pipeline/test_vlm_feature.py -q                     # pytest mode
    python backend/pipeline/test_vlm_feature.py                        # script mode
    python backend/pipeline/test_vlm_feature.py <views_dir>            # also calls real VLM
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.pipeline.vlm_feature import (
    _DRAWING_FIELDS,
    _apply_drawing_size_reference_to_lwh,
    _assemble_prt_fields,
    _default_vlm_fields,
    _extract_creo_thread_specs,
    _extract_geometry_structured_fields,
    _extract_vlm_semantic_fields,
    _infer_dimensions_from_occ_vlm,
    _interval_avg_thickness,
    _merge_geometry_creo_vlm_fields,
    _normalize_vlm_output,
    _parse_structured_fields,
    _select_creo_images,
    _validate_drawing_fields,
    build_vlm_feature_text,
    extract_creo_only_vlm_features,
    extract_creo_primary_features,
    extract_dual_source_vlm_features,
    extract_freecad_geo_constrained_features,
    extract_vlm_features,
    parse_creo_task_txt,
)


# ============================================================
# Helper: mock the two routing extractors
# ============================================================

def _patch_vlm_paths(monkeypatch, creo_primary="", freecad_geo="", freecad=""):
    monkeypatch.setattr(
        "backend.pipeline.vlm_feature.extract_creo_primary_features",
        lambda *args, **kwargs: creo_primary,
    )
    monkeypatch.setattr(
        "backend.pipeline.vlm_feature.extract_freecad_geo_constrained_features",
        lambda *args, **kwargs: freecad_geo,
    )
    monkeypatch.setattr(
        "backend.pipeline.vlm_feature.extract_vlm_features",
        lambda *args, **kwargs: freecad,
    )


# ============================================================
# Routing mode tests
# ============================================================

def test_build_vlm_feature_text_reports_none_without_any_images(monkeypatch):
    _patch_vlm_paths(monkeypatch)
    result, mode = build_vlm_feature_text("/tmp/freecad", "/tmp/creo")
    assert result == ""
    assert mode == "none"


def test_build_vlm_feature_text_reports_creo_primary_when_creo_succeeds(monkeypatch):
    _patch_vlm_paths(monkeypatch, creo_primary="creo features")
    result, mode = build_vlm_feature_text("/tmp/freecad", "/tmp/creo")
    assert result == "creo features"
    assert mode == "creo-primary"


def test_build_vlm_feature_text_reports_freecad_when_creo_fails(monkeypatch):
    _patch_vlm_paths(monkeypatch, freecad="freecad features")
    result, mode = build_vlm_feature_text("/tmp/freecad", "/tmp/creo")
    assert result == "freecad features"
    assert mode == "freecad"


def test_build_vlm_feature_text_reports_freecad_when_no_creo_dir(monkeypatch):
    _patch_vlm_paths(monkeypatch, freecad="freecad features")
    result, mode = build_vlm_feature_text("/tmp/freecad", creo_views_dir="")
    assert result == "freecad features"
    assert mode == "freecad"


def test_build_vlm_feature_text_reports_none_with_empty_creo_dir(monkeypatch):
    _patch_vlm_paths(monkeypatch)
    result, mode = build_vlm_feature_text("/tmp/freecad", creo_views_dir="")
    assert result == ""
    assert mode == "none"


def test_build_vlm_feature_text_reports_freecad_geo_when_creo_fails_and_step_path_given(monkeypatch):
    _patch_vlm_paths(monkeypatch, freecad_geo="geo constrained features")
    result, mode = build_vlm_feature_text("/tmp/freecad", "/tmp/creo", step_path="/tmp/model.step")
    assert result == "geo constrained features"
    assert mode == "freecad-geo"


def test_build_vlm_feature_text_reports_freecad_when_creo_fails_and_geo_fails(monkeypatch):
    _patch_vlm_paths(monkeypatch, freecad="freecad features")
    result, mode = build_vlm_feature_text("/tmp/freecad", "/tmp/creo", step_path="/tmp/model.step")
    assert result == "freecad features"
    assert mode == "freecad"


# ============================================================
# Environment / file-missing tests (pytest style)
# ============================================================

def test_missing_env_returns_empty_string():
    """Returns '' when API env vars are not set."""
    saved = {k: os.environ.pop(k, None) for k in ("VISION_API_KEY", "VISION_API_BASE", "VISION_MODEL_ID")}
    try:
        result = extract_vlm_features("nonexistent_views_dir_for_test")
        assert result == "", f"Expected '', got: {repr(result)}"
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v


def test_missing_images_returns_empty_string():
    """Returns '' when views_dir exists but contains no PNG files."""
    env_keys = ("VISION_API_KEY", "VISION_API_BASE", "VISION_MODEL_ID")
    saved = {k: os.environ.get(k) for k in env_keys}
    os.environ.setdefault("VISION_API_KEY", "dummy")
    os.environ.setdefault("VISION_API_BASE", "http://dummy")
    os.environ.setdefault("VISION_MODEL_ID", "dummy-model")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            result = extract_vlm_features(tmp)
            assert result == "", f"Expected '', got: {repr(result)}"
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_dual_source_fallback_without_creo_images():
    """Dual-source and Creo-only both return '' when no Creo images exist."""
    env_keys = ("VISION_API_KEY", "VISION_API_BASE", "VISION_MODEL_ID")
    saved = {k: os.environ.get(k) for k in env_keys}
    os.environ.setdefault("VISION_API_KEY", "dummy")
    os.environ.setdefault("VISION_API_BASE", "http://dummy")
    os.environ.setdefault("VISION_MODEL_ID", "dummy-model")
    try:
        with tempfile.TemporaryDirectory() as freecad_tmp, tempfile.TemporaryDirectory() as creo_tmp:
            for name in ("front", "right", "top"):
                Path(freecad_tmp, f"{name}.png").write_bytes(b"fake")
            dual = extract_dual_source_vlm_features(freecad_tmp, creo_tmp, zhushi_text="尺寸见注释")
            creo_only = extract_creo_only_vlm_features(creo_tmp, zhushi_text="尺寸见注释")
            combined, mode = build_vlm_feature_text(freecad_tmp, creo_tmp, creo_txt_path="")
            assert dual == "", f"Expected dual-source fallback '', got: {repr(dual)}"
            assert creo_only == "", f"Expected Creo-only fallback '', got: {repr(creo_only)}"
            assert combined == "", f"Expected combined '', got: {repr(combined)}"
            assert mode == "none", f"Expected mode 'none', got: {repr(mode)}"
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_build_vlm_feature_text_without_any_images():
    """No FreeCAD or Creo images → mode none."""
    env_keys = ("VISION_API_KEY", "VISION_API_BASE", "VISION_MODEL_ID")
    saved = {k: os.environ.get(k) for k in env_keys}
    os.environ.setdefault("VISION_API_KEY", "dummy")
    os.environ.setdefault("VISION_API_BASE", "http://dummy")
    os.environ.setdefault("VISION_MODEL_ID", "dummy-model")
    try:
        with tempfile.TemporaryDirectory() as freecad_tmp, tempfile.TemporaryDirectory() as creo_tmp:
            result, mode = build_vlm_feature_text(freecad_tmp, creo_tmp)
            assert result == "", f"Expected '', got: {repr(result)}"
            assert mode == "none", f"Expected mode 'none', got: {repr(mode)}"
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_dual_source_prefers_creo_only_when_freecad_missing():
    """When FreeCAD has no images, Creo-only path is tried (and returns '' since API call fails with dummy keys)."""
    env_keys = ("VISION_API_KEY", "VISION_API_BASE", "VISION_MODEL_ID")
    saved = {k: os.environ.get(k) for k in env_keys}
    os.environ.setdefault("VISION_API_KEY", "dummy")
    os.environ.setdefault("VISION_API_BASE", "http://dummy")
    os.environ.setdefault("VISION_MODEL_ID", "dummy-model")
    try:
        with tempfile.TemporaryDirectory() as freecad_tmp, tempfile.TemporaryDirectory() as creo_tmp:
            Path(creo_tmp, "iso.png").write_bytes(b"fake")
            result, mode = build_vlm_feature_text(freecad_tmp, creo_tmp, creo_txt_path="")
            assert result == "", f"Expected '', got: {repr(result)}"
            assert mode == "none", f"Expected mode 'none' without successful API call, got: {repr(mode)}"
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ============================================================
# Metadata / utility tests
# ============================================================

def test_prepare_prt_artifacts_metadata_shape():
    from backend.prt_pipeline import read_creo_zhushi

    with tempfile.TemporaryDirectory() as tmp:
        zhushi = Path(tmp, "zhushi.txt")
        zhushi.write_text("Φ10 H7", encoding="utf-8")
        text = read_creo_zhushi(str(zhushi))
        assert text == "Φ10 H7", f"Expected zhushi text, got: {repr(text)}"

        missing = read_creo_zhushi(str(Path(tmp, "missing.txt")))
        assert missing == "", f"Expected '', got: {repr(missing)}"


# ============================================================
# parse_creo_task_txt tests
# ============================================================

def test_parse_creo_task_txt_missing_file():
    result = parse_creo_task_txt("/nonexistent/path.txt")
    assert result == {"主要外形尺寸": [], "特征尺寸": [], "倒角圆角": [], "技术要求": []}


def test_parse_creo_task_txt_empty_file(tmp_path):
    txt = tmp_path / "empty.txt"
    txt.write_text("", encoding="utf-8")
    result = parse_creo_task_txt(str(txt))
    assert result == {"主要外形尺寸": [], "特征尺寸": [], "倒角圆角": [], "技术要求": []}


def test_parse_creo_task_txt_extracts_3d_notes(tmp_path):
    content = (
        "Creo Model Annotation Export\nmodel: CREO_TASK\n\n"
        + "=" * 60 + "\nDIMENSIONS (Standard)\n" + "=" * 60 + "\n\n"
        + "=" * 60 + "\n3D NOTES\n" + "=" * 60 + "\n\n"
        + "-" * 60 + "\n"
        + "[3D NOTE] index=1\nnote_text:\n"
        + " line 1:        技术要求：\n"
        + " line 2: 1,去除毛刺飞边。\n\n"
        + "-" * 60 + "\n"
        + "[3D NOTE] index=2\nnote_text:\n"
        + " line 1: 全部清根\n\n"
    )
    txt = tmp_path / "notes.txt"
    txt.write_text(content, encoding="utf-8")
    result = parse_creo_task_txt(str(txt))
    assert len(result["技术要求"]) == 2
    assert "去除毛刺飞边" in result["技术要求"][0]  # label "技术要求：" line is stripped
    assert "全部清根" in result["技术要求"][1]
    assert result["主要外形尺寸"] == []


def test_parse_creo_task_txt_categorizes_dimensions(tmp_path):
    content = (
        "Creo Model Annotation Export\nmodel: CREO_TASK\n\n"
        + "=" * 60 + "\nDIMENSIONS (Standard)\n" + "=" * 60 + "\n\n"
        + "-" * 60 + "\n[DIMENSION] index=1\nsymbol: d1\ndisplayed_value: 0.9\ndimension_text:\n line 1: {0:@D}\n\n"
        + "-" * 60 + "\n[DIMENSION] index=2\nsymbol: ad5\ndisplayed_value: 249\ndimension_text:\n line 1: {0:@D}\n\n"
        + "-" * 60 + "\n[DIMENSION] index=3\nsymbol: d10\ndisplayed_value: 12.5\ndimension_text:\n line 1: {0:@D}\n\n"
        + "=" * 60 + "\n3D NOTES\n" + "=" * 60 + "\n"
    )
    txt = tmp_path / "dims.txt"
    txt.write_text(content, encoding="utf-8")
    result = parse_creo_task_txt(str(txt))
    assert "249" in result["主要外形尺寸"]
    assert any("12.5" in v for v in result["特征尺寸"])
    assert any("0.9" in v for v in result["倒角圆角"])


def test_parse_creo_task_txt_deduplicates_small_values(tmp_path):
    sep = "-" * 60 + "\n"
    content = (
        "Creo Model Annotation Export\nmodel: CREO_TASK\n\n"
        + "=" * 60 + "\nDIMENSIONS (Standard)\n" + "=" * 60 + "\n\n"
    )
    for i in range(1, 4):
        content += (
            sep
            + f"[DIMENSION] index={i}\nsymbol: d{i}\n"
            + "displayed_value: 0.9\ndimension_text:\n line 1: {0:@D}\n\n"
        )
    content += "=" * 60 + "\n3D NOTES\n" + "=" * 60 + "\n"
    txt = tmp_path / "dedup.txt"
    txt.write_text(content, encoding="utf-8")
    result = parse_creo_task_txt(str(txt))
    assert result["倒角圆角"] == ["0.9 × 3"]


def test_parse_creo_task_txt_radius_notation_goes_to_small_bucket(tmp_path):
    content = (
        "Creo Model Annotation Export\nmodel: CREO_TASK\n\n"
        + "=" * 60 + "\nDIMENSIONS (Standard)\n" + "=" * 60 + "\n\n"
        + "-" * 60 + "\n[DIMENSION] index=1\nsymbol: r1\ndisplayed_value: 5.0\n"
        + "dimension_text:\n line 1: {0:R}{1:@D}\n\n"
        + "=" * 60 + "\n3D NOTES\n" + "=" * 60 + "\n"
    )
    txt = tmp_path / "radius.txt"
    txt.write_text(content, encoding="utf-8")
    result = parse_creo_task_txt(str(txt))
    assert any("5" in v for v in result["倒角圆角"])
    assert result["特征尺寸"] == []


# ============================================================
# extract_creo_primary_features tests
# ============================================================

def test_extract_creo_primary_features_returns_empty_for_missing_dir(tmp_path):
    result = extract_creo_primary_features(
        str(tmp_path / "nonexistent"), str(tmp_path / "none.txt")
    )
    assert result == ""


def test_extract_creo_primary_features_builds_structured_prompt(monkeypatch, tmp_path):
    creo_dir = tmp_path / "creo_views"
    creo_dir.mkdir()
    (creo_dir / "主视图.jpg").write_bytes(b"\xff\xd8\xff")

    txt = tmp_path / "zhushi.txt"
    txt.write_text(
        "Creo Model Annotation Export\nmodel: CREO_TASK\n\n"
        + "=" * 60 + "\nDIMENSIONS (Standard)\n" + "=" * 60 + "\n\n"
        + "-" * 60 + "\n[DIMENSION] index=1\nsymbol: ad5\ndisplayed_value: 249\n"
        + "dimension_text:\n line 1: {0:@D}\n\n"
        + "=" * 60 + "\n3D NOTES\n" + "=" * 60 + "\n\n"
        + "-" * 60 + "\n[3D NOTE] index=1\nnote_text:\n"
        + " line 1: 技术要求：\n line 2: 1,去除毛刺飞边。\n\n",
        encoding="utf-8",
    )

    captured: dict = {}

    def fake_call(image_paths, prompt):
        captured["prompt"] = prompt
        captured["n_images"] = len(image_paths)
        return (
            "【零件名称】测试零件\n"
            "【形态】轴类\n"
            "【类型】轴套类\n"
            "【外形尺寸】249×80×20\n"
            "【通孔】无"
        )

    monkeypatch.setattr("backend.pipeline.vlm_feature._call_vlm_with_images", fake_call)

    result = extract_creo_primary_features(str(creo_dir), str(txt))

    assert "【零件名称】测试零件" in result
    assert "【关键尺寸】249" in result
    assert "【技术要求】" in result
    assert "【形态】轴类" in result
    # No STEP path → no geometry authority block; Creo txt context still present
    assert "技术要求" in captured["prompt"]
    assert "249" in captured["prompt"]
    assert "【外形尺寸】249×80×20" in result
    assert "【通孔】无" in result
    assert "【螺纹孔】无" in result
    assert "逐张扫描" in captured["prompt"]
    assert captured["n_images"] == 1

    # 新提示词：外形尺寸三步推理
    assert "第一步" in captured["prompt"], "外形尺寸三步推理缺失"
    assert "视图类型" in captured["prompt"], "视图类型映射指令缺失"
    # 新提示词：公差扫描清单
    assert "公差符号" in captured["prompt"], "尺寸公差扫描清单缺失"
    assert "公差框格" in captured["prompt"], "形位公差框格扫描指令缺失"


def test_extract_creo_primary_features_uses_six_filtered_creo_images(monkeypatch, tmp_path):
    creo_dir = tmp_path / "creo_views"
    creo_dir.mkdir()
    for name in (
        "主视图.jpg",
        "左视图.jpg",
        "俯视图.jpg",
        "A-A.jpg",
        "B-B.jpg",
        "C-C.jpg",
        "技术要求.jpg",
        "CREO_TASK_default.jpg",
        "全部默认.jpg",
    ):
        (creo_dir / name).write_bytes(b"fake")

    captured = {}

    def fake_call(image_paths, prompt):
        captured["names"] = [p.name for p in image_paths]
        return "【零件名称】测试件\n【形态】板件\n【外形尺寸】100×80×10"

    monkeypatch.setattr("backend.pipeline.vlm_feature._call_vlm_with_images", fake_call)

    result = extract_creo_primary_features(str(creo_dir), "/nonexistent/txt.txt")

    assert captured["names"] == ["主视图.jpg", "左视图.jpg", "俯视图.jpg", "A-A.jpg", "B-B.jpg", "C-C.jpg"]
    assert "技术要求.jpg" not in captured["names"]
    assert "CREO_TASK_default.jpg" not in captured["names"]
    assert "全部默认.jpg" not in captured["names"]
    assert "【外形尺寸】100×80×10" in result


def test_extract_creo_primary_features_works_without_txt(monkeypatch, tmp_path):
    creo_dir = tmp_path / "creo_views"
    creo_dir.mkdir()
    (creo_dir / "主视图.jpg").write_bytes(b"\xff\xd8\xff")

    monkeypatch.setattr(
        "backend.pipeline.vlm_feature._call_vlm_with_images",
        lambda image_paths, prompt: "【零件名称】无\n【形态】壳体",
    )

    result = extract_creo_primary_features(str(creo_dir), "/nonexistent/txt.txt")
    assert "【零件名称】无" in result
    assert "【形态】壳体" in result
    assert "【关键尺寸】无" in result


# ============================================================
# extract_freecad_geo_constrained_features tests
# ============================================================

def test_extract_freecad_geo_constrained_missing_views(tmp_path):
    result = extract_freecad_geo_constrained_features(str(tmp_path / "nonexistent"), "/tmp/step.step")
    assert result == ""


def test_extract_freecad_geo_constrained_falls_back_to_unconstrained_when_missing_step(monkeypatch, tmp_path):
    views_dir = tmp_path / "views"
    views_dir.mkdir()
    for name in ("front.png", "right.png", "top.png"):
        (views_dir / name).write_bytes(b"\xff\xd8\xff")

    captured = {}
    def fake_call(image_paths, prompt):
        captured["n"] = len(image_paths)
        captured["prompt"] = prompt
        return "【零件名称】测试件\n【形态】块状"

    monkeypatch.setattr("backend.pipeline.vlm_feature._call_vlm_with_images", fake_call)

    result = extract_freecad_geo_constrained_features(str(views_dir), "/nonexistent.step")
    assert "【零件名称】测试件" in result
    assert "【形态】块状" in result
    assert captured["n"] == 3
    assert "权威来源" not in captured["prompt"]


def test_extract_freecad_geo_constrained_includes_geo_in_prompt_when_step_ok(monkeypatch, tmp_path):
    views_dir = tmp_path / "views"
    views_dir.mkdir()
    for name in ("front.png", "right.png", "top.png"):
        (views_dir / name).write_bytes(b"\xff\xd8\xff")

    step_file = tmp_path / "model.step"
    step_file.write_text("dummy step content", encoding="utf-8")

    captured = {}
    def fake_call(image_paths, prompt):
        captured["n"] = len(image_paths)
        captured["prompt"] = prompt
        return "【零件名称】测试件\n【形态】块状"

    monkeypatch.setattr("backend.pipeline.vlm_feature._call_vlm_with_images", fake_call)
    monkeypatch.setattr(
        "backend.prt_pipeline.extract_geometry_features",
        lambda step_path: "【尺寸】100×50×30mm",
    )

    result = extract_freecad_geo_constrained_features(str(views_dir), str(step_file))
    assert "【零件名称】测试件" in result
    assert "【形态】块状" in result
    assert "禁止推测或修改" in captured["prompt"]
    assert "100×50×30" in captured["prompt"]
    assert captured["n"] == 3


# ============================================================
# _assemble_prt_fields / _parse_structured_fields tests
# ============================================================

def test_parse_structured_fields_normal():
    text = "【零件名称】轴\n【形态】回转体\n【类型】轴套类"
    result = _parse_structured_fields(text)
    assert result["零件名称"] == "轴"
    assert result["形态"] == "回转体"
    assert result["类型"] == "轴套类"


def test_parse_structured_fields_empty():
    assert _parse_structured_fields("") == {}
    assert _parse_structured_fields("无格式文本") == {}


def test_extract_vlm_semantic_fields_keeps_engineering_drawing_fields(monkeypatch, tmp_path):
    image = tmp_path / "主视图.jpg"
    image.write_bytes(b"fake")

    monkeypatch.setattr(
        "backend.pipeline.vlm_feature._call_vlm_with_images",
        lambda image_paths, prompt: (
            "【外形尺寸】373×238×14\n"
            "【通孔】24-φ2.8\n"
            "【螺纹孔】26-M2.5 孔深8.1 底孔深9.1\n"
            "【零件名称】铝合金结构板\n"
            "【形态】矩形平板件\n"
            "【类型】航天结构件-电子设备安装板"
        ),
    )

    result = _extract_vlm_semantic_fields([image], "prompt")

    assert result["外形尺寸"] == "373×238×14"
    assert result["通孔"] == "24-φ2.8"
    assert result["螺纹孔"] == "26-M2.5 孔深8.1 底孔深9.1"
    assert result["零件名称"] == "铝合金结构板"
    assert result["形态"] == "矩形平板件"
    assert result["类型"] == "航天结构件-电子设备安装板"
    for field in _DRAWING_FIELDS:
        assert field in result


def test_extract_vlm_semantic_fields_defaults_missing_engineering_fields_to_none(monkeypatch, tmp_path):
    image = tmp_path / "主视图.jpg"
    image.write_bytes(b"fake")

    monkeypatch.setattr(
        "backend.pipeline.vlm_feature._call_vlm_with_images",
        lambda image_paths, prompt: "【零件名称】无\n【形态】壳体",
    )

    result = _extract_vlm_semantic_fields([image], "prompt")

    assert result["零件名称"] == "无"
    assert result["形态"] == "壳体"
    assert result["外形尺寸"] == "无"
    assert result["通孔"] == "无"
    assert result["刻字"] == "无"


def test_validate_drawing_fields_adds_warnings_without_modifying_values():
    fields = {
        "外形尺寸": "373×238×140",
        "通孔": "2-φ0.8；1-φ60",
        "螺纹孔": "4-M7 孔深10",
        "刻字": "字高3[?]深0.3内容X509",
    }

    result = _validate_drawing_fields(fields)

    assert result["外形尺寸"] == "373×238×140"
    assert result["通孔"] == "2-φ0.8；1-φ60"
    assert result["螺纹孔"] == "4-M7 孔深10"
    assert result["_has_warnings"] is True
    assert any("厚度 140.0mm 超过100mm" in w for w in result["_warnings"])
    assert any("螺纹规格 M7 非标准系列" in w for w in result["_warnings"])
    assert any("通孔直径 φ0.8 小于1mm" in w for w in result["_warnings"])
    assert any("通孔直径 φ60.0 超过50mm" in w for w in result["_warnings"])
    assert any("刻字" in w for w in result["_warnings"])


def test_validate_drawing_fields_accepts_normal_values():
    fields = {
        "外形尺寸": "373×238×14",
        "通孔": "24-φ2.8；20-φ3",
        "螺纹孔": "26-M2.5 孔深8.1 底孔深9.1",
    }

    result = _validate_drawing_fields(fields)

    assert result["_has_warnings"] is False
    assert result["_warnings"] == []


def test_assemble_prt_fields_full():
    txt = {"技术要求": ["去除毛刺"], "主要外形尺寸": ["249"], "特征尺寸": ["12.5"], "倒角圆角": ["0.9 × 3", "R5"]}
    vlm = "【零件名称】法兰\n【形态】盘状\n【类型】法兰盘类\n【外圆与内孔】外圆Φ120\n【螺纹与螺孔】4×M8\n【热处理与探伤】调质\n【其他特征】键槽"
    result = _assemble_prt_fields(txt, vlm)
    assert "【零件名称】法兰" in result
    assert "【形态】盘状" in result
    assert "【类型】法兰盘类" in result
    assert "【技术要求】去除毛刺" in result
    assert "【关键尺寸】249；12.5" in result or "【关键尺寸】12.5；249" in result
    assert "【外圆与内孔】外圆Φ120" in result
    assert "【螺纹与螺孔】4×M8" in result
    assert "【倒角】0.9 × 3" in result
    assert "【热处理与探伤】调质" in result
    assert "【过渡特征】R5" in result
    assert "【其他特征】键槽" in result


def test_assemble_prt_fields_empty_txt():
    result = _assemble_prt_fields({}, "【零件名称】壳体\n【形态】箱体")
    assert "【零件名称】壳体" in result
    assert "【关键尺寸】无" in result
    assert "【技术要求】无" in result
    assert "【倒角】无" in result


def test_merge_geometry_creo_vlm_fields_outputs_engineering_drawing_fields():
    geometry = {"关键尺寸": "长 380mm × 宽 240mm × 高 14mm", "外圆与内孔": "无", "螺纹与螺孔": "孔数量:44", "其他特征": "形状分类:板类"}
    creo = {"技术要求": ["去除毛刺"], "主要外形尺寸": ["373", "238"], "特征尺寸": ["14"], "倒角圆角": ["0.5 × 4", "R3"]}
    vlm = _default_vlm_fields()
    vlm.update({
        "零件名称": "铝合金结构板",
        "形态": "矩形平板件",
        "类型": "航天结构件-电子设备安装板",
        "外形尺寸": "373×238×14",
        "通孔": "24-φ2.8",
        "沉孔沉槽": "φ5.6×90°",
        "螺纹孔": "26-M2.5 孔深8.1 底孔深9.1",
        "特殊孔": "无",
        "尺寸公差": "外形±0.2",
        "形位公差": "平面度0.05",
        "表面粗糙度": "未注Ra3.2",
        "表面处理": "导电阳极化处理",
        "热处理与探伤": "无",
        "刻字": "字高3深0.3内容X509",
        "其他特征": "有镂空槽",
    })

    result = _merge_geometry_creo_vlm_fields(geometry, creo, vlm)

    assert "【关键尺寸】373；238；14；长 373mm × 宽 238mm × 高 14mm" in result
    assert "【外形尺寸】373×238×14" in result
    assert "【通孔】24-φ2.8" in result
    assert "【沉孔沉槽】φ5.6×90°" in result
    assert "【螺纹孔】26-M2.5 孔深8.1 底孔深9.1" in result
    assert "【尺寸公差】外形±0.2" in result
    assert "【表面处理】导电阳极化处理" in result
    assert "【刻字】字高3深0.3内容X509" in result
    assert "【过渡特征】R3" in result
    assert "【其他特征】形状分类:板类；有镂空槽" in result


def test_merge_geometry_creo_vlm_fields_outputs_warning_when_drawing_values_suspicious():
    vlm = _default_vlm_fields()
    vlm.update({"外形尺寸": "373×238×140", "通孔": "1-φ60", "螺纹孔": "4-M7"})

    result = _merge_geometry_creo_vlm_fields({}, {}, vlm)

    assert "【图纸提取警告】" in result
    assert "厚度 140.0mm 超过100mm" in result
    assert "螺纹规格 M7 非标准系列" in result


def test_merge_geometry_creo_vlm_fields_skips_drawing_size_reference_when_disabled():
    """VLM 外形尺寸 已暂停影响关键尺寸 — 仅使用 Creo 锚定 + OCC 几何值"""
    geometry = {"关键尺寸": "长 30.9mm × 宽 238mm × 高 140mm", "外圆与内孔": "", "螺纹与螺孔": "", "其他特征": ""}
    creo = {
        "技术要求": [],
        "主要外形尺寸": ["270", "238", "227", "163", "150.5", "147.4", "144", "131", "119", "118", "114.5", "113.5"],
        "特征尺寸": ["90.6", "89.65", "88.28", "78.5", "74.87", "72.27", "62.25", "2.05 × 7", "2.5 × 12", "3 × 5", "3.2", "3.5 × 2", "4 × 2", "4.75 × 3", "4.92 × 6", "5 × 8", "5.5 × 6", "6.23", "6.24", "6.25", "6.32 × 2", "6.33", "6.5 × 2", "6.57", "6.67 × 8", "7.3", "8 × 4", "8.35", "11.5 × 3", "12.91", "15 × 6", "16", "19", "20.72", "21.29", "21.57", "21.9", "30.9 × 3", "33.9", "36 × 4", "42.5 × 2"],
        "倒角圆角": [],
    }
    vlm = _default_vlm_fields()
    vlm.update({"外形尺寸": "238×163 | 227×150.5 | 227×114.5 | 227×78.5 | 227×42.5 | 227×6.5 | 147.4×11.5×8.35 | 8×131×6"})

    result = _merge_geometry_creo_vlm_fields(geometry, creo, vlm)

    # VLM 外形尺寸 不再修正关键尺寸 — OCC 锚定值直接使用
    assert "长 30.9mm × 宽 238mm × 高 144mm" in result
    assert "长 19.6mm × 宽 238mm × 高 163mm" not in result


def test_apply_drawing_size_reference_corrects_second_axis_when_best_group_directly_matches_max():
    # "240×163（来源：第一张视图）" — best group's axis[0]=240 exactly matches max(current).
    # Drawing labels second-large as 163, but OCC has 167.6. Diff=4.6 > _DS_AXIS2_REFINE_TOL=4 → override.
    result = _apply_drawing_size_reference_to_lwh(
        "长 21mm × 宽 240mm × 高 167.6mm",
        "240×163（来源：第一张视图）| 226×148（来源：第四张视图）| 167.6×8（来源：第三张视图）| 159.5×1（来源：第二张视图）",
        "长 23mm × 宽 240mm × 高 167.6mm",
    )
    assert result == "长 21mm × 宽 240mm × 高 163mm"


def test_apply_drawing_size_reference_corrects_second_axis_when_largest_dim_is_stripped():
    # "(240)" is stripped by parenthetical removal, leaving no group with axis[0]≈240.
    # Best group has axis[0]=167.6 ≈ current second-large (167.6) — cross-section view.
    # Its axis[1]=163 is the labeled dimension and should override OCC's 167.6.
    result = _apply_drawing_size_reference_to_lwh(
        "长 21mm × 宽 240mm × 高 167.6mm",
        "(240)|226|167.6 × 163|148 × 159.5[?]",
        "长 23mm × 宽 240mm × 高 167.6mm",
    )
    assert result == "长 21mm × 宽 240mm × 高 163mm"


def test_apply_drawing_size_reference_uses_axis_value_when_stored_thickness_is_feature_detail():
    # "220×29.9（第三视图）×7.4[?]（第六视图）": two views concatenated without '|'.
    # 7.4 < 29.9*0.5 — it's a feature detail, 29.9 is the real thickness.
    result = _apply_drawing_size_reference_to_lwh(
        "长 21.8mm × 宽 238mm × 高 163mm",
        "238×163（第一张视图）|226.2×156.6（第五张视图）|220×29.9（第三张视图）×7.4[?]（第六张视图）",
        "长 21.8mm × 宽 238mm × 高 163mm",
    )
    assert result == "长 29.9mm × 宽 238mm × 高 163mm"


def test_apply_drawing_size_reference_skips_face_view_slot_depth():
    # Drawing shows "238×163×6.5" — group axis[0]=238 matches max(current), and 6.5 << current_thickness.
    # This is a slot/pocket depth on the largest face, not overall part thickness.
    # Interval-median estimate (~14.88mm) should be preserved unchanged.
    result = _apply_drawing_size_reference_to_lwh(
        "长 14.88mm × 宽 238mm × 高 163mm",
        "238mm × 163mm × 6.5mm；227mm × 150.5mm × 6.5mm",
        "长 97.0mm × 宽 238mm × 高 163mm",
    )
    assert result == "长 14.9mm × 宽 238mm × 高 163mm"


def test_apply_drawing_size_reference_uses_consistent_signal_directly():
    # Drawing shows "360×12.5×3" and "218×12.5×3": ×3 is a view-count multiplier.
    # _resolve_t detects 3 < 12.5*0.5 → returns 12.5 for both groups.
    # Both groups agree → thickness_consistent=True → use 12.5 directly (no blend).
    result = _apply_drawing_size_reference_to_lwh(
        "长 31.2mm × 宽 380mm × 高 238mm",
        "380×238（主视图）|360×12.5×3（第六视图）|218×12.5×3（第二、四视图）",
        "长 31.2mm × 宽 380mm × 高 238mm",
    )
    assert result == "长 12.5mm × 宽 380mm × 高 238mm"



def test_apply_drawing_size_reference_face_view_detection_uses_drawing_max_not_occ():
    # Case 21 scenario: synthetic OCC inflates largest dim to 270 (270×238×163).
    # Drawing says "238×163×6.5 | 227×150.5×6.5" — both groups have thickness 6.5 which
    # is a face-view feature depth, not overall part thickness.
    # interval_median gives cur_t ≈ 19mm.
    # is_face_view_depth must fire even when max(current)=270 ≠ 238 (drawing max).
    result = _apply_drawing_size_reference_to_lwh(
        "长 270mm × 宽 163mm × 高 19mm",
        "238×163×6.5 | 227×150.5×6.5",
        "长 270mm × 宽 238mm × 高 163mm",
    )
    high_part = result.split("高 ")[1]
    assert high_part.startswith("19") or high_part.startswith("18") or high_part.startswith("20")


def test_assemble_prt_fields_no_vlm():
    txt = {"技术要求": ["去毛刺"], "主要外形尺寸": ["200"], "倒角圆角": ["1.0 × 5"]}
    result = _assemble_prt_fields(txt, "")
    assert "【零件名称】无" in result
    assert "【形态】无" in result
    assert "【关键尺寸】200" in result
    assert "【技术要求】去毛刺" in result
    assert "【倒角】1.0 × 5" in result
    assert "【过渡特征】无" in result


# ============================================================
# Three-layer feature assembly tests
# ============================================================


def test_extract_geometry_structured_fields_from_text():
    """_extract_geometry_structured_fields maps known geometry text correctly."""
    fields = _extract_geometry_structured_fields("")
    assert fields["关键尺寸"] == ""
    assert fields["外圆与内孔"] == ""
    assert fields["螺纹与螺孔"] == ""


def test_merge_geometry_priority_over_empty_vlm(monkeypatch):
    """几何字段存在时，VLM 不得覆盖尺寸类字段。"""
    geo = {"关键尺寸": "长100mm × 宽50mm × 高30mm", "外圆与内孔": "圆柱面半径25mm", "螺纹与螺孔": "孔数量:4", "过渡特征": "", "其他特征": ""}
    # VLM semantic returns empty — fields should come from geometry
    result = _merge_geometry_creo_vlm_fields(geo, {}, {"零件名称": "无", "形态": "无", "类型": "无", "热处理与探伤": "无", "其他特征": "无"})
    assert "长100mm" in result
    assert "圆柱面半径25mm" in result
    assert "孔数量:4" in result


def test_creo_txt_supplements_tolerance_and_thread():
    """几何给主尺寸，Creo txt 补关键尺寸和螺纹规格。"""
    geo = {"关键尺寸": "长100mm", "外圆与内孔": "", "螺纹与螺孔": "孔数量:4", "过渡特征": "", "其他特征": ""}
    creo = {"主要外形尺寸": ["100", "50"], "特征尺寸": ["12.5"], "倒角圆角": ["1.0 × 3", "R5"], "技术要求": ["技术要求：\n1.去毛刺\n2.4-M6深12螺纹孔"]}
    vlm = {"零件名称": "法兰", "形态": "盘状", "类型": "法兰盘类", "热处理与探伤": "调质", "其他特征": "键槽"}
    result = _merge_geometry_creo_vlm_fields(geo, creo, vlm)
    assert "长100mm" in result  # geometry main dimension
    assert "100" in result and "50" in result  # creo supplement
    assert "去毛刺" in result  # creo tech requirement
    assert "1.0 × 3" in result  # creo chamfer
    assert "R5" in result  # creo fillet
    assert "法兰" in result  # vlm semantic
    assert "盘状" in result
    assert "法兰盘类" in result
    assert "调质" in result
    # Creo thread specs supplement
    assert "M6" in result  # creo thread specs in 【螺纹与螺孔】


def test_extract_creo_thread_specs_from_tech_notes():
    """从技术要求中提取螺纹规格。"""
    creo = {"技术要求": ["技术要求：\n1.去毛刺\n2.4-M6深12螺纹孔\n3.攻丝", "全部清根"]}
    result = _extract_creo_thread_specs(creo)
    assert "M6" in result
    assert "4-M6" in result or "M6" in result
    assert "螺纹孔" in result or "攻丝" in result


def test_extract_creo_thread_specs_returns_empty_when_no_thread():
    """无螺纹相关内容时返回空字符串。"""
    creo = {"技术要求": ["去毛刺", "全部清根"]}
    result = _extract_creo_thread_specs(creo)
    assert result == ""


def test_vlm_only_fills_semantic_fields():
    """VLM 返回尺寸类字段时也被丢弃。"""
    # Simulate VLM over-returning (old behavior)
    vlm = {"零件名称": "轴", "形态": "回转体", "类型": "轴类", "热处理与探伤": "无", "其他特征": "无",
           "外圆与内孔": "φ50mm", "螺纹与螺孔": "M6"}  # These should be dropped
    geo = {"关键尺寸": "", "外圆与内孔": "", "螺纹与螺孔": "", "过渡特征": "", "其他特征": ""}
    result = _merge_geometry_creo_vlm_fields(geo, {}, vlm)
    # Semantic fields should appear
    assert "【零件名称】轴" in result
    assert "【形态】回转体" in result
    # Dimension fields should NOT come from VLM — should be "无"
    assert "【外圆与内孔】无" in result
    assert "【螺纹与螺孔】无" in result


def test_missing_geometry_uses_creo_for_available_fields():
    """几何缺失时，Creo txt 可填对应字段。"""
    geo = {"关键尺寸": "", "外圆与内孔": "", "螺纹与螺孔": "", "过渡特征": "", "其他特征": ""}
    creo = {"主要外形尺寸": ["200", "150"], "特征尺寸": [], "倒角圆角": ["2.0 × 4"], "技术要求": []}
    vlm = {"零件名称": "无", "形态": "无", "类型": "无", "热处理与探伤": "无", "其他特征": "无"}
    result = _merge_geometry_creo_vlm_fields(geo, creo, vlm)
    assert "200" in result
    assert "150" in result
    assert "2.0 × 4" in result


def test_all_missing_fields_fall_back_to_wu():
    """三层都缺失时，字段输出 '无'。"""
    result = _merge_geometry_creo_vlm_fields({}, {}, {"零件名称": "无", "形态": "无", "类型": "无", "热处理与探伤": "无", "其他特征": "无"})
    parsed = _parse_structured_fields(result)
    for key, val in parsed.items():
        assert val == "无", f"Field {key} should be '无', got '{val}'"


def test_extract_geometry_structured_fields_returns_empty_for_invalid():
    """无效的 step_path 返回空字段字典。"""
    result = _extract_geometry_structured_fields("")
    assert isinstance(result, dict)
    assert all(v == "" for v in result.values())


def test_extract_vlm_semantic_fields_returns_defaults_on_missing_images():
    """图片路径不存在时 VLM semantic 字段返回默认无值。"""
    result = _extract_vlm_semantic_fields([Path("/nonexistent/test.png")])
    assert isinstance(result, dict)
    assert result["零件名称"] == "无"
    assert result["形态"] == "无"
    assert result["类型"] == "无"
    assert result["热处理与探伤"] == "无"
    assert result["其他特征"] == "无"


# ============================================================
# Real VLM integration test (manual, requires .env)
# ============================================================

def real_vlm_test(views_dir: str):
    """Calls real VLM API with actual view images. Requires .env configured."""
    from dotenv import load_dotenv
    load_dotenv()
    result = extract_vlm_features(views_dir)
    print(f"\n--- VLM Output ({len(result)} chars) ---")
    print(result or "(empty — check API config and image paths)")
    print("---")


# ============================================================
# _validate_and_mark_dimensions tests
# ============================================================

def test_validate_and_mark_dimensions_flags_implausible_thickness():
    from backend.pipeline.vlm_feature import _validate_and_mark_dimensions
    fields = {"外形尺寸": "长373mm×宽238mm×高140mm"}
    result = _validate_and_mark_dimensions(fields, "test_key_1")
    assert "[?]" in result["外形尺寸"], "140mm thickness should be flagged"


def test_validate_and_mark_dimensions_accepts_normal_thickness():
    from backend.pipeline.vlm_feature import _validate_and_mark_dimensions
    fields = {"外形尺寸": "长373mm×宽238mm×高14mm"}
    result = _validate_and_mark_dimensions(fields, "test_key_2")
    assert "[?]" not in result["外形尺寸"]


def test_validate_and_mark_dimensions_locks_on_fluctuation():
    from backend.pipeline.vlm_feature import _validate_and_mark_dimensions, _dimension_cache
    key = "test_fluctuation_key"
    _dimension_cache.clear()
    # First call — establishes baseline
    fields1 = {"外形尺寸": "长373mm×宽238mm×高14mm"}
    r1 = _validate_and_mark_dimensions(fields1, key)
    assert r1["外形尺寸"] == "长373mm×宽238mm×高14mm"
    # Second call — 20% deviation triggers lock, returns cached
    fields2 = {"外形尺寸": "长450mm×宽280mm×高18mm"}
    r2 = _validate_and_mark_dimensions(fields2, key)
    assert r2["外形尺寸"] == "长373mm×宽238mm×高14mm"
    _dimension_cache.clear()


# ============================================================
# Script-mode runner (preserved for backward compatibility)
# ============================================================

if __name__ == "__main__":
    test_missing_env_returns_empty_string()
    test_missing_images_returns_empty_string()
    test_dual_source_fallback_without_creo_images()
    test_build_vlm_feature_text_without_any_images()
    test_dual_source_prefers_creo_only_when_freecad_missing()
    test_prepare_prt_artifacts_metadata_shape()
    # Run pytest-style routing mode tests via script runner too
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "pytest", __file__, "-v", "--tb=short"],
        capture_output=True, text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        sys.exit(result.returncode)
    if len(sys.argv) > 1:
        real_vlm_test(sys.argv[1])
    else:
        print("\nTip: pass <views_dir> to also test real VLM call")
    print("\nAll tests passed.")


# ============================================================
# _select_creo_images tests
# ============================================================

def test_select_creo_images_returns_all_non_excluded_when_few(tmp_path):
    creo_dir = tmp_path / "creo_views"
    creo_dir.mkdir()
    for name in ("主视图.jpg", "俯视图.jpg", "技术要求.jpg", "全部默认.jpg"):
        (creo_dir / name).write_bytes(b"fake")
    result = _select_creo_images(creo_dir, max_n=6)
    assert [p.name for p in result] == ["主视图.jpg", "俯视图.jpg"]


def test_select_creo_images_excludes_default_and_technical_requirement_images(tmp_path):
    creo_dir = tmp_path / "creo_views"
    creo_dir.mkdir()
    for name in (
        "主视图.jpg",
        "左视图.jpg",
        "俯视图.jpg",
        "技术要求.jpg",
        "CREO_TASK_default.jpg",
        "全部默认.jpg",
    ):
        (creo_dir / name).write_bytes(b"fake")

    selected = _select_creo_images(creo_dir, max_n=6)
    selected_names = [p.name for p in selected]

    assert selected_names == ["主视图.jpg", "左视图.jpg", "俯视图.jpg"]


def test_select_creo_images_prefers_main_left_top_and_abc_then_standard_fill(tmp_path):
    creo_dir = tmp_path / "creo_views"
    creo_dir.mkdir()
    for name in (
        "后视图.jpg",
        "B-B.jpg",
        "右视图.jpg",
        "主视图.jpg",
        "C-C.jpg",
        "左视图.jpg",
        "俯视图.jpg",
        "A-A.jpg",
        "其他视图.jpg",
    ):
        (creo_dir / name).write_bytes(b"fake")

    selected = _select_creo_images(creo_dir, max_n=6)
    selected_names = [p.name for p in selected]

    assert selected_names == ["主视图.jpg", "左视图.jpg", "俯视图.jpg", "A-A.jpg", "B-B.jpg", "C-C.jpg"]


def test_select_creo_images_fills_missing_sections_with_other_standard_views(tmp_path):
    creo_dir = tmp_path / "creo_views"
    creo_dir.mkdir()
    for name in (
        "主视图.jpg",
        "左视图.jpg",
        "俯视图.jpg",
        "右视图.jpg",
        "后视图.jpg",
        "仰视图.jpg",
        "其他视图.jpg",
    ):
        (creo_dir / name).write_bytes(b"fake")

    selected = _select_creo_images(creo_dir, max_n=6)
    selected_names = [p.name for p in selected]

    assert selected_names == ["主视图.jpg", "左视图.jpg", "俯视图.jpg", "右视图.jpg", "后视图.jpg", "仰视图.jpg"]


def test_select_creo_images_all_unranked_falls_back_to_sorted(tmp_path):
    creo_dir = tmp_path / "creo_views"
    creo_dir.mkdir()
    for name in ("其他B.jpg", "其他A.jpg"):
        (creo_dir / name).write_bytes(b"fake")
    result = _select_creo_images(creo_dir, max_n=2)
    assert [p.name for p in result] == ["其他A.jpg", "其他B.jpg"]


# ============================================================
# _normalize_vlm_output tests
# ============================================================


def test_normalize_vlm_output_fills_missing_fields():
    result = _normalize_vlm_output({"零件名称": "轴"})
    assert result["零件名称"] == "轴"
    assert result["外形尺寸"] == "无"
    assert result["刻字"] == "无"
    assert result["通孔"] == "无"


def test_normalize_vlm_output_unifies_empty_variants():
    result = _normalize_vlm_output({
        "零件名称": "无。",
        "形态": "暂无",
        "类型": "N/A",
        "热处理与探伤": "",
        "其他特征": "None",
    })
    assert result["零件名称"] == "无"
    assert result["形态"] == "无"
    assert result["类型"] == "无"
    assert result["热处理与探伤"] == "无"
    assert result["其他特征"] == "无"


def test_normalize_vlm_output_standardizes_overall_dims():
    result = _normalize_vlm_output({"外形尺寸": "373 x 238*140"})
    assert result["外形尺寸"] == "373×238×140"
    # 推测/来源 前缀保留
    result2 = _normalize_vlm_output({"外形尺寸": "推测:120*80*15(来源：主视图轮廓)"})
    assert "推测:" in result2["外形尺寸"]
    assert "来源" in result2["外形尺寸"]
    assert "120×80×15" in result2["外形尺寸"]


def test_normalize_overall_dims_strips_pipe_laiyuan_suffix():
    # VLM appends |来源：... explanation after dimension groups — strip it so it
    # doesn't contaminate dim_pool with internal-feature numbers like 172/84/75.
    from backend.pipeline.vlm_feature import _normalize_overall_dims
    val = _normalize_overall_dims(
        "282×129×21.5|来源：图1总外轮廓标注282（）、129（）；图4侧视图标注21.5为厚度方向通尺寸；其余标注尺寸如172/84/75等为内部特征尺寸"
    )
    assert val == "282×129×21.5"


def test_infer_h_single_group_large_diff_no_close_pool_uses_midpoint():
    # With max_delta=5 in single-group large-diff path, snap(184.5) should NOT
    # land on 172 (dist=12.5 > 5). When nothing is within 5mm, returns midpoint.
    result = _infer_dimensions_from_occ_vlm(
        "长282×宽44.0×高240",
        "282×129×21.5",
        dim_pool="282；172；129；44；21.5",  # no value within 5mm of 184.5
    )
    assert result is not None
    assert result["H"] == pytest.approx(184.5)  # unsnapped midpoint, NOT 172


# ============================================================
# _parse_structured_fields multi-line VLM output tests
# ============================================================

def test_parse_structured_fields_extracts_zhengtiwaixing_from_multiline_dim_block():
    """整体外形尺寸 line inside multi-line 外形尺寸 block should be captured."""
    text = (
        "【外形尺寸】\n"
        "视图类型：\n"
        "1. 主视图，长向标注238\n"
        "整体外形尺寸：238×163×8.35|270×163×8[?]\n\n"
        "【通孔】无\n"
    )
    result = _parse_structured_fields(text)
    assert result.get("外形尺寸") == "238×163×8.35|270×163×8[?]"


def test_parse_structured_fields_extracts_nextline_field_values():
    """Value on next line after field name (no same-line content) should be captured."""
    text = (
        "【通孔】\n"
        "6-∅3.2；∅2.0；∅6.5\n\n"
        "【螺纹孔】\n"
        "4-M3 孔深8\n"
        "【零件名称】轴套件\n"
    )
    result = _parse_structured_fields(text)
    assert result.get("通孔") == "6-∅3.2；∅2.0；∅6.5"
    assert result.get("螺纹孔") == "4-M3 孔深8"
    assert result.get("零件名称") == "轴套件"  # same-line still works


# ============================================================
# Creo txt → 刻字/表面处理 fallback tests
# ============================================================

def test_merge_extracts_kezi_from_creo_tech_req_when_vlm_is_none():
    """刻字 falls back to Creo txt 技术要求 when VLM returns '无'."""
    creo = {
        "技术要求": ["7,仰视图刻字，宋体，高5、2，深0.3，涂黑漆。"],
        "主要外形尺寸": [], "特征尺寸": [], "倒角圆角": [],
    }
    vlm = _default_vlm_fields()  # 刻字 == "无"
    result = _merge_geometry_creo_vlm_fields({}, creo, vlm)
    parsed = _parse_structured_fields(result)
    assert parsed.get("刻字", "无") != "无", "刻字 should be extracted from 技术要求"
    assert "刻字" in parsed.get("刻字", "")


def test_merge_vlm_kezi_takes_priority_over_creo_fallback():
    """When VLM provides 刻字, do not override with Creo txt."""
    creo = {
        "技术要求": ["7,仰视图刻字，宋体，高5、2，深0.3，涂黑漆。"],
        "主要外形尺寸": [], "特征尺寸": [], "倒角圆角": [],
    }
    vlm = _default_vlm_fields()
    vlm["刻字"] = "字高3深0.3内容X509"
    result = _merge_geometry_creo_vlm_fields({}, creo, vlm)
    parsed = _parse_structured_fields(result)
    assert parsed.get("刻字") == "字高3深0.3内容X509"


def test_merge_extracts_surface_treatment_from_creo_tech_req_when_vlm_is_none():
    """表面处理 falls back to Creo txt 技术要求 when VLM returns '无'."""
    creo = {
        "技术要求": ["6,全部导电阳极化。"],
        "主要外形尺寸": [], "特征尺寸": [], "倒角圆角": [],
    }
    vlm = _default_vlm_fields()  # 表面处理 == "无"
    result = _merge_geometry_creo_vlm_fields({}, creo, vlm)
    parsed = _parse_structured_fields(result)
    assert parsed.get("表面处理", "无") != "无", "表面处理 should be extracted from 技术要求"
    assert "阳极化" in parsed.get("表面处理", "")


def test_merge_vlm_surface_treatment_takes_priority_over_creo_fallback():
    """When VLM provides 表面处理, do not override with Creo txt."""
    creo = {
        "技术要求": ["6,全部导电阳极化。"],
        "主要外形尺寸": [], "特征尺寸": [], "倒角圆角": [],
    }
    vlm = _default_vlm_fields()
    vlm["表面处理"] = "硬质阳极化，膜厚25μm"
    result = _merge_geometry_creo_vlm_fields({}, creo, vlm)
    parsed = _parse_structured_fields(result)
    assert parsed.get("表面处理") == "硬质阳极化，膜厚25μm"


# ============================================================
# _infer_dimensions_from_occ_vlm tests
# ============================================================


def test_infer_G1_vlm_corrects_inflated_occ_thickness():
    # G1: OCC_T=30.9 >> true T=19. VLM group2 (first≠L) exposes 19.
    # ratio=30.9/19=1.63>1.3 → VLM_T wins.
    result = _infer_dimensions_from_occ_vlm(
        "长30.9×宽238×高163",
        "238×163×10|147×19×30.9",
    )
    assert result is not None
    assert result["T"] == pytest.approx(19.0)
    assert result["L"] == pytest.approx(238.0)
    assert result["H"] == pytest.approx(163.0)


def test_infer_G5_vlm_invalid_uses_all_occ():
    # G5: vlm_max=240, max(OCC_L,OCC_H)=266. 240/266=0.902<0.95 → vlm_invalid.
    # All dims from OCC.
    result = _infer_dimensions_from_occ_vlm(
        "长40×宽266×高169",
        "221.8×106.4×17|240×84.5×17.3|234×32×17|228×106×17.3",
    )
    assert result is not None
    assert result["T"] == pytest.approx(40.0)
    assert result["L"] == pytest.approx(266.0)
    assert result["H"] == pytest.approx(169.0)


def test_infer_G7_vlm_h_above_threshold_uses_vlm_h():
    # G7: VLM_H=163, OCC_H=177.5. 163/177.5=91.8%>90% → use VLM_H=163.
    result = _infer_dimensions_from_occ_vlm(
        "长32.5×宽238×高177.5",
        "238×163×16|227×157×7.5|229×31×16",
    )
    assert result is not None
    assert result["H"] == pytest.approx(163.0)
    assert result["L"] == pytest.approx(238.0)


# ============================================================
# Rule A: single-group vlm_second=None, diff in [50, 100) → H = VLM_H
# ============================================================


def test_infer_G16_single_group_h_diff_50_to_100_uses_vlm_h():
    # G16: OCC_H=240, VLM_H=186, diff=54 ∈ [50,100), no vlm_second → H=VLM_H=186
    result = _infer_dimensions_from_occ_vlm("长258×宽44.5×高240", "258×186×3")
    assert result is not None
    assert result["H"] == pytest.approx(186.0)
    assert result["T"] == pytest.approx(44.5)
    assert result["L"] == pytest.approx(258.0)


def test_infer_h_single_group_diff_under_50_no_vlm_second_uses_occ():
    # diff=30 < 50, vlm_second=None → H stays OCC_H (Rule A guard)
    result = _infer_dimensions_from_occ_vlm("长5×宽250×高200", "250×170×5")
    assert result is not None
    assert result["H"] == pytest.approx(200.0)


# ============================================================
# Rule B: T_candidates high-ratio branch and semicolon-laiyuan parsing fix
# ============================================================


def test_infer_t_side_candidates_high_ratio_averages():
    # VLM_T=20, OCC_T=55, ratio=2.75>2.5 → T=(55+20)/2=37.5 (not direct VLM_T)
    result = _infer_dimensions_from_occ_vlm(
        "长55×宽250×高200",
        "250×200×55|180×100×20",
    )
    assert result is not None
    assert result["T"] == pytest.approx(37.5)


def test_infer_t_pipe_semicolon_laiyuan_group_parsed():
    # Third VLM group "147.4×19×8.35；来源：各视图标注" was filtered by Chinese char guard.
    # After stripping ；来源：... suffix: T_candidates=[19,8.35], VLM_T=8.35,
    # ratio=30.9/8.35≈3.7>2.5 → T=(30.9+8.35)/2=19.625 (not T=6.5 via face fallback)
    result = _infer_dimensions_from_occ_vlm(
        "长30.9×宽238×高163",
        "238×163×6.5|227×150.5×6.5|147.4×19×8.35；来源：各视图标注",
    )
    assert result is not None
    assert result["T"] == pytest.approx(19.625)
    assert result["L"] == pytest.approx(238.0)
    assert result["H"] == pytest.approx(163.0)


def test_infer_G8_vlm_h_below_threshold_uses_occ_h():
    # G8: VLM_H=151, OCC_H=169. 151/169=89.3%<90% → use OCC_H=169.
    # L=max(256,246)=256. T: 141 filtered (>OCC_H*0.5), 4 filtered (<OCC_T*0.3).
    result = _infer_dimensions_from_occ_vlm(
        "长35.1×宽246×高169",
        "256×151×17.2|246×141×4",
    )
    assert result is not None
    assert result["H"] == pytest.approx(169.0)
    assert result["L"] == pytest.approx(256.0)
    assert result["T"] == pytest.approx(35.1)


def test_infer_returns_none_on_bad_occ_input():
    assert _infer_dimensions_from_occ_vlm("not a dimension", "100×50×10") is None
    assert _infer_dimensions_from_occ_vlm("", "100×50×10") is None


# ── 12-group algorithm improvements ──────────────────────────────────────────


def test_parse_structured_fields_extracts_zuizhong_from_reasoning_block():
    # G9: VLM outputs 3-step reasoning with "最终尺寸：A×B×C" conclusion
    text = (
        "【外形尺寸】\n"
        "第一步：图1俯视图，图2左视图\n"
        "第二步：提取234、144.5、厚2\n"
        "第三步：最终尺寸：234×144.5×2\n"
        "【通孔】无"
    )
    result = _parse_structured_fields(text)
    assert result["外形尺寸"] == "234×144.5×2"


def test_parse_structured_fields_zuizhong_stops_before_reference_list():
    # Conclusion followed by "| 参考外形尺寸：..." — keep only clean part
    text = (
        "【外形尺寸】\n"
        "最终尺寸：234×144.5×2 | 参考外形尺寸：294.99/234/227\n"
        "【通孔】无"
    )
    result = _parse_structured_fields(text)
    assert result["外形尺寸"] == "234×144.5×2"


def test_parse_structured_fields_clean_first_line_not_overridden_by_pattern():
    # When first line already is a clean "A×B×C", embedded pattern must not override it
    text = "【外形尺寸】234×144.5×8\n整体外形尺寸：100×50×10\n【通孔】无"
    result = _parse_structured_fields(text)
    assert result["外形尺寸"] == "234×144.5×8"


def test_infer_skips_groups_with_chinese_text():
    # G12: VLM output is verbose view-type description with no numbers → fall back to OCC
    result = _infer_dimensions_from_occ_vlm(
        "长240×宽163×高28",
        "视图类型：图1为主视图、图2/4/6为左/右视图 [?]",
    )
    assert result is not None
    assert result["T"] == pytest.approx(28.0)
    assert result["L"] == pytest.approx(240.0)
    assert result["H"] == pytest.approx(163.0)


def test_infer_G10_face_group_large_ratio_corrects_occ_t():
    # G10: OCC_T=50, face-group last=12.5, ratio=4.0>2.5 → T=12.5
    result = _infer_dimensions_from_occ_vlm(
        "长50×宽380×高238",
        "380×238×12.5|360×218×3",
    )
    assert result is not None
    assert result["T"] == pytest.approx(12.5)
    assert result["L"] == pytest.approx(380.0)
    assert result["H"] == pytest.approx(238.0)


def test_infer_G14_face_group_small_diff_trusts_vlm():
    # G14: OCC_T=3.9, VLM_T=2, diff=1.9 < 5 → trust VLM directly (true=2)
    result = _infer_dimensions_from_occ_vlm(
        "长3.9×宽234×高144.5",
        "234×144.5×2",
    )
    assert result is not None
    assert result["T"] == pytest.approx(2.0)
    assert result["L"] == pytest.approx(234.0)
    assert result["H"] == pytest.approx(144.5)


def test_infer_G13_face_group_large_diff_no_side_group_averages():
    # G13: OCC_T=30.9, VLM_T=8, diff=22.9>20, no side group → T=(30.9+8)/2≈19.45 (true=19)
    result = _infer_dimensions_from_occ_vlm(
        "长30.9×宽238×高163",
        "238×163×8",
    )
    assert result is not None
    assert result["T"] == pytest.approx((30.9 + 8) / 2, rel=0.01)
    assert result["L"] == pytest.approx(238.0)
    assert result["H"] == pytest.approx(163.0)


def test_infer_G10_side_group_protects_vlm_when_diff_large():
    # G10 regression guard: diff=37.5>20 but side group [360,218,3] present → trust VLM (true=12.5)
    result = _infer_dimensions_from_occ_vlm(
        "长50×宽380×高238",
        "380×238×12.5|360×218×3",
    )
    assert result is not None
    assert result["T"] == pytest.approx(12.5)
    assert result["L"] == pytest.approx(380.0)
    assert result["H"] == pytest.approx(238.0)


def test_infer_G11_vlm_h_confirmed_by_two_groups():
    # G11: VLM_H=186, OCC_H=240 (77.5%<90%), but 186 in BOTH groups → use VLM_H
    result = _infer_dimensions_from_occ_vlm(
        "长258×宽44.5×高240",
        "258×186×42|250×186×42",
    )
    assert result is not None
    assert result["H"] == pytest.approx(186.0)
    assert result["L"] == pytest.approx(258.0)


def test_infer_vlm_h_below_threshold_single_group_uses_occ():
    # VLM_H=151 appears in only 1 group, 151/169=89.3%<90% → use OCC_H=169
    result = _infer_dimensions_from_occ_vlm(
        "长35.1×宽246×高169",
        "256×151×17.2",
    )
    assert result is not None
    assert result["H"] == pytest.approx(169.0)


def test_merge_combined_dim_appends_inferred_when_occ_and_vlm_available():
    # G1 scenario: geometry has OCC LWH, VLM has drawing size that corrects T.
    geometry = {"关键尺寸": "长 30.9mm × 宽 238mm × 高 163mm", "外圆与内孔": "无", "螺纹与螺孔": "无", "其他特征": "无"}
    creo = {"技术要求": [], "主要外形尺寸": [], "特征尺寸": [], "倒角圆角": []}
    vlm = _default_vlm_fields()
    vlm["外形尺寸"] = "238×163×10|147×19×30.9"

    result = _merge_geometry_creo_vlm_fields(geometry, creo, vlm)

    assert "推断:" in result
    assert "T19" in result


def test_infer_G15_h_large_diff_averages_without_pool():
    # G15: OCC_H=240, VLM_H=129, diff=111>100, no dim_pool → H=(240+129)/2=184.5 (true=188)
    result = _infer_dimensions_from_occ_vlm(
        "长282×宽44.0×高240",
        "282×129×21.5",
    )
    assert result is not None
    assert result["H"] == pytest.approx(184.5, abs=0.1)
    assert result["L"] == pytest.approx(282.0)


def test_infer_G15_h_large_diff_snaps_to_pool():
    # G15 with dim_pool containing 186 → nearest to 184.5 is 186 (true=188)
    result = _infer_dimensions_from_occ_vlm(
        "长282×宽44.0×高240",
        "282×129×21.5",
        dim_pool="282；276；258；246；240；233；226；186；180；172；129；21.5",
    )
    assert result is not None
    assert result["H"] == pytest.approx(186.0)
    assert result["L"] == pytest.approx(282.0)


def test_infer_G15_h_small_diff_still_uses_occ():
    # Guard: diff=18 < 100 → OCC_H unchanged even with dim_pool
    result = _infer_dimensions_from_occ_vlm(
        "长35.1×宽246×高169",
        "256×151×17.2",
        dim_pool="256；246；186；169；151；17.2",
    )
    assert result is not None
    assert result["H"] == pytest.approx(169.0)


def test_infer_G15_vlm_completely_failed_pool_provides_h():
    # G15 worst case: VLM 外形尺寸 = view description → vlm_str discarded → vlm_groups empty.
    # dim_pool from 尺寸公差 field contains 186 (< OCC_H*0.9=216) → use as H.
    result = _infer_dimensions_from_occ_vlm(
        "长282×宽44.0×高240",
        "视图类型：图1=俯视图 [?]",           # completely filtered, no numbers
        dim_pool="282；276；258；246；242；240；233；226；186；180；172；129；44.0；21.5",
    )
    assert result is not None
    assert result["H"] == pytest.approx(186.0)
    assert result["L"] == pytest.approx(282.0)


def test_infer_G15_real_vlm_groups_vlm_second_corrects_h():
    # G15 third form: 3 VLM groups, face group first=[282]≈L, non-face groups have first=[172,75].
    # vlm_second = 172 (max non-face first). |OCC_H(240) - 172| = 68 > 50 → H = 172+16 = 188.
    result = _infer_dimensions_from_occ_vlm(
        "长282×宽44.0×高240",
        "282×129×21.5|172×84|75×21.5",
    )
    assert result is not None
    assert result["H"] == pytest.approx(188.0)
    assert result["L"] == pytest.approx(282.0)


def test_infer_h_vlm_second_error_20_to_50_averages():
    # vlm_second = 190, |OCC_H(225) - 190| = 35 → in 20-50 range → H = (225+190)/2 = 207.5
    result = _infer_dimensions_from_occ_vlm(
        "长5×宽300×高225",
        "300×165×5|190×110",
    )
    assert result is not None
    assert result["H"] == pytest.approx(207.5)


def test_infer_h_vlm_second_small_error_trusts_vlm_directly():
    # vlm_second = 185, |OCC_H(200) - 185| = 15 < 20 → H = 185 directly
    result = _infer_dimensions_from_occ_vlm(
        "长5×宽300×高200",
        "300×165×5|185×110",
    )
    assert result is not None
    assert result["H"] == pytest.approx(185.0)


def test_interval_median_all_high_zero_power_uses_count_tiebreak():
    # Production case: 0→12vals, 10→4, 20→1, 40→2, 50→1.
    # All high buckets have count<5 → power=0 → old code picks max bucket=50 (WRONG).
    # Fix: when power tie at 0, prefer bucket with most count → bucket 10, avg≈15.19.
    parts = [2.2, 2.5, 3.0, 3.3, 3.5, 4.0, 5.0, 6.0, 6.5, 6.67, 7.0, 8.5,
             10.0, 12.5, 19.0, 19.25,
             23.5,
             40.25, 49.0,
             50.0]
    result = _interval_avg_thickness([str(v) for v in parts])
    # Bucket 10 average: (10+12.5+19+19.25)/4 = 15.1875 → 15.19
    assert result == pytest.approx(15.19, abs=0.01)


def test_interval_median_equal_count_zero_power_prefers_lower_bucket():
    # Two high buckets both have count=2 (power=0 tie); lower bucket should win.
    parts = [15.0, 18.0, 45.0, 48.0]
    result = _interval_avg_thickness([str(v) for v in parts])
    # Both b=10 (15,18) and b=40 (45,48) have count=2; prefer b=10 → avg=16.5
    assert result == pytest.approx(16.5, abs=0.01)


def test_parse_structured_fields_no_digit_waixingchicun_cleared():
    # When 外形尺寸 value has no digits (VLM output view description only) → value becomes ""
    text = (
        "【外形尺寸】\n"
        "视图类型：图1=俯视图（详细标注）、图2=左视图 [?]\n"
        "【通孔】无\n"
    )
    result = _parse_structured_fields(text)
    assert result.get("外形尺寸", "") == ""


def test_parse_structured_fields_laiyuan_only_recovers_contour_dims():
    # VLM outputs 来源：...标注NNN（）...NNN为厚度... only (no dimension line).
    # Fallback should extract contour dims from 标注NNN（） and thickness from NNN为厚度.
    text = (
        "【外形尺寸】\n"
        "来源：图1总外轮廓标注282（）、129（）；图4侧视图标注21.5为厚度方向通尺寸；"
        "其余标注尺寸如172/84/75等为内部特征尺寸\n"
        "【通孔】M6×8个\n"
    )
    result = _parse_structured_fields(text)
    assert result.get("外形尺寸") == "282×129×21.5"


def test_parse_structured_fields_laiyuan_only_no_thickness_stays_empty():
    # 来源：...标注 text without 为厚度 → can't recover, stays ""
    text = (
        "【外形尺寸】\n"
        "来源：图1总外轮廓标注282（）、129（）；尺寸不完整\n"
        "【通孔】无\n"
    )
    result = _parse_structured_fields(text)
    # Only 2 contour dims without thickness → cannot form full NNN×NNN×NNN → stay empty
    assert result.get("外形尺寸", "") == ""


# ============================================================
# _interval_avg_thickness: defenders power-priority + penalty threshold
# ============================================================


def test_interval_median_bucket10_count14_beats_bucket20_count9():
    # Production case: b10=14 vals, b20=9 vals.
    # Old: b10 penalty→power=7, b20 power=9, defenders sorted by interval→locked=20 (WRONG).
    # Fix: raise penalty threshold to c>=20, sort defenders by power→b10 power=14>9→locked=10.
    parts_b10 = ["10.0", "10.5", "11.0", "11.5", "12.0", "12.5", "13.0",
                 "13.5", "14.0", "14.5", "15.0", "15.5", "16.0", "16.5"]  # 14 vals
    parts_b20 = ["20.0", "21.0", "22.0", "23.0", "24.0", "25.0", "26.0", "27.0", "28.0"]
    result = _interval_avg_thickness(parts_b10 + parts_b20)
    # locked=10, avg([10.0..16.5]) = 185.5/14 = 13.25
    assert result == pytest.approx(13.25)


def test_interval_median_bucket10_count20_still_penalized():
    # count(b10)=20 >= 20 → still hits penalty→power=7; b20 power=9 wins by power-priority.
    parts_b10 = ["10.0", "10.5", "11.0", "11.5", "12.0", "12.5", "13.0",
                 "13.5", "14.0", "14.5", "15.0", "15.5", "16.0", "16.5",
                 "17.0", "17.5", "18.0", "18.5", "19.0", "19.5"]  # 20 vals
    parts_b20 = ["20.0", "21.0", "22.0", "23.0", "24.0", "25.0", "26.0", "27.0", "28.0"]
    result = _interval_avg_thickness(parts_b10 + parts_b20)
    # locked=20, avg([20..28]) = 216/9 = 24.0
    assert result == pytest.approx(24.0)


def test_interval_median_multi_high_buckets_highest_wins():
    # Production case: b10=15, b20=12, b30=11, b40=12 — all count>=10.
    # Old: b10 power=15 (highest) → locked=10 (WRONG).
    # Fix: cap count>=10 at power=10 → all tied → interval priority → locked=40.
    parts_b10 = ["10.0", "10.5", "11.0", "11.7", "12.0", "13.0", "13.3", "13.6",
                 "14.0", "14.2", "14.6", "15.0", "16.4", "17.0", "18.0"]   # 15 vals
    parts_b20 = ["20.0", "20.5", "21.5", "22.0", "22.88", "24.0", "25.0",
                 "26.0", "27.0", "28.0", "28.07", "29.1"]                    # 12 vals
    parts_b30 = ["30.0", "32.0", "32.5", "33.3", "33.69", "34.0",
                 "35.0", "36.0", "37.0", "38.0", "38.4"]                     # 11 vals
    parts_b40 = ["40.0", "40.8", "41.0", "41.5", "42.0", "42.3", "42.5",
                 "45.0", "47.0", "48.0", "48.5", "49.0"]                     # 12 vals
    result = _interval_avg_thickness(parts_b10 + parts_b20 + parts_b30 + parts_b40)
    # locked=40, avg([40.0,40.8,41.0,41.5,42.0,42.3,42.5,45.0,47.0,48.0,48.5,49.0])
    # = 527.6 / 12 = 43.97
    assert result == pytest.approx(43.97, abs=0.01)


# ============================================================
# VLM thin-value guard: VLM_T < 5 + OCC_T >= 5 → revert to OCC_T
# ============================================================


def test_infer_t_vlm_face_fallback_under_5_reverts_to_occ_t():
    # Production: OCC_T=12.7, VLM fb=3.5 (<5) via face fallback, OCC_T>=5 → T=OCC_T=12.7
    result = _infer_dimensions_from_occ_vlm(
        "长12.7×宽380×高201.2",
        "380×189.5×3.5|375.45×143×3.5；来源：图1主视图标注380、总189.5；图2、4左视图标注厚度3.5、总143；图5主视图标注375.45",
    )
    assert result is not None
    assert result["T"] == pytest.approx(12.7)
    assert result["L"] == pytest.approx(380.0)
    assert result["H"] == pytest.approx(189.5)


def test_infer_t_vlm_under_5_occ_also_thin_no_revert():
    # OCC_T=3.9 (also <5): guard must NOT fire — part is genuinely thin (G14 regression)
    result = _infer_dimensions_from_occ_vlm(
        "长3.9×宽234×高144.5",
        "234×144.5×2",
    )
    assert result is not None
    assert result["T"] == pytest.approx(2.0)  # VLM wins, guard silent


def test_infer_t_vlm_value_8_excluded_when_occ_double_digit():
    # Production: OCC_T=23 (>=10), side candidate v=8 is ≤8 → excluded.
    # No other candidates; face fallback fb=3 < lower_bound → skip.
    # T falls back to OCC_T=23.
    result = _infer_dimensions_from_occ_vlm(
        "长23×宽240×高167.6",
        "240×163×3 | 226×148×3 | 167.6×3×8",
    )
    assert result is not None
    assert result["T"] == pytest.approx(23.0)
    assert result["L"] == pytest.approx(240.0)
    assert result["H"] == pytest.approx(163.0)


def test_infer_t_vlm_value_8_allowed_when_occ_single_digit():
    # OCC_T=9 (single-digit, <10): guard inactive; VLM v=8 is allowed as candidate.
    # ratio=9/8=1.125 ≤ 1.3 → T=OCC_T=9 (close enough, VLM just confirms).
    result = _infer_dimensions_from_occ_vlm(
        "长9×宽200×高150",
        "200×150×8",
    )
    assert result is not None
    # OCC_T<10 → no guard; face fallback fb=8, diff=1<5 → T=8
    assert result["T"] == pytest.approx(8.0)


def test_infer_h_parenthetical_annotation_stripped_before_cn_check():
    # "240(参考)×163×3" contains 参考 (Chinese) → old code filtered entire group → 163 lost.
    # After fix: (参考) stripped → "240×163×3" admitted → VLM_H=163 ≥ OCC_H*0.9 → H=163.
    result = _infer_dimensions_from_occ_vlm(
        "长240×宽163×高24.5",
        "234×94×3 | 240(参考)×163×3 | 132.5×234×3",
    )
    assert result is not None
    assert result["H"] == pytest.approx(163.0), f"got H={result['H']}"
    assert result["L"] == pytest.approx(240.0)
    assert result["T"] == pytest.approx(24.5)


def test_infer_t_side_group_with_no_valid_t_candidate_still_averages():
    # OCC_T=30.9, face-group fb=8.35 (diff=22.55>20, ratio=3.7>2.5).
    # Side group [227,150.5,6.5]: 6.5 < vlm_t_floor=8, 227/150.5 > OCC_H*0.5 → no valid T.
    # Old: has_side_group=True → T=fb=8.35. Guard: 8.35>8 → no fire → T=8.35 (wrong).
    # Fix: has_side_group=False (no credible T in side group) → average → T=(30.9+8.35)/2≈19.6.
    result = _infer_dimensions_from_occ_vlm(
        "长30.9×宽238×高163",
        "238×163×8.35|227×150.5×6.5",
    )
    assert result is not None
    assert result["T"] == pytest.approx(19.625), f"got T={result['T']}"
    assert result["L"] == pytest.approx(238.0)
    assert result["H"] == pytest.approx(163.0)


def test_infer_h_square_bracket_annotation_stripped_before_question_check():
    # "234×163×132.5 [?]" has [?] suffix → old code filtered entire group → vlm_groups=[]
    # → dim_pool fallback picks 132.5 (49 < 132.5 < 146.7) → H=132.5 (wrong).
    # After fix: [?] stripped → "234×163×132.5" admitted → VLM_H=163 ≥ OCC_H*0.9 → H=163.
    result = _infer_dimensions_from_occ_vlm(
        "长240×宽163×高24.5",
        "234×163×132.5 [?]",
    )
    assert result is not None
    assert result["H"] == pytest.approx(163.0), f"got H={result['H']}"
    assert result["L"] == pytest.approx(240.0)
    assert result["T"] == pytest.approx(24.5)


def test_infer_h_parenthesized_dimension_kept_not_stripped():
    # "(240)×163×50.5" — (240) is a parenthesized dimension, not a text annotation.
    # Old regex [^（(）)]* stripped (240) → group became [163,50.5] → vlm_max=167.6 < 240*0.95
    # → vlm_valid=False → H=OCC_H=167.6 (wrong).
    # Fix: regex [^（(）)0-9]* only strips text-only parentheticals like (参考),
    # keeps (240) → group=[240,163,50.5] → vlm_valid → VLM_H=163 ≥ 167.6*0.9 → H=163.
    result = _infer_dimensions_from_occ_vlm(
        "长23×宽240×高167.6",
        "(240)×163×50.5 | 167.6×3×2",
    )
    assert result is not None
    assert result["H"] == pytest.approx(163.0), f"got H={result['H']}"
    assert result["L"] == pytest.approx(240.0)
    assert result["T"] == pytest.approx(23.0)


def test_infer_h_vlm_h_too_low_falls_back_to_occ():
    # VLM group [234,94,132.5]: VLM_H=94, OCC_H=163, abs=69 in [50,100] moderate-gap path.
    # Old: H=VLM_H=94 (94/163=57% — unrelated feature dim, not part height).
    # Fix: VLM_H < OCC_H*0.7=114 → reject VLM_H → H=OCC_H=163.
    result = _infer_dimensions_from_occ_vlm(
        "长240×宽163×高24.5",
        "234×94×132.5",
    )
    assert result is not None
    assert result["H"] == pytest.approx(163.0), f"got H={result['H']}"
    assert result["L"] == pytest.approx(240.0)
    assert result["T"] == pytest.approx(24.5)


def test_merge_ocr_fields_appends_to_vlm_tongkong():
    """ocr_fields 中的通孔新条目追加到 VLM 已有值后面。"""
    geo = {}
    creo = {"技术要求": [], "主要外形尺寸": [], "特征尺寸": [], "倒角圆角": []}
    vlm = {
        "通孔": "24-Ø2.8",
        "沉孔沉槽": "无", "螺纹孔": "无", "特殊孔": "无",
        "外形尺寸": "无", "尺寸公差": "无", "形位公差": "无",
        "表面粗糙度": "无", "表面处理": "无", "刻字": "无",
        "零件名称": "无", "形态": "无", "类型": "无",
        "热处理与探伤": "无", "其他特征": "无",
    }
    ocr = {"通孔": ["20-Ø3"], "沉孔沉槽": [], "螺纹孔": [], "特殊孔": []}
    result = _merge_geometry_creo_vlm_fields(geo, creo, vlm, ocr_fields=ocr)
    tong_line = next((l for l in result.splitlines() if l.startswith("【通孔】")), "")
    assert "20-Ø3" in tong_line
    assert "24-Ø2.8" in tong_line


def test_merge_ocr_fields_dedup_does_not_double_append():
    """ocr_fields 中与 VLM 重复的条目不再追加。"""
    geo = {}
    creo = {"技术要求": [], "主要外形尺寸": [], "特征尺寸": [], "倒角圆角": []}
    vlm = {
        "通孔": "24-Ø2.8；20-Ø3",
        "沉孔沉槽": "无", "螺纹孔": "无", "特殊孔": "无",
        "外形尺寸": "无", "尺寸公差": "无", "形位公差": "无",
        "表面粗糙度": "无", "表面处理": "无", "刻字": "无",
        "零件名称": "无", "形态": "无", "类型": "无",
        "热处理与探伤": "无", "其他特征": "无",
    }
    ocr = {"通孔": ["24-Ø2.8"], "沉孔沉槽": [], "螺纹孔": [], "特殊孔": []}
    result = _merge_geometry_creo_vlm_fields(geo, creo, vlm, ocr_fields=ocr)
    tong_line = next((l for l in result.splitlines() if l.startswith("【通孔】")), "")
    assert tong_line.count("24-Ø2.8") == 1
