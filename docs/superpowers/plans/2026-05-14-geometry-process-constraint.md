# Geometry Process Constraint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pass OpenCASCADE geometry data (bounding box, shape class, hole info) as authoritative constraints into process generation, so the 0010 blank step format (δT×L×W=1 / φD×L=1), hole count, and bore diameter range are geometry-driven rather than LLM-generated.

**Architecture:** Three-layer addition — (1) `derive_blank_spec()` in geometry_analyzer converts raw geo_data to blank format string; (2) `_extract_process_constraints()` and `_post_check_process()` in process_gen accept `geo_data` and apply three correction types; (3) upload.py passes `analyze_step_geometry()` result to `generate()`. Backward compatible: `geo_data=None` preserves existing behaviour.

**Tech Stack:** Python 3.11+, FreeCAD OpenCASCADE (already wired), pytest, regex

---

## File Map

| File | Change |
|------|--------|
| `backend/pipeline/geometry_analyzer.py` | Add `derive_blank_spec(geo_result: dict) -> str` |
| `backend/pipeline/test_geometry_analyzer.py` | Create — unit tests for `derive_blank_spec` |
| `backend/pipeline/process_gen.py` | Extend `_extract_process_constraints`, `_post_check_process`, `generate()` signature |
| `backend/pipeline/test_process_gen_geo.py` | Create — unit tests for new constraint + post-check logic |
| `backend/api/upload.py` | Call `analyze_step_geometry` before `generate()`; pass `geo_data` |

---

## Task 1 — `derive_blank_spec` in geometry_analyzer.py

**Files:**
- Modify: `backend/pipeline/geometry_analyzer.py`
- Create: `backend/pipeline/test_geometry_analyzer.py`

- [ ] **Step 1.1 — Write failing tests**

Create `backend/pipeline/test_geometry_analyzer.py`:

```python
# -*- coding: utf-8 -*-
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from backend.pipeline.geometry_analyzer import derive_blank_spec


def _make_geo(shape, x, y, z, cylinder_radii=None):
    faces = []
    for r in (cylinder_radii or []):
        faces.append({"type_name": "Cylinder", "params": {"radius": r}, "area": 100.0})
    return {
        "shape_class": shape,
        "dimensions": {"x": x, "y": y, "z": z},
        "faces": faces,
    }


def test_plate_thickness_is_min_dim():
    geo = _make_geo("板类", x=250.0, y=100.0, z=30.0)
    assert derive_blank_spec(geo) == "δ30×250×100=1"


def test_plate_orientation_invariant():
    """δ is always min dim regardless of which axis it's on."""
    geo = _make_geo("板类", x=30.0, y=250.0, z=100.0)
    assert derive_blank_spec(geo) == "δ30×250×100=1"


def test_shaft_uses_max_cylinder_radius():
    geo = _make_geo("轴类", x=80.0, y=80.0, z=320.0, cylinder_radii=[40.0, 35.0])
    assert derive_blank_spec(geo) == "φ80×320=1"


def test_shaft_no_cylinder_falls_back_to_box():
    geo = _make_geo("轴类", x=80.0, y=80.0, z=320.0, cylinder_radii=[])
    # No cylinder radii → falls back to 箱体 format
    assert derive_blank_spec(geo) == "320×80×80=1"


def test_disc_uses_min_dim_as_height():
    geo = _make_geo("盘类", x=120.0, y=120.0, z=40.0, cylinder_radii=[60.0])
    assert derive_blank_spec(geo) == "φ120×40=1"


def test_box_sorted_descending():
    geo = _make_geo("箱体类", x=100.0, y=200.0, z=150.0)
    assert derive_blank_spec(geo) == "200×150×100=1"


def test_general_part():
    geo = _make_geo("一般件", x=50.0, y=80.0, z=120.0)
    assert derive_blank_spec(geo) == "120×80×50=1"


def test_empty_dict_returns_empty():
    assert derive_blank_spec({}) == ""


def test_error_key_returns_empty():
    assert derive_blank_spec({"error": "FreeCAD not available"}) == ""


def test_integer_formatting():
    """Whole-number dimensions should have no decimal point."""
    geo = _make_geo("板类", x=250.0, y=100.0, z=30.0)
    result = derive_blank_spec(geo)
    assert "30.0" not in result
    assert "250.0" not in result
```

