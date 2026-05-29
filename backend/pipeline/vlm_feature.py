# -*- coding: utf-8 -*-
import base64
import hashlib
import json
import logging
import os
import re
import time
from collections import Counter
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

from openai import OpenAI

_FACES = ("front", "right", "top")
_CREO_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}

_LWH_RE = re.compile(
    r'长\s*([\d.]+)\s*mm\s*[×x]\s*宽\s*([\d.]+)\s*mm\s*[×x]\s*高\s*([\d.]+)\s*mm'
)
_DS_FULL_REPLACE_TOL = 5       # per-axis tolerance for single-group complete replacement (mm)
_DS_AXIS2_REFINE_TOL = 4       # minimum deviation (mm) to accept drawing second-axis over OCC when best group directly shows largest dim
_DS_AXIS2_OVERRIDE_TOL = 20    # second-axis deviation above which drawing overrides in intermediate-match cases (mm)
_DS_THICKNESS_BLEND_TOL = 5    # thickness deviation below which OCC is kept as-is (mm)
_DS_THICKNESS_DIRECT_TOL = 15  # thickness deviation below which drawing value is used directly (mm); above this, blend

# ── Semantic-only VLM prompt (new, used by all PRT extractors) ──
# VLM only fills: 零件名称, 形态, 类型, 热处理与探伤, 其他特征
# Geometry dimensions are sourced from STEP analysis, not VLM.
_VLM_SEMANTIC_FIELDS_PROMPT = """
以下图片是该零件的截图。请仅根据图片可见内容，按以下格式逐字段输出：

【零件名称】（根据外形推断，如无法判断填"无"）
【形态】（一句话描述整体几何形态）
【类型】（功能类别，如：轴套类-配合件）
【热处理与探伤】（硬度要求或热处理工艺；如无填"无"）
【其他特征】（描述槽、凸台、台阶、布置关系等语义信息；如无填"无"）

要求：
- 只描述图片中明确可见的特征
- 不推测未标注的主尺寸数值
- 不输出关键尺寸、外圆内孔、孔径、公差等几何主字段
""".strip()

_DRAWING_FIELDS = (
    "外形尺寸",
    "通孔",
    "沉孔沉槽",
    "螺纹孔",
    "特殊孔",
    "尺寸公差",
    "形位公差",
    "表面粗糙度",
    "表面处理",
    "刻字",
)

_SEMANTIC_FIELDS = ("零件名称", "形态", "类型", "热处理与探伤", "其他特征")

_VLM_ENGINEERING_DRAWING_PROMPT = """
你是专业机械工程师，正在阅读同一个零件的 Creo 工程视图截图。请先逐张扫描图片中的数字标注和文字标注，再按字段输出。

【外形尺寸】
第一步：识别每张图的视图类型（主视图/左视图/右视图/俯视图/剖视图/其他）
第二步：按视图类型提取轴向尺寸
  - 主视图 → 长方向和高方向的最大外轮廓标注值
  - 左视图/右视图 → 宽（厚度）方向和高方向的最大外轮廓标注值
  - 俯视图 → 长方向和宽方向的最大外轮廓标注值
第三步：取各方向最大整体外轮廓值，合并输出一个值，格式：长×宽×厚
若无明确标注或仅部分方向有数字，可补充推测值，格式：推测:长×宽×厚(来源：主视图轮廓/俯视图比例等)；推测值与已标注值用"|"分隔
★ 格式强制要求：【外形尺寸】字段必须以数字（如 282×129×21.5）开头；可在"|"后附加来源说明，但绝不允许只输出"来源："或分析文字而省略数字
规则：厚度取最薄方向整体通长尺寸，不取槽深/台阶高/局部特征深度；只抄图纸数字，不估算
【通孔】数量-直径，多种孔径用分号分隔
【沉孔沉槽】沉孔写直径×角度或直径×深度，沉槽写宽×深
【螺纹孔】数量-规格 孔深N 底孔深N，平底或通孔需注明
【特殊孔】钢丝螺套、销孔、铆孔等特殊孔型
【尺寸公差】逐张扫描以下位置：
  ① 每个尺寸数字旁的公差符号（如 ±0.05、+0.02/-0.01、H7、h6、JS6）
  ② 标题栏或技术要求区的"未注公差"说明（如"未注公差按GB/T 1804-m"）
  ③ 公差框格内的极限偏差数值
  格式：尺寸值 公差；未注公差说明；如确实无任何公差标注则填"无"
【形位公差】逐张扫描公差框格（矩形框+箭头引线），提取：类型符号（平面度/垂直度/位置度等）、公差值、基准代号；如确实无形位公差标注则填"无"
【表面粗糙度】Ra 或 Rz 值，含未注说明
【表面处理】阳极化、镀层、发黑、喷涂等
【热处理与探伤】硬度、热处理、探伤检测要求
【刻字】字高×深度×内容，逐处列出
【零件名称】根据外形推断，如无法判断填"无"
【形态】一句话描述整体几何形态
【类型】功能类别
【其他特征】凸台、加强筋、镂空、退刀槽、键槽、装配孔等结构描述

规则：
- 数字必须原样抄录，不得估算
- 识别不确定时在该值后加"[?]"
- 多视图同一字段有矛盾时用"|"分隔并注明来源
- 所有字段必须输出，无内容填"无"
- 不要输出字段之外的解释文字
""".strip()


def _default_vlm_fields() -> dict:
    return {field: "无" for field in (*_SEMANTIC_FIELDS, *_DRAWING_FIELDS)}

# Legacy VLM prompt (kept for non-PRT routes like dual-source/creo-only)
_VLM_VISUAL_FIELDS_PROMPT = """
以下图片是该零件的截图。请仅根据图片可见内容，按以下格式逐字段输出：

【零件名称】（根据外形推断，如无法判断填"无"）
【形态】（一句话描述整体几何形态）
【类型】（功能类别，如：轴套类-配合件）
【外圆与内孔】（外圆直径及公差；内孔直径及公差；如无填"无"）
【螺纹与螺孔】（螺纹规格、数量；如无填"无"）
【热处理与探伤】（硬度要求或热处理工艺；如无填"无"）
【其他特征】（键槽、退刀槽等特殊结构；如无填"无"）

要求：
- 只描述图片中明确可见的特征
- 不推测未标注的数值
- 每字段多条内容用分号（；）分隔
""".strip()


def _parse_structured_fields(text: str) -> dict:
    result = {}
    segments = re.split(r"(【[^】]+】)", text)
    # segments alternates: [pre_text, 【key1】, raw1, 【key2】, raw2, ...]
    i = 1
    while i < len(segments) - 1:
        key = segments[i].strip("【】").strip()
        raw = segments[i + 1] if i + 1 < len(segments) else ""
        first_line = raw.split('\n')[0].strip().lstrip("：").strip()
        if key == "外形尺寸":
            # Prefer explicit conclusion patterns (handles 3-step VLM reasoning output).
            # Capture full line, then strip only Chinese-text noise after `|` (e.g. "参考外形尺寸：...").
            # View-group pipes like "238×163×8.35|270×163×8[?]" start with a digit → kept.
            m = re.search(r'(?:整体外形尺寸|最终尺寸)[：:]\s*([^\n]+)', raw)
            if m and (not first_line or not re.match(r'^\d', first_line)):
                val = re.sub(r'\s*\|\s*[一-鿿\s][^|]*$', '', m.group(1)).strip()
            elif first_line:
                val = first_line
            else:
                val = next(
                    (ln.strip().lstrip("：").strip() for ln in raw.split('\n')[1:] if ln.strip()),
                    ""
                )
            # If the resolved value has no × separator and doesn't start with a digit (after
            # stripping 推测: prefix), it's descriptive text (e.g. view-type labels), not a
            # dimension. Discard to avoid polluting downstream parsing.
            # Exclude "无" — it's a valid empty marker, not junk text.
            if val and val != "无" and '×' not in val:
                _stripped = re.sub(r'^推测:\s*', '', val)
                if not re.match(r'^\d', _stripped):
                    val = ""
            # Fallback: VLM sometimes outputs 来源：...标注NNN（）...NNN为厚度... only,
            # with no leading dimension numbers (non-compliant with prompt format).
            # Extract outer contour dims from 标注NNN（） annotations and thickness from NNN为厚度.
            if not val:
                raw_flat = raw.replace('\n', ' ')
                contour = re.findall(r'(\d+(?:\.\d+)?)[（(][）)]', raw_flat)
                thick_m = re.search(r'(\d+(?:\.\d+)?)为厚度', raw_flat)
                if len(contour) >= 2 and thick_m:
                    val = f"{contour[0]}×{contour[1]}×{thick_m.group(1)}"
        elif first_line:
            val = first_line
        else:
            val = next(
                (ln.strip().lstrip("：").strip() for ln in raw.split('\n')[1:] if ln.strip()),
                ""
            )
        if key:
            result[key] = val
        i += 2
    return result


# ── Expected VLM output fields (from _SEMANTIC_FIELDS + _DRAWING_FIELDS) ──
_NORMALIZE_FIELDS = (
    "零件名称", "形态", "类型", "热处理与探伤", "其他特征",
    "外形尺寸", "通孔", "沉孔沉槽", "螺纹孔", "特殊孔",
    "尺寸公差", "形位公差", "表面粗糙度", "表面处理", "刻字",
)

