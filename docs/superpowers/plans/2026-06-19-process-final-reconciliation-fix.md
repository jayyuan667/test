# Process Final Reconciliation Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent page-summary text from being treated as an authoritative blank specification and overwriting a correct generated 0010 process row.

**Architecture:** Keep the existing generation, SSE streaming, throttling, frontend row animation, and final reconciliation paths unchanged. Tighten blank-spec extraction in `ProcessGenerator._extract_process_constraints()` and add a defensive validation gate in `_post_check_process()` so only compact, recognizable stock specifications can rewrite the blank-preparation row.

**Tech Stack:** Python 3.11, pytest, regular expressions, existing Flask/process-generation pipeline.

## Global Constraints

- Do not modify SSE events, stream throttling, stream timing, or frontend typewriter behavior.
- Preserve valid plate-stock and round-stock correction behavior.
- Do not include YOLO dependency or model installation in this change.
- Run GitNexus impact analysis before editing each production symbol.
- Run GitNexus `detect-changes` before committing implementation changes.

---

### Task 1: Guard authoritative blank specifications

**Files:**
- Modify: `backend/pipeline/test_process_gen_geo.py`
- Modify: `backend/pipeline/process_gen.py:697`
- Modify: `backend/pipeline/process_gen.py:1483`

**Interfaces:**
- Consumes: `ProcessGenerator._extract_process_constraints(feature_text: str, geo_data=None) -> dict`
- Consumes: `ProcessGenerator._post_check_process(process_raw: str, constraints: dict) -> str`
- Produces: `hard_constraints["blank_size"]` containing only a valid stock specification or an empty string.
- Produces: final process text that preserves an already-correct 0010 row when no valid authoritative stock specification exists.

- [ ] **Step 1: Add failing regression tests**

Add these tests to `backend/pipeline/test_process_gen_geo.py`:

```python
def test_extract_constraints_ignores_page_summary_as_blank_spec():
    pg = _make_pg()
    text = (
        "【毛坯类型】：12Cr1MoVG；：无\n"
        "【物料形态】棒料（圆）\n"
        "【第1页摘要】图号：2779.301.13.0；零件名称：高温过热器出口集箱；"
        "毛坯类型：12Cr1MoVG；技术要求：按图制造；"
        "关键尺寸：900；10630；φ273×40；2-φ102；12-φ107；236-φ29"
    )

    constraints = pg._extract_process_constraints(text, geo_data=None)

    assert constraints["hard_constraints"]["blank_size"] == ""


def test_post_check_preserves_tube_stock_row_when_summary_is_not_a_blank_spec():
    pg = _make_pg()
    raw = (
        "- 0010: 下料，按图纸尺寸准备12Cr1MoVG无缝钢管，"
        "规格为φ273×40，长度10630mm （工种：料）\n"
        "- 0020: 车削两端端面及外圆，保证总长900mm （工种：车）"
    )
    constraints = _make_constraints(
        blank_size=(
            "图号：2779.301.13.0；零件名称：高温过热器出口集箱；"
            "毛坯类型：12Cr1MoVG；关键尺寸：900；10630；φ273×40"
        )
    )

    result = pg._post_check_process(raw, constraints)

    assert result == raw
```

- [ ] **Step 2: Run the regression tests and verify RED**

Run:

```bash
./.venv/bin/python -m pytest \
  backend/pipeline/test_process_gen_geo.py::test_extract_constraints_ignores_page_summary_as_blank_spec \
  backend/pipeline/test_process_gen_geo.py::test_post_check_preserves_tube_stock_row_when_summary_is_not_a_blank_spec \
  -q
```

Expected: both tests fail because the page summary is currently stored as `blank_size` and then replaces the 0010 row.

- [ ] **Step 3: Run impact analysis for both production symbols**

Run:

```bash
node .gitnexus/run.cjs impact _extract_process_constraints --direction upstream
node .gitnexus/run.cjs impact _post_check_process --direction upstream
```

Expected: report the risk level, direct callers, and affected execution processes before editing.

- [ ] **Step 4: Implement compact blank-spec validation**

In `backend/pipeline/process_gen.py`, add a static helper near `_extract_dim_pattern`:

```python
@staticmethod
def _extract_authoritative_blank_spec(text: str) -> str:
    value = (text or "").strip()
    if not value or "\n" in value or len(value) > 120:
        return ""

    patterns = (
        r"(?:[δ≠]\s*\d+(?:\.\d+)?\s*[×xX*]\s*\d+(?:\.\d+)?"
        r"(?:\s*[×xX*]\s*\d+(?:\.\d+)?)?(?:\s*=\s*\d+)?)",
        r"(?:[φΦØ]\s*\d+(?:\.\d+)?\s*[×xX*]\s*\d+(?:\.\d+)?"
        r"(?:\s*=\s*\d+)?)",
    )
    matches = []
    for pattern in patterns:
        matches.extend(re.findall(pattern, value))
    unique = list(dict.fromkeys(match.strip() for match in matches if match.strip()))
    return unique[0] if len(unique) == 1 else ""
```

Update `_extract_process_constraints()` so `blank_candidates` only collects explicit stock-related fields and passes each candidate through `_extract_authoritative_blank_spec()`:

```python
blank_candidates = []
for name, val in fields.items():
    if not val or name in {"第1页摘要", "第2页摘要", "第3页摘要"} or name.endswith("页摘要"):
        continue
    if name in {"毛坯尺寸", "毛坯规格", "备料规格", "板材规格", "棒材规格", "型材规格"}:
        spec = self._extract_authoritative_blank_spec(val)
        if spec:
            blank_candidates.append(spec)
hard["blank_size"] = "；".join(dict.fromkeys(blank_candidates))
```

Update `_post_check_process()` so `legacy_blank` is validated before it can become authoritative:

```python
legacy_blank = self._extract_authoritative_blank_spec(hard.get("blank_size", ""))
authoritative_blank = geo_blank or legacy_blank
```

- [ ] **Step 5: Run targeted tests and verify GREEN**

Run:

```bash
./.venv/bin/python -m pytest \
  backend/pipeline/test_process_gen_geo.py::test_extract_constraints_ignores_page_summary_as_blank_spec \
  backend/pipeline/test_process_gen_geo.py::test_post_check_preserves_tube_stock_row_when_summary_is_not_a_blank_spec \
  backend/pipeline/test_process_gen_geo.py::test_post_check_geo_blank_overrides_wrong_dim \
  backend/pipeline/test_process_gen_geo.py::test_post_check_fallback_to_blank_size_when_no_geo \
  backend/pipeline/test_process_gen_geo.py::test_post_check_shaft_blank_phi_format \
  -q
```

Expected: `5 passed`.

- [ ] **Step 6: Reproduce the real task input**

Run a Python check using `output/313effc7-de32-4bb1-9044-e14720ebe87d/result.json`:

```bash
./.venv/bin/python - <<'PY'
import json
from pathlib import Path
from backend.pipeline.process_gen import ProcessGenerator

data = json.loads(Path(
    "output/313effc7-de32-4bb1-9044-e14720ebe87d/result.json"
).read_text())
pg = ProcessGenerator.__new__(ProcessGenerator)
constraints = pg._extract_process_constraints(data["review_text"], geo_data=None)
raw = (
    "- 0010: 下料，按图纸尺寸准备12Cr1MoVG无缝钢管，"
    "规格为φ273×40，长度10630mm （工种：料）"
)
assert constraints["hard_constraints"]["blank_size"] == ""
assert pg._post_check_process(raw, constraints) == raw
print("real-task regression: PASS")
PY
```

Expected: `real-task regression: PASS`.

- [ ] **Step 7: Run the relevant regression suite**

Run:

```bash
./.venv/bin/python -m pytest \
  backend/pipeline/test_process_gen_geo.py \
  backend/test_core.py \
  backend/test_startup_import.py \
  -q
```

Expected: all selected tests pass.

- [ ] **Step 8: Build the frontend to prove streaming UI remains untouched and valid**

Run:

```bash
npm --prefix frontend-react run build
```

Expected: TypeScript and Vite build complete successfully.

- [ ] **Step 9: Inspect affected scope**

Run:

```bash
node .gitnexus/run.cjs detect-changes --scope working
git diff --check
git diff -- backend/pipeline/process_gen.py backend/pipeline/test_process_gen_geo.py
```

Expected: implementation changes are limited to blank-spec extraction/validation and regression tests; no SSE or frontend files are modified.

- [ ] **Step 10: Commit the implementation**

```bash
git add backend/pipeline/process_gen.py backend/pipeline/test_process_gen_geo.py
git commit -m "fix: preserve generated process rows during reconciliation"
```
