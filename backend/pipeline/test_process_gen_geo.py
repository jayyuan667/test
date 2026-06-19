# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from unittest.mock import patch
from backend.pipeline.process_gen import ProcessGenerator


def _make_pg():
    return object.__new__(ProcessGenerator)


REAL_PAGE_SUMMARY_REVIEW_TEXT = (
    "【毛坯类型】：12Cr1MoVG；：无\n"
    "【物料形态】棒料（圆）\n"
    "【第1页摘要】图号：2779.301.13.0；零件名称：高温过热器出口集箱；"
    "毛坯类型：12Cr1MoVG；技术要求：按图制造；"
    "关键尺寸：900；10630；φ273×40；2-φ102；12-φ107；236-φ29"
)


_GEO_PLATE = {
    "shape_class": "板类",
    "dimensions": {"x": 250.0, "y": 100.0, "z": 30.0},
    "faces": [],
    "hole_info": {"count": 4, "min_diameter": 8.0, "max_diameter": 12.0, "thread_range": "M8~M12"},
}

_GEO_SHAFT = {
    "shape_class": "轴类",
    "dimensions": {"x": 80.0, "y": 80.0, "z": 320.0},
    "faces": [{"type_name": "Cylinder", "params": {"radius": 40.0}, "area": 1000.0}],
    "hole_info": {},
}


# ── Constraint extraction tests ────────────────────────────────────────────

def test_geo_blank_spec_populated_for_plate():
    pg = _make_pg()
    with patch('backend.pipeline.geometry_analyzer.derive_blank_spec', return_value="δ30×250×100=1"):
        constraints = pg._extract_process_constraints("【关键尺寸】无", geo_data=_GEO_PLATE)
    assert constraints["hard_constraints"]["geo_blank_spec"] == "δ30×250×100=1"


def test_geo_hole_count_populated():
    pg = _make_pg()
    with patch('backend.pipeline.geometry_analyzer.derive_blank_spec', return_value="δ30×250×100=1"):
        constraints = pg._extract_process_constraints("", geo_data=_GEO_PLATE)
    assert constraints["hard_constraints"]["geo_hole_count"] == 4


def test_geo_bore_range_populated():
    pg = _make_pg()
    with patch('backend.pipeline.geometry_analyzer.derive_blank_spec', return_value="δ30×250×100=1"):
        constraints = pg._extract_process_constraints("", geo_data=_GEO_PLATE)
    assert constraints["hard_constraints"]["geo_bore_range"] == "8.0~12.0mm"


def test_extract_process_constraints_quantity_from_tech_requirement():
    pg = _make_pg()
    text = "【技术要求】1,去毛刺。2,全部导电阳极化。3,数量5。"
    with patch('backend.pipeline.geometry_analyzer.derive_blank_spec', return_value="δ30×250×100=1"):
        constraints = pg._extract_process_constraints(text, geo_data=_GEO_PLATE)
    assert constraints["hard_constraints"]["part_count"] == 5


def test_extract_process_constraints_does_not_treat_hole_count_as_part_count():
    pg = _make_pg()
    text = "【技术要求】孔数量4；全部导电阳极化。"
    with patch('backend.pipeline.geometry_analyzer.derive_blank_spec', return_value="δ30×250×100=1"):
        constraints = pg._extract_process_constraints(text, geo_data=_GEO_PLATE)
    assert constraints["hard_constraints"]["part_count"] == 1


def test_no_geo_data_returns_empty_geo_fields():
    pg = _make_pg()
    constraints = pg._extract_process_constraints("【关键尺寸】100×80×50", geo_data=None)
    assert constraints["hard_constraints"]["geo_blank_spec"] == ""
    assert constraints["hard_constraints"]["geo_hole_count"] == 0
    assert constraints["hard_constraints"]["geo_bore_range"] == ""


def test_geo_error_returns_empty_geo_fields():
    pg = _make_pg()
    constraints = pg._extract_process_constraints("", geo_data={"error": "FreeCAD not available"})
    assert constraints["hard_constraints"]["geo_blank_spec"] == ""


def test_no_hole_info_leaves_hole_fields_zero():
    pg = _make_pg()
    with patch('backend.pipeline.geometry_analyzer.derive_blank_spec', return_value="φ80×320=1"):
        constraints = pg._extract_process_constraints("", geo_data=_GEO_SHAFT)
    assert constraints["hard_constraints"]["geo_hole_count"] == 0
    assert constraints["hard_constraints"]["geo_bore_range"] == ""


# ── Creo calibration tests ──────────────────────────────────────────────────

def test_calibrate_blank_replaces_near_match():
    pg = _make_pg()
    # 234 is 0.4% from 233, 162.5 is 0.7% from 161.4 — both within 1%
    result = pg._calibrate_blank_with_creo(
        "δ16.2×233×161.4=5",
        {"关键尺寸": "234×162.5×16.2"},
    )
    assert "234" in result
    assert "162.5" in result
    assert "233" not in result
    assert "161.4" not in result


def test_calibrate_blank_preserves_when_no_near_match():
    pg = _make_pg()
    result = pg._calibrate_blank_with_creo(
        "δ40×248×173=1",
        {"关键尺寸": "89×75×118"},  # no value within 1% of 40/248/173
    )
    assert result == "δ40×248×173=1"


