# -*- coding: utf-8 -*-
from typing import List, Dict, TypedDict, Any


class MatchItem(TypedDict, total=False):
    drawing_id: str
    similarity: float
    vector_similarity: float
    rank_score: float
    match_type: str
    matched: List[str]
    process_list: List[str]


class RagResult(TypedDict, total=False):
    matches: List[MatchItem]
    rag_context: str
    top_similarity: float
    key_features: Dict[str, str]
    tech_requirement: str
    meta: Dict[str, Any]
