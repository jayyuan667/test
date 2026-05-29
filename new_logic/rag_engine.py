# -*- coding: utf-8 -*-
from typing import Dict, List, Tuple

from .rag_ranker import reciprocal_rank_fusion_by_signal
from .rag_signals import (
    extract_all_features,
    extract_prefix_from_text,
    load_index,
    query_by_prefix as prefix_exact_query,
    signal_process,
    signal_tech_requirement,
    signal_vector_similarity,
)


def query_by_prefix(prefix: str, top_k: int = 1) -> Dict:
    return prefix_exact_query(prefix, top_k=top_k)


def _build_rag_context(matches: List[Dict]) -> str:
    lines = [f"## 参考工艺候选 ({len(matches)}个)", ""]
    for i, m in enumerate(matches[:3], 1):
        plist = m.get("process_list", [])
        lines.append(
            f"--- 候选{i}: {m.get('drawing_id')} ({m.get('match_type', '')}) - 共{len(plist)}道工序 ---"
        )
        for row in plist:
            row = str(row)
            parts = row.split("@")
            if len(parts) >= 2:
                tag = parts[0].strip()
                content = parts[3].strip() if len(parts) > 3 else parts[-1].strip()
                lines.append(f"{tag}: {content}")
            else:
                lines.append(f"- {row}")
        lines.append("")
    return "\n".join(lines)


def query_by_fused_text(
    fused_description: str,
    top_k: int = 3,
    min_similarity: float = 0.3,
    prefix_hint: str = None,
) -> Dict:
    idx = load_index()
    if not idx.get("records"):
        return {
            "matches": [],
            "rag_context": "",
            "top_similarity": 0.0,
            "key_features": {},
            "tech_requirement": None,
        }

    extracted_prefix = (prefix_hint or "").strip().upper() or extract_prefix_from_text(
        fused_description
    )

    features = extract_all_features(fused_description)

    expanded_top_n = max(top_k * 10, 30)
    vector_ranking = signal_vector_similarity(
        fused_description,
        top_n=expanded_top_n,
        min_similarity=min_similarity,
    )
    process_ranking = signal_process(features, vector_ranking, limit=20)
    tech_ranking = signal_tech_requirement(features, vector_ranking, limit=20)

    prefix_ranking = []
    if extracted_prefix:
        prefix_result = prefix_exact_query(extracted_prefix, top_k=1)
        if prefix_result and prefix_result.get("matches"):
            m = prefix_result["matches"][0]
            vec_map = {v["drawing_id"]: v.get("similarity", 0.0) for v in vector_ranking}
            similarity = vec_map.get(m["drawing_id"], 1.0)
            prefix_ranking = [
                {
                    "drawing_id": m["drawing_id"],
                    "similarity": similarity,
                    "vector_similarity": similarity,
                    "process_list": m.get("process_list", []),
                    "match_type": "prefix_exact",
                    "matched": ["prefix"],
                }
            ]

    rankings: List[Tuple[str, List[Dict]]] = []
    if prefix_ranking:
        rankings.append(("prefix", prefix_ranking))
    if vector_ranking:
        rankings.append(("vector", vector_ranking))
    if tech_ranking:
        rankings.append(("tech_req", tech_ranking))
    if process_ranking:
        rankings.append(("process", process_ranking))

    if not rankings:
        first = next(iter(idx["records"].values()))
        matches = [
            {
                "drawing_id": first["drawing_id"],
                "similarity": 0.1,
                "vector_similarity": 0.1,
                "rank_score": 0.0,
                "match_type": "fallback",
                "matched": ["fallback"],
                "process_list": first.get("process_list", []),
            }
        ]
    else:
        fused = reciprocal_rank_fusion_by_signal(
            rankings,
            signal_k={
                "vector": 20,
                "prefix": 50,
                "tech_req": 55,
                "process": 60,
            },
        )
        matches = fused[:top_k]

        if prefix_ranking:
            prefix_id = prefix_ranking[0]["drawing_id"]
            in_top = any(m["drawing_id"] == prefix_id for m in matches)
            if not in_top:
                matches.insert(0, prefix_ranking[0])
                matches = matches[:top_k]
            for m in matches:
                if m["drawing_id"] == prefix_id and "prefix" not in m.get("matched", []):
                    m["matched"] = m.get("matched", []) + ["prefix"]
                    m["match_type"] = (
                        (m.get("match_type", "") + "+prefix_exact").strip("+")
                    )

    rag_context = _build_rag_context(matches)
    top_similarity = matches[0].get("similarity", 0.0) if matches else 0.0

    return {
        "matches": matches,
        "rag_context": rag_context,
        "top_similarity": top_similarity,
        "key_features": features.get("key_features", {}),
        "tech_requirement": features.get("tech_requirement"),
        "meta": {
            "prefix_hint": extracted_prefix,
            "vector_candidates": len(vector_ranking),
        },
    }