def test_calibrate_blank_preserves_thickness_when_no_creo_match():
    pg = _make_pg()
    # 234 is 0.4% from 233, 162.5 is 0.7% from 161.4 — both within 1%
    result = pg._calibrate_blank_with_creo(
        "δ16.2×233×161.4=1",
        {"关键尺寸": "234×162.5"},  # missing thickness 16.2
    )
    assert "16.2" in result
    assert "234" in result
    assert "162.5" in result
    assert "233" not in result


def test_calibrate_blank_handles_empty_fields():
    pg = _make_pg()
    result = pg._calibrate_blank_with_creo("δ30×250×100=1", {})
    assert result == "δ30×250×100=1"


def test_calibrate_blank_handles_phi_format():
    pg = _make_pg()
    # 80 is 0.6% from 79.5, 320 is 0.4% from 318.7 — both within 1%
    result = pg._calibrate_blank_with_creo(
        "φ79.5×318.7=1",
        {"关键尺寸": "φ80×320"},
    )
    assert "80" in result
    assert "320" in result
    assert "79.5" not in result


def test_calibrate_blank_skips_values_outside_tolerance():
    pg = _make_pg()
    # 233 vs 238 = 2.1% difference, outside 1% tolerance
    result = pg._calibrate_blank_with_creo(
        "δ16.2×233×161.4=1",
        {"关键尺寸": "238×165"},  # 165 vs 161.4 = 2.2%, also outside
    )
    assert result == "δ16.2×233×161.4=1"


def test_extract_constraints_calibrates_blank_with_creo_fields():
    pg = _make_pg()
    # 234 is 0.4% from 233, 162.5 is 0.7% from 161.4
    # After ceil-to-ten: 16.2→20, 234→240, 162.5→170
    text = "【关键尺寸】234×162.5×16"
    with patch('backend.pipeline.geometry_analyzer.derive_blank_spec', return_value="δ16.2×233×161.4=1"):
        constraints = pg._extract_process_constraints(text, geo_data=_GEO_PLATE)
    blank = constraints["hard_constraints"]["geo_blank_spec"]
    assert "240" in blank
    assert "170" in blank
    assert "233" not in blank
    assert "20" in blank  # 16.2 ceiled to ten


# ── Creo explicit shape dimension tests ─────────────────────────────────────

def test_derive_blank_from_abc_format():
    pg = _make_pg()
    result = pg._derive_blank_from_creo_fields(
        {"外形尺寸": "a=169,b=244,c=36"},
        part_count=1,
    )
    assert result == "δ36×249×174=1"


def test_derive_blank_from_abc_format_case_insensitive():
    pg = _make_pg()
    result = pg._derive_blank_from_creo_fields(
        {"外形尺寸": "A=100,B=200,C=50"},
        part_count=2,
    )
    assert result == "δ50×205×105=2"


def test_derive_blank_from_creo_fields_ignores_vlm_lwh():
    pg = _make_pg()
    # VLM 长/宽/高 不可靠（截图视角依赖），不应被解析
    result = pg._derive_blank_from_creo_fields(
        {"外形尺寸": "长244×宽169×高36"},
        part_count=1,
    )
    assert result == ""


def test_derive_blank_from_creo_fields_empty_when_no_match():
    pg = _make_pg()
    result = pg._derive_blank_from_creo_fields(
        {"关键尺寸": "250×100×30"},
        part_count=1,
    )
    assert result == ""


def test_derive_blank_from_creo_fields_empty_without_fields():
    pg = _make_pg()
    result = pg._derive_blank_from_creo_fields({}, part_count=1)
    assert result == ""


def test_ceil_blank_dims_rounds_up_to_tens():
    pg = _make_pg()
    assert pg._ceil_blank_dims("δ16.2×233×161.4=5") == "δ20×240×170=5"


def test_ceil_blank_dims_preserves_multiples_of_ten():
    pg = _make_pg()
    assert pg._ceil_blank_dims("δ30×250×100=1") == "δ30×250×100=1"


def test_ceil_blank_dims_phi_format():
    pg = _make_pg()
    assert pg._ceil_blank_dims("φ79.5×318.7=1") == "φ80×320=1"


def test_ceil_blank_dims_ceils_9_to_10():
    pg = _make_pg()
    assert pg._ceil_blank_dims("δ9×19×29=1") == "δ10×20×30=1"


def test_extract_constraints_uses_creo_explicit_over_step():
    pg = _make_pg()
    text = "【外形尺寸】a=169,b=244,c=36"
    with patch('backend.pipeline.geometry_analyzer.derive_blank_spec', return_value="δ30×250×100=1"):
        constraints = pg._extract_process_constraints(text, geo_data=_GEO_PLATE)
    # Creo explicit takes priority over STEP; then ceil-to-ten
    assert constraints["hard_constraints"]["geo_blank_spec"] == "δ40×250×180=1"


def test_extract_authoritative_blank_spec_accepts_suffixed_plate_spec():
    pg = _make_pg()
    assert pg._extract_authoritative_blank_spec("毛坯规格：δ20×390×248（锯床下料）") == "δ20×390×248"