_EMPTY_VARIANTS = frozenset({"无", "无。", "暂无", "N/A", "None", "none", ""})

_SURFACE_TREATMENT_KEYWORDS = frozenset({
    "阳极化", "镀层", "发黑", "喷漆", "喷涂", "电镀", "磷化", "氧化", "涂覆",
    "镀铬", "镀锌", "镀镍", "镀铜", "化学镀", "钝化",
})


def _extract_kezi_from_tech_req(tech_list: list) -> str:
    for item in tech_list:
        for line in str(item).split('\n'):
            if "刻字" in line:
                return re.sub(r'^\s*\d+[,，]?\s*', '', line).strip().rstrip('。')
    return ""


def _extract_surface_treatment_from_tech_req(tech_list: list) -> str:
    for item in tech_list:
        for line in str(item).split('\n'):
            if any(kw in line for kw in _SURFACE_TREATMENT_KEYWORDS):
                return re.sub(r'^\s*\d+[,，]?\s*', '', line).strip().rstrip('。')
    return ""


def _normalize_overall_dims(val: str) -> str:
    """Minimal normalization: unify × separator, preserve 推测/|/source."""
    if not val or val == "无":
        return "无"

    # Strip |来源：... explanation suffixes added by VLM to justify its extraction.
    # These contain internal-feature numbers (e.g. 172/84/75) that must not
    # contaminate the dim_pool used for H snapping.
    val = re.sub(r'\s*\|\s*来源[：:][^|]*', '', val)
    # Unify separators globally: x, X, * → ×
    val = re.sub(r'\s*[xX*]\s*', '×', val)
    # Remove stray 长/宽/高/mm prefixes (VLM may add them inconsistently)
    val = re.sub(r'[长宽高]\s*', '', val)
    val = re.sub(r'mm', '', val)
    # Collapse multiple spaces
    val = re.sub(r'\s+', ' ', val).strip()
    return val


def _normalize_vlm_output(fields: dict) -> dict:
    """Normalize VLM output fields for consistent format across calls."""
    result = {}
    for field in _NORMALIZE_FIELDS:
        val = (fields.get(field, "") or "").strip()
        val = re.sub(r'\s+', ' ', val)
        if val in _EMPTY_VARIANTS:
            val = "无"
        if field == "外形尺寸" and val != "无":
            val = _normalize_overall_dims(val)
        result[field] = val
    # Carry through extra fields not in standard list
    for k, v in fields.items():
        if k not in result:
            result[k] = v
    return result


# Cross-call dimension stability cache (in-process only, resets on restart)
_dimension_cache: dict[str, dict] = {}


def _make_cache_key(image_paths: list) -> str:
    """Create a deterministic cache key from image paths."""
    h = hashlib.sha256()
    for p in sorted(image_paths, key=lambda x: str(x)):
        try:
            st = Path(p).stat()
            h.update(f"{Path(p).resolve()}|{st.st_mtime}|{st.st_size}\n".encode())
        except Exception:
            h.update(str(p).encode())
    return h.hexdigest()[:16]


def _validate_and_mark_dimensions(fields: dict, cache_key: str) -> dict:
    """Validate 外形尺寸 reasonableness and apply cross-call stability lock."""
    result = dict(fields)
    dim_str = result.get("外形尺寸", "无")
    if dim_str == "无":
        return result

    nums = re.findall(r'(\d+(?:\.\d+)?)', dim_str)
    if len(nums) < 3:
        return result

    values = [float(n) for n in nums[:3]]
    thickness = min(values)

    # Range check: flag implausible thickness
    if thickness > 100 or thickness < 2:
        result["外形尺寸"] = dim_str + " [?]"
        return result

    # Cross-call stability lock
    if cache_key in _dimension_cache:
        cached = _dimension_cache[cache_key]
        cached_vals = cached["values"]
        for cur, prev in zip(values, cached_vals):
            if prev > 0 and abs(cur - prev) / prev > 0.10:
                result["外形尺寸"] = cached["dim_str"]
                return result

    _dimension_cache[cache_key] = {"values": values, "dim_str": dim_str}
    return result


def _snap_to_pool(candidate: float, pool_str: str, max_delta: float = 20.0) -> float:
    """Return the number in pool_str nearest to candidate if within max_delta; else candidate."""
    nums = [float(x) for x in re.findall(r'\d+(?:\.\d+)?', pool_str)]
    if not nums:
        return candidate
    nearest = min(nums, key=lambda v: abs(v - candidate))
    return nearest if abs(nearest - candidate) <= max_delta else candidate


