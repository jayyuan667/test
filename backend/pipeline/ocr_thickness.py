# -*- coding: utf-8 -*-
"""OCR-based thickness cross-validation for drawing analysis.

Extracts numerical dimensions from drawing images via RapidOCR,
applies deterministic rules to infer plate thickness, and compares
against VLM output. Designed as a non-blocking validation layer —
annotates conflicts but does not modify VLM output.

Env var OCR_THICKNESS_CHECK=0 disables this module entirely.
"""

import logging
import os
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_ENABLED = os.getenv("OCR_THICKNESS_CHECK", "1") != "0"
_CONFLICT_THRESHOLD_MM = 5  # absolute difference trigger

# ── Numeric extraction ────────────────────────────────────────────


def _extract_numeric_values(lines: list[str]) -> list[float]:
    """Extract plausible plate-thickness numbers from OCR text lines.

    Filters: integer/float values in [3, 2000], excluding numbers that
    are clearly not dimensions (R-prefixed radii, M-prefixed thread specs,
    φ-prefixed diameters, angle suffixes, tolerance suffixes, page numbers).
    """
    vals: list[float] = []
    # Remove dimension-prefix and unit-prefix patterns before numeric extraction
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        # Skip lines that are clearly thread specs (M3, M2.5 etc.)
        if re.match(r'^M\d', line):
            continue
        # Strip common prefixes: Ø φ R M
        cleaned = re.sub(r'^[ØφRr]\s*', '', line)
        # Strip trailing tolerance (±...)
        cleaned = re.sub(r'[±±][\d.]+$', '', cleaned)
        # Try to match a pure number
        m = re.search(r'\b(\d+(?:\.\d+)?)\b', cleaned)
        if m:
            v = float(m.group(1))
            if 3 <= v <= 2000:
                vals.append(v)
    return vals


def _parse_vlm_key_dimensions(feature_text: str) -> list[float]:
    """Parse VLM 关键尺寸 field and extract all numeric values."""
    m = re.search(r'【关键尺寸】[：:\s]*([^\n]+)', feature_text)
    if not m:
        return []
    dim_str = m.group(1).strip()
    vals = []
    for part in re.split(r'[；;]', dim_str):
        part = part.strip()
        if not part:
            continue
        # Strip tolerance suffixes like ±0.1, -0.3
        cleaned = re.sub(r'[±±][\d.]+$', '', part)
        cleaned = re.sub(r'[+-]\d+(?:\.\d+)?$', '', cleaned)
        # Strip prefix symbols
        cleaned = re.sub(r'^[ØφRrMm]\s*', '', cleaned)
        m2 = re.search(r'\b(\d+(?:\.\d+)?)\b', cleaned)
        if m2:
            v = float(m2.group(1))
            if 3 <= v <= 2000:
                vals.append(v)
    return vals


def _is_stepped_plate(feature_text: str) -> bool:
    """Detect stepped plates by numerical signal: 外形尺寸 third dim appears in 关键尺寸.

    Works regardless of 物料形态 classification (which VLM often mislabels).
    Relies on the observation that in stepped plates, the cascade of step dimensions
    always includes the VLM-extracted 'thickness' value in the '关键尺寸' list.
    """
    _, _, vlm_t = _parse_vlm_dimensions(feature_text)
    if vlm_t is None:
        return False
    key_dims = _parse_vlm_key_dimensions(feature_text)
    if not key_dims:
        return False
    # Confirmation 1: key dimensions must have ≥3 large values (step-dimension cluster)
    large_dims = [kd for kd in key_dims if kd > 100]
    if len(large_dims) < 3:
        return False
    # Confirmation 2: VLM thickness value appears in key dimensions
    t_rounded = int(round(vlm_t))
    for kd in key_dims:
        if abs(kd - t_rounded) <= 1:
            return True
    return False