def test_extract_authoritative_blank_spec_accepts_suffixed_round_spec():
    pg = _make_pg()
    assert pg._extract_authoritative_blank_spec("毛坯规格：φ80×320=1") == "φ80×320=1"


def test_extract_authoritative_blank_spec_rejects_counterbore_angle_spec():
    pg = _make_pg()
    assert pg._extract_authoritative_blank_spec("钻φ5.6×90°沉孔") == ""


def test_extract_authoritative_blank_spec_accepts_round_spec_with_l_length():
    pg = _make_pg()
    assert pg._extract_authoritative_blank_spec("毛坯规格：φ65×L，L=120") == "φ65×120"


def test_extract_authoritative_blank_spec_normalizes_spaced_quantity():
    pg = _make_pg()
    assert pg._extract_authoritative_blank_spec("毛坯规格：φ80×320 = 1") == "φ80×320=1"


def test_extract_authoritative_blank_spec_accepts_plate_spec_with_quantity():
    pg = _make_pg()
    assert pg._extract_authoritative_blank_spec("毛坯规格：δ20×390×248=1") == "δ20×390×248=1"


def test_extract_authoritative_blank_spec_normalizes_spaced_plate_quantity():
    pg = _make_pg()
    assert pg._extract_authoritative_blank_spec("毛坯规格：δ20×390×248 = 1") == "δ20×390×248=1"


def test_extract_authoritative_blank_spec_rejects_multiple_specs():
    pg = _make_pg()
    assert pg._extract_authoritative_blank_spec("毛坯规格：δ20×390×248；φ80×320=1") == ""


def test_extract_authoritative_blank_spec_rejects_long_summary():
    pg = _make_pg()
    text = (
        "图号：2779.301.13.0；零件名称：高温过热器出口集箱；毛坯类型：12Cr1MoVG；"
        "技术要求：按图制造；关键尺寸：900；10630；φ273×40；2-φ102；12-φ107；236-φ29"
    )

    assert pg._extract_authoritative_blank_spec(text) == ""


# ── Post-check tests ────────────────────────────────────────────────────────

def _make_constraints(geo_blank="", blank_size="", hole_count=0, bore_range=""):
    return {
        "hard_constraints": {
            "blank_size": blank_size,
            "outer_size": "",
            "key_dims": "",
            "geo_blank_spec": geo_blank,
            "geo_hole_count": hole_count,
            "geo_bore_range": bore_range,
            "part_count": 1,
        },
        "soft_features": {}
    }


def test_post_check_geo_blank_overrides_wrong_dim():
    pg = _make_pg()
    raw = "- 0010: 备料 δ20×300×150=1\n- 0020: 铣削"
    result = pg._post_check_process(raw, _make_constraints(geo_blank="δ30×250×100=1"))
    assert "δ30×250×100=1" in result
    assert "δ20×300×150" not in result


def test_post_check_geo_blank_no_change_when_correct():
    pg = _make_pg()
    raw = "- 0010: 备料 δ30×250×100=1\n- 0020: 铣削"
    result = pg._post_check_process(raw, _make_constraints(geo_blank="δ30×250×100=1"))
    assert result == raw


def test_post_check_geo_blank_fills_placeholder_blank_line():
    pg = _make_pg()
    raw = "- 0010: 备料 按毛坯尺寸备料。\n- 0020: 去应力退火处理。"
    result = pg._post_check_process(raw, _make_constraints(geo_blank="δ30×250×100=1"))
    assert "δ30×250×100=1" in result
    assert "按毛坯尺寸备料" not in result


def test_post_check_geo_blank_fills_empty_blank_line():
    pg = _make_pg()
    raw = "- 0010: 备料\n- 0020: 去应力退火处理。"
    result = pg._post_check_process(raw, _make_constraints(geo_blank="δ30×250×100=1"))
    assert "- 0010: 备料 δ30×250×100=1" in result


def test_post_check_geo_blank_rewrites_quantity_suffix():
    pg = _make_pg()
    constraints = _make_constraints(geo_blank="δ30×250×100=1")
    constraints["hard_constraints"]["part_count"] = 5
    raw = "- 0010: 备料 δ30×250×100=1"
    result = pg._post_check_process(raw, constraints)
    assert "δ30×250×100=5" in result


def test_post_check_geo_blank_preserves_line_when_dimensions_and_quantity_already_match():
    pg = _make_pg()
    constraints = _make_constraints(geo_blank="δ30×250×100=1")
    constraints["hard_constraints"]["part_count"] = 5
    raw = "- 0010: 备料 δ30×250×100=5 锻件"
    result = pg._post_check_process(raw, constraints)
    assert result == raw


def test_post_check_geo_blank_preserves_non_placeholder_text_without_dimensions():
    pg = _make_pg()
    raw = "- 0010: 备料 锻件\n- 0020: 去应力退火处理。"
    result = pg._post_check_process(raw, _make_constraints(geo_blank="δ30×250×100=1"))
    assert result == raw


def test_post_check_fallback_to_blank_size_when_no_geo():
    pg = _make_pg()
    raw = "- 0010: 备料 δ20×300×150=1"
    result = pg._post_check_process(raw, _make_constraints(blank_size="δ30×250×100"))
    assert "δ30×250×100" in result


