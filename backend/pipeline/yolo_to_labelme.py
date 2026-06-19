# -*- coding: utf-8 -*-
"""Convert YOLO detection results to labelme 0.4.36 JSON.

Output format is identical to manual annotation tool, so the frontend
loads YOLO pre-labels via the same `_loadFromServer()` path with zero changes.
"""

import json
import os
from typing import List, Dict, Any

from PIL import Image


def write_labelme(image_path: str, detections: List[Dict[str, Any]], out_path: str) -> None:
    """Write a labelme JSON for one image.

    Args:
        image_path: Source PNG path (used for size + imagePath field).
        detections: From YOLODetector.detect() — may be empty.
        out_path:   Destination JSON path.
    """
    with Image.open(image_path) as img:
        w, h = img.size

    shapes = [
        {
            "label":      d["cls_name"],
            "text":       f"auto:{d['conf']:.2f}",  # source tag + confidence (JSON only)
            "points":     [[d["x1"], d["y1"]], [d["x2"], d["y2"]]],
            "group_id":   None,
            "shape_type": "rectangle",
            "flags":      {},
        }
        for d in detections
    ]

    labelme = {
        "version":     "0.4.36",
        "flags":       {},
        "shapes":      shapes,
        "imagePath":   os.path.basename(image_path),
        "imageData":   None,
        "imageHeight": h,
        "imageWidth":  w,
        "text":        "",
    }

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(labelme, f, ensure_ascii=False, indent=2)
