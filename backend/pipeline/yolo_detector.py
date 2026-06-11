# -*- coding: utf-8 -*-
"""YOLO 工艺特征检测器 — 单例懒加载。"""

import logging
import threading
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

ID_TO_LABEL = {0: "threaded_hole", 1: "circle_hole", 2: "chamfer"}


class YOLODetector:
    """Lazy-loaded singleton wrapping ultralytics YOLO inference.

    The model weights (~50–200MB) are loaded once on first .get() and reused
    for all subsequent tasks within the process.
    """

    _instance: "YOLODetector | None" = None
    _lock = threading.Lock()

    def __init__(self, weight_path: str, conf: float, iou: float,
                 imgsz: int, device: str):
        from ultralytics import YOLO  # local import: avoid forcing dep at module load
        logger.info("[YOLO] loading %s (device=%s)", weight_path, device)
        self._model = YOLO(weight_path)
        self._conf = conf
        self._iou = iou
        self._imgsz = imgsz
        self._device = device

    @classmethod
    def get(cls) -> "YOLODetector":
        if cls._instance is not None:
            return cls._instance
        with cls._lock:
            if cls._instance is None:
                try:
                    from ..config import (
                        YOLO_WEIGHT_PATH, YOLO_CONF, YOLO_IOU,
                        YOLO_IMG_SIZE, YOLO_DEVICE,
                    )
                except ImportError:
                    from backend.config import (
                        YOLO_WEIGHT_PATH, YOLO_CONF, YOLO_IOU,
                        YOLO_IMG_SIZE, YOLO_DEVICE,
                    )
                cls._instance = cls(
                    weight_path=YOLO_WEIGHT_PATH,
                    conf=YOLO_CONF, iou=YOLO_IOU,
                    imgsz=YOLO_IMG_SIZE, device=YOLO_DEVICE,
                )
        return cls._instance

    def detect(self, image_path: str) -> List[Dict[str, Any]]:
        """Run inference on one image, return list of detections.

        Each detection: {cls_id, cls_name, conf, x1, y1, x2, y2} (pixel ints).
        """
        results = self._model.predict(
            image_path,
            conf=self._conf, iou=self._iou,
            imgsz=self._imgsz, device=self._device,
            verbose=False,
        )
        out: List[Dict[str, Any]] = []
        for r in results:
            boxes = getattr(r, "boxes", None)
            if boxes is None:
                continue
            for box in boxes:
                cls_id = int(box.cls)
                xyxy = box.xyxy[0].tolist()
                out.append({
                    "cls_id":   cls_id,
                    "cls_name": ID_TO_LABEL.get(cls_id, f"cls_{cls_id}"),
                    "conf":     float(box.conf),
                    "x1": int(xyxy[0]), "y1": int(xyxy[1]),
                    "x2": int(xyxy[2]), "y2": int(xyxy[3]),
                })
        return out