def test_post_check_rewrites_spaced_plate_quantity_suffix():
    pg = _make_pg()
    constraints = _make_constraints(blank_size="δ20×390×248 = 1")
    constraints["hard_constraints"]["part_count"] = 5
    raw = "- 0010: 备料 δ20×390×248 = 1"

    result = pg._post_check_process(raw, constraints)

    assert "δ20×390×248=5" in result
    assert "δ20×390×248 = 1" not in result


def test_post_check_rewrites_plate_quantity_when_dimensions_match():
    pg = _make_pg()
    constraints = _make_constraints(blank_size="δ20×390×248=1")
    constraints["hard_constraints"]["part_count"] = 5
    raw = "- 0010: 备料 δ20×390×248=1"

    result = pg._post_check_process(raw, constraints)

    assert "δ20×390×248=5" in result


def test_post_check_rewrites_plate_quantity_when_dimensions_change():
    pg = _make_pg()
    constraints = _make_constraints(blank_size="δ20×390×248=1")
    constraints["hard_constraints"]["part_count"] = 5
    raw = "- 0010: 备料 δ20×300×150=1"

    result = pg._post_check_process(raw, constraints)

    assert "δ20×390×248=5" in result


def test_post_check_rewrites_spaced_quantity_suffix():
    pg = _make_pg()
    constraints = _make_constraints(geo_blank="φ80×320 = 1")
    constraints["hard_constraints"]["part_count"] = 5
    raw = "- 0010: 备料 φ80×320 = 1"

    result = pg._post_check_process(raw, constraints)

    assert "φ80×320=5" in result
    assert "φ80×320 = 1" not in result


def test_extract_constraints_and_post_check_preserve_original_0010_for_real_page_summary():
    pg = _make_pg()
    constraints = pg._extract_process_constraints(REAL_PAGE_SUMMARY_REVIEW_TEXT, geo_data=None)
    raw = (
        "- 0010: 下料，按图纸尺寸准备12Cr1MoVG无缝钢管，"
        "规格为φ273×40，长度10630mm （工种：料）"
    )

    result = pg._post_check_process(raw, constraints)

    assert constraints["hard_constraints"]["blank_size"] == ""
    assert result == raw
    assert "图号：" not in result
    assert "零件名称：" not in result
    assert "毛坯类型：" not in result


def test_post_check_shaft_blank_phi_format():
    pg = _make_pg()
    raw = "- 0010: 备料 φ60×320=1"
    result = pg._post_check_process(raw, _make_constraints(geo_blank="φ80×320=1"))
    assert "φ80×320=1" in result


def test_post_check_hole_count_corrected():
    pg = _make_pg()
    raw = "- 0030: 钻4×φ8通孔"
    result = pg._post_check_process(raw, _make_constraints(hole_count=6))
    assert "6×φ8" in result
    assert "4×φ8" not in result


def test_post_check_hole_count_zero_no_change():
    pg = _make_pg()
    raw = "- 0030: 钻4×φ8通孔"
    result = pg._post_check_process(raw, _make_constraints(hole_count=0))
    assert result == raw


def test_post_check_bore_out_of_range_flagged():
    pg = _make_pg()
    raw = "- 0030: 钻φ20孔"
    result = pg._post_check_process(raw, _make_constraints(bore_range="8.0~12.0mm"))
    assert "⚠几何孔径范围:8.0~12.0mm" in result


def test_post_check_bore_in_range_not_flagged():
    pg = _make_pg()
    raw = "- 0030: 钻φ10孔"
    result = pg._post_check_process(raw, _make_constraints(bore_range="8.0~12.0mm"))
    assert "⚠" not in result


def test_post_check_bore_tolerance_margin():
    pg = _make_pg()
    raw = "- 0030: 钻φ13孔"  # 13 = 12 + 1 → still OK
    result = pg._post_check_process(raw, _make_constraints(bore_range="8.0~12.0mm"))
    assert "⚠" not in result


def test_post_check_no_geo_constraints_unchanged():
    pg = _make_pg()
    raw = "- 0010: 备料 δ20×300×150=1\n- 0030: 钻4×φ8"
    result = pg._post_check_process(raw, _make_constraints())
    assert result == raw


# ── generate() signature test ──────────────────────────────────────────────

def test_build_controlled_prompt_contains_authoritative_blank_instruction():
    pg = _make_pg()
    prompt = pg._build_controlled_prompt(
        fused_description="【尺寸】长 250mm × 宽 100mm × 高 30mm",
        expert_judgment="",
        rag_context="候选工艺A",
        rag_results={"matches": []},
        constraints={
            "hard_constraints": {
                "blank_size": "",
                "outer_size": "250×100×30",
                "key_dims": "250×100×30",
                "geo_blank_spec": "δ30×250×100=5",
                "geo_hole_count": 0,
                "geo_bore_range": "",
                "part_count": 5,
            },
            "soft_features": {},
        },
        use_blueprint=False,
        allowed_fragments={},
    )
    assert "0010 备料必须直接使用当前零件的权威毛坯规格" in prompt
    assert "δ30×250×100=5" in prompt


