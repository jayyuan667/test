# -*- coding: utf-8 -*-
"""Shared helpers for vision-analysis result handling."""

from typing import Dict, Any, List, Tuple


def split_vision_results(results: List[Dict[str, Any]] | None) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Split raw vision results into successful descriptions and failure records."""
    successful: List[Dict[str, Any]] = []
    failures: List[Dict[str, Any]] = []

    for index, item in enumerate(results or [], start=1):
        page_number = int(item.get("page") or item.get("_page_number") or index)
        description = (item.get("description") or "").strip()
        error = (item.get("error") or "").strip()

        if error or not description:
            failure: Dict[str, Any] = {
                "page": page_number,
                "image_path": item.get("image_path", ""),
                "message": error or "视觉模型未返回任何内容",
            }
            if item.get("file"):
                failure["file"] = item.get("file")
            failures.append(failure)
            continue

        successful_item = dict(item)
        successful_item["_page_number"] = page_number
        successful.append(successful_item)

    return successful, failures


def format_vision_failure_message(
    failures: List[Dict[str, Any]] | None,
    prefix: str = "视觉分析失败",
    max_items: int = 3,
) -> str:
    """Build a compact human-readable error summary for failed pages."""
    items = failures or []
    if not items:
        return prefix

    details = []
    for failure in items[:max_items]:
        location_parts = []
        if failure.get("file"):
            location_parts.append(f"文件《{failure['file']}》")
        if failure.get("page"):
            location_parts.append(f"第{failure['page']}页")
        location = " ".join(location_parts) or "未知位置"
        details.append(f"{location}：{failure.get('message') or '视觉分析失败'}")

    if len(items) > max_items:
        details.append(f"其余 {len(items) - max_items} 处请查看日志")

    return f"{prefix}：{'；'.join(details)}"
