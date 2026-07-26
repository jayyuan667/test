# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.pipeline.process_gen import ProcessGenerator


def _make_pg():
    return object.__new__(ProcessGenerator)


def _y13_like_text(extra_field: str = ""):
    return (
        "【图号】Y13\n"
        "【物料形态】板料\n"
        "【外形尺寸】147×100.43×17\n"
        "【关键尺寸】147×100.43×17；G面孔位\n"
        "【材料】5A06\n"
        "【过渡特征】存在翻面加工需求，第2张显示G面倒角过渡\n"
        f"{extra_field}"
    )


def test_extract_process_constraints_detects_flip_face_from_transition_and_full_text():
    pg = _make_pg()

    constraints = pg._extract_process_constraints(
        _y13_like_text("补充说明：背面特征见第2张，G面需要反面装夹。"),
        geo_data=None,
    )

    assert constraints["hard_constraints"]["flip_face"]
    assert "存在翻面加工需求" in constraints["hard_constraints"]["flip_face"]


def test_post_check_inserts_plate_milling_and_inspection_after_single_material_row():
    pg = _make_pg()
    constraints = pg._extract_process_constraints(_y13_like_text(), geo_data=None)
    raw = "- 0010: 按图纸要求备料，材料5A06，板料尺寸147×100.43×17mm（工种：料）"

    result = pg._post_check_process(raw, constraints)

    assert "- 0010: 按图纸要求备料，材料5A06，板料尺寸147×100.43×17mm（工种：料）" in result
    assert "- 0100: 铣四边147×100 （工种：铣）" in result
    assert "- 0105: 外观检验 （工种：检）" in result
    assert result.splitlines()[1:3] == [
        "- 0100: 铣四边147×100 （工种：铣）",
        "- 0105: 外观检验 （工种：检）",
    ]


def test_repair_incomplete_process_uses_llm_once(monkeypatch):
    pg = _make_pg()
    constraints = pg._extract_process_constraints(_y13_like_text(), geo_data=None)

    def fake_stream(prompt, log_callback=None):
        assert "当前工艺规程明显不完整" in prompt
        return """## 生成的工艺规程
- 0010: 按图纸要求备料，材料5A06（工种：料）
- 0020: 铣四边，保证外形基准尺寸（工种：铣）
- 0030: 数控铣加工槽、孔及螺纹特征（工种：数铣）
- 0040: 彩虹色导电氧化（工种：镀覆）
- 0050: 最终检验（工种：检）
"""

    monkeypatch.setattr(pg, "_stream_llm_response", fake_stream)

    raw, rows = pg.repair_incomplete_process(
        _y13_like_text("【表面处理与镀层特征】彩虹色导电氧化\n"),
        "专家判断：板类散热安装板",
        constraints,
        reasons=["too_few_rows", "holes_or_threads"],
    )

    assert "铣四边" in raw
    assert len(rows) >= 5


def test_conservative_fallback_route_covers_y13_facts():
    pg = _make_pg()
    text = _y13_like_text(
        "【螺纹与螺孔】6×φ2.2；2×M2.5\n"
        "【表面处理与镀层特征】彩虹色导电氧化\n"
        "【技术要求】按图所示内容激光刻字\n"
    )
    constraints = pg._extract_process_constraints(text, geo_data=None)

    raw, rows = pg.build_conservative_fallback_route(text, constraints)

    assert "备料" in raw
    assert "铣四边" in raw
    assert "数控铣" in raw
    assert "镀覆" in raw or "表处" in raw
    assert "检" in raw
    assert len(rows) >= 5