def test_build_controlled_prompt_normalizes_blank_quantity_from_part_count():
    pg = _make_pg()
    prompt = pg._build_controlled_prompt(
        fused_description="【尺寸】长 250mm × 宽 100mm × 高 30mm",
        expert_judgment="",
        rag_context="候选工艺A",
        rag_results={"matches": []},
        constraints={
            "hard_constraints": {
                "blank_size": "",
                "outer_size": "250×100×30",
                "key_dims": "250×100×30",
                "geo_blank_spec": "δ30×250×100=1",
                "geo_hole_count": 0,
                "geo_bore_range": "",
                "part_count": 5,
            },
            "soft_features": {},
        },
        use_blueprint=False,
        allowed_fragments={},
    )
    assert "δ30×250×100=5" in prompt
    assert "δ30×250×100=1" not in prompt


def test_build_controlled_prompt_does_not_require_same_step_count_as_blueprint():
    pg = _make_pg()
    prompt = pg._build_controlled_prompt(
        fused_description="【尺寸】长 243mm × 宽 164mm × 高 20mm\n【技术要求】全部表面导电阳极化处理。",
        expert_judgment="",
        rag_context="0010@备料：δ20×390×200=1。\n0060@按组件进行试装及组合加工。",
        rag_results={"matches": []},
        constraints={"hard_constraints": {"blank_size": "", "outer_size": "243×164×20", "key_dims": "243×164×20", "geo_blank_spec": "δ20×243×164=5", "geo_hole_count": 12, "geo_bore_range": "3.0~5.8mm", "part_count": 5}, "soft_features": {}},
        use_blueprint=False,
        allowed_fragments={},
    )
    assert "工序数量原则上与蓝本一致" not in prompt


def test_build_controlled_prompt_requires_dropping_unsupported_blueprint_steps():
    pg = _make_pg()
    prompt = pg._build_controlled_prompt(
        fused_description="【尺寸】长 243mm × 宽 164mm × 高 20mm\n【技术要求】全部表面导电阳极化处理。",
        expert_judgment="",
        rag_context="0060@按组件进行试装及组合加工。",
        rag_results={"matches": []},
        constraints={"hard_constraints": {"blank_size": "", "outer_size": "243×164×20", "key_dims": "243×164×20", "geo_blank_spec": "δ20×243×164=5", "geo_hole_count": 12, "geo_bore_range": "3.0~5.8mm", "part_count": 5}, "soft_features": {}},
        use_blueprint=False,
        allowed_fragments={},
    )
    assert "若蓝本某工序在当前零件特征中找不到依据，则删除该工序" in prompt


# ── generate() signature test ──────────────────────────────────────────────

def test_generate_accepts_geo_data_kwarg():
    pg = _make_pg()
    pg._fuse_descriptions = lambda d: "【关键尺寸】250×100×30"
    pg._replace_placeholder_tokens = lambda t: t
    pg._extract_process_constraints = lambda text, geo_data=None: {
        "hard_constraints": {
            "blank_size": "", "outer_size": "", "key_dims": "",
            "geo_blank_spec": "δ30×250×100=1",
            "geo_hole_count": 0, "geo_bore_range": "",
            "part_count": 1,
        },
        "soft_features": {}
    }
    pg._run_rag_lookup = lambda *a, **k: ({}, "", False, None)
    pg._nearest_neighbor_fallback = lambda *a, **k: ("", {})
    pg._build_fallback_prompt = lambda *a: "prompt"
    pg._stream_llm_response = lambda *a, **k: "- 0010: 备料 δ20×300×150=1"
    pg._extract_process_section = lambda t: t
    pg._post_check_process = lambda raw, c: raw
    pg._parse_markdown_process = lambda t: []

    raw, data, rag = pg.generate(
        descriptions=[{"description": ""}],
        expert_judgment="",
        geo_data={"shape_class": "板类", "dimensions": {"x": 250, "y": 100, "z": 30}, "faces": [], "hole_info": {}},
    )
    assert isinstance(raw, str)


def test_generate_result_raw_is_post_checked():
    """Verify generate() returns raw text that has been through _post_check_process."""
    pg = _make_pg()
    pg._fuse_descriptions = lambda d: "【关键尺寸】250×100×30"
    pg._replace_placeholder_tokens = lambda t: t
    pg._extract_process_constraints = lambda text, geo_data=None: {
        "hard_constraints": {
            "blank_size": "", "outer_size": "", "key_dims": "",
            "geo_blank_spec": "δ30×250×100=1",
            "geo_hole_count": 0, "geo_bore_range": "",
            "part_count": 1,
        },
        "soft_features": {}
    }
    pg._run_rag_lookup = lambda *a, **k: ({}, "", False, None)
    pg._nearest_neighbor_fallback = lambda *a, **k: ("", {})
    pg._build_fallback_prompt = lambda *a: "prompt"

    raw_output = "- 0010: 备料 δ20×300×150=1\n- 0020: 铣削"
    pg._stream_llm_response = lambda *a, **k: raw_output
    pg._extract_process_section = lambda t: t
    pg._post_check_process = lambda raw, c: raw.replace("δ20×300×150=1", "δ30×250×100=1")
    pg._parse_markdown_process = lambda t: [["0010", "备料 δ30×250×100=1"], ["0020", "铣削"]]

    raw, data, rag = pg.generate(
        descriptions=[{"description": ""}],
        expert_judgment="",
        geo_data={"shape_class": "板类", "dimensions": {"x": 250, "y": 100, "z": 30}, "faces": [], "hole_info": {}},
    )
    assert "δ30×250×100=1" in raw
    assert "δ20×300×150" not in raw
    assert len(data) == 2