def _infer_dimensions_from_occ_vlm(occ_str: str, vlm_str: str, dim_pool: str = "") -> Optional[dict]:
    """Infer true part dimensions (T, L, H) from OCC bounding box + VLM drawing values.

    Algorithm derived from empirical analysis of (OCC, VLM, true) triples.
    dim_pool: optional space/semicolon-separated number string for snapping H estimates.
    Returns {"T": float, "L": float, "H": float} or None if OCC is unparseable.
    """
    occ_nums = [float(x) for x in re.findall(r'\d+(?:\.\d+)?', occ_str or "")]
    if len(occ_nums) < 3:
        return None
    OCC_L, OCC_H, OCC_T = sorted(occ_nums, reverse=True)[:3]

    # Parse VLM groups: split by |, strip 推测: prefix
    # Skip groups that contain ?, Chinese characters, or slash-separated dim lists
    vlm_groups: list[list[float]] = []
    for part in re.split(r'\s*\|\s*', vlm_str or ""):
        part = re.sub(r'^推测:\s*', '', part.strip())
        # Strip ；来源：... or ;来源：... suffix (fullwidth/halfwidth semicolon) so that
        # dimension groups like "147.4×19×8.35；来源：各视图标注" are not discarded.
        part = re.sub(r'\s*[；;]\s*来源[：:][^|]*', '', part)
        part = re.sub(r'[（(][^（(）)0-9]*[）)]', '', part)  # strip (参考) / （参考） — text-only, keep (240)
        part = re.sub(r'\s*\[[^\[\]]*\]', '', part)     # strip [?] / [参考] etc.
        if '?' in part or re.search(r'[一-鿿/]', part):
            continue
        nums = [float(x) for x in re.findall(r'\d+(?:\.\d+)?', part)]
        if len(nums) >= 2:
            vlm_groups.append(nums)

    if not vlm_groups:
        # VLM extraction completely failed. If dim_pool (from other VLM fields) is available,
        # attempt to recover H: the largest pool value that is below OCC_H*0.9 indicates a
        # real part height dimension that OCC over-inflated (e.g. G15: 186 < 240*0.9=216).
        if dim_pool:
            pool_nums = [float(x) for x in re.findall(r'\d+(?:\.\d+)?', dim_pool)]
            h_candidates = [v for v in pool_nums if OCC_T * 2 < v < OCC_H * 0.9]
            if h_candidates:
                return {"T": OCC_T, "L": OCC_L, "H": max(h_candidates)}
        return {"T": OCC_T, "L": OCC_L, "H": OCC_H}

    # Step 1: VLM validity — max VLM value must be ≥ 95% of OCC large-face max
    vlm_max = max(v for grp in vlm_groups for v in grp)
    vlm_valid = vlm_max / max(OCC_L, OCC_H) >= 0.95

    # Step 2: L and H
    main_group: list[float] = []
    if vlm_valid:
        main_group = max(vlm_groups, key=lambda g: g[0])
        L = max(main_group[0], OCC_L)
        # For face groups (first ≈ L, 3+ values), prefer the value closer to OCC_H
        # between second and last element. Engineering drawings often place height
        # as the third element (e.g. "240×94×132.5" where 132.5 is height), but
        # sometimes as the second (e.g. "258×186×42" where 186 is height).
        VLM_H = main_group[1] if len(main_group) >= 2 else OCC_H
        if (
            len(main_group) >= 3
            and L > 0 and abs(main_group[0] - L) / L < 0.01
        ):
            cand_last = main_group[-1]
            if abs(cand_last - OCC_H) < abs(VLM_H - OCC_H):
                VLM_H = cand_last
        if VLM_H >= OCC_H * 0.9:
            H = VLM_H
        else:
            # Multi-group confirmation: VLM_H in ≥2 groups overrides the 90% threshold
            confirmed = sum(
                1 for grp in vlm_groups
                if any(abs(v - VLM_H) / max(VLM_H, 1) <= 0.05 for v in grp)
            )
            if confirmed >= 2:
                # Cross-confirmed across views; check discrepancy against OCC.
                # Moderate gap [20, 50]: OCC is more reliable than VLM for height.
                if 20 <= abs(OCC_H - VLM_H) <= 50:
                    H = OCC_H
                else:
                    H = VLM_H
            else:
                # vlm_second: max first-element of non-face groups that is a plausible H.
                # Guard g[0] < OCC_H to exclude near-face length projections (e.g. 246 when OCC_H=169).
                vlm_second = max(
                    (g[0] for g in vlm_groups
                     if len(g) >= 1 and L > 0 and abs(g[0] - L) / L > 0.01 and g[0] < OCC_H),
                    default=None,
                )
                if vlm_second is not None:
                    err_s = abs(OCC_H - vlm_second)
                    if err_s > 50:
                        # Large gap: vlm_second+16 empirically corrects; snap tight (max_delta=10)
                        H = _snap_to_pool(vlm_second + 16, dim_pool, max_delta=10)
                    elif err_s >= 20:
                        H = (OCC_H + vlm_second) / 2
                    else:
                        H = vlm_second
                elif abs(OCC_H - VLM_H) > 100:
                    # No valid non-face groups; single-group large discrepancy → average + snap.
                    # max_delta=5: only snap to very close annotated values; prevents wrong snaps
                    # to distant pool numbers (e.g. 172 at dist=12.5 from midpoint 184.5).
                    H = _snap_to_pool((OCC_H + VLM_H) / 2, dim_pool, max_delta=5)
                elif abs(OCC_H - VLM_H) >= 50:
                    # Moderate discrepancy [50, 100]: OCC inflated but VLM reading is credible
                    # only when VLM_H is ≥70% of OCC_H. Below that the reading is an unrelated
                    # feature dimension, not the part height → fall back to OCC_H.
                    # (e.g. VLM_H=94 vs OCC_H=163: 57% → reject; VLM_H=186 vs OCC_H=240: 77% → accept)
                    H = VLM_H if VLM_H >= OCC_H * 0.7 else OCC_H
                else:
                    H = OCC_H
    else:
        L, H = OCC_L, OCC_H

    # Step 3: T — find VLM_T candidate from side-view groups
    # Lower bound raised vs. flat OCC_T*0.3 to handle massively inflated OCC_T
    lower_bound = max(1.0, OCC_T * 0.15)
    rounded_counts = Counter(round(v, 1) for grp in vlm_groups for v in grp)
    repeated_max = max((v for v, cnt in rounded_counts.items() if cnt >= 2), default=0.0)

    # VLM values ≤8mm typically reflect holes/slots, not plate thickness.
    # Raised from the earlier <5 threshold. Guard inactive when OCC_T<10
    # (single-digit geometry minimum = genuinely thin part, e.g. 3mm sheet).
    vlm_t_floor = 8.0 if OCC_T >= 10 else 0.0

    T_candidates: list[float] = []
    for grp in vlm_groups:
        first = grp[0]
        if L > 0 and abs(first - L) / L < 0.01:  # face group (first ≈ L), skip
            continue
        for v in grp:
            if (round(v, 1) > repeated_max
                    and v > max(lower_bound, vlm_t_floor)
                    and v < OCC_H * 0.5):
                T_candidates.append(v)

    if T_candidates:
        VLM_T = min(T_candidates)
        ratio = OCC_T / VLM_T
        if ratio <= 1.3:
            T = OCC_T
        elif ratio > 2.5:
            # OCC heavily inflated: average to avoid over-correcting (e.g. 30.9 vs 8.35 → 19.6)
            T = (OCC_T + VLM_T) / 2
        else:
            T = VLM_T
    else:
        T = OCC_T
        # Face-group fallback: last value of main-group face view when no side candidates
        if vlm_valid and main_group and len(main_group) >= 3:
            if L > 0 and abs(main_group[0] - L) / L < 0.01:
                fb = main_group[-1]
                if fb > lower_bound and fb < OCC_H * 0.5:
                    diff_fb = abs(OCC_T - fb)
                    has_side_group = any(
                        len(g) >= 2 and abs(g[0] - L) / max(L, 1) > 0.01
                        for g in vlm_groups
                    )
                    if diff_fb < 5:
                        # Small absolute gap: trust VLM directly (G14: 3.9 vs 2 → 2)
                        T = fb
                    elif OCC_T / fb > 2.5:
                        # Average when OCC heavily inflated AND no side corroboration, OR face T
                        # is only marginally above the thin-value floor (fb < floor*1.5) meaning
                        # VLM face reading itself is unreliable even with a side group present.
                        # (G13: no side group → avg; new case: fb=8.35 < 12 → avg)
                        # When side group present AND fb is well above floor: trust VLM (G10: fb=12.5≥12)
                        if diff_fb > 20 and (not has_side_group or fb < vlm_t_floor * 1.5):
                            T = (OCC_T + fb) / 2
                        else:
                            # Side group corroborates credible fb, or moderate gap: trust VLM
                            T = fb

    # VLM thin-value guard: values ≤8mm in VLM often reflect small features (holes, slots),
    # not plate thickness. When VLM-derived T ≤8 but OCC is double-digit (≥10), revert to OCC_T.
    # Guard is silent when OCC_T <10 (single-digit geometry minimum = genuinely thin part).
    if T <= 8 and OCC_T >= 10:
        T = OCC_T

    return {"T": T, "L": L, "H": H}


def _fmt_inferred(v: float) -> str:
    """Format inferred dimension: integer when possible, else 1 decimal."""
    return str(int(v)) if v == int(v) else str(round(v, 1))


def _assemble_prt_fields(txt_buckets: dict, vlm_visual_text: str) -> str:
    """Legacy: Merge CREO_TASK.txt buckets with VLM visual fields into 11-field text.
    Kept for backward compatibility (non-PRT routes). PRT routes now use
    _merge_geometry_creo_vlm_fields instead.
    """
    vlm_fields = _parse_structured_fields(vlm_visual_text)

    def _get(key, fallback="无"):
        return vlm_fields.get(key, fallback) or fallback

    tech_req = "；".join(txt_buckets.get("技术要求", [])) or "无"
    major_dims = "；".join(txt_buckets.get("主要外形尺寸", []))
    feature_dims = "；".join(txt_buckets.get("特征尺寸", []))
    key_dims = "；".join(filter(None, [major_dims, feature_dims])) or "无"
    chamfers = "；".join(
        v for v in txt_buckets.get("倒角圆角", []) if not v.startswith("R")
    ) or "无"
    fillets = "；".join(
        v for v in txt_buckets.get("倒角圆角", []) if v.startswith("R")
    ) or "无"

    lines = [
        f"【零件名称】{_get('零件名称')}",
        f"【形态】{_get('形态')}",
        f"【类型】{_get('类型')}",
        f"【技术要求】{tech_req}",
        f"【关键尺寸】{key_dims}",
        f"【外圆与内孔】{_get('外圆与内孔')}",
        f"【螺纹与螺孔】{_get('螺纹与螺孔')}",
        f"【倒角】{chamfers}",
        f"【热处理与探伤】{_get('热处理与探伤')}",
        f"【过渡特征】{fillets}",
        f"【其他特征】{_get('其他特征')}",
    ]
    return "\n".join(lines)


# ── Three-layer feature assembly (new for PRT) ──────────────────────────
# Layer priority: Geometry (STEP) > Creo txt supplement > VLM semantic


def _empty_geo_fields() -> dict:
    return {"关键尺寸": "", "外圆与内孔": "", "螺纹与螺孔": "", "过渡特征": "", "其他特征": ""}


def _extract_geometry_structured_fields(step_path: str) -> dict:
    """从STEP几何分析文本中解析结构化字段。

    调用现有 extract_geometry_features(), 将其自由文本输出映射为结构化字段字典。
    如果STEP不可用或解析失败，返回空字段。
    """
    if not step_path or not os.path.exists(step_path):
        return _empty_geo_fields()

    try:
        from ..prt_pipeline import extract_geometry_features
        geo_text = extract_geometry_features(step_path)
    except Exception:
        return _empty_geo_fields()

    if not geo_text or geo_text.startswith("[") or geo_text == "[No features extracted]":
        return _empty_geo_fields()

    return _parse_geometry_text_to_fields(geo_text)


def _parse_geometry_text_to_fields(text: str) -> dict:
    """解析 geometry_analyzer 的 format_features_text 输出为结构化字段。"""
    fields = {}
    for m in re.finditer(r'【([^】]+)】([^\n【]*)', text):
        fields[m.group(1).strip()] = m.group(2).strip()

    result = _empty_geo_fields()

    # 【关键尺寸】← 【尺寸】
    dim = fields.get("尺寸", "")
    if dim:
        result["关键尺寸"] = dim

    # 【外圆与内孔】← 【圆柱面特征】
    cyl = fields.get("圆柱面特征", "")
    if cyl:
        result["外圆与内孔"] = cyl

    # 【螺纹与螺孔】← 【孔特征】
    hole = fields.get("孔特征", "")
    if hole:
        result["螺纹与螺孔"] = hole

    # 【过渡特征】← not directly available from geometry (FreeCAD doesn't reliably identify fillets)
    # Leave empty; filled by Creo txt supplement.

    # 【其他特征】← 【几何特征】+ 【形状分类】
    other_parts = []
    shape = fields.get("形状分类", "")
    if shape:
        other_parts.append(f"形状分类:{shape}")
    geo_feat = fields.get("几何特征", "")
    if geo_feat:
        other_parts.append(geo_feat)
    if other_parts:
        result["其他特征"] = "；".join(other_parts)

    return result


def _extract_vlm_semantic_fields(
    image_paths: list[Path],
    prompt: Optional[str] = None,
) -> dict:
    effective_prompt = prompt or _VLM_SEMANTIC_FIELDS_PROMPT
    vlm_text = _call_vlm_with_images(image_paths, effective_prompt)
    defaults = _default_vlm_fields()
    if not vlm_text:
        return defaults

    fields = _parse_structured_fields(vlm_text)
    result = defaults.copy()
    for key in result:
        result[key] = fields.get(key, "无") or "无"
    return result


