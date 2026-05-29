# -*- coding: utf-8 -*-
from typing import Dict, List, Tuple


def reciprocal_rank_fusion_by_signal(
    rankings: List[Tuple[str, List[Dict]]],
    signal_k: Dict[str, int],
) -> List[Dict]:
    """按信号名加权的RRF，避免依赖列表位置。"""
    merged: Dict[str, Dict] = {}

    for signal_name, ranking in rankings:
        if not ranking:
            continue
        k = signal_k.get(signal_name, 60)

        for rank, item in enumerate(ranking, 1):
            drawing_id = item["drawing_id"]
            score = 1.0 / (k + rank)

            if drawing_id not in merged:
                merged[drawing_id] = {
                    "drawing_id": drawing_id,
                    "rank_score": 0.0,
                    "vector_similarity": item.get("vector_similarity", item.get("similarity", 0.0)),
                    "process_list": item.get("process_list", []),
                    "matched": set(),
                    "match_types": [],
                }

            row = merged[drawing_id]
            row["rank_score"] += score

            if item.get("vector_similarity", 0.0) > row.get("vector_similarity", 0.0):
                row["vector_similarity"] = item.get("vector_similarity", 0.0)

            if item.get("process_list") and not row.get("process_list"):
                row["process_list"] = item.get("process_list", [])

            if item.get("matched"):
                for m in item["matched"]:
                    row["matched"].add(m)

            if item.get("match_type"):
                row["match_types"].append(item["match_type"])

    results = []
    for row in merged.values():
        match_types = list(dict.fromkeys(row.pop("match_types", [])))
        row["match_type"] = "+".join(match_types) if match_types else ""
        row["matched"] = sorted(list(row.get("matched", set())))
        row["similarity"] = row.get("vector_similarity", 0.0)
        results.append(row)

    results.sort(key=lambda x: x.get("rank_score", 0.0), reverse=True)
    return results
