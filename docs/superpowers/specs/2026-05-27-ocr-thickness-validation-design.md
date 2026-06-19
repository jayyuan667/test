# OCR Thickness Cross-Validation for Drawing Analysis

## Problem

VLM frequently misidentifies plate thickness from engineering drawings:
- 凸台/台阶 height misread as overall thickness (实心厚板 trap)
- End-view section height (36mm) misread as plate thickness on bent-channel/bracket parts (槽弯形板 trap)

These errors propagate into process generation undetected. Each fix so far has been another VLM prompt rule — fragile, interdependent, and unverifiable at runtime.

## Solution

Add an **independent OCR-based validation layer** that parses raw dimension numbers from the drawing image using PaddleOCR, applies deterministic rules to infer thickness, and **tags** the result (does not modify VLM output) when a conflict is detected. The tag is written to `pending_review.json` for downstream inspection.

The layer is fully gated by an environment variable and zero-coupling — no existing code paths are modified.

## Architecture

```
                  ┌─────────────┐
drawing PNG ─────→│    VLM      │──→ feature_text (含 外形尺寸)
                  └─────────────┘
                        │
                  ┌─────┴──────┐
                  │   OCR +    │
                  │  Rule      │
                  │  Engine    │
                  └─────┬──────┘
                        │
                  ┌─────┴──────┐
                  │  Compare   │
                  │  thickness │
                  └─────┬──────┘
                   ok   │   conflict
                   │    └──→ tag + write to pending_review.json
                   ▼
            feature_text (unchanged)
```

## Module Detail

### `backend/pipeline/ocr_thickness.py` (new file)

**Function 1: `extract_thickness_candidate(lines: list[str]) -> Optional[dict]`**

Extracts a thickness candidate from OCR text lines using deterministic rules (no LLM):

1. Filter lines to pure numeric values in range [3, 200] (plausible plate thickness range). Strip non-numeric prefixes (φ, Ø, R, M).
2. Sort candidate values ascending.
3. Apply rule chain:
   - **Three-group rule**: Three values with realistic aspect ratios (largest/mid ≤ 10, mid/smallest ≤ 10) → smallest = thickness
   - **Bent-channel rule**: Two values with ratio > 2:1 → smaller = thickness (bracket end-view, e.g. 36:10)
   - **Otherwise**: Return None (cannot determine)
4. Return `{"thickness": int, "source": "bent_channel|three_group", "candidates": [list of numbers]}` or None

**Function 2: `verify_drawing_thickness(vlm_feature_text: str, image_paths: list[Path], drawing_id: str) -> Optional[dict]`**

1. Parse VLM output for the `外形尺寸` field, extract the third dimension (thickness)
2. If VLM thickness is missing or numeric parse fails → return None (skip)
3. Run PaddleOCR via existing `run_ocr_on_images(image_paths)` to get text lines
4. Run `extract_thickness_candidate()` on the OCR lines
5. If OCR candidate is None → return None (skip)
6. Compare: `abs(vlm_thickness - ocr_thickness) > 5` → conflict
7. Return conflict flag dict:
```python
{
    "thickness_conflict": True,
    "thickness_vlm": 36,
    "thickness_ocr": 10,
    "thickness_source": "bent_channel",
    "thickness_candidates_vlm": "268×72×36",
    "thickness_candidates_ocr": [297, 55, 36, 10, 5],
    "thickness_recommended": 10
}
```

### `backend/pipeline/vision_analyzer.py` (5-line addition)

In `analyze_drawing()` or equivalent entry point, after VLM extraction completes:

```python
if os.getenv("OCR_THICKNESS_CHECK", "1") != "0":
    from backend.pipeline.ocr_thickness import verify_drawing_thickness
    flag = verify_drawing_thickness(result, image_paths, drawing_id)
    if flag:
        result.setdefault("flags", {}).update(flag)
```

No other changes to this file. The env var `OCR_THICKNESS_CHECK=0` eliminates the entire code path at runtime.

### `backend/pipeline/process_gen.py` (integration point)

When loading `pending_review.json`, if `flags.thickness_conflict` is present, include a human-readable warning in the review context so the user sees it during review.

No pipeline blocking, no auto-correction.

## Rollback Paths

| Level | Action |
|-------|--------|
| Runtime disable | `export OCR_THICKNESS_CHECK=0` |
| Code revert | Delete the 5 lines in `vision_analyzer.py`, delete `ocr_thickness.py` |
| Modular | `ocr_thickness.py` has zero imports from the rest of the pipeline (only imports `run_ocr_on_images` from `ocr_feature.py`). Delete one file, remove 5 lines. |

## Known Limitations

- **No ≠ symbol on drawings** (≠ only appears in craft xlsx). OCR reads raw dimension numbers, not process annotions.
- **Complex structural plates (Y14-type)**: OCR will see a dozen numbers with no clear thickness candidate → returns None → no validation. This is correct behavior — the system cannot validate what the drawing doesn't explicitly label.
- **OCR accuracy**: PaddleOCR may miss small dimension text, misread numbers (e.g., 10 → 1O). The rule engine handles this implicitly by requiring ≥2 candidates for bent-channel rule.
- **Multi-page drawings**: OCR runs on all pages. The rule engine sees numbers from all pages which may add noise. The three-group rule's ratio constraint filters most cross-page pollution.

## Testing

- Unit tests for `extract_thickness_candidate()` against known cases (Y1, Y2, Y10, Y14, Y15, Y20)
- Unit test for conflict comparison threshold
- Integration: run on Y2 drawing PNG, confirm thickness_conflict flag is emitted
- Integration: env var OCR_THICKNESS_CHECK=0 confirms no flag emitted