def _validate_drawing_fields(fields: dict) -> dict:
    warnings = []

    dim_str = fields.get("外形尺寸", "")
    nums = []
    for raw in re.findall(r"\d+(?:\.\d+)?", dim_str):
        try:
            value = float(raw)
        except ValueError:
            continue
        if value > 0:
            nums.append(value)
    if len(nums) >= 3:
        thickness = min(nums)
        if thickness > 100:
            warnings.append(f"外形尺寸厚度 {thickness}mm 超过100mm，疑似误读")
        elif thickness < 5:
            warnings.append(f"外形尺寸厚度 {thickness}mm 小于5mm，疑似误读")

    standard_threads = {"M2", "M2.5", "M3", "M4", "M5", "M6", "M8", "M10", "M12", "M16"}
    for spec in re.findall(r"M\d+(?:\.\d+)?", fields.get("螺纹孔", "")):
        if spec not in standard_threads:
            warnings.append(f"螺纹规格 {spec} 非标准系列，请确认")

    for raw in re.findall(r"φ\s*(\d+(?:\.\d+)?)", fields.get("通孔", ""), flags=re.IGNORECASE):
        diameter = float(raw)
        if diameter > 50:
            warnings.append(f"通孔直径 φ{diameter} 超过50mm，疑似误读")
        elif diameter < 1:
            warnings.append(f"通孔直径 φ{diameter} 小于1mm，疑似误读")

    uncertain_fields = [field for field in _DRAWING_FIELDS if "[?]" in str(fields.get(field, ""))]
    if uncertain_fields:
        warnings.append(f"以下字段识别存在不确定性（已标[?]）：{', '.join(uncertain_fields)}")

    result = dict(fields)
    result["_warnings"] = warnings
    result["_has_warnings"] = bool(warnings)
    return result


def _extract_creo_thread_specs(creo_txt_buckets: dict) -> str:
    """从 Creo txt 技术要求中提取螺纹规格作为补充。

    搜索 M 螺纹模式（M3、M6、M10×1.5、4-M6 等），
    以及 螺纹孔/攻丝 等关键词所在行。
    """
    tech_notes = creo_txt_buckets.get("技术要求", [])
    if not isinstance(tech_notes, list) or not tech_notes:
        return ""

    found = []
    for note in tech_notes:
        # Match patterns like M3, M6, M10×1.5, 4-M6, M6-6H
        m_matches = re.findall(r'(?:\d+\s*[-–×xX*])?\s*M\d+(?:\s*[×xX*]\s*\d+\.?\d*)?(?:\s*[-–]\s*\d*[Hh])?', note)
        found.extend(m_matches)
        # Match 螺纹孔/攻丝 related lines
        if re.search(r'螺纹|攻丝|螺孔', note):
            # Extract the sentence/line containing the keyword
            for line in note.split('\n'):
                if re.search(r'螺纹|攻丝|螺孔', line):
                    cleaned = line.strip().rstrip('。，；')
                    if cleaned and cleaned not in found:
                        found.append(cleaned)

    return "；".join(dict.fromkeys(found)) if found else ""


def _fmt_mm_value(v: float) -> str:
    return str(int(v)) if v % 1 == 0 else str(round(v, 1))


def _apply_drawing_size_reference_to_lwh(lwh_str: str, drawing_size: str, occ_ref: str = "") -> str:
    m = _LWH_RE.search(lwh_str)
    if not m or not drawing_size or drawing_size == "无":
        return lwh_str

    # Strip parenthetical notes (Chinese/parens) which may contain stray numbers
    clean = re.sub(r"[（(][^）)]*[）)]", "", drawing_size).strip()

    current = [float(m.group(1)), float(m.group(2)), float(m.group(3))]
    current_thickness_idx = current.index(min(current))
    large_idx = sorted(
        [i for i in range(3) if i != current_thickness_idx],
        key=lambda i: current[i], reverse=True,
    )

    # Use occ_ref to determine the original second large value (before Creo anchoring)
    om = _LWH_RE.search(occ_ref)
    if om:
        occ_vals = [float(om.group(1)), float(om.group(2)), float(om.group(3))]
        occ_thickness_idx = occ_vals.index(min(occ_vals))
        occ_large_idx = sorted(
            [i for i in range(3) if i != occ_thickness_idx],
            key=lambda i: occ_vals[i], reverse=True,
        )
        ref_2nd_large = occ_vals[occ_large_idx[1]]
    else:
        ref_2nd_large = current[large_idx[1]]

    parsed_groups = []
    for part in re.split(r"[；;|]", clean):
        nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", part)]
        if len(nums) >= 2:
            ordered = sorted(nums, reverse=True)
            thickness = ordered[2] if len(nums) >= 3 else None
            parsed_groups.append(((ordered[0], ordered[1]), thickness))

    if not parsed_groups:
        return lwh_str

    # 0) Single complete 3D group: replace entirely when close enough to current.
    complete_3d = [g for g in parsed_groups if g[1] is not None]
    if len(complete_3d) == 1:
        cand = complete_3d[0]
        cand_ordered = [cand[0][0], cand[0][1], cand[1]]
        cur_s = sorted(current, reverse=True)
        if abs(cand_ordered[0] - cur_s[0]) <= _DS_FULL_REPLACE_TOL and abs(cand_ordered[1] - cur_s[1]) <= _DS_FULL_REPLACE_TOL:
            current[large_idx[0]] = cand_ordered[0]
            current[large_idx[1]] = cand_ordered[1]
            current[current_thickness_idx] = cand_ordered[2]
            return f"长 {_fmt_mm_value(current[0])}mm × 宽 {_fmt_mm_value(current[1])}mm × 高 {_fmt_mm_value(current[2])}mm"

    # 1) Second-axis correction.
    best = min(parsed_groups, key=lambda g: abs(g[0][0] - max(current)))
    _cur_max = max(current)
    if abs(best[0][0] - _cur_max) <= 5:
        # Best group directly shows the largest dim — its axis[1] is the labeled second-large.
        # Trust the drawing if it differs from OCC by more than _DS_AXIS2_REFINE_TOL.
        if abs(best[0][1] - current[large_idx[1]]) > _DS_AXIS2_REFINE_TOL:
            current[large_idx[1]] = best[0][1]
    elif abs(best[0][0] - _cur_max) > 30 and abs(best[0][0] - current[large_idx[1]]) <= 5:
        # No group captured the largest dim (e.g. stripped as parenthetical) — best group is
        # a cross-section view of the second-large dim; use its axis[1] to refine it.
        if abs(best[0][1] - current[large_idx[1]]) > 1:
            current[large_idx[1]] = best[0][1]
    elif abs(best[0][1] - ref_2nd_large) > _DS_AXIS2_OVERRIDE_TOL:
        # Intermediate match — strong deviation from pre-anchor OCC suggests axis reordering.
        current[large_idx[1]] = best[0][1]

    # 2) Thickness correction.
    def _resolve_t(g):
        t, ax1 = g[1], g[0][1]
        # Substitute axis[1] only when it's a plausible thickness (≤50mm) AND t is tiny.
        # If ax1 > 50mm it's a large dimension, not a thickness — always keep t.
        return t if (t >= ax1 * 0.5 or ax1 > 50) else ax1

    ref_thickness = None
    thickness_group = None
    thickness_consistent = False  # True when all complete_3d groups agree

    if best[1] is not None:
        ref_thickness = _resolve_t(best)
        thickness_group = best
    else:
        cur_t = current[current_thickness_idx]
        resolved = [(g, _resolve_t(g)) for g in complete_3d]
        if resolved:
            thickness_group, ref_thickness = min(resolved, key=lambda x: abs(x[1] - cur_t))
            # Consistent signal: all groups agree within 1mm → drawing is authoritative
            thickness_consistent = len({round(rt, 1) for _, rt in resolved}) == 1

    if ref_thickness is not None:
        # Skip if source group is a face-view (axis[0]≈max) showing a feature depth.
        # Such a group's "thickness" is a slot/pocket depth, not the overall part thickness.
        # Anchor against the drawing's own largest value (not max(current)) so that an
        # inflated OCC estimate doesn't prevent the face-view check from firing.
        drawing_max = max(g[0][0] for g in parsed_groups) if parsed_groups else max(current)
        is_face_view_depth = (
            thickness_group is not None
            and abs(thickness_group[0][0] - drawing_max) <= 5
            and ref_thickness < current[current_thickness_idx] * 0.5
        )
        if not is_face_view_depth:
            diff = abs(ref_thickness - current[current_thickness_idx])
            if thickness_consistent and diff > _DS_THICKNESS_BLEND_TOL:
                # All drawing groups agree — use directly regardless of magnitude
                current[current_thickness_idx] = ref_thickness
            elif diff > _DS_THICKNESS_DIRECT_TOL:
                # Large discrepancy, inconsistent sources — blend as compromise
                current[current_thickness_idx] = (current[current_thickness_idx] + ref_thickness) / 2
            elif diff > _DS_THICKNESS_BLEND_TOL:
                # Moderate discrepancy — drawing value is trustworthy, use directly
                current[current_thickness_idx] = ref_thickness

    return f"长 {_fmt_mm_value(current[0])}mm × 宽 {_fmt_mm_value(current[1])}mm × 高 {_fmt_mm_value(current[2])}mm"