def _classify_stepped_plate_cluster(vals: list[float], vlm_l: float, vlm_w: float) -> Optional[float]:
    """Special thickness classification for stepped plates.

    Stepped plates have many planar step dimensions that confuse standard
    classification. The actual plate thickness is typically the first value
    BEFORE the first large gap (> 2×) in the sorted OCR values, after
    filtering out very small values (< 7mm) that are likely surface
    roughness or chamfer annotations.

    Example for Y20: sorted OCR = [5, 7, 10, 13, 37, 48, 170, 282, ...]
      Values > 6: [7, 10, 13, 37, 48, 170, ...]
      13→37 gap is 2.8× → thickness = 13 (value BEFORE the gap)
    """
    sorted_vals = sorted(set(vals))
    # Exclude values <= 6 (surface roughness Ra6.3, chamfer radii, etc.)
    filtered = [v for v in sorted_vals if v > 6]
    if len(filtered) < 2:
        return None

    # Find the first gap where consecutive ratio > 2.0
    for i in range(len(filtered) - 1):
        ratio = filtered[i + 1] / filtered[i]
        if ratio > 2.0:
            return filtered[i]

    # No clear gap — fallback: pick the smallest thickness candidate
    small = [v for v in filtered if v <= min(vlm_l, vlm_w) * 0.2]
    if small:
        return min(small)
    return None


def _parse_vlm_dimensions(feature_text: str) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """Parse VLM output to extract all three outer dimensions (L, W, T).

    Returns (length, width, thickness) or (None, None, None).
    Supports formats like:
      - 外形尺寸：268×72×36
      - 【外形尺寸】268×72×36
      - 外形尺寸：282×129×21.5
      - Ø63.17×16.4  (circular — thickness is after ×)
    """
    m = re.search(r'(?:外形尺寸|【外形尺寸】)[：:\s]*([^\n]+)', feature_text)
    if not m:
        return None, None, None
    dim_str = m.group(1).strip().replace('，', '×').replace(',', '×')
    parts = [p.strip() for p in dim_str.split('×') if p.strip()]
    if len(parts) >= 3:
        nums = []
        for p in parts[:3]:
            cleaned = re.sub(r'^[Øφ]\s*', '', p)
            m2 = re.search(r'(\d+(?:\.\d+)?)', cleaned)
            if m2:
                nums.append(float(m2.group(1)))
            else:
                nums.append(None)
        if len(nums) >= 3 and all(n is not None for n in nums):
            return nums[0], nums[1], nums[2]  # type: ignore[return-value]
    if len(parts) == 2:
        # Circular: Ød×t → L=None, W=None, T=t
        m2 = re.search(r'(\d+(?:\.\d+)?)', parts[-1])
        if m2:
            return None, None, float(m2.group(1))
    return None, None, None


def _parse_vlm_thickness(feature_text: str) -> Optional[float]:
    """Backward-compatible wrapper: returns just thickness (third dim)."""
    _, _, t = _parse_vlm_dimensions(feature_text)
    return t


def _classify_numeric_cluster(vals: list[float]) -> Optional[float]:
    """Apply deterministic rules to infer plate thickness from clustered numeric values.

    Rules (in priority order):
      1. Three-group: look at the three largest values as L×W×T candidates.
         Take the smallest of these as thickness. If there's a value more
         than 2× smaller below it, reject — the candidate is a structural
         height (bent-channel case), not material thickness.
      2. Bent-channel: after three-group rejection, scan for a value that
         has at least one larger counterpart with ratio > 2:1, skipping
         the absolute minimum as likely noise (radii, small hole specs).

    Returns None if no rule applies.
    """
    sorted_vals = sorted(vals)
    if len(sorted_vals) < 2:
        return None

    # Rule 1: Three-group — top 3 largest values
    if len(sorted_vals) >= 3:
        candidate = sorted_vals[-3]  # smallest of the top 3
        max_ratio = sorted_vals[-1] / candidate if candidate > 0 else 999

        if max_ratio <= 100:
            # Check for a suspicious gap below candidate
            smaller_vals = [v for v in sorted_vals if v < candidate and v >= 5]
            if not smaller_vals or candidate / max(smaller_vals) <= 2:
                return candidate

    # Rule 2: Bent-channel — find value with a >2× larger counterpart
    # Skip the absolute minimum (likely noise from radii, small holes).
    for v in sorted_vals[1:]:
        if any(larger / v > 2.0 for larger in sorted_vals if larger > v):
            return v

    # Last resort: for a clean two-value list (no internal noise)
    a, b = sorted_vals[0], sorted_vals[-1]
    if a > 0 and b / a > 2.0:
        return a

    return None


# ── Public API ────────────────────────────────────────────────────


