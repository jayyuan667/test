# -*- coding: utf-8 -*-
import json
import os
import re
import sqlite3
from typing import Dict, List, Optional, Tuple

import numpy as np
import requests

BASE_DIR = r"D:\Work_project\Artificial_agent"
DB_PATH = os.path.join(BASE_DIR, "db_data", "vector_map_new.db")

PROCESS_KEYWORDS = [
    "车", "铣", "钻", "镗", "磨", "刨", "插", "滚齿", "剃齿", "线切割", "电火花",
    "热处理", "淬火", "回火", "渗碳", "氮化", "时效", "装配", "热套", "找摆", "同镗",
    "配焊", "铰孔", "冲压", "焊接", "钣金", "抛光", "探伤", "UT", "MT", "PT", "VT",
    "镀", "涂", "喷",
]

MATERIAL_KEYWORDS = [
    "锻件", "铸件", "棒料", "板材", "无缝钢管", "合金钢", "不锈钢", "铝合金", "铜合金", "钛合金",
]

TECH_KEYWORDS = [
    "精度", "同轴度", "圆跳动", "垂直度", "平行度", "位置度", "对称度", "平面度", "直线度", "粗糙度",
    "Ra", "Rz", "形位公差", "公差等级", "IT", "热处理", "硬度", "HB", "HRC", "淬火", "回火", "渗碳",
    "氮化", "调质", "正火", "探伤", "UT", "MT", "PT", "VT", "RT", "超声", "磁粉", "渗透",
    "平衡", "动平衡", "静平衡", "装配", "配合", "间隙", "过盈", "键槽", "表面处理", "防腐", "防锈",
    "涂漆", "喷漆", "电镀", "镀铬", "氧化", "材料", "材质", "牌号", "化学成分", "力学性能",
    "焊接", "时效", "去应力", "退火", "尺寸公差",
]

_index_cache: Optional[Dict] = None


def extract_all_features(text: str) -> Dict:
    raw = text or ""
    raw_upper = raw.replace(" ", "")
    raw_lower = raw_upper.lower()

    result = {
        "key_features": {},
        "tech_requirement": None,
        "processes": [],
        "materials": [],
    }

    for field, value in re.findall(r"【([^】]+)】([^【】\n]*)", raw_upper):
        value = value.strip()
        if value and value not in ["无", "无明确标注", "未标注"]:
            result["key_features"][field] = value

    for name in ["技术要求", "技术规范", "技术条件"]:
        m = re.search(rf"【{name}】([^【】\n]+)", raw_upper)
        if m:
            result["tech_requirement"] = m.group(1).strip()
            result["key_features"][name] = result["tech_requirement"]
            break

    for value in result["key_features"].values():
        for kw in PROCESS_KEYWORDS:
            if kw in value and kw not in result["processes"]:
                result["processes"].append(kw)
        for kw in MATERIAL_KEYWORDS:
            if kw in value and kw not in result["materials"]:
                result["materials"].append(kw)

    return result


def extract_tech_keywords(text: str) -> List[str]:
    if not text:
        return []
    out = []
    upper = text.upper()
    for kw in TECH_KEYWORDS:
        if kw in upper or kw in text:
            out.append(kw)
    return list(set(out))


def _parse_vector(raw_vector) -> Optional[np.ndarray]:
    try:
        if isinstance(raw_vector, bytes):
            vec = np.frombuffer(raw_vector, dtype=np.float32)
        else:
            vec = np.array(json.loads(raw_vector), dtype=np.float32)
        if vec.size == 0:
            return None
        return vec
    except Exception:
        return None


def _normalize_process_list(content: str) -> List[str]:
    try:
        parsed = json.loads(content)
    except Exception:
        return [content]

    if isinstance(parsed, list):
        return [str(x) for x in parsed]
    return [str(parsed)]


def load_index() -> Dict:
    global _index_cache
    if _index_cache is not None:
        return _index_cache

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT prefix, vector, content, key_features, tech_requirement FROM vectors_v2"
    )
    rows = cursor.fetchall()
    conn.close()

    index = {
        "records": {},
        "by_process": {},
        "by_tech": {},
    }

    for prefix, vector_raw, content, key_features_raw, tech_requirement in rows:
        vec = _parse_vector(vector_raw)
        process_list = _normalize_process_list(content)
        if vec is None or not process_list:
            continue

        key_features_raw = key_features_raw or ""
        parsed = extract_all_features(key_features_raw)
        if not parsed.get("tech_requirement") and tech_requirement:
            parsed["tech_requirement"] = tech_requirement
            parsed["key_features"]["技术要求"] = tech_requirement

        record = {
            "drawing_id": prefix,
            "vector": vec,
            "process_list": process_list,
            "key_features": parsed.get("key_features", {}),
            "tech_requirement": parsed.get("tech_requirement"),
            "processes": parsed.get("processes", []),
        }
        index["records"][prefix] = record

        for p in record["processes"]:
            index["by_process"].setdefault(p, []).append(record)

        for tk in extract_tech_keywords(record.get("tech_requirement") or ""):
            index["by_tech"].setdefault(tk, []).append(record)

    _index_cache = index
    return index


