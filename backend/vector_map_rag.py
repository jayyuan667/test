# -*- coding: utf-8 -*-
"""
RAG检索模块 - 多维度混合匹配
1. 产品类型精确匹配（优先）
2. 工艺关键词匹配
3. 向量相似匹配（对于外来图纸）
4. 兜底
"""

import os
import json
import sqlite3
import re
import numpy as np
from typing import Dict, List, Optional
from openai import OpenAI

# Use repository-relative paths so the project can move safely.
BASE_DIR = os.getenv("FEATURIZER_BASE_DIR") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "db_data", "2d-v.db")


def _resolve_library_scope(library_key: str):
    if not library_key:
        return None
    try:
        from .library_scope import resolve_scope
    except ImportError:
        try:
            from backend.library_scope import resolve_scope
        except ImportError:
            from library_scope import resolve_scope
    return resolve_scope(library_key)


# ============ 结构化特征表（已合并进 vector 表，保留存根避免导入报错）============
def create_structured_features_table():
    pass


def extract_and_store_structured_features(force_update: bool = False):
    # Structured fields are now written directly into the vector table at import time.
    pass


# ============ 结构化过滤检索 ============
def query_by_structured_filter(
    structured_filter: Dict,
    top_k: int = 10,
    vector_table: str = "vectors_v2",
) -> List[Dict]:
    """基于结构化字段过滤检索（直接查 vector 表，已按 library 隔离）。"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    results = []
    try:
        conditions: List[str] = []
        params: List = []

        if structured_filter.get("blank_type"):
            conditions.append("blank_type = ?")
            params.append(structured_filter["blank_type"])

        if structured_filter.get("overall_length"):
            min_len, max_len = structured_filter["overall_length"]
            conditions.append(
                "overall_length_min IS NOT NULL AND overall_length_max IS NOT NULL "
                "AND overall_length_min <= ? AND overall_length_max >= ?"
            )
            params.extend([max_len, min_len])

        if structured_filter.get("main_diameter"):
            min_dia, max_dia = structured_filter["main_diameter"]
            conditions.append(
                "main_diameter_min IS NOT NULL AND main_diameter_max IS NOT NULL "
                "AND main_diameter_min <= ? AND main_diameter_max >= ?"
            )
            params.extend([max_dia, min_dia])

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        cursor.execute(
            f"""
            SELECT prefix, blank_type, tolerance_levels, thread_specs,
                   hole_specs, roughness, content
            FROM {vector_table}
            WHERE COALESCE(real, 1) = 1 AND {where_clause}
            """,
            params,
        )

        for row in cursor.fetchall():
            drawing_id, blank_type, tol_json, thread_json, hole_json, rough_json, content_raw = row

            filter_score = 0.0
            matched_details = []

            if structured_filter.get("blank_type") and blank_type == structured_filter["blank_type"]:
                filter_score += 30
                matched_details.append("毛坯类型")

            if structured_filter.get("tolerance_levels") and tol_json:
                overlap = set(json.loads(tol_json)) & set(structured_filter["tolerance_levels"])
                if overlap:
                    filter_score += len(overlap) * 20
                    matched_details.append(f"公差:{overlap}")

            if structured_filter.get("thread_specs") and thread_json:
                overlap = set(json.loads(thread_json)) & set(structured_filter["thread_specs"])
                if overlap:
                    filter_score += len(overlap) * 15
                    matched_details.append(f"螺纹:{overlap}")

            if structured_filter.get("hole_specs") and hole_json:
                overlap = set(json.loads(hole_json)) & set(structured_filter["hole_specs"])
                if overlap:
                    filter_score += len(overlap) * 10
                    matched_details.append(f"孔径:{overlap}")

            if structured_filter.get("roughness") and rough_json:
                overlap = set(json.loads(rough_json)) & set(structured_filter["roughness"])
                if overlap:
                    filter_score += len(overlap) * 5
                    matched_details.append(f"粗糙度:{overlap}")

            if filter_score > 0:
                results.append({
                    "drawing_id": drawing_id,
                    "filter_score": filter_score,
                    "matched": matched_details,
                    "process_list": parse_rows_field(content_raw),
                })

        results.sort(key=lambda x: x["filter_score"], reverse=True)
        results = results[:top_k]

    except Exception as e:
        print(f"[RAG] Structured filter error: {e}")
    finally:
        conn.close()

    return results


# ============ 关键词库 ============
# 产品类型关键词
PRODUCT_KEYWORDS = [
    "转子支架",
    "端盖",
    "法兰",
    "箱体",
    "轴套",
    "齿轮",
    "叶片",
    "主轴",
    "阀体",
    "泵体",
    "缸体",
    "连杆",
    "曲轴",
    "凸轮",
    "蜗轮",
    "蜗杆",
    "叶轮",
    "导瓦",
    # 新增：更具体的工艺相关关键词
    "回转体",
    "轴类",
    "盘类",
    "支架",
    "壳体",
    "座体",
]

# 工艺关键词（按类型分组）
PROCESS_KEYWORDS = [
    "车",
    "铣",
    "钻",
    "镗",
    "磨",
    "刨",
    "插",
    "滚齿",
    "剃齿",
    "线切割",
    "电火花",
    "热处理",
    "淬火",
    "回火",
    "渗碳",
    "氮化",
    "时效",
    "装配",
    "热套",
    "找摆",
    "同镗",
    "配焊",
    "铰孔",
    "冲压",
    "焊接",
    "钣金",
    "抛光",
    "探伤",
    "UT",
    "MT",
    "PT",
    "VT",
    "镀",
    "涂",
    "喷",
]

# 工艺关键词
PROCESS_KEYWORDS = [
    "车",
    "铣",
    "钻",
    "镗",
    "磨",
    "刨",
    "插",
    "滚齿",
    "剃齿",
    "热处理",
    "淬火",
    "回火",
    "渗碳",
    "氮化",
    "装配",
    "热套",
    "找摆",
    "同镗",
    "配焊",
    "铰孔",
    "冲压",
    "焊接",
    "钣��",
]

# 材料关键词
MATERIAL_KEYWORDS = [
    "锻件",
    "铸件",
    "棒料",
    "板材",
    "无缝钢管",
    "合金钢",
    "不锈钢",
    "铝合金",
    "铜合金",
    "钛合金",
]


# ============ 向量创建函数 ============
def create_query_vector(text: str) -> Optional[np.ndarray]:
    """从文本创建向量 - 使用豆包多模态Embedding API"""
    try:
        import requests as req

        api_key = os.getenv("EMBEDDING_API_KEY", "")
        base_url = os.getenv(
            "EMBEDDING_BASE_URL",
            "https://ark.cn-beijing.volces.com/api/v3/embeddings/multimodal",
        )
        model = os.getenv("EMBEDDING_MODEL", "doubao-embedding-vision-251215")

        if not api_key:
            print("[RAG] EMBEDDING_API_KEY not set")
            return None

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        data = {
            "model": model,
            "instructions": "Target_modality: text.\nInstruction:Compress the text into a semantic vector for retrieval.\nQuery:",
            "input": [{"type": "text", "text": text[:2000]}],
            "dimensions": 1024,
            "encoding_format": "float",
        }

        resp = req.post(base_url, headers=headers, json=data).json()
        return np.array(resp["data"]["embedding"], dtype=np.float32)
    except Exception as e:
        print(f"[RAG] create_query_vector error: {e}")
        return None



def parse_rows_field(raw_value):
    """Parse stored rows that may be JSON or plain text."""
    if raw_value is None:
        return []
    if isinstance(raw_value, list):
        return raw_value
    if isinstance(raw_value, str):
        text = raw_value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return lines or [text]
    return [str(raw_value)]


def _split_process_row_for_prompt(row: str) -> tuple[str, str, str]:
    """Split a stored process row into code, body and trailing metadata.

    Handles two formats:
    - Old two-segment: `0010@工序内容@设备：W201@工时：无`
      → (0010, 工序内容, 设备：W201 工时：无)
    - New three-segment (process_spec_analyzer): `0010@工种@工序内容`
      → (0010, 工序内容, 工种：工种)

    Detection: if part[1] is a short Chinese-only token (≤6 chars, no digits/symbols)
    and part[2] is longer content (not a meta label like 工种：/设备：), treat as three-segment.
    """
    text = str(row or "").replace("ENDD$$", " ").strip()
    if not text:
        return "", "", ""

    parts = [part.strip() for part in text.split("@") if part.strip()]
    if not parts:
        return "", text, ""

    code = parts[0]

    # ── 检测三段式格式：NNNN@工种@工序内容 ──
    trade = ""
    body_start = 1
    if len(parts) >= 3:
        p1 = parts[1]
        p2 = parts[2]
        # Heuristic: trade is short (≤6 chars), Chinese/hyphen only, and p2 is
        # longer actual content (not a meta key-value like 工种：/设备：/工时：)
        if (len(p1) <= 6
                and re.match(r'^[一-鿿\-]+$', p1)
                and not re.match(r'^(?:工种|设备|工时|备注)[：:]', p2)
                and len(p2) > len(p1)):
            trade = p1
            body_start = 2

    body = parts[body_start] if len(parts) > body_start else ""
    meta_parts = []
    if trade:
        meta_parts.append(f"工种：{trade}")
    if len(parts) > body_start + 1:
        meta_parts.extend(parts[body_start + 1:])
    meta = " ".join(meta_parts) if meta_parts else ""

    if not body:
        return code, text, meta

    return code, body, meta


def _normalize_prefix_token(prefix: str) -> str:
    candidate = (prefix or "").strip()
    if not candidate:
        return ""
    stem = os.path.splitext(os.path.basename(candidate))[0].strip()
    return (stem or candidate).upper()


# ============ 零件类别分类 ============

# 零件类别不相容表：key=查询零件类别，value=应被降权的数据库零件类别集合
_CATEGORY_INCOMPATIBLE: Dict[str, set] = {
    "板类":   {"轴类", "回转体类", "环类", "套类"},
    "腔体类": {"轴类", "回转体类", "环类", "套类"},
    "轴类":   {"板类", "腔体类", "支架类", "环类"},
    "盘类":   {"板类", "腔体类", "支架类"},
    "套类":   {"板类", "腔体类", "支架类"},
    "支架类": {"轴类", "套类", "环类"},
    "环类":   {"板类", "腔体类", "支架类", "套类"},
}

# 降权系数（相似度乘以此系数）
_CATEGORY_MISMATCH_PENALTY = 0.55


def classify_part_category(features: Dict) -> str:
    """从零件特征字典推断零件类别。

    解析 【零件名称】【形态】【类型】 三个字段。
    返回值：轴类 / 盘类 / 板类 / 腔体类 / 套类 / 支架类 / 环类 / 回转体类 / 未知
    """
    name = features.get("零件名称", "")
    shape = features.get("形态", "")
    part_type = features.get("类型", "")
    all_text = name + shape + part_type

    if not all_text.strip():
        return "未知"

    # 腔体类（优先：腔体板也属于腔体类，不能当成普通板类）
    if re.search(r'腔体|内腔|型腔|空腔|深腔|箱体|缸体|壳体|泵体|阀体', all_text):
        return "腔体类"

    # 轴类
    if re.search(r'主轴|传动轴|阶梯轴|心轴|花键轴|光轴|转轴|曲轴|偏心轴|(?<![套承瓦])轴(?![承套瓦类])', all_text):
        return "轴类"

    # 套类
    if re.search(r'轴套|衬套|套筒|导套|密封套|内套|外套|[^螺]套(?![类筒管])', all_text):
        return "套类"

    # 盘类（法兰盘/齿轮/叶轮等回转盘件）
    if re.search(r'法兰盘|圆盘|齿轮|叶轮|飞轮|端盖|压盖|法兰|盘类|轮盘', all_text):
        return "盘类"

    # 环类
    if re.search(r'环形|圆环|法兰环|密封环|锁紧环|挡环|[^密封]环(?![境形])', all_text):
        return "环类"

    # 支架类
    if re.search(r'支架|基座|支撑架|转子支架|底座|托架|吊架', all_text):
        return "支架类"

    # 板类（板状零件，需排除腔体板已被腔体类捕获的情况）
    if re.search(r'平板|底板|安装板|盖板|支撑板|固定板|导向板|矩形体|方形体|板状|板件|[^刀模]板(?![料状件])', all_text):
        return "板类"

    # 回转体通用（以上未匹配到，但有回转体特征）
    if re.search(r'回转体|旋转体|圆柱体|圆柱形', all_text):
        return "回转体类"

    return "未知"


# ============ Reciprocal Rank Fusion ============
def reciprocal_rank_fusion(
    rankings: List[List[Dict]], k_vector: int = 30, k_other: int = 60
) -> List[Dict]:
    """
    Reciprocal Rank Fusion - combine multiple rankings into one.

    当前策略：向量相似度是主排序信号，RRF 只作为次排序与稳定器。
    prefix 精确命中仍可在后续阶段强制置顶。

    Args:
        rankings: List of ranked lists
        k_vector: 向量排名的k值（越小权重越大）
        k_other: 其他排名的k值
    """
    print(f"  [RRF] Received {len(rankings)} rankings")
    scores = {}

    for i, ranking in enumerate(rankings):
        # 向量排名使用更小的k值（更大权重）
        k = k_vector if i == 1 else k_other  # i=1 是vector ranking
        print(f"  [RRF] Processing ranking {i + 1} with {len(ranking)} items (k={k})")

        for rank, item in enumerate(ranking, 1):
            drawing_id = item["drawing_id"]
            rrf_score = 1.0 / (k + rank)

            if drawing_id not in scores:
                scores[drawing_id] = {
                    "drawing_id": drawing_id,
                    "rrf_score": 0.0,
                    "process_list": item.get("process_list", []),
                    "match_type": item.get("match_type", ""),
                    "matched": [],
                    "vector_similarity": item.get("similarity", 0.0),
                }
            elif item.get("similarity", 0.0) > scores[drawing_id].get("vector_similarity", 0.0):
                scores[drawing_id]["vector_similarity"] = item.get("similarity", 0.0)

            scores[drawing_id]["rrf_score"] += rrf_score
            # Track which signals matched
            if item.get("match_type"):
                scores[drawing_id]["matched"].append(item.get("match_type"))

            # Debug: show prefix drawing_id
            if "prefix" in item.get("match_type", "").lower():
                print(
                    f"    [RRF] Found prefix match: {drawing_id} at rank {rank}, RRF contribution: {rrf_score:.4f}"
                )

    # Sort by cosine similarity first, then RRF score as tie-breaker
    sorted_scores = sorted(
        scores.values(),
        key=lambda x: (
            x.get("vector_similarity", 0.0),
            x["rrf_score"],
        ),
        reverse=True,
    )

    # Keep original RRF score as rrf_score, and vector_similarity as actual similarity
    # Don't normalize to avoid confusion (1.0 looks like 100% match)
    for item in sorted_scores:
        # Keep the actual vector similarity for display
        if item.get("vector_similarity"):
            item["similarity"] = item["vector_similarity"]
        # Keep RRF score for ranking info
        item["rrf_score"] = item.get("rrf_score", 0)

    return sorted_scores


# ============ 提取函数 ============
def extract_all_features(description: str) -> Dict:
    """从图纸描述中提取所有特征

    支持新旧两种格式的Vision输出
    使用【】字段作为特征进行匹配
    """
    desc = description.replace(" ", "").lower()
    desc_upper = description.replace(" ", "")


# ============ 字段分层解析 ============
# 向量索引字段（语义相似匹配）
VECTOR_INDEX_FIELDS = [
    # Vision-analysis fields (drawing images)
    "零件名称",
    "形态",
    "类型",
    "表面处理与镀层特征",
    "端面与平面",
    # Geometry-analysis fields (STEP/PRT via FreeCAD)
    "尺寸",
    "几何特征",
    "圆柱面特征",
    "平面特征",
    "图号",
    # Enhanced geometry fields (new extraction)
    "形状分类",
    "体积",
    "孔特征",
]

# 结构化过滤字段（精确匹配/范围查询）
STRUCTURED_FILTER_FIELDS = [
    "毛坯类型",
    "关键尺寸",  # 需要数值解析
    "公差等级",  # H7, h6等
    "螺纹与螺孔",  # M16, M24等规格
    "外圆与内孔",  # 直径尺寸
]

# 工艺参考字段（直接传给LLM）
PROCESS_REFERENCE_FIELDS = [
    "技术要求",
    "热处理与探伤",
    "标识与检验",
    "线切割",
    "精度与检测特征",
    "倒角",
    "过渡特征",
    "其他特征",
]


def extract_structured_features(description: str) -> Dict:
    """分层提取图纸特征

    将Vision输出按用途分层：
    - vector_index: 向量检索用（语义相似）
    - structured_filter: 结构化过滤用（精确匹配）
    - process_reference: 工艺参考用（直接传给LLM）

    Args:
        description: Vision输出的原始描述

    Returns:
        {
            "vector_index": str,  # 拼接触发给向量检索的文本
            "structured_filter": {
                "blank_type": str,
                "overall_length": (min, max),  # 总长范围
                "main_diameter": (min, max),   # 主直径范围
                "tolerance_levels": [str],      # 公差等级列表
                "thread_specs": [str],          # 螺纹规格列表
                "hole_specs": [str],            # 孔径规格列表
                "roughness": [str],             # 粗糙度列表
            },
            "process_reference": str,  # 工艺参考文本（全部技术要求）
            "key_features": Dict,       # 原始【】字段
        }
    """
    import re

    result = {
        "vector_index": "",
        "structured_filter": {
            "blank_type": None,
            "overall_length": None,
            "main_diameter": None,
            "tolerance_levels": [],
            "thread_specs": [],
            "hole_specs": [],
            "roughness": [],
        },
        "process_reference": "",
        "key_features": {},
    }

    desc_upper = description.replace(" ", "")

    # 1. 提取所有【】字段
    bracket_pattern = r"【([^】]+)】([^【】\n]*)"
    bracket_matches = re.findall(bracket_pattern, desc_upper)
    for field_name, field_value in bracket_matches:
        field_value = field_value.strip()
        if field_value and field_value not in ["无", "无明确标注", "未标注"]:
            result["key_features"][field_name] = field_value

    # 2. 构建向量索引文本
    vector_parts = []
    for field_name in VECTOR_INDEX_FIELDS:
        if field_name in result["key_features"]:
            vector_parts.append(f"{field_name}: {result['key_features'][field_name]}")
    result["vector_index"] = " | ".join(vector_parts)

    # 3. 解析结构化字段
    # 毛坯类型
    if "毛坯类型" in result["key_features"]:
        result["structured_filter"]["blank_type"] = result["key_features"]["毛坯类型"]

    # 关键尺寸解析
    if "关键尺寸" in result["key_features"]:
        size_text = result["key_features"]["关键尺寸"]
        # 提取总长（查找类似 "总长5950" 或 "长度5950"）
        length_match = re.search(r"(?:总长|长度)[^0-9]*([0-9]+(?:\.[0-9]+)?)", size_text)
        if length_match:
            length_val = float(length_match.group(1))
            result["structured_filter"]["overall_length"] = (length_val * 0.9, length_val * 1.1)  # ±10%范围

        # 提取主直径（φxxx格式）
        diameter_matches = re.findall(r"φ([0-9]+(?:\.[0-9]+)?)", size_text)
        if diameter_matches:
            diameters = [float(d) for d in diameter_matches]
            max_dia = max(diameters)
            result["structured_filter"]["main_diameter"] = (max_dia * 0.8, max_dia * 1.2)  # ±20%范围

    # 公差等级解析
    if "精度与检测特征" in result["key_features"]:
        tol_text = result["key_features"]["精度与检测特征"]
        # 匹配H7, h7, H6, h6, IT7, IT6等
        tolerance_matches = re.findall(r"([A-Za-z]*[0-9]+[A-Za-z]*)", tol_text)
        result["structured_filter"]["tolerance_levels"] = list(set(tolerance_matches))

    # 螺纹规格解析
    if "螺纹与螺孔" in result["key_features"]:
        thread_text = result["key_features"]["螺纹与螺孔"]
        # 匹配M16, M24, M12等
        thread_matches = re.findall(r"M([0-9]+(?:\.[0-9]+)?)", thread_text)
        result["structured_filter"]["thread_specs"] = [f"M{t}" for t in thread_matches]

    # 孔径规格解析
    if "外圆与内孔" in result["key_features"]:
        hole_text = result["key_features"]["外圆与内孔"]
        # 匹配φ40, φ110H7等
        hole_matches = re.findall(r"φ([0-9]+(?:\.[0-9]+)?)", hole_text)
        result["structured_filter"]["hole_specs"] = [f"Φ{h}" for h in hole_matches]
        # 提取带公差的孔
        h7_holes = re.findall(r"φ([0-9]+(?:\.[0-9]+)?)H7", hole_text, re.IGNORECASE)
        result["structured_filter"]["tolerance_levels"].extend([f"H7" for _ in h7_holes])

    # 粗糙度解析
    if "外圆与内孔" in result["key_features"]:
        rough_text = result["key_features"]["外圆与内孔"]
        ra_matches = re.findall(r"Ra([0-9]+(?:\.[0-9]+)?)", rough_text)
        result["structured_filter"]["roughness"] = [f"Ra{r}" for r in ra_matches]

    # 4. 构建工艺参考文本
    ref_parts = []
    for field_name in PROCESS_REFERENCE_FIELDS:
        if field_name in result["key_features"]:
            ref_parts.append(f"{field_name}: {result['key_features'][field_name]}")
    result["process_reference"] = "\n".join(ref_parts)

    return result


def extract_all_features(description: str) -> Dict:
    """从图纸描述中提取所有特征（兼容旧接口）

    支持新旧两种格式的Vision输出
    使用【】字段作为特征进行匹配
    """
    # 调用新的分层提取函数
    structured = extract_structured_features(description)

    # 转换为旧接口格式
    result = {
        "key_features": structured["key_features"],
        "tech_requirement": structured["key_features"].get("技术要求"),
        "processes": [],
        "materials": [],
        "sizes": [],
        "key_holes": structured["structured_filter"].get("hole_specs", []),
        "tolerance_h7": structured["structured_filter"].get("tolerance_levels", []),
        "assembly_features": [],
    }

    desc_upper = description.replace(" ", "").upper()

    # 从key_features中提取工艺关键词
    for field_name, field_value in result["key_features"].items():
        for kw in PROCESS_KEYWORDS:
            if kw in field_value and kw not in result["processes"]:
                result["processes"].append(kw)
        for kw in MATERIAL_KEYWORDS:
            if kw in field_value and kw not in result["materials"]:
                result["materials"].append(kw)

    return result


def extract_feature_keywords(text: str) -> List[str]:
    """从特征文本中提取关键词用于部分匹配

    用于【形态】、【类型】等字段的关键词提取
    提取有意义的词作为匹配关键词

    优化：移除超通用关键词，避免假阳性
    """
    if not text:
        return []

    keywords = []

    # 机械零件类型关键词（移除单字符，保留2+字符的专有词）
    part_keywords = [
        "转子",
        "支架",
        "主轴",
        "法兰",
        "端盖",
        "叶轮",
        "涡轮",
        "叶片",
        "轴套",
        "衬套",
        "汽封",
        "密封件",
        "汽封圈",
        "密封圈",
        "齿轮",
        "蜗轮",
        "蜗杆",
        "皮带轮",
        "箱体",
        "壳体",
        "座体",
        "基座",
        "活塞",
        "缸体",
        "缸盖",
        "曲轴",
        "连杆",
        "法兰盘",
        "环形",
        "圆盘",
        "圆环",
        "键槽",
        "油槽",
        "通孔",
        "盲孔",
        "深孔",
        "外圆",
        "内孔",
        "内腔",
        "止口",
        "阶梯",
        "锥度",
        "孔径",
        "外径",
        "内径",
        "法兰端",
        "轴端",
        "轴身",
        "轴颈",
        "轴肩",
        "轴头",
        "连接",
        "配合",
        "定位",
        "密封",
        "减重",
        "通径",
    ]

    # 工艺特征关键词（移除单字符，保留具体工艺名称）
    process_keywords = [
        "粗车",
        "精车",
        "半精车",
        "车削",
        "铣削",
        "刨削",
        "磨削",
        "镗孔",
        "钻孔",
        "铰孔",
        "热处理",
        "淬火",
        "回火",
        "渗碳",
        "氮化",
        "调质",
        "时效",
        "探伤",
        "UT探伤",
        "MT探伤",
        "PT探伤",
        "超声探伤",
        "磁粉探伤",
        "装配",
        "焊接",
        "拼焊",
        "组焊",
        "动平衡",
        "静平衡",
        "精加工",
        "粗加工",
        "半精加工",
        "车磨",
        "铣钻",
        "车镗",
        "铣镗",
        "钻攻",
        "镗铣",
        "镗钻",
    ]

    # 形状特征关键词
    shape_keywords = [
        "环形",
        "圆形",
        "筒形",
        "柱形",
        "锥形",
        "多齿",
        "齿形",
        "螺旋",
        "螺纹",
        "法兰",
        "止口",
        "键槽",
        "油槽",
        "通孔",
        "盲孔",
        "深孔",
        "外圆",
        "内孔",
        "内腔",
        "过渡",
        "圆角",
        "倒角",
        "坡口",
    ]

    # 组合所有关键词
    all_keywords = set(part_keywords + process_keywords + shape_keywords)

    # 提取至少2个字符的关键词
    for kw in all_keywords:
        if len(kw) >= 2 and kw in text:
            keywords.append(kw)

    return list(set(keywords))  # 去重


def match_features_by_keywords(
    input_features: Dict,  # extracted_features from input
    db_record_features: Dict,  # extracted_features from database record
) -> tuple[int, List[str]]:
    """通过关键词匹配两个特征集

    匹配策略：
    1. 精确字段匹配（零件名称、类型）- 最高权重
    2. 字段名+字段值精确匹配 - 高权重
    3. 关键词重叠匹配 - 普通权重

    优化：增加字段值长度要求，避免短文本匹配假阳性
    """
    total_score = 0
    matched_details = []

    # 关键匹配字段（最高权重）- 需要字段值长度 >= 4 才计入
    critical_fields = ["零件名称", "类型", "毛坯类型", "形态", "关键尺寸"]
    important_fields = ["技术要求", "外圆与内孔", "螺纹与螺孔"]

    # Step 1: 精确字段值匹配（最高优先级）
    # 要求：字段值长度 >= 4 才有意义匹配
    for field_name in critical_fields:
        if field_name not in input_features:
            continue
        input_value = input_features[field_name]
        if not input_value or input_value in ["无", "无明确标注", "未标注"]:
            continue
        if len(input_value) < 4:  # 跳过太短的字段值
            continue

        input_kw = set(extract_feature_keywords(input_value))

        if field_name in db_record_features:
            db_value = db_record_features[field_name]
            if not db_value or db_value in ["无", "无明确标注", "未标注"]:
                continue
            if len(db_value) < 4:  # 跳过太短的字段值
                continue

            db_kw = set(extract_feature_keywords(db_value))

            overlap = input_kw & db_kw
            if overlap:
                critical_score = len(overlap) * 100
                total_score += critical_score
                matched_details.append(
                    f"【精确匹配】{field_name}: {list(overlap)} (score={critical_score})"
                )

    # Step 2: 字段名+字段值精确匹配（高优先级）
    # 要求：字段值长度 >= 6 才计入（避免短文本噪音）
    for field_name, input_value in input_features.items():
        if not input_value or input_value in ["无", "无明确标注", "未标注"]:
            continue
        if len(input_value) < 6:  # 跳过太短的字段值
            continue

        input_keywords = set(extract_feature_keywords(input_value))
        if not input_keywords:  # 没有有效关键词则跳过
            continue

        for db_field_name, db_value in db_record_features.items():
            if not db_value or db_value in ["无", "无明确标注", "未标注"]:
                continue
            if len(db_value) < 6:  # 跳过太短的字段值
                continue

            db_keywords = set(extract_feature_keywords(db_value))
            if not db_keywords:  # 没有有效关键词则跳过
                continue

            overlap = input_keywords & db_keywords
            if overlap:
                overlap_ratio = len(overlap) / len(input_keywords)

                # 权重计算
                if field_name in critical_fields:
                    weight = 10.0
                elif field_name in important_fields:
                    weight = 3.0
                else:
                    weight = 1.0

                field_name_match_bonus = 2.0 if field_name == db_field_name else 1.0

                score = len(overlap) * overlap_ratio * weight * field_name_match_bonus

                # 只有分数 > 5 才记录（过滤低质量匹配）
                if score > 5:
                    total_score += score
                    matched_details.append(
                        f"{field_name}({len(overlap)}/{len(input_keywords)})={list(overlap)[:3]}"
                    )

    return int(total_score), matched_details


def extract_tech_req_keywords(tech_req: str) -> List[str]:
    """从技术要求文本中提取关键词

    用于技术要求匹配索引
    """
    if not tech_req:
        return []

    keywords = []
    desc_upper = tech_req.upper()

    # 常见技术要求关键词
    tech_keywords = [
        # 精度要求
        "精度",
        "同轴度",
        "圆跳动",
        "垂直度",
        "平行度",
        "位置度",
        "对称度",
        "平面度",
        "直线度",
        "粗糙度",
        "Ra",
        "Rz",
        # 形位公差
        "形位公差",
        "形位误差",
        "公差等级",
        "IT",
        # 热处理要求
        "热处理",
        "硬度",
        "HB",
        "HRC",
        "淬火",
        "回火",
        "渗碳",
        "氮化",
        "调质",
        "正火",
        # 探伤要求
        "探伤",
        "UT",
        "MT",
        "PT",
        "VT",
        "RT",
        "超声",
        "磁粉",
        "渗透",
        # 平衡要求
        "平衡",
        "动平衡",
        "静平衡",
        "不平衡量",
        # 装配要求
        "装配",
        "配合",
        "间隙",
        "过盈",
        "键槽",
        # 表面处理
        "表面处理",
        "防腐",
        "防锈",
        "涂漆",
        "喷漆",
        "电镀",
        "镀铬",
        "氧化",
        # 材料要求
        "材料",
        "材质",
        "牌号",
        "化学成分",
        "力学性能",
        # 其他要求
        "焊接",
        "时效",
        "去应力",
        "退火",
        "尺寸公差",
        "形位公差",
    ]

    for kw in tech_keywords:
        if kw in desc_upper or kw in tech_req:
            keywords.append(kw)

    return list(set(keywords))  # 去重


def extract_key_features_text(description: str) -> str:
    """提取【】字段特征文本，用于RAG检索"""
    result = extract_all_features(description)
    # 将【】字段拼接为检索文本
    feature_parts = []
    for field_name, field_value in result["key_features"].items():
        # 使用字段名作为前缀，提高匹配准确性
        feature_parts.append(f"{field_name}: {field_value}")
    return " | ".join(feature_parts)


# ============ 多维度索引 ============
def build_multi_index(library_key: str | None = None) -> Dict:
    """构建多维度索引 - 使用key_features和技术要求作为主要检索条件

    Args:
        library_key: optional library key to scope the index; defaults to public vectors_v2
    """
    # Determine target vector table
    if library_key:
        scope = _resolve_library_scope(library_key)
        vector_table = (scope["vector_table"] if scope else "vectors_v2")
    else:
        vector_table = "vectors_v2"

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Query the target vector table (supports per-library tables)
    cursor.execute(
        f"SELECT prefix, vector, content, context, product_type, process_summary, key_features, tech_requirement FROM {vector_table}"
    )
    rows = cursor.fetchall()
    print(f"[RAG] Building index on {vector_table}: {len(rows)} rows")

    conn.close()

    # 多维度索引
    index = {
        "by_key_field": {},  # 【】字段名 -> 值 -> 记录
        "by_tech_req": {},  # 技术要求索引
        "by_process": {},  # 工艺类型
        "by_material": {},  # 材料
        "records": {},  # 完整记录
    }

    # 处理目标表 - 使用预提取的key_features
    for (
        prefix,
        vector_bytes,
        content,
        context,
        product_type,
        process_summary,
        key_features,
        tech_requirement,
    ) in rows:
        try:
            processes = parse_rows_field(content)
            if not processes:
                continue

            # 从key_features提取【】字段
            extracted_features = {}
            if key_features:
                # 尝试【】括号格式 first
                bracket_pattern = r"【([^】]+)】([^【】\n]*)"
                matches = re.findall(bracket_pattern, key_features)
                if matches:
                    for field_name, field_value in matches:
                        field_value = field_value.strip()
                        if field_value and field_value not in [
                            "无",
                            "无明确标注",
                            "未标注",
                        ]:
                            extracted_features[field_name] = field_value
                else:
                    # 尝试冒号分隔格式: "零件名称：xxx\n类型：xxx"
                    colon_pattern = r"([^：\n]+)：([^【】\n]+)"
                    colon_matches = re.findall(colon_pattern, key_features)
                    for field_name, field_value in colon_matches:
                        field_value = field_value.strip()
                        if field_value and field_value not in [
                            "无",
                            "无明确标注",
                            "未标注",
                            "",
                        ]:
                            extracted_features[field_name] = field_value

            # 如果key_features中没有技术要求，但从tech_requirement字段有值
            if not extracted_features.get("技术要求") and tech_requirement:
                extracted_features["技术要求"] = tech_requirement

            # 从key_features提取工艺类型
            process_types = []
            if key_features:
                for kw in PROCESS_KEYWORDS:
                    if kw in key_features:
                        process_types.append(kw)

            # 从key_features提取材料
            materials = []
            if key_features:
                for kw in MATERIAL_KEYWORDS:
                    if kw in key_features:
                        materials.append(kw)

            record = {
                "drawing_id": prefix,
                "vector": vector_bytes,
                "process_list": processes,
                "context": context or "",
                "key_features": extracted_features,
                "tech_requirement": tech_requirement
                or extracted_features.get("技术要求"),
                "process_types": process_types,
                "materials": materials,
            }

            # 按【】字段索引
            for field_name, field_value in extracted_features.items():
                if field_name not in index["by_key_field"]:
                    index["by_key_field"][field_name] = {}
                if field_value not in index["by_key_field"][field_name]:
                    index["by_key_field"][field_name][field_value] = []
                index["by_key_field"][field_name][field_value].append(record)

            # 按技术要求索引（如果存在）
            if tech_requirement or extracted_features.get("技术要求"):
                tech_req_value = tech_requirement or extracted_features.get("技术要求")
                if tech_req_value and tech_req_value not in [
                    "无",
                    "无明确标注",
                    "未标注",
                ]:
                    # 提取关键词进行索引
                    tech_keywords = extract_tech_req_keywords(tech_req_value)
                    for keyword in tech_keywords:
                        if keyword not in index["by_tech_req"]:
                            index["by_tech_req"][keyword] = []
                        index["by_tech_req"][keyword].append(record)

            # 按工艺类型索引
            for p in process_types:
                if p not in index["by_process"]:
                    index["by_process"][p] = []
                index["by_process"][p].append(record)

            # 按材料索引
            for m in materials:
                if m not in index["by_material"]:
                    index["by_material"][m] = []
                index["by_material"][m].append(record)

            # 完整记录
            index["records"][prefix] = record

        except:
            continue

    return index


# 缓存索引 - 按库分组
# 结构: { vector_table_name: { "index": <index_dict>, "built": bool } }
_index_cache_per_lib = {}
_index_cache = None
_index_built = False


def invalidate_index_cache(library_key: str | None = None, vector_table: str | None = None):
    """Invalidate cached indexes after database updates.

    Args:
        library_key: library key to invalidate specific cache, or None for all
        vector_table: vector table name to invalidate (preferred over library_key)
    """
    global _index_cache_per_lib, _index_cache, _index_built
    if vector_table:
        _index_cache_per_lib.pop(vector_table, None)
    elif library_key:
        scope = _resolve_library_scope(library_key)
        if scope:
            _index_cache_per_lib.pop(scope["vector_table"], None)
    else:
        _index_cache_per_lib.clear()
    _index_cache = None
    _index_built = False


def get_multi_index(library_key: str | None = None) -> Dict:
    """获取多维度索引（带缓存，按库隔离）

    Args:
        library_key: optional library key to scope the index
    """
    global _index_cache_per_lib

    # Determine target vector table
    if library_key:
        scope = _resolve_library_scope(library_key)
        vector_table = (scope["vector_table"] if scope else "vectors_v2")
    else:
        vector_table = "vectors_v2"

    # Per-library cache
    if vector_table not in _index_cache_per_lib:
        _index_cache_per_lib[vector_table] = {
            "index": None,
            "built": False,
        }

    cache_entry = _index_cache_per_lib[vector_table]
    if not cache_entry["built"]:
        cache_entry["index"] = build_multi_index(library_key=library_key)
        cache_entry["built"] = True
        print(f"[RAG] Index built for {vector_table}: {len(cache_entry['index']['records'])} records")
        print(f"[RAG] Key Fields: {list(cache_entry['index']['by_key_field'].keys())}")
        print(f"[RAG] Processes: {list(cache_entry['index']['by_process'].keys())[:10]}...")

    return cache_entry["index"]


def query_by_prefix(prefix: str, top_k: int = 1, library_key: str | None = None) -> Dict:
    """根据图号前缀精确匹配（最高优先级）

    Args:
        prefix: 图号前缀，如 "1F11956"
        top_k: 返回结果数量
        library_key: 可选的库键，默认为 public

    Returns:
        匹配的记录，如果没有则返回None
    """
    if not prefix:
        return None

    # Determine target vector table
    if library_key:
        scope = _resolve_library_scope(library_key)
        vector_table = (scope["vector_table"] if scope else "vectors_v2")
    else:
        vector_table = "vectors_v2"

    prefix = _normalize_prefix_token(prefix)
    print(f"[RAG] Prefix exact match: '{prefix}' on {vector_table}")

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 查询目标向量表
        cursor.execute(
            f"SELECT prefix, content, context, product_type FROM {vector_table} WHERE UPPER(prefix) = ?",
            (prefix,),
        )
        row = cursor.fetchone()

        if row:
            drawing_id, content, context, product_type = row
            process_list = parse_rows_field(content)
            if not process_list:
                print(f"[RAG] Found exact match: {drawing_id} but process_list is empty (PRT-only import), skip")
                conn.close()
                return None

            print(
                f"[RAG] Found exact match: {drawing_id} ({product_type}), {len(process_list)} processes"
            )

            conn.close()
            return {
                "matches": [
                    {
                        "drawing_id": drawing_id,
                        "similarity": 1.0,
                        "matched": ["prefix_exact"],
                        "process_list": process_list,
                        "match_type": "prefix_exact",
                    }
                ],
                "rag_context": f"## 精确匹配工艺 ({drawing_id}, 共{len(process_list)}道工序)\n"
                + "\n".join([f"- {p}" for p in process_list]),  # 返回全部工序
                "top_similarity": 1.0,
                "product_type": product_type,
            }

        conn.close()

    except Exception as e:
        print(f"[RAG] Prefix error: {e}")

    return None


def query_by_vector_similarity(
    fused_description: str,
    top_k: int = 3,
    min_similarity: float = 0.3,
    library_key: str | None = None,
) -> List[Dict]:
    """向量相似匹配 - 使用豆包多模态Embedding API

    Args:
        fused_description: 融合的图纸描述
        top_k: 返回结果数量
        min_similarity: 最小相似度
        library_key: 可选的库键，默认为 public
    """
    print("[RAG] Doing vector similarity...")

    # Determine target vector table
    if library_key:
        scope = _resolve_library_scope(library_key)
        vector_table = (scope["vector_table"] if scope else "vectors_v2")
    else:
        vector_table = "vectors_v2"

    try:
        import requests as req

        api_key = os.getenv("EMBEDDING_API_KEY", "")
        base_url = os.getenv(
            "EMBEDDING_BASE_URL",
            "https://ark.cn-beijing.volces.com/api/v3/embeddings/multimodal",
        )
        model = os.getenv("EMBEDDING_MODEL", "doubao-embedding-vision-251215")

        if not api_key:
            print("[RAG] ERROR: EMBEDDING_API_KEY not set")
            return []

        key_text = fused_description[:2000]
        print(f"[RAG] Query text: {key_text[:100]}...")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        data = {
            "model": model,
            "instructions": "Target_modality: text.\nInstruction:Compress the text into a semantic vector for retrieval.\nQuery:",
            "input": [{"type": "text", "text": key_text}],
            "dimensions": 1024,
            "encoding_format": "float",
        }

        resp = req.post(base_url, headers=headers, json=data).json()
        query_vector = np.array(resp["data"]["embedding"], dtype=np.float32)
        print(f"[RAG] Query vector shape: {query_vector.shape}")

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 查询目标向量表
        cursor.execute(f"SELECT prefix, vector, content, context FROM {vector_table}")
        rows = cursor.fetchall()
        print(f"[RAG] {vector_table} table: {len(rows)} rows")

        conn.close()

        print(f"[RAG] Total rows to compare: {len(rows)}")

        results = []
        for prefix, vector_bytes, content, context in rows:
            try:
                # 兼容两种存储格式：blob(旧)和text(JSON字符串，新)
                if isinstance(vector_bytes, bytes):
                    stored_vector = np.frombuffer(vector_bytes, dtype=np.float32)
                else:
                    # JSON字符串格式
                    vector_list = json.loads(vector_bytes)
                    stored_vector = np.array(vector_list, dtype=np.float32)

                cos_sim = np.dot(query_vector, stored_vector) / (
                    np.linalg.norm(query_vector) * np.linalg.norm(stored_vector) + 1e-8
                )

                if cos_sim >= min_similarity:
                    processes = parse_rows_field(content)
                    if not processes:
                        continue
                    results.append(
                        {
                            "drawing_id": prefix,
                            "similarity": cos_sim,
                            "process_list": processes,
                            "context": context or "",
                        }
                    )
                    print(f"[RAG] MATCH: {prefix} sim={cos_sim:.4f}")
            except Exception as e:
                print(f"[RAG] Vector parse error for {prefix}: {e}")
                continue

        print(f"[RAG] Total matches above {min_similarity}: {len(results)}")
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]

    except Exception as e:
        print(f"[RAG] Vector error: {e}")
        return []


def score_record(record: Dict, features: Dict) -> float:
    """计算记录与输入特征的匹配分数"""
    score = 0.0
    matched = []

    # 1. 产品类型匹配（权重：0.5）
    if record.get("product_type") and features.get("product_type"):
        if record["product_type"] == features["product_type"]:
            score += 0.5
            matched.append(f"产品:{record['product_type']}")

    # 2. 工艺关键词匹配（权重：0.3）
    record_procs = set(record.get("process_types", []))
    input_procs = set(features.get("processes", []))
    if input_procs and record_procs:
        overlap = len(record_procs & input_procs)
        score += min(overlap * 0.1, 0.3)
        if overlap:
            matched.append(f"工艺:{overlap}")

    # 3. 材料匹配（权重：0.2）
    record_mats = set(record.get("materials", []))
    input_mats = set(features.get("materials", []))
    if input_mats and record_mats:
        overlap = len(record_mats & input_mats)
        score += min(overlap * 0.1, 0.2)
        if overlap:
            matched.append(f"材料:{overlap}")

    return score, matched


def query_by_fused_text(
    fused_description: str,
    top_k: int = 3,
    min_similarity: float = 0.3,
    prefix_hint: str = None,
    log_callback=None,
    library_key: str | None = None,
) -> Dict:
    """多维度混合检索 - 使用Reciprocal Rank Fusion

    向量相似度是主要排名信号，前缀匹配是次要增强信号。
    如果前缀匹配存在于top结果中，会被提升到最前面。

    Args:
        fused_description: 融合的图纸描述
        top_k: 返回结果数量
        min_similarity: 最小相似度
        prefix_hint: 可选的图号前缀
        log_callback: 可选的日志回调函数，接受(message)参数
        library_key: 可选的库键，默认为 public
    """
    import time

    def _log(msg):
        """内部日志函数，同时打印和回调，间隔0.2秒模拟思考过程"""
        print(msg)
        if log_callback:
            log_callback(msg)
            time.sleep(0.2)  # 0.2秒间隔，模拟思考过程

    _log("✨ 启动工艺智能检索...")
    _log(f"📝 分析图纸特征中...")

    # Step 0: 提取图号用于后续增强
    import re

    extracted_prefix = prefix_hint  # 从调用者传入的prefix_hint开始

    # 如果没有传入prefix_hint，从描述中提取
    if not extracted_prefix:
        patterns = [
            r"【图号】\s*([1-9][A-Z]\d{4,6})",  # Vision格式
            r"(?:^|[^\w])([1-9][A-Z]\d{4,6})(?:[A-Z]|$|[^\w])",  # 通用格式
        ]
        for pattern in patterns:
            matches = re.findall(pattern, fused_description, re.IGNORECASE)
            if matches:
                extracted_prefix = matches[0].upper()
                _log(f"🔍 发现图号: {extracted_prefix}")
                break

    # Step 1: 提取所有特征（分层）
    features = extract_all_features(fused_description)
    structured_data = extract_structured_features(fused_description)

    index = get_multi_index(library_key=library_key)

    # Resolve vector_table for structured filter query (same logic as other query functions)
    if library_key:
        _scope = _resolve_library_scope(library_key)
        vector_table = _scope["vector_table"] if _scope else "vectors_v2"
    else:
        vector_table = "vectors_v2"

    # ========== 构建多个排名列表 ==========
    rankings = []

    # Ranking 1: 向量相似度排名（主要信号）
    _log("🔍 向量相似度检索中...")

    # 优化：使用标准化后的特征文本进行向量检索，与数据库构建方式一致
    standardized_text = extract_key_features_text(fused_description)
    if not standardized_text:
        # 如果标准化失败，回退到原始描述
        standardized_text = fused_description

    vector_results = query_by_vector_similarity(
        standardized_text,
        top_k * 10,  # 增大搜索范围以获得更好的排名
        library_key=library_key,
    )
    if vector_results:
        vector_ranking = [
            {
                "drawing_id": vr["drawing_id"],
                "similarity": vr["similarity"],
                "vector_similarity": vr["similarity"],  # 保存原始向量相似度
                "process_list": vr["process_list"],
                "match_type": "vector",
                "matched": ["vector"],
            }
            for vr in vector_results
        ]
        rankings.append(vector_ranking)
        _log(f"   找到 {len(vector_results)} 个向量匹配项")

        # 如果找到前缀，检查是否在top结果中
        if extracted_prefix:
            prefix_in_top = any(
                r["drawing_id"].upper() == extracted_prefix.upper()
                for r in vector_results[: top_k * 3]
            )
            if prefix_in_top:
                _log(f"   ✅ 图号 '{extracted_prefix}' 在向量检索结果中")
            else:
                _log(f"   ⚠️ 图号 '{extracted_prefix}' 不在向量检索结果中")
    else:
        vector_ranking = []
        _log("   未找到向量匹配结果")

    # Ranking 2: Key Features匹配排名（使用关键词部分匹配）
    key_feature_ranking = []
    extracted_features = features.get("key_features", {})

    # 提取输入特征的关键词
    input_keywords = set()
    for field_name, field_value in extracted_features.items():
        if field_value and field_value not in ["无", "无明确标注", "未标注"]:
            kw_list = extract_feature_keywords(field_value)
            input_keywords.update(kw_list)

    # 检查向量是否有效
    vectors_valid = len(vector_ranking) > 0 and any(
        vr.get("similarity", 0) > 0.4 for vr in vector_ranking[:5]
    )

    _log("🔄 关键词特征匹配中...")

    if input_keywords and index["records"]:
        feature_scores = {}

        # 对每个数据库记录计算关键词匹配分数
        for drawing_id, record in index["records"].items():
            db_features = record.get("key_features", {})

            # 使用关键词匹配函数
            match_score, match_details = match_features_by_keywords(
                extracted_features, db_features
            )

            if match_score > 0:
                feature_scores[drawing_id] = {
                    "record": record,
                    "score": match_score,
                    "details": match_details,
                }

        if feature_scores:
            # 按匹配分数和向量相似度排序
            feature_sorted = []
            for drawing_id, data in feature_scores.items():
                vec_sim = 0.5
                for vr in vector_ranking:
                    if vr["drawing_id"] == drawing_id:
                        vec_sim = vr["similarity"]
                        break

                # 组合分数计算
                if vectors_valid:
                    combined_score = data["score"] * 5 + vec_sim
                else:
                    combined_score = data["score"] * 10

                feature_sorted.append(
                    (
                        combined_score,
                        data["score"],
                        vec_sim,
                        data["record"],
                        data["details"],
                    )
                )

            # 按组合分数排序
            feature_sorted.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)

            for combined, feature_score, vec_sim, record, details in feature_sorted[
                :10
            ]:
                key_feature_ranking.append(
                    {
                        "drawing_id": record["drawing_id"],
                        "similarity": max(vec_sim, 0.5),  # 至少给0.5的基础分
                        "process_list": record["process_list"],
                        "match_type": f"key_feature({feature_score})",
                        "matched": [f"key_feature:{feature_score}"],
                    }
                )

            if key_feature_ranking:
                _log(f"   关键词匹配找到 {len(key_feature_ranking)} 个候选")

    # Ranking 3: 技术要求匹配排名
    tech_req_ranking = []
    tech_req_value = features.get("tech_requirement")

    if tech_req_value:
        # 从技术要求中提取关键词
        tech_keywords = extract_tech_req_keywords(tech_req_value)
        _log("📋 技术要求匹配中...")

        if tech_keywords:
            tech_scores = {}
            for keyword in tech_keywords:
                matches = index["by_tech_req"].get(keyword, [])
                for m in matches:
                    if m["drawing_id"] not in tech_scores:
                        tech_scores[m["drawing_id"]] = {
                            "record": m,
                            "count": 0,
                            "matched_keywords": [],
                        }
                    tech_scores[m["drawing_id"]]["count"] += 1
                    tech_scores[m["drawing_id"]]["matched_keywords"].append(keyword)

            if tech_scores:
                # 按匹配数量排序
                tech_sorted = []
                for drawing_id, data in tech_scores.items():
                    vec_sim = 0.5
                    for vr in vector_ranking:
                        if vr["drawing_id"] == drawing_id:
                            vec_sim = vr["similarity"]
                            break
                    tech_sorted.append((data["count"], vec_sim, data["record"]))

                tech_sorted.sort(key=lambda x: (x[0], x[1]), reverse=True)

                for count, vec_sim, m in tech_sorted[:10]:
                    tech_req_ranking.append(
                        {
                            "drawing_id": m["drawing_id"],
                            "similarity": vec_sim,
                            "process_list": m["process_list"],
                            "match_type": f"tech_req({count})",
                            "matched": [f"tech_req:{count}"],
                        }
                    )

                if tech_req_ranking:
                    _log(f"   技术要求匹配找到 {len(tech_req_ranking)} 个候选")

    # Ranking 4: 工艺关键词匹配排名
    process_ranking = []
    if features.get("processes"):
        process_scores = {}
        for proc in features["processes"][:5]:  # 最多5个工艺
            matches = index["by_process"].get(proc, [])
            for m in matches:
                if m["drawing_id"] not in process_scores:
                    process_scores[m["drawing_id"]] = {
                        "record": m,
                        "count": 0,
                    }
                process_scores[m["drawing_id"]]["count"] += 1

        # 按工艺匹配数量排序
        sorted_processes = sorted(
            process_scores.items(), key=lambda x: x[1]["count"], reverse=True
        )

        for drawing_id, data in sorted_processes[:10]:  # 最多10个
            m = data["record"]
            # 获取向量相似度
            vec_sim = 0.5
            for vr in vector_ranking:
                if vr["drawing_id"] == drawing_id:
                    vec_sim = vr["similarity"]
                    break
            process_ranking.append(
                {
                    "drawing_id": drawing_id,
                    "similarity": vec_sim,
                    "process_list": m["process_list"],
                    "match_type": f"process({data['count']})",
                    "matched": [f"process:{data['count']}"],
                }
            )

        _log(f"   工艺关键词匹配找到 {len(process_ranking)} 个候选")

    # Ranking 5: 结构化过滤排名（新增）
    structured_ranking = []
    _log("🔧 结构化字段过滤检索中...")

    structured_filter = structured_data.get("structured_filter", {})
    if any([
        structured_filter.get("blank_type"),
        structured_filter.get("overall_length"),
        structured_filter.get("main_diameter"),
        structured_filter.get("tolerance_levels"),
        structured_filter.get("thread_specs"),
    ]):
        structured_results = query_by_structured_filter(
            structured_filter,
            top_k=20,
            vector_table=vector_table,
        )
        if structured_results:
            # 合并到排名
            for sr in structured_results:
                vec_sim = 0.5
                for vr in vector_ranking:
                    if vr["drawing_id"] == sr["drawing_id"]:
                        vec_sim = vr["similarity"]
                        break
                structured_ranking.append({
                    "drawing_id": sr["drawing_id"],
                    "similarity": vec_sim,
                    "process_list": sr["process_list"],
                    "match_type": f"structured({sr['filter_score']:.0f})",
                    "matched": sr.get("matched", []),
                })
            _log(f"   结构化过滤找到 {len(structured_ranking)} 个候选")

    # Ranking 6: 前缀精确匹配排名
    prefix_ranking = []
    if extracted_prefix:
        # 检查前缀是否在数据库中
        prefix_record = query_by_prefix(extracted_prefix, top_k=1)
        if prefix_record:
            prefix_drawing_id = prefix_record["matches"][0]["drawing_id"]
            # 获取该记录的向量相似度
            vec_sim = 0.5
            for vr in vector_ranking:
                if vr["drawing_id"] == prefix_drawing_id:
                    vec_sim = vr["similarity"]
                    break
            prefix_ranking.append(
                {
                    "drawing_id": prefix_drawing_id,
                    "similarity": vec_sim,
                    "process_list": prefix_record["matches"][0]["process_list"],
                    "match_type": "prefix_exact",
                    "matched": ["prefix"],
                }
            )
            _log(f"   🎯 精确图号匹配: {prefix_drawing_id} (相似度 {vec_sim:.1%})")

    # ========== 使用RRF合并排名 ==========
    # 注意：prefix_ranking是最高优先级信号，放在第一位
    all_rankings = [
        r
        for r in [
            prefix_ranking,
            vector_ranking,
            key_feature_ranking,
            tech_req_ranking,
            process_ranking,
            structured_ranking,  # 新增结构化过滤排名
        ]
        if r
    ]

    _log("⚖️ 综合评分中...")

    if not all_rankings:
        _log("⚠️ 未找到匹配结果，使用默认工艺...")
        if not index["records"]:
            _log("⚠️ 当前库没有任何有效工艺 content，返回空候选")
            return {
                "matches": [],
                "rag_context": (
                    (f"## 图纸工艺参考信息\n{structured_data['process_reference']}\n\n" if structured_data.get("process_reference") else "")
                    + "## 参考工艺候选 (0个)\n\n"
                ),
                "top_similarity": 0.0,
                "key_features": extracted_features,
                "tech_requirement": tech_req_value,
                "process_reference": structured_data.get("process_reference", ""),
                "structured_filter": structured_data.get("structured_filter", {}),
            }
        # 兜底：按零件类别选最近邻，而不是随机取字典第一条
        query_category_fb = classify_part_category(extracted_features)
        candidate_records = list(index["records"].values())
        if query_category_fb != "未知":
            same_cat = [r for r in candidate_records
                        if classify_part_category(r.get("key_features", {})) == query_category_fb]
            if same_cat:
                candidate_records = same_cat
        # 从候选中选工序数最多的（工序数多 = 数据更完整）
        best_fallback = max(candidate_records, key=lambda r: len(r.get("process_list", [])))
        _log(f"⚠️ 无检索命中，兜底使用同类 [{query_category_fb}] 蓝本: {best_fallback['drawing_id']}")
        all_results = [
            {
                "drawing_id": best_fallback["drawing_id"],
                "similarity": 0.1,
                "matched": ["fallback"],
                "process_list": best_fallback["process_list"],
                "match_type": "fallback",
            }
        ]
    else:
        # 使用RRF合并
        fused_results = reciprocal_rank_fusion(all_rankings)

        # 合并匹配信息
        for result in fused_results:
            result["matched"] = []
            result["match_type"] = ""
            # 收集所有匹配类型
            for ranking in all_rankings:
                for item in ranking:
                    if item["drawing_id"] == result["drawing_id"]:
                        result["matched"].extend(item.get("matched", []))
                        if item.get("match_type"):
                            if result["match_type"]:
                                result["match_type"] += "+" + item["match_type"]
                            else:
                                result["match_type"] = item["match_type"]

            # 去重匹配类型
            matched_set = set()
            for m in result["matched"]:
                # 提取基础类型（去除括号内容）
                base = m.split("(")[0].strip()
                matched_set.add(base)
            result["matched"] = list(matched_set)

        all_results = fused_results[:top_k]

    # ========== 前缀精确匹配增强 ==========
    # 如果找到前缀精确匹配，将其提升到最前面（prefix是最高优先级信号）
    if extracted_prefix and prefix_ranking:
        prefix_drawing_id = prefix_ranking[0]["drawing_id"]
        prefix_in_results = any(
            r["drawing_id"] == prefix_drawing_id for r in all_results
        )

        if not prefix_in_results:
            # 前缀匹配不在top结果中，直接插入到位置1
            prefix_result = prefix_ranking[0].copy()
            prefix_result["match_type"] = "prefix_exact"
            prefix_result["matched"] = ["prefix"]
            prefix_result["similarity"] = 1.0  # 强制最高相似度
            all_results.insert(0, prefix_result)
            all_results = all_results[:top_k]  # 重新限制数量
            _log(f"   ⬆️ 图号精确匹配优先排序")

        # 更新已存在结果的匹配类型
        for r in all_results:
            if r["drawing_id"] == prefix_drawing_id:
                if "prefix" not in r.get("matched", []):
                    r["matched"] = r.get("matched", []) + ["prefix"]
                if "prefix" not in r.get("match_type", ""):
                    r["match_type"] = "vector+prefix_exact"
                # 如果prefix匹配在位置1，更新相似度为1.0
                if all_results.index(r) == 0:
                    r["similarity"] = 1.0

    # ========== 零件类别感知降权 ==========
    # 推断查询零件的类别，对不兼容类别的候选做软降权（prefix精确匹配豁免）
    query_category = classify_part_category(extracted_features)
    _log(f"🏷️ 查询零件类别: {query_category}")

    if query_category != "未知":
        incompatible_cats = _CATEGORY_INCOMPATIBLE.get(query_category, set())
        if incompatible_cats:
            for r in all_results:
                # prefix精确匹配豁免降权
                if "prefix" in r.get("matched", []) or r.get("match_type") == "prefix_exact":
                    r["part_category"] = query_category
                    continue
                rec = index["records"].get(r["drawing_id"])
                rec_category = classify_part_category(rec.get("key_features", {}) if rec else {})
                r["part_category"] = rec_category
                if rec_category in incompatible_cats:
                    old_sim = r.get("similarity", 0)
                    r["similarity"] = old_sim * _CATEGORY_MISMATCH_PENALTY
                    if "vector_similarity" in r:
                        r["vector_similarity"] *= _CATEGORY_MISMATCH_PENALTY
                    _log(
                        f"   ⚠️ {r['drawing_id']} 类别({rec_category})与查询({query_category})不符"
                        f"，相似度降权 {old_sim:.1%} → {r['similarity']:.1%}"
                    )

            # 降权后重新按相似度排序（prefix精确匹配已在首位，跳过它）
            prefix_head = [r for r in all_results if "prefix" in r.get("matched", []) or r.get("match_type") == "prefix_exact"]
            rest = [r for r in all_results if r not in prefix_head]
            rest.sort(key=lambda x: x.get("similarity", 0), reverse=True)
            all_results = prefix_head + rest

    # 显示top结果
    _log(f"✅ 检索完成！找到 {len(all_results)} 个候选工艺：")
    for i, r in enumerate(all_results, 1):
        vec_sim = r.get("vector_similarity", r.get("similarity", 0))
        cat_label = f" [{r['part_category']}]" if r.get("part_category") else ""
        _log(f"   候选{i}: {r['drawing_id']}{cat_label} (匹配度 {vec_sim:.1%})")

    best = all_results[0] if all_results else {}

    # 构建多个参考工艺的上下文（用于LLM判断）
    # 如果有工艺参考信息，添加到开头
    process_ref_header = ""
    if structured_data.get("process_reference"):
        process_ref_header = f"## 图纸工艺参考信息\n{structured_data['process_reference']}\n\n"

    rag_context = process_ref_header + f"## 参考工艺候选 ({len(all_results)}个)\n\n"
    for i, r in enumerate(all_results[:3], 1):
        process_count = len(r["process_list"])
        rag_context += f"--- 候选{i}: {r['drawing_id']} ({r['match_type']}) - 共{process_count}道工序 ---\n"
        for row in r["process_list"]:  # 显示完整工艺流程
            tag, content, meta = _split_process_row_for_prompt(row)
            if content:
                rag_context += f"{tag}: {content}"
                if meta:
                    rag_context += f" （{meta}）"
                rag_context += "\n"
        rag_context += "\n"

    return {
        "matches": all_results,
        "rag_context": rag_context,
        "top_similarity": best.get("similarity", 0.0),
        "key_features": extracted_features,
        "tech_requirement": tech_req_value,
        # 新增：工艺参考信息（不适合向量检索但对工艺生成有用的内容）
        "process_reference": structured_data.get("process_reference", ""),
        "structured_filter": structured_data.get("structured_filter", {}),
    }


# ============ 初始化 ============
def init_structured_features(force_rebuild: bool = False):
    # Structured columns are now part of the vector table; nothing to initialise separately.
    pass


# 兼容旧接口
def query_by_product_type(fused_description, top_k=3, min_similarity=0.3):
    return query_by_fused_text(fused_description, top_k, min_similarity)


if __name__ == "__main__":
    test_cases = [
        "转子支架锻件车铣钻镗Φ890",
        "齿轮加工模数5",
        "外来新零件",  # 外来图纸
    ]

    for test in test_cases:
        print(f"\n{'=' * 50}")
        print(f"Test: {test}")
        result = query_by_fused_text(test)
        if result.get("matches"):
            m = result["matches"][0]
            print(f"Best: {m['drawing_id']} ({m['match_type']})")