- [ ] **Step 1.2 — Run tests to verify they fail**

```
cd F:\Work_Dir\new_3dversion\my_working
python -m pytest backend/pipeline/test_geometry_analyzer.py -v 2>&1 | head -40
```

Expected: `ImportError` or `AttributeError: module 'geometry_analyzer' has no attribute 'derive_blank_spec'`

- [ ] **Step 1.3 — Implement `derive_blank_spec`**

Add at the bottom of `backend/pipeline/geometry_analyzer.py` (before the `if __name__ == "__main__":` block):

```python
def derive_blank_spec(geo_result: dict) -> str:
    """Derive blank material spec string from geometry analysis result.

    Shape rules (PRT orientation-invariant):
      轴类  → φD×L=1   (D = max cylinder diameter; L = longest dim)
      盘类  → φD×H=1   (D = max cylinder diameter; H = shortest dim)
      板类  → δT×L×W=1 (T = shortest dim = thickness; L≥W)
      other → L×W×H=1  (sorted descending)

    Returns "" when geo_result is empty or contains an error key.
    """
    if not geo_result or "error" in geo_result:
        return ""

    dims = geo_result.get("dimensions", {})
    x = dims.get("x", 0)
    y = dims.get("y", 0)
    z = dims.get("z", 0)
    if not (x or y or z):
        return ""

    sorted_dims = sorted([x, y, z])  # [min, mid, max]

    faces = geo_result.get("faces", [])
    cylinders = [f for f in faces if f.get("type_name") == "Cylinder"]
    radii = [f.get("params", {}).get("radius", 0) for f in cylinders]
    max_r = max(radii, default=0)

    def _fmt(v: float) -> str:
        return str(int(v)) if v == int(v) else str(round(v, 1))

    shape = geo_result.get("shape_class", "一般件")

    if shape == "轴类" and max_r > 0:
        D = _fmt(round(max_r * 2, 1))
        L = _fmt(sorted_dims[2])
        return f"φ{D}×{L}=1"
    elif shape == "盘类" and max_r > 0:
        D = _fmt(round(max_r * 2, 1))
        H = _fmt(sorted_dims[0])
        return f"φ{D}×{H}=1"
    elif shape == "板类":
        T = _fmt(sorted_dims[0])
        W = _fmt(sorted_dims[1])
        L = _fmt(sorted_dims[2])
        return f"δ{T}×{L}×{W}=1"
    else:
        L = _fmt(sorted_dims[2])
        W = _fmt(sorted_dims[1])
        H = _fmt(sorted_dims[0])
        return f"{L}×{W}×{H}=1"
```

- [ ] **Step 1.4 — Run tests to verify they pass**

```
python -m pytest backend/pipeline/test_geometry_analyzer.py -v
```

Expected: all 10 tests PASS.

- [ ] **Step 1.5 — Commit**

```bash
git add backend/pipeline/geometry_analyzer.py backend/pipeline/test_geometry_analyzer.py
git commit -m "feat: add derive_blank_spec to geometry_analyzer"
```

---

## Task 2 — Expand `_extract_process_constraints` in process_gen.py

**Files:**
- Modify: `backend/pipeline/process_gen.py` (method `_extract_process_constraints`, lines ~455–520)
- Create: `backend/pipeline/test_process_gen_geo.py`

- [ ] **Step 2.1 — Write failing tests**

Create `backend/pipeline/test_process_gen_geo.py`:

```python
# -*- coding: utf-8 -*-
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from unittest.mock import patch, MagicMock
from backend.pipeline.process_gen import ProcessGenerator


def _make_pg():
    """Instantiate ProcessGenerator without real LLM/RAG init."""
    pg = object.__new__(ProcessGenerator)
    return pg


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
```

- [ ] **Step 2.2 — Run tests to verify they fail**

```
python -m pytest backend/pipeline/test_process_gen_geo.py::test_geo_blank_spec_populated_for_plate -v
```

Expected: FAIL — `TypeError: _extract_process_constraints() got an unexpected keyword argument 'geo_data'`

- [ ] **Step 2.3 — Extend `_extract_process_constraints`**

In `backend/pipeline/process_gen.py`, change the method signature and add geo block at the end:

```python
def _extract_process_constraints(self, feature_text: str, geo_data=None) -> dict:
    """从审阅特征文本中提取结构化约束。(existing docstring unchanged)"""
    # ... ALL EXISTING CODE UNCHANGED ...
    # After the existing `return {"hard_constraints": hard, "soft_features": soft}` line,
    # insert the geo block BEFORE the return:

    # ── 几何硬约束（geo_data 优先，不覆盖已有 hard 键）──
    hard["geo_blank_spec"] = ""
    hard["geo_hole_count"] = 0
    hard["geo_bore_range"] = ""

    if geo_data and "error" not in geo_data:
        try:
            from .geometry_analyzer import derive_blank_spec
        except ImportError:
            try:
                from backend.pipeline.geometry_analyzer import derive_blank_spec
            except ImportError:
                from pipeline.geometry_analyzer import derive_blank_spec

        blank = derive_blank_spec(geo_data)
        if blank:
            hard["geo_blank_spec"] = blank

        hole_info = geo_data.get("hole_info", {})
        if hole_info:
            count = hole_info.get("count", 0)
            min_d = hole_info.get("min_diameter", 0)
            max_d = hole_info.get("max_diameter", 0)
            if count:
                hard["geo_hole_count"] = count
            if min_d and max_d:
                hard["geo_bore_range"] = f"{min_d}~{max_d}mm"

    return {"hard_constraints": hard, "soft_features": soft}
```

> **Note:** The three new keys are added to `hard` dict before the return. Do not move or delete any existing code above.

- [ ] **Step 2.4 — Run tests**

```
python -m pytest backend/pipeline/test_process_gen_geo.py -v -k "constraint"
```

Expected: all 6 constraint tests PASS.

- [ ] **Step 2.5 — Commit**

```bash
git add backend/pipeline/process_gen.py backend/pipeline/test_process_gen_geo.py
git commit -m "feat: extend _extract_process_constraints with geo_data support"
```

---

## Task 3 — Expand `_post_check_process` in process_gen.py

**Files:**
- Modify: `backend/pipeline/process_gen.py` (method `_post_check_process`, lines ~623–654)
- Modify: `backend/pipeline/test_process_gen_geo.py` (append new tests)

- [ ] **Step 3.1 — Append failing tests to test_process_gen_geo.py**

Append to `backend/pipeline/test_process_gen_geo.py`:

```python
# ── Post-check tests ──────────────────────────────────────────────────────

def _make_constraints(geo_blank="", blank_size="", hole_count=0, bore_range=""):
    return {
        "hard_constraints": {
            "blank_size": blank_size,
            "outer_size": "",
            "key_dims": "",
            "geo_blank_spec": geo_blank,
            "geo_hole_count": hole_count,
            "geo_bore_range": bore_range,
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


def test_post_check_fallback_to_blank_size_when_no_geo():
    """Without geo_blank_spec, existing blank_size logic still works."""
    pg = _make_pg()
    raw = "- 0010: 备料 δ20×300×150=1"
    # blank_size uses old δ-pattern format: needs a δ/δ char for _extract_dim_pattern
    result = pg._post_check_process(raw, _make_constraints(blank_size="δ30×250×100"))
    assert "δ30×250×100" in result


def test_post_check_shaft_blank_phi_format():
    pg = _make_pg()
    raw = "- 0010: 备料 φ60×320=1"
    result = pg._post_check_process(raw, _make_constraints(geo_blank="φ80×320=1"))
    assert "φ80×320=1" in result


def test_post_check_hole_count_corrected():
    pg = _make_pg()
    raw = "- 0030: 钻4×φ8通孔\n- 0040: 攻丝4×M8"
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
    """Bore within ±1mm of range should NOT be flagged."""
    pg = _make_pg()
    raw = "- 0030: 钻φ13孔"  # 13 = 12 + 1 → still OK
    result = pg._post_check_process(raw, _make_constraints(bore_range="8.0~12.0mm"))
    assert "⚠" not in result


def test_post_check_no_geo_constraints_unchanged():
    pg = _make_pg()
    raw = "- 0010: 备料 δ20×300×150=1\n- 0030: 钻4×φ8"
    result = pg._post_check_process(raw, _make_constraints())
    assert result == raw
```

- [ ] **Step 3.2 — Run new tests to verify they fail**

```
python -m pytest backend/pipeline/test_process_gen_geo.py -v -k "post_check" 2>&1 | head -30
```

Expected: FAIL — `assert "δ30×250×100=1" in result` or similar.

- [ ] **Step 3.3 — Replace `_post_check_process` in process_gen.py**

Replace the existing `_post_check_process` method body entirely:

```python
def _post_check_process(self, process_raw: str, constraints: dict) -> str:
    """对生成的工艺进行约束校验和几何数据覆盖。

    三类校验（按几何优先级）：
      ① 备料规格 (0010行): geo_blank_spec > blank_size
      ② 孔数量: 用 geo_hole_count 覆盖 N×φ/M 模式中的 N
      ③ 孔径范围: 超出 geo_bore_range ±1mm 时追加 ⚠ 标记
    """
    if not process_raw or not constraints:
        return process_raw

    hard = constraints.get("hard_constraints", {})

    # ── ① 备料规格 ──────────────────────────────────────────────────────────
    geo_blank = hard.get("geo_blank_spec", "")
    legacy_blank = hard.get("blank_size", "")
    authoritative_blank = geo_blank or legacy_blank

    if authoritative_blank:
        def _fix_blank_line(match):
            tag = match.group(1)
            action = match.group(2)
            rest = match.group(3).strip()
            if not rest:
                return match.group(0)
            current_dim = self._extract_dim_pattern(authoritative_blank)
            output_dim = self._extract_dim_pattern(rest)
            if current_dim and output_dim and current_dim != output_dim:
                return f"- {tag}: {action} {authoritative_blank}"
            return match.group(0)

        blank_pat = re.compile(
            r'^(?:-\s*)?(\d{4})\s*[:：@\-\|,，;；\s]*(备料|下料|毛坯)(.*?)$',
            re.MULTILINE,
        )
        process_raw = blank_pat.sub(_fix_blank_line, process_raw)

    # ── ② 孔数量覆盖 ─────────────────────────────────────────────────────────
    geo_hole_count = hard.get("geo_hole_count", 0)
    if geo_hole_count > 0:
        def _fix_hole_count(m):
            n_str = m.group(1)
            if int(n_str) != geo_hole_count:
                return m.group(0).replace(n_str, str(geo_hole_count), 1)
            return m.group(0)

        hole_pat = re.compile(r'(\d+)\s*[×x\*]\s*(?:[Mφ]\d+|螺纹孔|通孔)')
        process_raw = hole_pat.sub(_fix_hole_count, process_raw)

    # ── ③ 孔径范围标记 ───────────────────────────────────────────────────────
    geo_bore_range = hard.get("geo_bore_range", "")
    if geo_bore_range:
        m_range = re.match(r'([\d.]+)~([\d.]+)mm', geo_bore_range)
        if m_range:
            bore_lo = float(m_range.group(1)) - 1.0
            bore_hi = float(m_range.group(2)) + 1.0

            bore_pat = re.compile(r'[Φφ]([\d.]+)')
            result_lines = []
            for line in process_raw.split('\n'):
                hits = bore_pat.findall(line)
                out_of_range = [d for d in hits if not (bore_lo <= float(d) <= bore_hi)]
                if out_of_range:
                    line = line.rstrip() + f"  ⚠几何孔径范围:{geo_bore_range}"
                result_lines.append(line)
            process_raw = '\n'.join(result_lines)

    return process_raw
```