def query_by_prefix(prefix: str, top_k: int = 1) -> Optional[Dict]:
    if not prefix:
        return None

    index = load_index()
    key = prefix.strip().upper()
    rec = index["records"].get(key)
    if not rec:
        return None

    matches = [
        {
            "drawing_id": rec["drawing_id"],
            "similarity": 1.0,
            "vector_similarity": 1.0,
            "matched": ["prefix"],
            "match_type": "prefix_exact",
            "process_list": rec.get("process_list", []),
        }
    ]

    context_lines = [
        f"## 精确匹配工艺 ({rec['drawing_id']}, 共{len(rec.get('process_list', []))}道工序)"
    ]
    context_lines.extend([f"- {p}" for p in rec.get("process_list", [])])

    return {
        "matches": matches[:top_k],
        "rag_context": "\n".join(context_lines),
        "top_similarity": 1.0,
    }


def create_query_vector(text: str) -> Optional[np.ndarray]:
    api_key = os.getenv("EMBEDDING_API_KEY", "")
    base_url = os.getenv(
        "EMBEDDING_BASE_URL",
        "https://ark.cn-beijing.volces.com/api/v3/embeddings/multimodal",
    )
    model = os.getenv("EMBEDDING_MODEL", "doubao-embedding-vision-251215")

    if not api_key:
        return None

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    data = {
        "model": model,
        "instructions": "Target_modality: text.\nInstruction:Compress the text into a semantic vector for retrieval.\nQuery:",
        "input": [{"type": "text", "text": (text or "")[:2000]}],
        "dimensions": 1024,
        "encoding_format": "float",
    }
    try:
        resp = requests.post(base_url, headers=headers, json=data, timeout=30)
        payload = resp.json()
        emb = payload["data"]["embedding"]
        return np.array(emb, dtype=np.float32)
    except Exception:
        return None


def signal_vector_similarity(
    fused_description: str,
    top_n: int,
    min_similarity: float,
) -> List[Dict]:
    idx = load_index()
    query_vec = create_query_vector(fused_description)
    if query_vec is None:
        return []

    out = []
    for rec in idx["records"].values():
        vec = rec["vector"]
        denom = float(np.linalg.norm(query_vec) * np.linalg.norm(vec) + 1e-8)
        sim = float(np.dot(query_vec, vec) / denom)
        if sim < min_similarity:
            continue
        out.append(
            {
                "drawing_id": rec["drawing_id"],
                "similarity": sim,
                "vector_similarity": sim,
                "process_list": rec.get("process_list", []),
                "match_type": "vector",
                "matched": ["vector"],
            }
        )

    out.sort(key=lambda x: x["similarity"], reverse=True)
    return out[:top_n]


def signal_process(features: Dict, vector_ranking: List[Dict], limit: int = 20) -> List[Dict]:
    idx = load_index()
    process_terms = features.get("processes", [])[:6]
    if not process_terms:
        return []

    counts: Dict[str, int] = {}
    for p in process_terms:
        for rec in idx["by_process"].get(p, []):
            did = rec["drawing_id"]
            counts[did] = counts.get(did, 0) + 1

    vec_map = {r["drawing_id"]: r.get("similarity", 0.0) for r in vector_ranking}
    ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)

    out = []
    for did, count in ranked[:limit]:
        rec = idx["records"][did]
        out.append(
            {
                "drawing_id": did,
                "similarity": vec_map.get(did, 0.0),
                "vector_similarity": vec_map.get(did, 0.0),
                "process_list": rec.get("process_list", []),
                "match_type": f"process({count})",
                "matched": [f"process:{count}"],
            }
        )
    return out


def signal_tech_requirement(
    features: Dict,
    vector_ranking: List[Dict],
    limit: int = 20,
) -> List[Dict]:
    idx = load_index()
    tech_req = features.get("tech_requirement")
    if not tech_req:
        return []

    kws = extract_tech_keywords(tech_req)
    if not kws:
        return []

    counts: Dict[str, int] = {}
    for kw in kws:
        for rec in idx["by_tech"].get(kw, []):
            did = rec["drawing_id"]
            counts[did] = counts.get(did, 0) + 1

    vec_map = {r["drawing_id"]: r.get("similarity", 0.0) for r in vector_ranking}
    ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)

    out = []
    for did, count in ranked[:limit]:
        rec = idx["records"][did]
        out.append(
            {
                "drawing_id": did,
                "similarity": vec_map.get(did, 0.0),
                "vector_similarity": vec_map.get(did, 0.0),
                "process_list": rec.get("process_list", []),
                "match_type": f"tech_req({count})",
                "matched": [f"tech_req:{count}"],
            }
        )
    return out


def extract_prefix_from_text(fused_description: str) -> Optional[str]:
    patterns = [
        r"【图号】\s*([1-9][A-Z]\d{4,6})",
        r"(?:^|[^\w])([1-9][A-Z]\d{4,6})(?:[A-Z]|$|[^\w])",
    ]
    for p in patterns:
        found = re.findall(p, fused_description or "", re.IGNORECASE)
        if found:
            return found[0].upper()
    return None