# ── derive_blank_from_creo_zhushi: VLM 长×宽×高 primary path tests ─────────

def test_derive_blank_uses_vlm_lwh_over_creo_raw_dims():
    """When 关键尺寸 ends with 长×宽×高 summary, use it instead of Creo raw values."""
    pg = _make_pg()
    fields = {
        "Creo原始尺寸": "247；240；234；227；222；209.8；206.3；201.6；186；185.6；185.4；165.7",
        "关键尺寸": "247；240；234；...；长 240.0mm × 宽 163.0mm × 高 24.5mm",
    }
    result = pg._derive_blank_from_creo_zhushi(fields, part_count=1, geo_data=None)
    # D3=24.5 → floor=20, D3_b=30, gap=5.5<6.5 → +5 → 35; D1=240→250; D2=163→173
    assert result == "δ35×250×173=1", f"got {result}"


def test_derive_blank_lwh_thickness_rounding():
    """Thickness rule: floor(D3/10)*10+10; if gap<6.5 add 5. 24.5→35, 30→40, 27→35."""
    pg = _make_pg()
    for h, expected_d3b in [(24.5, 35), (30.0, 40), (27.0, 35)]:
        fields = {"关键尺寸": f"长 200.0mm × 宽 100.0mm × 高 {h}mm"}
        result = pg._derive_blank_from_creo_zhushi(fields, part_count=1, geo_data=None)
        assert result.startswith(f"δ{expected_d3b}×"), f"h={h}: {result}"


def test_derive_blank_thickness_rule_t14():
    """T=14 → floor=10, D3_b=20, gap=6.0, not <6.0 → 20; L=380→390, H=238→248。"""
    pg = _make_pg()
    fields = {"关键尺寸": "长 380.0mm × 宽 238.0mm × 高 14.0mm"}
    result = pg._derive_blank_from_creo_zhushi(fields, part_count=1, geo_data=None)
    assert result == "δ20×390×248=1", f"got {result}"


def test_derive_blank_lwh_fallback_to_creo_raw_when_no_lwh():
    """Without 长×宽×高 summary, fall back to Creo原始尺寸 parsing."""
    pg = _make_pg()
    fields = {"Creo原始尺寸": "250；163；24"}
    result = pg._derive_blank_from_creo_zhushi(fields, part_count=1, geo_data=None)
    # Fallback logic: top-2 large + global min
    assert result != "", "should produce a blank spec from raw dims"
    assert result.startswith("δ"), f"unexpected format: {result}"


# ── derive_blank_from_creo_zhushi: 综合尺寸 推断:T×L×H path tests ─────────

def test_derive_blank_uses_inferred_dim_from_combined():
    """综合尺寸 推断:T×L×H → 用作备料尺寸计算（无 关键尺寸 LWH 时触发）。
    T=12.7, L=380, H=189.5 → D3=12.7, D2=189.5, D1=380
    D3_b=floor(12.7/10)*10+10=20, D1_b=390, D2_b=199.5 → δ20×390×199.5=1
    """
    pg = _make_pg()
    fields = {
        "综合尺寸": "几何:长380×宽201.2×高12.7；图纸:380×189.5×3.5；推断:T12.7×L380×H189.5",
    }
    result = pg._derive_blank_from_creo_zhushi(fields, part_count=1, geo_data=None)
    assert result == "δ20×390×199.5=1", f"got {result}"


def test_derive_blank_inferred_dim_not_triggered_without_推断():
    """综合尺寸 无 推断: 前缀 → 不触发，返回空（无其他数据时）。"""
    pg = _make_pg()
    fields = {
        "综合尺寸": "几何:长380×宽201.2×高12.7；图纸:380×189.5×3.5",
    }
    result = pg._derive_blank_from_creo_zhushi(fields, part_count=1, geo_data=None)
    assert result == "", f"should be empty without 推断, got {result}"


def test_derive_blank_inferred_takes_priority_over_keydim_lwh():
    """综合尺寸 推断:T×L×H 优先于 关键尺寸 长×宽×高（OCC 摘要）。
    关键尺寸 OCC 给出 H=24.5，但推断用 VLM 图纸修正后 H=189.5；应取推断值。
    """
    pg = _make_pg()
    fields = {
        "关键尺寸": "长 380.0mm × 宽 244.5mm × 高 13.7mm",   # OCC 值
        "综合尺寸": "几何:长380×宽201.2×高12.7；图纸:380×189.5×3.5；推断:T12.7×L380×H189.5",
    }
    result = pg._derive_blank_from_creo_zhushi(fields, part_count=1, geo_data=None)
    # 推断优先：T=12.7→20, L=380→390, H=189.5→199.5；NOT OCC 的 244.5+10=254.5
    assert result == "δ20×390×199.5=1", f"got {result}"