def _anchor_occ_lwh_to_creo(occ_str: str, creo_parts: list, creo_feature_parts: list = None) -> str:
    """Replace OCC bounding-box 长/宽/高 values with nearest Creo annotated dims.

    Strategy (mirrors _pick_occ_anchored in process_gen.py):
      - Parse three floats from "长 Xmm × 宽 Ymm × 高 Zmm"
      - Collect simple numeric values from creo_parts
      - Process axes largest-first; for each OCC value prefer the closest
        Creo candidate in [occ*0.85, occ*1.05]; fall back to globally nearest
      - Only substitute when the best candidate is within 15% of OCC value;
        otherwise keep the OCC value (bad substitution is worse than OCC estimate)
      - creo_feature_parts: feature dims only (2-50mm ×N), for interval median algorithm
    """
    m = _LWH_RE.search(occ_str)
    if not m:
        return occ_str

    creo_nums = []
    for p in creo_parts:
        for tok in re.findall(r'\d+(?:\.\d+)?', str(p)):
            v = float(tok)
            if v > 1:
                creo_nums.append(v)
    creo_nums = sorted(set(creo_nums), reverse=True)
    if not creo_nums:
        return occ_str

    occ_vals = [float(m.group(1)), float(m.group(2)), float(m.group(3))]
    order = sorted(range(3), key=lambda i: occ_vals[i], reverse=True)
    remaining = list(creo_nums)
    result = list(occ_vals)  # default: keep OCC value

    for idx in order:
        occ_v = occ_vals[idx]
        in_range = [x for x in remaining if occ_v * 0.85 <= x <= occ_v * 1.05]
        chosen = (
            min(in_range, key=lambda x: abs(x - occ_v))
            if in_range
            else min(remaining, key=lambda x: abs(x - occ_v))
        )
        if abs(chosen - occ_v) / occ_v <= 0.15:
            result[idx] = chosen
        if chosen in remaining:
            remaining.remove(chosen)

    # Cap thickness: the smallest of the three values represents thickness and cannot exceed 50mm.
    # When triggered, use Creo feature dims (2-50mm) with interval-game median algorithm
    # to compute a realistic thickness instead of crude 50mm fallback.
    min_idx = result.index(min(result))
    logger.debug(f"[VLM_DEBUG] result={result} min_idx={min_idx} min_val={result[min_idx]} trigger={result[min_idx] >= 50}")
    if result[min_idx] >= 50:
        # Use feature dims only (creo_feature_parts) for interval algorithm;
        # fall back to creo_parts if feature list not provided (backward compat)
        thickness_parts = creo_feature_parts if creo_feature_parts else creo_parts
        thickness = _interval_avg_thickness(thickness_parts)
        logger.debug(f"[VLM_DEBUG] interval_avg_thickness returned: {thickness}")
        result[min_idx] = thickness

    return f"长 {_fmt_mm_value(result[0])}mm × 宽 {_fmt_mm_value(result[1])}mm × 高 {_fmt_mm_value(result[2])}mm"


# Fallback thickness (mm) returned when no valid Creo feature dims are found.
_INTERVAL_T_FALLBACK = 50