- [ ] **Step 3.4 — Run all process_gen_geo tests**

```
python -m pytest backend/pipeline/test_process_gen_geo.py -v
```

Expected: all tests PASS (both constraint and post-check groups).

- [ ] **Step 3.5 — Commit**

```bash
git add backend/pipeline/process_gen.py backend/pipeline/test_process_gen_geo.py
git commit -m "feat: expand _post_check_process with geo blank, hole count, bore range checks"
```

---

## Task 4 — Add `geo_data` param to `generate()` in process_gen.py

**Files:**
- Modify: `backend/pipeline/process_gen.py` (method `generate()`, lines ~151–229)
- Modify: `backend/pipeline/test_process_gen_geo.py` (append integration test)

- [ ] **Step 4.1 — Append integration test**

Append to `backend/pipeline/test_process_gen_geo.py`:

```python
# ── generate() signature test ─────────────────────────────────────────────

def test_generate_accepts_geo_data_kwarg():
    """generate() must accept geo_data without raising TypeError."""
    pg = _make_pg()
    # Stub everything generate() calls
    pg._fuse_descriptions = lambda d: "【关键尺寸】250×100×30"
    pg._replace_placeholder_tokens = lambda t: t
    pg._extract_process_constraints = lambda text, geo_data=None: {
        "hard_constraints": {
            "blank_size": "", "outer_size": "", "key_dims": "",
            "geo_blank_spec": "δ30×250×100=1",
            "geo_hole_count": 0, "geo_bore_range": "",
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

    # Should not raise
    raw, data, rag = pg.generate(
        descriptions=[{"description": ""}],
        expert_judgment="",
        geo_data={"shape_class": "板类", "dimensions": {"x": 250, "y": 100, "z": 30}, "faces": [], "hole_info": {}},
    )
    assert isinstance(raw, str)
```

- [ ] **Step 4.2 — Run to verify failure**

```
python -m pytest backend/pipeline/test_process_gen_geo.py::test_generate_accepts_geo_data_kwarg -v
```

Expected: FAIL — `TypeError: generate() got an unexpected keyword argument 'geo_data'`

- [ ] **Step 4.3 — Add `geo_data` parameter to `generate()`**

In `backend/pipeline/process_gen.py`, change the `generate()` signature from:

```python
def generate(
    self,
    descriptions: List[Dict[str, Any]],
    expert_judgment: str,
    prefix_hint: Optional[str] = None,
    log_callback=None,
    stream_callback=None,
    library_key: Optional[str] = None,
) -> tuple[str, list[list[str]], dict | None]:
```

To:

```python
def generate(
    self,
    descriptions: List[Dict[str, Any]],
    expert_judgment: str,
    prefix_hint: Optional[str] = None,
    log_callback=None,
    stream_callback=None,
    library_key: Optional[str] = None,
    geo_data: Optional[dict] = None,
) -> tuple[str, list[list[str]], dict | None]:
```

Then change the single line inside `generate()` that calls `_extract_process_constraints`:

```python
# Before:
constraints = self._extract_process_constraints(fused_description)

# After:
constraints = self._extract_process_constraints(fused_description, geo_data=geo_data)
```