def test_derive_blank_uses_occ_t_when_larger_than_inferred_t():
    """T_inf < OCC_T → blank D3 should use OCC_T (stock must fit full geometry).

    Real case: T_inf=18.7 (VLM-corrected plate face), OCC_T=24.5 (bounding box depth).
    T_inf=18.7 → D3_b=floor(18.7/10)*10+10=20 (wrong).
    OCC_T=24.5 → D3_b=floor(24.5/10)*10+10=30 → δ30×248×173=1 (correct).
    """
    pg = _make_pg()
    fields = {
        "综合尺寸": "几何:长240×宽163×高24.5；图纸:xxx；推断:T18.7×L238×H163",
    }
    # geo_data=None — fix must work via text parsing only (几何:长240×宽163×高24.5)
    result = pg._derive_blank_from_creo_zhushi(fields, part_count=1, geo_data=None)
    # D3=max(18.7, 24.5)=24.5 → floor=20, D3_b=30, gap=5.5<6.5 → 35; L=238+10=248; H=163+10=173
    assert result == "δ35×248×173=1", f"got {result}"


def test_derive_blank_keeps_inferred_t_when_larger_than_occ():
    """T_inf > OCC_T → blank uses T_inf (OCC under-estimated in this scenario).
    geo_data=None: fix must work via text parsing only (几何:长240×宽163×高12.7).
    """
    pg = _make_pg()
    fields = {
        "综合尺寸": "几何:长240×宽163×高12.7；图纸:xxx；推断:T18.7×L238×H163",
    }
    result = pg._derive_blank_from_creo_zhushi(fields, part_count=1, geo_data=None)
    # D3=max(18.7, 12.7)=18.7 → floor(18.7/10)*10+10=20; L=238+10=248; H=163+10=173
    # T_inf=18.7 → floor=10, D3_b=20, gap=1.3<6.5 → +5=25 → δ25×248×173=1
    assert result == "δ25×248×173=1", f"got {result}"


# ── _build_mill_blank_instruction: 铣方尺寸规则 ──────────────────────────────

def test_mill_blank_instruction_basic():
    """备料δ20×390×248=1（T_b=20），铣方各 -5 → T_mill_raw=15<20→取20，L=385、W=243，始终 ±0.1。"""
    pg = _make_pg()
    feature_text = "【零件名称】测试零件\n【形位公差】无\n"
    result = pg._build_mill_blank_instruction(feature_text, "δ20×390×248=1")
    assert "20±0.1×385±0.1×243±0.1" in result, f"got: {result}"
    for line in result.splitlines():
        if "铣方目标尺寸" in line:
            assert "±0.1" in line, f"应始终带 ±0.1，got: {line}"


def test_mill_blank_instruction_with_gdt():
    """备料δ20×390×248=1，T_mill_raw=15<20→取20、L=385、W=243，始终 ±0.1。"""
    pg = _make_pg()
    feature_text = "【零件名称】测试零件\n【形位公差】平面度0.1；垂直度0.05\n"
    result = pg._build_mill_blank_instruction(feature_text, "δ20×390×248=1")
    assert "20±0.1×385±0.1×243±0.1" in result, f"got: {result}"


def test_mill_blank_instruction_no_blank_returns_empty():
    """无 authoritative_blank 且无可解析数据 → 返回空字符串。"""
    pg = _make_pg()
    result = pg._build_mill_blank_instruction("【形位公差】无\n", "")
    assert result == "", f"got: {result}"


def test_mill_blank_instruction_rule_text_updated():
    """指令文本应说明新规则：备料各-5mm，厚度<20不减。"""
    pg = _make_pg()
    result = pg._build_mill_blank_instruction("", "δ20×390×248=1")
    assert "各 -5mm" in result, f"应包含 各 -5mm，got: {result}"
    assert "始终带 ±0.1" in result, f"应包含 ±0.1 说明，got: {result}"


def test_mill_instruction_outline_with_tol():
    """蓝本含最大轮廓外形尺寸公差 ±0.2，推断 T14×L380×H238 → 铣外形目标 14×380±0.2×238±0.2。"""
    pg = _make_pg()
    feature_text = (
        "【综合尺寸】几何:长13.7×宽380×高238；推断:T14×L380×H238\n"
        "【形位公差】无\n"
    )
    rag_ctx = "最大轮廓外形尺寸公差按±0.2尺寸精度控制"
    result = pg._build_mill_blank_instruction(feature_text, "δ20×390×248=1", rag_context=rag_ctx)
    assert "14×380±0.2×238±0.2" in result, f"got: {result}"


def test_mill_instruction_outline_no_tol():
    """蓝本无外形公差文字 → 铣外形目标无 ± 标注：14×380×238。"""
    pg = _make_pg()
    feature_text = (
        "【综合尺寸】几何:长13.7×宽380×高238；推断:T14×L380×H238\n"
        "【形位公差】无\n"
    )
    result = pg._build_mill_blank_instruction(feature_text, "δ20×390×248=1", rag_context="")
    assert "14×380×238" in result, f"got: {result}"
    # T (14) must NOT have ± even when it appears in the line
    for line in result.splitlines():
        if "铣外形目标尺寸" in line:
            assert "14±" not in line, f"T 不应带公差标注，got: {line}"