def _interval_avg_thickness(creo_parts: list) -> float:
    """区间博弈战力值算法：从 Creo 特征尺寸中推算材料厚度，返回胜出区间的均值。

    战力规则（三级）:
      count < 5               → 战力 = 0（无竞争力）
      5 ≤ count < 10          → 战力 = count（自然值）
      count ≥ 10              → 战力封顶 = 10（多区间高位 tie-break 决胜）
      b10 且 count ≥ 20       → 战力 = 7（极端大爆炸惩罚，覆盖封顶规则）

    擂台规则:
      b≥10 的上位区间中，战力 ≥ 7 的区间进入「绝对防御」— 取其中战力最高者（平局取高位区间）。
      无绝对防御时：纯战力 PK，最高者胜；全部 count<5 时取出现最多的区间（平局取低位）。
      b=0 底线防线：仅当所有 b≥10 区间均无数据时激活。
    返回 _INTERVAL_T_FALLBACK 当无有效尺寸数据。
    """
    # Step 1: parse feature dims, strip ×N, deduplicate
    core_vals = set()
    for p in creo_parts:
        s = str(p).strip()
        m = re.match(r'^([\d.]+)', s)
        if not m:
            continue
        v = float(m.group(1))
        if 2 <= v <= 60:
            core_vals.add(v)

    if not core_vals:
        return _INTERVAL_T_FALLBACK

    # Group by tens: [0,10), [10,20), [20,30), [30,40), [40,50), [50,60]
    buckets: dict = {}
    for v in core_vals:
        b = (int(v) // 10) * 10
        if b > 50:
            b = 50
        buckets.setdefault(b, []).append(v)
    for b in buckets:
        buckets[b].sort()

    counts = {b: len(vals) for b, vals in buckets.items()}
    logger.debug(f"[VLM_DEBUG] interval buckets: {sorted(buckets.items())}")
    logger.debug(f"[VLM_DEBUG] interval counts: {sorted(counts.items())}")

    # Step 2: dynamic combat power (战力值) per interval
    def _combat_power(b: int) -> int:
        c = counts.get(b, 0)
        if c < 5:
            return 0
        if b == 10 and c >= 20:
            return 7   # 极端爆炸惩罚：b10 count≥20 时压制
        if c >= 10:
            return 10  # 多区间竞争封顶：所有 count≥10 的区间战力相等，由高位 tie-break 决胜
        return c

    powers = {b: _combat_power(b) for b in counts}
    upper_buckets = [b for b in powers if b >= 10]

    # [0,10) last resort: only when no upper-interval buckets (b≥10) exist in data
    if not upper_buckets:
        if counts.get(0, 0) > 0:
            locked = 0
        else:
            return _INTERVAL_T_FALLBACK
    else:
        #擂台 comparison with absolute defense
        # 高位绝对防御: if any high interval has combat power >= 7,
        # the highest such interval wins (blocks lower intervals from leaping)
        defenders = [(b, powers[b]) for b in upper_buckets if powers[b] >= 7]
        if defenders:
            locked = max(defenders, key=lambda x: (x[1], x[0]))[0]  # highest power wins; tie → higher interval
        else:
            # Pure combat power: highest wins; tie → higher interval.
            # Exception: when ALL powers are 0 (no bucket meets the ≥5 threshold),
            # prefer the bucket with the most count — more occurrences = stronger signal.
            # Equal count → prefer lower interval (more conservative, avoids inflated T).
            max_power = max(powers[b] for b in upper_buckets)
            candidates = [b for b in upper_buckets if powers[b] == max_power]
            if max_power == 0:
                locked = max(candidates, key=lambda b: (counts.get(b, 0), -b))
            else:
                locked = max(candidates)  # tie → highest interval wins (implicit, matches defenders branch)

    sorted_vals = buckets.get(locked, [])
    if not sorted_vals:
        return _INTERVAL_T_FALLBACK

    # Step 3: average (not median)
    avg = sum(sorted_vals) / len(sorted_vals)
    result = round(avg, 2)
    logger.debug(f"[VLM_DEBUG] locked={locked} sorted_vals={sorted_vals} avg={avg:.4f} result={result}")
    return result


def _merge_geometry_creo_vlm_fields(
    geometry_fields: dict,
    creo_txt_buckets: dict,
    vlm_semantic_fields: dict,
    ocr_fields: dict | None = None,
) -> str:
    """按字段优先级合并三层特征来源，输出11字段结构化文本。

    优先级规则:
      1. Geometry layer（最高）: 关键尺寸/外圆与内孔/螺纹与螺孔/过渡特征/其他特征
      2. Creo txt supplement: 技术要求/倒角/过渡特征标注值/螺纹规格/公差
      3. VLM semantic: 零件名称/形态/类型/热处理与探伤/其他特征语义

    图号由调用方追加，不在此函数输出。
    """
    def _safe(val, fallback="无"):
        return val if val and val.strip() and val != "无" else fallback

    def _no_val(val):
        return not val or val.strip() in ("", "无")

    # ── Prepare Creo txt data ──
    creo_tech_list = creo_txt_buckets.get("技术要求", [])
    creo_tech = "；".join(creo_tech_list) if isinstance(creo_tech_list, list) and creo_tech_list else "无"
    creo_major = creo_txt_buckets.get("主要外形尺寸", [])
    creo_feature = creo_txt_buckets.get("特征尺寸", [])
    creo_small = creo_txt_buckets.get("倒角圆角", [])

    chamfers_list = [v for v in creo_small if isinstance(v, str) and not v.startswith("R")]
    fillets_list = [v for v in creo_small if isinstance(v, str) and v.startswith("R")]
    creo_chamfer = "；".join(chamfers_list) if chamfers_list else "无"
    creo_fillet = "；".join(fillets_list) if fillets_list else "无"

    # Key dimensions from Creo (supplement to geometry)
    creo_dims_parts = []
    if isinstance(creo_major, list):
        creo_dims_parts.extend(creo_major)
    if isinstance(creo_feature, list):
        creo_dims_parts.extend(creo_feature)
    creo_dims_str = "；".join(creo_dims_parts) if creo_dims_parts else ""

    # ── VLM semantic fields ──
    vlm_name = vlm_semantic_fields.get("零件名称", "无")
    vlm_form = vlm_semantic_fields.get("形态", "无")
    vlm_type = vlm_semantic_fields.get("类型", "无")
    vlm_heat = vlm_semantic_fields.get("热处理与探伤", "无")
    vlm_other = vlm_semantic_fields.get("其他特征", "无")
    drawing_fields = {field: vlm_semantic_fields.get(field, "无") for field in _DRAWING_FIELDS}
    drawing_fields = _validate_drawing_fields(drawing_fields)

    # Creo txt fallback: fill 刻字/表面处理 when VLM returned "无"
    if _no_val(drawing_fields.get("刻字", "无")):
        kezi = _extract_kezi_from_tech_req(creo_tech_list)
        if kezi:
            drawing_fields["刻字"] = kezi
    if _no_val(drawing_fields.get("表面处理", "无")):
        surface = _extract_surface_treatment_from_tech_req(creo_tech_list)
        if surface:
            drawing_fields["表面处理"] = surface

    # ── Layer D: OCR 孔字段补全（追加去重）──
    if ocr_fields:
        from backend.pipeline.ocr_feature import merge_ocr_into_field
        _ocr_merged = []
        for _ocr_field in ("通孔", "沉孔沉槽", "螺纹孔", "特殊孔"):
            _ocr_items = ocr_fields.get(_ocr_field, [])
            if _ocr_items:
                _before = drawing_fields.get(_ocr_field) or "无"
                drawing_fields[_ocr_field] = merge_ocr_into_field(_before, _ocr_items)
                if drawing_fields[_ocr_field] != _before:
                    _ocr_merged.append(f"{_ocr_field}(+{len(_ocr_items)})")
        if _ocr_merged:
            logger.info("[vlm_feature] OCR merged into fields: %s", ", ".join(_ocr_merged))
        else:
            logger.info("[vlm_feature] OCR fields: no new items added (all duplicates or empty)")

    # ── Merge each 12-field ──

    # 【零件名称】→ VLM only
    name_val = _safe(vlm_name)

    # 【形态】→ VLM only
    form_val = _safe(vlm_form)

    # 【类型】→ VLM only
    type_val = _safe(vlm_type)

    # 【技术要求】→ Creo txt only
    tech_val = _safe(creo_tech)

    # 【关键尺寸】→ Creo txt primary + Geometry supplement (Creo is authoritative for dims)
    key_parts = []
    if creo_dims_str:
        key_parts.append(creo_dims_str)
    geo_key = geometry_fields.get("关键尺寸", "")
    if not _no_val(geo_key):
        occ_lwh = geo_key  # save original OCC before anchoring
        geo_key = _anchor_occ_lwh_to_creo(geo_key, creo_dims_parts, creo_feature)
        # NOTE: VLM 外形尺寸 已暂停影响关键尺寸 LWH
        # geo_key = _apply_drawing_size_reference_to_lwh(geo_key, drawing_fields.get("外形尺寸", ""), occ_lwh)
        key_parts.append(geo_key)
    key_val = "；".join(key_parts) if key_parts else "无"

    # 【综合尺寸】→ geometry LWH + VLM drawing size + inferred T×L×H
    geo_lwh_nums = ""
    if not _no_val(geo_key):
        _m = _LWH_RE.search(geo_key)
        if _m:
            geo_lwh_nums = f"长{_m.group(1)}×宽{_m.group(2)}×高{_m.group(3)}"
    drawing_lwh = drawing_fields.get("外形尺寸", "无")
    if geo_lwh_nums or (drawing_lwh and drawing_lwh != "无"):
        geo_part = f"几何:{geo_lwh_nums}" if geo_lwh_nums else "几何:无"
        drawing_part = f"图纸:{drawing_lwh}" if drawing_lwh and drawing_lwh != "无" else "图纸:无"
        combined_dim = f"{geo_part}；{drawing_part}"
        # Build dim_pool from all VLM drawing fields for H snapping
        _dim_pool = " ".join(v for v in drawing_fields.values() if isinstance(v, str) and v not in ("", "无", "无。"))
        # Append inferred best-estimate when OCC data is available
        _inferred = _infer_dimensions_from_occ_vlm(
            geo_key, drawing_lwh if drawing_lwh != "无" else "", _dim_pool
        )
        if _inferred:
            combined_dim += (
                f"；推断:T{_fmt_inferred(_inferred['T'])}"
                f"×L{_fmt_inferred(_inferred['L'])}"
                f"×H{_fmt_inferred(_inferred['H'])}"
            )
    else:
        combined_dim = "无"

    # 【外圆与内孔】→ Geometry only (VLM补主尺寸被禁止)
    outer_val = _safe(geometry_fields.get("外圆与内孔", ""), "无")

    # 【螺纹与螺孔】→ Geometry (hole stat) + Creo txt (thread specs)
    thread_parts = []
    geo_thread = geometry_fields.get("螺纹与螺孔", "")
    if not _no_val(geo_thread):
        thread_parts.append(geo_thread)
    # Creo txt thread supplement: extract M-patterns from 技术要求
    creo_thread_specs = _extract_creo_thread_specs(creo_txt_buckets)
    if creo_thread_specs:
        thread_parts.append(creo_thread_specs)
    thread_val = "；".join(thread_parts) if thread_parts else "无"

    # 【倒角】→ Creo txt only (non-R from small bucket)
    chamfer_val = _safe(creo_chamfer)

    # 【热处理与探伤】→ VLM semantic
    heat_val = _safe(vlm_heat)

    # 【过渡特征】→ Creo txt only (R-prefix from small bucket)
    fillet_val = _safe(creo_fillet)

    # 【其他特征】→ Geometry structural + VLM semantic description
    other_parts = []
    geo_other = geometry_fields.get("其他特征", "")
    if not _no_val(geo_other):
        other_parts.append(geo_other)
    if not _no_val(vlm_other):
        other_parts.append(vlm_other)
    other_val = "；".join(other_parts) if other_parts else "无"

    # 【Creo原始尺寸】→ raw zhushi.txt dim values for blank spec calculation
    # Combines 主要外形尺寸 (>50mm) and significant 特征尺寸 (>10mm) sorted desc
    creo_raw_nums = []
    for v in (creo_major if isinstance(creo_major, list) else []):
        try:
            creo_raw_nums.append(float(str(v)))
        except (ValueError, TypeError):
            pass
    for v in (creo_feature if isinstance(creo_feature, list) else []):
        try:
            fv = float(str(v))
            if fv > 10:
                creo_raw_nums.append(fv)
        except (ValueError, TypeError):
            pass
    creo_raw_nums = sorted(set(creo_raw_nums), reverse=True)[:12]
    creo_raw_val = "；".join(_fmt_mm_value(v) for v in creo_raw_nums) if creo_raw_nums else ""

    lines = [
        f"【零件名称】{name_val}",
        f"【形态】{form_val}",
        f"【类型】{type_val}",
        f"【技术要求】{tech_val}",
        f"【关键尺寸】{key_val}",
        f"【综合尺寸】{combined_dim}",
        f"【外形尺寸】{_safe(drawing_fields.get('外形尺寸', '无'))}",
        f"【通孔】{_safe(drawing_fields.get('通孔', '无'))}",
        f"【沉孔沉槽】{_safe(drawing_fields.get('沉孔沉槽', '无'))}",
        f"【螺纹孔】{_safe(drawing_fields.get('螺纹孔', '无'))}",
        f"【特殊孔】{_safe(drawing_fields.get('特殊孔', '无'))}",
        f"【尺寸公差】{_safe(drawing_fields.get('尺寸公差', '无'))}",
        f"【形位公差】{_safe(drawing_fields.get('形位公差', '无'))}",
        f"【表面粗糙度】{_safe(drawing_fields.get('表面粗糙度', '无'))}",
        f"【表面处理】{_safe(drawing_fields.get('表面处理', '无'))}",
        f"【外圆与内孔】{outer_val}",
        f"【螺纹与螺孔】{thread_val}",
        f"【倒角】{chamfer_val}",
        f"【热处理与探伤】{heat_val}",
        f"【过渡特征】{fillet_val}",
        f"【刻字】{_safe(drawing_fields.get('刻字', '无'))}",
        f"【其他特征】{other_val}",
    ]
    if drawing_fields.get("_has_warnings"):
        lines.append(f"【图纸提取警告】{'；'.join(drawing_fields['_warnings'])}")
    if creo_raw_val:
        lines.append(f"【Creo原始尺寸】{creo_raw_val}")
    return "\n".join(lines)


_SINGLE_SOURCE_PROMPT = """你将看到同一个机械零件的三视图图片（正视图、右视图、俯视图）。

请综合所有图片提取零件的机械加工特征，重点识别：
平面、台阶、槽、型腔、孔、沉孔、埋头孔、螺纹孔、凸台、肋板、倒角、圆角、旋转体、自由曲面等。

输出格式：每条特征一行，格式为"特征类型：描述（含数量或典型尺寸，若可从图中判断）"。
示例：
旋转体：主体为轴类零件，带多级外圆台阶
螺纹孔：端面分布 4 个螺纹孔
内孔：中心通孔
倒角：各棱边均有倒角"""


def _collect_creo_images(creo_dir: Path) -> list[Path]:
    if not creo_dir.exists():
        return []
    return sorted(
        p for p in creo_dir.iterdir()
        if p.is_file() and p.suffix.lower() in _CREO_IMAGE_EXTENSIONS
    )


_CREO_EXCLUDE_KEYWORDS = ("默认", "default", "技术要求")
_CREO_PRIORITY_PATTERNS = (
    (0, re.compile(r"主视图")),
    (1, re.compile(r"左视图")),
    (2, re.compile(r"俯视图")),
    (3, re.compile(r"A-A|A图|A\s*向|(?:^|[-_\s])A(?:[-_\s]|$)", re.IGNORECASE)),
    (4, re.compile(r"B-B|B图|B\s*向|(?:^|[-_\s])B(?:[-_\s]|$)", re.IGNORECASE)),
    (5, re.compile(r"C-C|C图|C\s*向|(?:^|[-_\s])C(?:[-_\s]|$)", re.IGNORECASE)),
    (6, re.compile(r"右视图")),
    (7, re.compile(r"后视图")),
    (8, re.compile(r"仰视图")),
)


def _creo_image_rank(path: Path) -> tuple[int, str]:
    stem = path.stem
    for rank, pattern in _CREO_PRIORITY_PATTERNS:
        if pattern.search(stem):
            return rank, path.name
    return len(_CREO_PRIORITY_PATTERNS), path.name


def _select_creo_images(creo_dir: Path, max_n: int = 6) -> list[Path]:
    all_images = [
        p for p in _collect_creo_images(creo_dir)
        if not any(kw in p.stem.lower() for kw in _CREO_EXCLUDE_KEYWORDS)
    ]
    return sorted(all_images, key=_creo_image_rank)[:max_n]


def _format_dim_counts(vals: list) -> list:
    counts = Counter(vals)
    result = []
    for v, c in sorted(counts.items()):
        s = str(int(v)) if v == int(v) else str(v)
        result.append(f"{s} × {c}" if c > 1 else s)
    return result


def parse_creo_task_txt(txt_path: str) -> dict:
    """Parse CREO_TASK.txt into 4 categorized dimension buckets.

    Buckets: 主要外形尺寸 (>50), 特征尺寸 (2–50), 倒角圆角 (≤2 or R-prefix), 技术要求.
    Same-value dimensions are deduplicated with count: '0.9 × 15'.
    Safe with missing or malformed files — returns empty lists.
    """
    empty: dict = {"主要外形尺寸": [], "特征尺寸": [], "倒角圆角": [], "技术要求": []}
    path = Path(txt_path)
    if not path.exists():
        return empty
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return empty

    main_vals: list = []
    feature_vals: list = []
    small_vals: list = []
    notes: list = []

    for block in re.split(r"-{20,}", text):
        block = block.strip()
        if not block:
            continue

        if "[DIMENSION]" in block:
            val_m = re.search(r"displayed_value:\s*([\d.]+)", block)
            if not val_m:
                continue
            try:
                value = float(val_m.group(1))
            except ValueError:
                continue
            dim_text_m = re.search(r"dimension_text:(.*)", block, re.DOTALL)
            dim_text = dim_text_m.group(1) if dim_text_m else ""
            v = round(value, 2)
            if "{0:R}" in dim_text or v <= 2.0:
                small_vals.append(v)
            elif v > 50:
                main_vals.append(v)
            else:
                feature_vals.append(v)

        elif "[3D NOTE]" in block:
            note_m = re.search(r"note_text:(.*)", block, re.DOTALL)
            if not note_m:
                continue
            lines = re.findall(r"line \d+:\s*(.*)", note_m.group(1))
            note = "\n".join(ln.strip() for ln in lines if ln.strip())
            # Strip leading label-only line like "技术要求：" with no content after colon
            note = re.sub(r'^[一-鿿\w]+[：:]\s*\n', '', note).strip()
            # Skip pure placeholder notes
            if note and note.upper() not in ("NOT SPECIFIED", "N/A", "NONE", "无"):
                notes.append(note)

    return {
        "主要外形尺寸": [
            str(int(v)) if v == int(v) else str(v)
            for v in sorted(set(main_vals), reverse=True)
        ],
        "特征尺寸": _format_dim_counts(feature_vals),
        "倒角圆角": _format_dim_counts(small_vals),
        "技术要求": notes,
    }


_VLM_CACHE_TTL = 7 * 24 * 3600  # 7 天


def _vlm_cache_dir() -> Path:
    try:
        from ..config import OUTPUT_FOLDER
        base = Path(OUTPUT_FOLDER)
    except Exception:
        base = Path(__file__).resolve().parent.parent.parent / "output"
    d = base / "vlm_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _vlm_cache_key(image_paths: list, prompt: str, model_id: str) -> str:
    h = hashlib.sha256()
    for p in image_paths:
        try:
            st = Path(p).stat()
            h.update(f"{Path(p).resolve()}|{st.st_mtime}|{st.st_size}\n".encode())
        except Exception:
            h.update(str(p).encode())
    h.update(model_id.encode())
    h.update(b"\x00")
    h.update(prompt.encode("utf-8"))
    return h.hexdigest()[:32]


def _vlm_cache_get(key: str) -> Optional[str]:
    try:
        f = _vlm_cache_dir() / f"{key}.json"
        if not f.exists():
            return None
        data = json.loads(f.read_text(encoding="utf-8"))
        if time.time() - data.get("ts", 0) > _VLM_CACHE_TTL:
            f.unlink(missing_ok=True)
            return None
        return data.get("text")
    except Exception:
        return None


def _vlm_cache_set(key: str, text: str) -> None:
    try:
        f = _vlm_cache_dir() / f"{key}.json"
        f.write_text(
            json.dumps({"text": text, "ts": time.time()}, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass


def _build_image_content(path: Path) -> dict:
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return {
        "type": "image_url",
        "image_url": {"url": f"data:image/png;base64,{b64}"},
    }


def _call_vlm_with_images(image_paths: list[Path], prompt: str) -> str:
    api_key = os.getenv("VISION_API_KEY", "")
    api_base = os.getenv("VISION_API_BASE", "").rstrip("/")
    model_id = os.getenv("VISION_MODEL_ID", "").replace("model_id=", "").strip()

    if not api_key or not api_base or not model_id:
        logger.warning("[vlm_feature] VISION_API_KEY/VISION_API_BASE/VISION_MODEL_ID not configured, VLM skipped")
        return ""

    missing = [str(p) for p in image_paths if not p.exists()]
    if missing:
        logger.warning("[vlm_feature] missing view images: %s, VLM skipped", missing)
        return ""

    cache_key = _vlm_cache_key(image_paths, prompt, model_id)
    cached = _vlm_cache_get(cache_key)
    if cached is not None:
        logger.info("[vlm_feature] cache hit %s…", cache_key[:8])
        return cached

    try:
        content = [_build_image_content(path) for path in image_paths]
        content.append({"type": "text", "text": prompt})

        client = OpenAI(api_key=api_key, base_url=api_base)
        response = client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": "你是机械零件识别助手。只描述图片或文字中明确给出的信息，不推测未标注数值。"},
                {"role": "user", "content": content},
            ],
            max_tokens=1024,
            timeout=120,
        )
        if not response.choices:
            logger.warning("[vlm_feature] VLM returned empty choices")
            return ""
        result = (response.choices[0].message.content or "").strip()
        logger.info("[vlm_feature] VLM raw output (%d chars): %s...", len(result), result[:200])
        if result:
            _vlm_cache_set(cache_key, result)
        return result
    except Exception as exc:
        logger.warning("[vlm_feature] VLM call failed: %s", exc)
        return ""


def extract_creo_primary_features(
    creo_dir: str,
    txt_path: str,
    step_path: str = "",
) -> str:
    """Three-layer feature extraction: geometry + Creo txt + VLM semantic.

    Layer A (Geometry): extracts dimension/bore/hole fields from STEP analysis.
    Layer B (Creo txt): supplements tolerance/thread/chamfer/fillet/tech-req.
    Layer C (VLM semantic): fills name/form/type/heat-treatment/other description.

    txt_path may be missing — Creo txt layer returns empty buckets.
    step_path may be missing — geometry layer returns empty fields.

    Returns '' if the Creo screenshots directory is empty.
    Output is assembled into structured 11-field format via _merge_geometry_creo_vlm_fields.
    """
    creo_paths = _select_creo_images(Path(creo_dir), max_n=6)
    if not creo_paths:
        return ""

    # Layer A: Geometry from STEP
    geometry_fields = _extract_geometry_structured_fields(step_path)

    # Layer B: Creo txt
    creo_buckets = parse_creo_task_txt(txt_path)

    # Layer C: VLM semantic.
    # OCC bore/thread data injected as reference; Creo images are primary for dimensions.
    _has_val = lambda v: bool(v and v.strip() and v not in ("无",))
    sections = []

    # Only inject bore/thread facts from OCC (accurate for holes); dimensions come from Creo
    geo_facts = [
        (k, geometry_fields.get(k, ""))
        for k in ("外圆与内孔", "螺纹与螺孔")
        if _has_val(geometry_fields.get(k, ""))
    ]
    if geo_facts:
        sections.append("以下孔径及螺纹数据已由程序从三维模型精确计算，供参考：")
        for field, val in geo_facts:
            sections.append(f"【{field}】{val}")
        sections.append("---")

    if creo_buckets["技术要求"] or creo_buckets["主要外形尺寸"] or creo_buckets["特征尺寸"]:
        if creo_buckets["技术要求"]:
            sections.append("以下是从模型注释中提取的技术要求，仅供参考理解零件用途：")
            sections.extend(creo_buckets["技术要求"])
        if creo_buckets["主要外形尺寸"]:
            sections.append("主要外形尺寸：" + " / ".join(creo_buckets["主要外形尺寸"]))
        if creo_buckets["特征尺寸"]:
            sections.append("特征尺寸：" + " / ".join(creo_buckets["特征尺寸"]))
        sections.append("---")

    sections.append(_VLM_ENGINEERING_DRAWING_PROMPT)
    creo_context_prompt = "\n".join(sections)

    vlm_semantic = _extract_vlm_semantic_fields(creo_paths, creo_context_prompt)

    # Normalize and validate VLM output
    vlm_semantic = _normalize_vlm_output(vlm_semantic)
    vlm_semantic = _validate_and_mark_dimensions(vlm_semantic, _make_cache_key(creo_paths))

    # Merge all layers (geometry + Creo txt + VLM + OCR)
    from backend.pipeline.ocr_feature import extract_hole_fields_from_ocr
    _ocr_fields = extract_hole_fields_from_ocr(creo_dir)
    result = _merge_geometry_creo_vlm_fields(
        geometry_fields, creo_buckets, vlm_semantic, ocr_fields=_ocr_fields
    )

    # If all layers are empty, return "" (caller will fall back to next route)
    if all(v in ("", "无") for v in _parse_structured_fields(result).values()):
        return ""

    return result


def extract_vlm_features(views_dir: str) -> str:
    """
    Semantic-only VLM extraction from FreeCAD three-views.
    VLM only fills: 零件名称, 形态, 类型, 热处理与探伤, 其他特征.
    No geometry layer available (no STEP file in this route).
    Returns '' if views are missing or VLM API fails.
    """
    views_path = Path(views_dir)
    image_paths = [views_path / f"{face}.png" for face in _FACES]
    missing = [str(p) for p in image_paths if not p.exists()]
    if missing:
        return ""

    vlm_semantic = _extract_vlm_semantic_fields(image_paths, _VLM_SEMANTIC_FIELDS_PROMPT)

    # Normalize and validate VLM output
    vlm_semantic = _normalize_vlm_output(vlm_semantic)
    vlm_semantic = _validate_and_mark_dimensions(vlm_semantic, _make_cache_key(image_paths))

    # No geometry layer, no Creo txt layer — merge with empty buckets
    result = _merge_geometry_creo_vlm_fields({}, {}, vlm_semantic)

    if all(v in ("", "无") for v in _parse_structured_fields(result).values()):
        return ""

    return result


def extract_dual_source_vlm_features(
    freecad_views_dir: str,
    creo_views_dir: str,
    zhushi_text: str = "",
    prompt: Optional[str] = None,
) -> str:
    freecad_dir = Path(freecad_views_dir)
    creo_dir = Path(creo_views_dir)

    freecad_paths = [freecad_dir / f"{face}.png" for face in _FACES]
    creo_paths = _collect_creo_images(creo_dir)
    if not creo_paths:
        print(f"[vlm_feature] no Creo images found in {creo_views_dir}, skipping dual-source")
        return ""

    zhushi_section = ""
    if zhushi_text and zhushi_text.strip():
        zhushi_section = (
            "以下是从模型注释中直接提取的文字说明，请优先以此为准，不要与图片矛盾：\n"
            f"{zhushi_text.strip()}\n\n"
            "---\n\n"
        )

    joint_prompt = prompt or (
        zhushi_section
        + "以下图片来自同一个机械零件：\n"
        "前 3 张是 FreeCAD 标准三视图（front/right/top）。\n"
        "后面的若干张是 Creo 截图（包含尺寸标注、公差符号、技术要求等）。\n"
        "请综合所有图片和注释文字提取零件结构特征。\n"
        "优先使用 FreeCAD 判断投影结构，用 Creo 图和注释文字确认真实尺寸和公差。\n"
        "只描述图片中明确可见或注释文字中明确标注的特征，不要推测或估算任何未标注的数值。"
    )
    return _call_vlm_with_images(freecad_paths + creo_paths, joint_prompt)


def extract_creo_only_vlm_features(
    creo_views_dir: str,
    zhushi_text: str = "",
    prompt: Optional[str] = None,
) -> str:
    creo_dir = Path(creo_views_dir)
    creo_paths = _collect_creo_images(creo_dir)
    if not creo_paths:
        print(f"[vlm_feature] no Creo images found in {creo_views_dir}, skipping Creo-only")
        return ""

    zhushi_section = ""
    if zhushi_text and zhushi_text.strip():
        zhushi_section = (
            "以下是从模型注释中直接提取的文字说明，请优先以此为准，不要与图片矛盾：\n"
            f"{zhushi_text.strip()}\n\n"
            "---\n\n"
        )

    creo_prompt = prompt or (
        zhushi_section
        + "以下图片是同一个机械零件的 Creo 截图（包含尺寸标注、公差符号、技术要求等）。\n"
        "请根据图片和注释文字提取零件结构特征。\n"
        "只描述图片中明确可见或注释文字中明确标注的特征，不要推测或估算任何未标注的数值。"
    )
    return _call_vlm_with_images(creo_paths, creo_prompt)


def extract_freecad_geo_constrained_features(views_dir: str, step_path: str) -> str:
    """Two-layer extraction: geometry + VLM semantic.

    Layer A (Geometry): extracts dimension/bore/hole fields from STEP analysis.
    Layer C (VLM semantic): fills name/form/type/heat-treatment/other from FreeCAD views.

    No Creo txt layer in this route.
    Geometry data feeds structured fields directly (not just prompt injection).
    Returns '' if the views directory has no images.
    """
    views_path = Path(views_dir)
    image_paths = [views_path / f"{face}.png" for face in _FACES]
    missing = [str(p) for p in image_paths if not p.exists()]
    if missing:
        return ""

    # Layer A: Geometry from STEP
    geometry_fields = _extract_geometry_structured_fields(step_path)

    # Layer C: VLM semantic (geometry facts injected as authoritative pre-context).
    _has_val = lambda v: bool(v and v.strip() and v not in ("无",))
    geo_facts = [
        (k, geometry_fields.get(k, ""))
        for k in ("关键尺寸", "外圆与内孔", "螺纹与螺孔")
        if _has_val(geometry_fields.get(k, ""))
    ]
    geo_context_prompt = None
    if geo_facts:
        lines = ["以下字段已由程序从三维模型精确计算，禁止推测或修改："]
        for field, val in geo_facts:
            lines.append(f"【{field}】{val}")
        lines.append("---")
        lines.append(_VLM_SEMANTIC_FIELDS_PROMPT)
        geo_context_prompt = "\n".join(lines)

    vlm_semantic = _extract_vlm_semantic_fields(image_paths, geo_context_prompt)

    # Normalize and validate VLM output
    vlm_semantic = _normalize_vlm_output(vlm_semantic)
    vlm_semantic = _validate_and_mark_dimensions(vlm_semantic, _make_cache_key(image_paths))

    # Merge (no Creo txt layer)
    result = _merge_geometry_creo_vlm_fields(geometry_fields, {}, vlm_semantic)

    if all(v in ("", "无") for v in _parse_structured_fields(result).values()):
        return ""

    return result


def build_vlm_feature_text(
    freecad_views_dir: str,
    creo_views_dir: str = "",
    creo_txt_path: str = "",
    step_path: str = "",
) -> tuple[str, str]:
    """Route VLM feature extraction: Creo-primary → freecad-geo → FreeCAD → none.

    All three routes now use three-layer (geometry + creo-txt + VLM-semantic)
    or two-layer (geometry + VLM-semantic) assembly. VLM no longer determines
    dimension/bore/thread fields — those come from STEP geometry analysis.

    creo_txt_path: path to CREO_TASK.txt copy at creo_views/zhushi.txt.
    step_path: path to STEP file for geometry extraction.
    Returns (feature_text, mode). Modes: 'creo-primary', 'freecad-geo', 'freecad', 'none'.
    """
    if creo_views_dir:
        creo_text = extract_creo_primary_features(creo_views_dir, creo_txt_path, step_path)
        if creo_text:
            return creo_text, "creo-primary"

    if step_path:
        geo_text = extract_freecad_geo_constrained_features(freecad_views_dir, step_path)
        if geo_text:
            return geo_text, "freecad-geo"

    freecad_text = extract_vlm_features(freecad_views_dir)
    if freecad_text:
        return freecad_text, "freecad"

    return "", "none"


def build_single_source_prompt() -> str:
    return _VLM_SEMANTIC_FIELDS_PROMPT