def extract_thickness_candidate(lines: list[str]) -> Optional[dict]:
    """Extract a thickness candidate from OCR text lines.

    Args:
        lines: Raw OCR text lines from run_ocr_on_images().

    Returns:
        dict with keys: thickness (int), source (str),
        candidates (list[float])
        or None if no rule applies.
    """
    vals = _extract_numeric_values(lines)
    if not vals:
        return None
    thickness = _classify_numeric_cluster(vals)
    if thickness is None:
        return None
    # Determine source label from which rule fired
    sorted_vals = sorted(vals)
    if len(sorted_vals) >= 3:
        top3_smallest = sorted_vals[-3]
        if thickness == int(round(top3_smallest)):
            source = "three_group"
        else:
            source = "bent_channel"
    else:
        source = "bent_channel"
    return {
        "thickness": int(round(thickness)),
        "source": source,
        "candidates": sorted(set(int(round(v)) for v in vals)),
    }


def verify_drawing_thickness(
    feature_text: str,
    image_paths: list[Path],
    drawing_id: str = "",
) -> Optional[dict]:
    """Compare VLM thickness against OCR-derived thickness.

    This is the main entry point for the pipeline integration.

    Args:
        feature_text: VLM output (structured fields with 【外形尺寸】).
        image_paths: Paths to drawing PNG files for OCR processing.
        drawing_id: Optional identifier for logging.

    Returns:
        Conflict flag dict if a discrepancy > threshold is found:
          {
              "thickness_conflict": true,
              "thickness_vlm": 36,
              "thickness_ocr": 10,
              "thickness_source": "bent_channel",
              "thickness_candidates_vlm": "268×72×36",
              "thickness_candidates_ocr": [10, 36, 55, 297],
              "thickness_recommended": 10
          }
        None if no conflict or not enough info.
    """
    if not _ENABLED:
        logger.debug("[ocr_thickness] disabled via OCR_THICKNESS_CHECK=0")
        return None
    if not feature_text or not image_paths:
        return None

    # 1) Parse VLM thickness and overall dimensions
    vlm_l, vlm_w, vlm_t = _parse_vlm_dimensions(feature_text)
    if vlm_t is None:
        logger.debug("[ocr_thickness] VLM thickness not found, skipping")
        return None

    # 1a) Check for stepped plate: 外形尺寸 third dim appears in 关键尺寸
    _is_stepped = _is_stepped_plate(feature_text)
    if _is_stepped:
        logger.info(
            "[ocr_thickness] Detected stepped plate: 外形尺寸 T=%g also in 关键尺寸  (cls=%s)",
            vlm_t, drawing_id,
        )

    # 2) Run OCR on the drawing images
    from backend.pipeline.ocr_feature import run_ocr_on_images  # noqa: PLC0415

    try:
        lines = run_ocr_on_images(image_paths)
    except ImportError:
        logger.warning("[ocr_thickness] RapidOCR not available, skipping")
        return None
    except Exception:
        logger.warning("[ocr_thickness] OCR failed", exc_info=True)
        return None

    # 2a) For stepped plates, run additional targeted OCR on sub-regions
    #     where detail/section views typically live (top-right, right-half).
    #     The full-image OCR often misses small-dimension annotations there.
    #     Use multiple overlapping crops to maximize OCR coverage, since
    #     RapidOCR can miss values on any single crop.
    if _is_stepped:
        _extra_lines: list[str] = []
        for _img_path in image_paths:
            try:
                from PIL import Image  # noqa: PLC0415
                _img = Image.open(str(_img_path))
                _w, _h = _img.size
                # Multiple overlapping crops in the top-right / right-half area
                _crops = [
                    (_w // 2, 0, _w * 3 // 4, _h // 3),           # core detail
                    (int(_w * 0.45), 0, int(_w * 0.85), _h // 2),  # wider right
                    (int(_w * 0.4), 0, int(_w * 0.8), int(_h * 0.35)),  # right-top
                ]
                for _i, (_x1, _y1, _x2, _y2) in enumerate(_crops):
                    _crop_img = _img.crop((_x1, _y1, _x2, _y2))
                    _crop_path = _img_path.parent / f"_ocr_crop_{_i}.png"
                    _crop_img.save(str(_crop_path))
                    _extra_lines.extend(run_ocr_on_images([_crop_path]))
                    _crop_path.unlink(missing_ok=True)
            except Exception:
                pass
        if _extra_lines:
            lines = list(lines) + list(_extra_lines)
            logger.info(
                "[ocr_thickness] Stepped plate: added %d extra OCR lines from detail region  (cls=%s)",
                len(_extra_lines), drawing_id,
            )

    if not lines:
        logger.debug("[ocr_thickness] OCR returned no text lines")
        return None

    # 3) Determine OCR thickness
    # 3a) Stepped plate path: use special classification that looks for actual
    #     plate thickness among small values, skipping step-dimension cluster.
    # Uses multi-region OCR (with detail region overlay) to find the small
    # thickness annotation that full-image OCR often misses.
    if _is_stepped and vlm_l is not None and vlm_w is not None:
        _ocr_vals = _extract_numeric_values(lines)
        _stepped_t = _classify_stepped_plate_cluster(_ocr_vals, vlm_l, vlm_w)
        if _stepped_t is not None:
            candidate = {
                "thickness": int(round(_stepped_t)),
                "source": "stepped_plate",
                "candidates": sorted(set(int(round(v)) for v in _ocr_vals)),
            }
            logger.info(
                "[ocr_thickness] Stepped plate: OCR thickness=%d from small-value cluster  (cls=%s)",
                int(round(_stepped_t)), drawing_id,
            )
        else:
            # Fall through to standard classification
            candidate = extract_thickness_candidate(lines)
    else:
        candidate = extract_thickness_candidate(lines)
    if candidate is None:
        logger.debug(
            "[ocr_thickness] Could not determine thickness from OCR "
            "(cls=%s)", drawing_id
        )
        return None

    ocr_t = candidate["thickness"]
    vlm_rounded = int(round(vlm_t))

    # 4a) Override: 若 VLM 厚度值本身就出现在 OCR 候选列表中，且 OCR 推荐值远大于 VLM 值
    #     （>5×），说明 OCR 把其他大尺寸标注误判为厚度，这时信任 VLM。
    _ocr_candidates = candidate.get("candidates", [])
    if vlm_rounded in _ocr_candidates and ocr_t > vlm_rounded * 5:
        logger.info(
            "[ocr_thickness] VLM=%d found in OCR candidates, OCR=%d is likely a non-thickness dimension, trusting VLM  (cls=%s)",
            vlm_rounded, ocr_t, drawing_id,
        )
        return None

    # 4b) 对称保护：若 VLM 厚度值也在 OCR 候选列表中，且 OCR 推荐了一个更小的值，
    #     说明 OCR 分类器被小尺寸标注（倒角/小孔/粗糙度值）误导，gap 分析选错了。
    #     此时若 VLM 值是合理板厚（< min(长,宽)/3），信任 VLM 的端视图判断。
    if vlm_rounded in _ocr_candidates and ocr_t < vlm_rounded:
        if vlm_l is not None and vlm_w is not None and vlm_rounded < min(vlm_l, vlm_w) / 3:
            logger.info(
                "[ocr_thickness] VLM=%d in OCR candidates, OCR=%d is smaller (likely chamfer/radius), VLM is reasonable plate thickness → trusting VLM  (cls=%s)",
                vlm_rounded, ocr_t, drawing_id,
            )
            return None

    # 4) Compare
    diff = abs(vlm_t - ocr_t)
    if diff <= _CONFLICT_THRESHOLD_MM:
        logger.info(
            "[ocr_thickness] OK  diff=%dmm vlm=%s ocr=%s  (cls=%s)",
            diff, vlm_t, ocr_t, drawing_id,
        )
        return None

    # 5) Conflict detected
    # Extract the raw dim string for diagnostics
    dim_m = re.search(r'(?:外形尺寸|【外形尺寸】)[：:\s]*([^\n]+)', feature_text)
    dim_str = dim_m.group(1).strip() if dim_m else "?"

    flag = {
        "thickness_conflict": True,
        "thickness_vlm": int(round(vlm_t)),
        "thickness_ocr": ocr_t,
        "thickness_source": candidate["source"],
        "thickness_candidates_vlm": dim_str,
        "thickness_candidates_ocr": candidate["candidates"],
        "thickness_recommended": ocr_t,
    }
    logger.warning(
        "[ocr_thickness] CONFLICT vlm=%s ocr=%s rule=%s  (cls=%s)",
        vlm_t, ocr_t, candidate["source"], drawing_id,
    )
    return flag