No other changes to `generate()` are needed — `_post_check_process` already receives `constraints` which now contains the geo keys.

- [ ] **Step 4.4 — Run all tests**

```
python -m pytest backend/pipeline/test_process_gen_geo.py -v
```

Expected: all tests PASS.

- [ ] **Step 4.5 — Commit**

```bash
git add backend/pipeline/process_gen.py backend/pipeline/test_process_gen_geo.py
git commit -m "feat: add geo_data param to ProcessGenerator.generate()"
```

---

## Task 5 — Wire geo_data in upload.py

**Files:**
- Modify: `backend/api/upload.py`

> No unit tests for this task — the change is wiring-only and requires a live FreeCAD + process pipeline to test. Verify manually by running the upload flow with a known PRT file.

- [ ] **Step 5.1 — Locate the import section in upload.py**

In `backend/api/upload.py`, add one import near the existing prt_pipeline imports (around line 20):

```python
from ..pipeline.geometry_analyzer import analyze_step_geometry
```

- [ ] **Step 5.2 — Add geo_data derivation before `generator.generate()` call**

Locate the block in `upload.py` around line 357–366:

```python
    generator = ProcessGenerator()
    with time_block("process_generation"):
        process_flow_raw, process_data, rag_results = generator.generate(
            descriptions,
            expert_judgment,
            prefix_hint=prefix_hint,
            log_callback=rag_log_callback,
            stream_callback=stream_callback,
            library_key=library_key,
        )
```

Replace with:

```python
    # ── Derive geometry constraints for process generation ──
    geo_data = None
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
            expert_judgment,
            prefix_hint=prefix_hint,
            log_callback=rag_log_callback,
            stream_callback=stream_callback,
            library_key=library_key,
            geo_data=geo_data,
        )
```

- [ ] **Step 5.3 — Verify import resolves**

```
python -c "from backend.api.upload import _run_task_pipeline" 2>&1
```

Expected: no ImportError.

- [ ] **Step 5.4 — Run existing vlm_feature tests to confirm no regressions**

```
python -m pytest backend/pipeline/test_vlm_feature.py -v
```

Expected: all existing tests PASS.

- [ ] **Step 5.5 — Commit**

```bash
git add backend/api/upload.py
git commit -m "feat: pass geo_data from analyze_step_geometry to ProcessGenerator.generate()"
```

---

## Dependency Graph

```
Task 1 (geometry_analyzer.py)  ──────────────────────────────────┐
                                                                   │
Task 2 (_extract_process_constraints) ──┐                         │
                                         ├─ Task 4 (generate()) ──┴─ Task 5 (upload.py)
Task 3 (_post_check_process) ───────────┘
```

**Can be parallelised:** Task 1 is fully independent. Tasks 2 and 3 are in the same file but logically separate methods — can be done by the same agent or sequentially.

---

## Self-Review

**Spec coverage:**
- ✅ `derive_blank_spec` with shape-based format (§4.1)
- ✅ `generate()` `geo_data` param (§4.2)
- ✅ `_extract_process_constraints` geo keys (§4.3)
- ✅ `_post_check_process` 3 types: blank, hole count, bore range (§4.4)
- ✅ `upload.py` wiring (§4.5)
- ✅ Backward compatible — `geo_data=None` path unchanged (§7)

**Placeholder scan:** No TBD, no vague "add error handling", all code blocks complete.

**Type consistency:**
- `derive_blank_spec(geo_result: dict) -> str` — used identically in Task 1 and Task 2
- `geo_data: Optional[dict]` — consistent across Tasks 2, 4, 5
- `hard["geo_blank_spec"]`, `hard["geo_hole_count"]`, `hard["geo_bore_range"]` — defined in Task 2, consumed in Task 3
- `_extract_process_constraints(self, feature_text: str, geo_data=None)` — consistent between Tasks 2 and 4