# ── _restore_inspection_numbering: 0100 检验步 1）2）序号恢复 ──────────────────

def test_restore_inspection_numbering_adds_numbers():
    """0100 行合并了 目视检查…；检验，标识 → 自动拆分加 1）2）。"""
    from backend.pipeline.process_gen import ProcessGenerator
    raw = (
        "- 0100: 检 目视检查产品，无油渍、金属屑、记号笔痕迹等多余物；检验，标识，入库。"
    )
    result = ProcessGenerator._restore_inspection_numbering(raw)
    assert "1）目视检查产品" in result, f"got: {result}"
    assert "2）检验，标识，入库" in result, f"got: {result}"
    assert "1）目视检查" in result.split("\n")[0], "1）应在首行"
    assert "2）检验" in result.split("\n")[1], "2）应在次行"


def test_restore_inspection_numbering_skips_already_numbered():
    """已含 1）的行不重复添加序号。"""
    from backend.pipeline.process_gen import ProcessGenerator
    raw = "- 0100: 检 1）目视检查产品，...；\n2）检验，标识，入库。"
    result = ProcessGenerator._restore_inspection_numbering(raw)
    assert result.count("1）") == 1, f"不应重复添加，got: {result}"


def test_restore_inspection_numbering_no_match_unchanged():
    """不含检验模式的行不受影响。"""
    from backend.pipeline.process_gen import ProcessGenerator
    raw = "- 0010: 料 备料：δ30×250×173=1。"
    assert ProcessGenerator._restore_inspection_numbering(raw) == raw


# ── _merge_same_prefix_subitems: 连续相同前缀子条目合并 ──────────────────────

def test_merge_same_prefix_subitems_consecutive_merged():
    """场景A：连续同前缀(2-4)合并为一条，编号重排。"""
    from backend.pipeline.process_gen import ProcessGenerator
    raw = (
        "1）按图，铣方；\n"
        "2）按主视图，钻孔A；\n"
        "3）按主视图，钻孔B；\n"
        "4）按主视图，钻孔C；\n"
        "5）锐边倒钝。"
    )
    result = ProcessGenerator._merge_same_prefix_subitems(raw)
    lines = [l for l in result.splitlines() if l.strip()]
    assert len(lines) == 3, f"应合并为3条，got:\n{result}"
    assert lines[0].startswith("1）按图，"), f"第1条不变：{lines[0]}"
    assert lines[1].startswith("2）按主视图，"), f"第2条应合并：{lines[1]}"
    assert "钻孔A" in lines[1] and "钻孔B" in lines[1] and "钻孔C" in lines[1]
    assert lines[2].startswith("3）锐边倒钝")


def test_merge_same_prefix_subitems_interrupted_stays_separate():
    """场景B：相同前缀被不同前缀隔断 → 各段独立，不跨段合并。"""
    from backend.pipeline.process_gen import ProcessGenerator
    raw = (
        "1）按主视图，钻孔A；\n"
        "2）按左视图，钻孔B；\n"
        "3）按主视图，钻孔C；\n"
        "4）按主视图，钻孔D；"
    )
    result = ProcessGenerator._merge_same_prefix_subitems(raw)
    lines = [l for l in result.splitlines() if l.strip()]
    assert len(lines) == 3, f"应为3条，got:\n{result}"
    assert "钻孔A" in lines[0] and "钻孔C" not in lines[0], "第1条独立"
    assert lines[1].startswith("2）按左视图，"), "第2条不变"
    assert "钻孔C" in lines[2] and "钻孔D" in lines[2], "第3-4条合并"


def test_merge_same_prefix_subitems_single_item_unchanged():
    """场景C：单条相同前缀不触发合并，原样返回。"""
    from backend.pipeline.process_gen import ProcessGenerator
    raw = "1）按主视图，钻孔A；\n2）锐边倒钝。"
    assert ProcessGenerator._merge_same_prefix_subitems(raw) == raw


def test_merge_same_prefix_subitems_non_item_line_unchanged():
    """场景D：无编号子条目的行不受影响。"""
    from backend.pipeline.process_gen import ProcessGenerator
    raw = "- 0010: 备料 δ30×250×173=1。"
    assert ProcessGenerator._merge_same_prefix_subitems(raw) == raw


def test_derive_blank_keydim_lwh_fallback_when_no_inferred():
    """无 推断: 时，关键尺寸 长×宽×高 作为 step② 回退正常工作。"""
    pg = _make_pg()
    fields = {
        "关键尺寸": "长 240.0mm × 宽 163.0mm × 高 24.5mm",
        "综合尺寸": "几何:长380×宽201.2×高12.7；图纸:380×189.5×3.5",  # 无 推断:
    }
    result = pg._derive_blank_from_creo_zhushi(fields, part_count=1, geo_data=None)
    # 无推断 → 关键尺寸 OCC 摘要：D3=24.5, gap=5.5<6.5→35, D1=240→250, D2=163→173
    assert result == "δ35×250×173=1", f"got {result}"
