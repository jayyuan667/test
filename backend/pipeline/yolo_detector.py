"""
YOLO 检测器 — ONNX 优先，ultralytics (.pt) 兜底。
"""

import logging
import os
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

from backend.config import (
    YOLO_CONF,
    YOLO_DEVICE,
    YOLO_IMG_SIZE,
    YOLO_IOU,
    YOLO_ONNX_PATH,
    YOLO_WEIGHT_PATH,
)

logger = logging.getLogger(__name__)

# ---------- ultralytics 类型（延迟导入） ----------
_ultralytics = None  # type: ignore[assignment]


def _try_import_ultralytics():
    global _ultralytics
    if _ultralytics is not None:
        return True
    try:
        import ultralytics as ul
        _ultralytics = ul
        return True
    except ImportError:
        return False


# ---------- ONNX helper（兜底用） ----------

def _letterbox(
    img: np.ndarray,
    new_shape: Tuple[int, int] = (640, 640),
    color: Tuple[int, int, int] = (114, 114, 114),
) -> Tuple[np.ndarray, float, Tuple[int, int]]:
    h, w = img.shape[:2]
    r = min(new_shape[0] / h, new_shape[1] / w)
    new_unpad = int(round(w * r)), int(round(h * r))
    dw = (new_shape[1] - new_unpad[0]) / 2
    dh = (new_shape[0] - new_unpad[1]) / 2
    if (w, h) != new_unpad:
        img = cv2.resize(img, new_unpad, interpolation=cv2.INTER_LINEAR)
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    img = cv2.copyMakeBorder(img, top, bottom, left, right,
                             cv2.BORDER_CONSTANT, value=color)
    return img, r, (int(round(dw)), int(round(dh)))


def _xywh2xyxy(x: np.ndarray) -> np.ndarray:
    y = np.empty_like(x)
    y[:, 0] = x[:, 0] - x[:, 2] / 2
    y[:, 1] = x[:, 1] - x[:, 3] / 2
    y[:, 2] = x[:, 0] + x[:, 2] / 2
    y[:, 3] = x[:, 1] + x[:, 3] / 2
    return y


def _nms(boxes: np.ndarray, scores: np.ndarray, iou_thres: float) -> List[int]:
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]
    keep: List[int] = []
    while order.size > 0:
        i = order[0]
        keep.append(int(i))
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        inter = np.maximum(0.0, xx2 - xx1) * np.maximum(0.0, yy2 - yy1)
        iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-7)
        inds = np.where(iou <= iou_thres)[0]
        order = order[inds + 1]
    return keep


# ---------- 检测结果数据类 ----------

class YOLODetection:
    """单条检测结果"""
    __slots__ = ("x1", "y1", "x2", "y2", "confidence", "class_id")

    def __init__(self, x1: float, y1: float, x2: float, y2: float,
                 confidence: float, class_id: int):
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
        self.confidence = confidence
        self.class_id = class_id

    def to_dict(self) -> dict:
        return {
            "x1": self.x1, "y1": self.y1,
            "x2": self.x2, "y2": self.y2,
            "confidence": self.confidence,
            "class_id": self.class_id,
        }


# ---------- 检测器主类 ----------

class YOLODetector:
    """YOLO 检测器：ONNX 优先，ultralytics (.pt) 兜底。"""

    def __init__(self, pt_path: Optional[str] = None,
                 onnx_path: Optional[str] = None,
                 conf: float = YOLO_CONF,
                 iou: float = YOLO_IOU,
                 img_size: int = YOLO_IMG_SIZE,
                 device: str = YOLO_DEVICE,
                 class_names: Optional[dict] = None):
        self.conf = conf
        self.iou = iou
        self.img_size = img_size
        self.device = device
        self.class_names = class_names or {0: "threaded_hole", 1: "circle_hole"}

        self._backend: Optional[str] = None  # "ultralytics" | "onnx" | None
        self._ul_model = None   # ultralytics YOLO model
        self._ort_session = None  # onnxruntime InferenceSession

        # 优先 ONNX
        if onnx_path and self._load_onnx(onnx_path):
            return

        if pt_path and self._load_ultralytics(pt_path):
            return

        logger.warning("YOLO不可用：ONNX和ultralytics/PT均加载失败")

    # ---- ultralytics 加载 ----

    def _load_ultralytics(self, pt_path: str) -> bool:
        if not _try_import_ultralytics():
            logger.info("ultralytics 未安装，跳过 .pt 加载")
            return False
        if not os.path.isfile(pt_path):
            logger.info("pt 权重不存在: %s，跳过", pt_path)
            return False
        try:
            from ultralytics import YOLO
            self._ul_model = YOLO(pt_path)
            # 强制 CPU 推理一次以确认可用
            self._ul_model.predict(
                np.zeros((640, 640, 3), dtype=np.uint8),
                conf=self.conf, iou=self.iou,
                imgsz=self.img_size, device=self.device,
                verbose=False,
            )
            self._backend = "ultralytics"
            logger.info("YOLO 后端: ultralytics (%s)", pt_path)
            return True
        except Exception as exc:
            logger.warning("ultralytics 加载失败 (%s): %s", pt_path, exc)
            self._ul_model = None
            return False

    # ---- ONNX 加载 ----

    def _load_onnx(self, onnx_path: str) -> bool:
        try:
            import onnxruntime as ort
        except ImportError:
            logger.info("onnxruntime 未安装，跳过 ONNX 加载")
            return False
        if not os.path.isfile(onnx_path):
            logger.info("ONNX 模型不存在: %s，跳过", onnx_path)
            return False
        try:
            self._ort_session = ort.InferenceSession(
                onnx_path, providers=["CPUExecutionProvider"]
            )
            self._backend = "onnx"
            logger.info("YOLO 后端: ONNX (%s)", onnx_path)
            return True
        except Exception as exc:
            logger.warning("ONNX 加载失败 (%s): %s", onnx_path, exc)
            self._ort_session = None
            return False

    # ---- 公开接口 ----

    @property
    def available(self) -> bool:
        return self._backend is not None

    @property
    def backend_name(self) -> Optional[str]:
        return self._backend

    def detect(self, image: np.ndarray) -> List[YOLODetection]:
        if not self.available:
            return []
        if self._backend == "ultralytics":
            return self._detect_ul(image)
        return self._detect_onnx(image)

    # ---- ultralytics 推理 ----

    def _detect_ul(self, image: np.ndarray) -> List[YOLODetection]:
        try:
            results = self._ul_model.predict(
                image, conf=self.conf, iou=self.iou,
                imgsz=self.img_size, device=self.device,
                verbose=False,
            )
        except Exception as exc:
            logger.warning("ultralytics 推理失败: %s", exc)
            return []
        detections: List[YOLODetection] = []
        for r in results:
            if r.boxes is None:
                continue
            for box in r.boxes:
                xyxy = box.xyxy[0].cpu().numpy()
                conf_val = float(box.conf[0])
                cls_id = int(box.cls[0])
                detections.append(YOLODetection(
                    float(xyxy[0]), float(xyxy[1]),
                    float(xyxy[2]), float(xyxy[3]),
                    conf_val, cls_id,
                ))
        return detections

    # ---- ONNX 推理 ----

    def _detect_onnx(self, image: np.ndarray) -> List[YOLODetection]:
        import onnxruntime as ort  # noqa: F811

        img, ratio, (dw, dh) = _letterbox(image, (self.img_size, self.img_size))
        blob = img[:, :, ::-1].transpose(2, 0, 1).astype(np.float32) / 255.0
        blob = np.expand_dims(blob, axis=0)
        if blob.dtype != np.float32:
            blob = blob.astype(np.float32)

        inp_name = self._ort_session.get_inputs()[0].name
        try:
            outs = self._ort_session.run(None, {inp_name: blob})
        except Exception as exc:
            logger.warning("ONNX 推理失败: %s", exc)
            return []

        preds = outs[0]
        if preds.ndim == 3:
            preds = preds[0]
        num_classes = preds.shape[1] - 4
        if num_classes <= 0:
            logger.warning("ONNX 输出格式异常: shape=%s", preds.shape)
            return []

        boxes_xywh = preds[:, :4].T
        class_scores = preds[:, 4:]
        max_scores = class_scores.max(axis=1)
        max_ids = class_scores.argmax(axis=1)

        mask = max_scores >= self.conf
        if not mask.any():
            return []

        boxes_xywh = boxes_xywh[:, mask].T
        scores = max_scores[mask]
        cls_ids = max_ids[mask]

        boxes_xyxy = _xywh2xyxy(boxes_xywh)
        keep = _nms(boxes_xyxy, scores, self.iou)
        if not keep:
            return []

        boxes_xyxy = boxes_xyxy[keep]
        scores = scores[keep]
        cls_ids = cls_ids[keep]

        boxes_xyxy[:, [0, 2]] = (boxes_xyxy[:, [0, 2]] - dw) / ratio
        boxes_xyxy[:, [1, 3]] = (boxes_xyxy[:, [1, 3]] - dh) / ratio

        detections: List[YOLODetection] = []
        for i in range(len(keep)):
            detections.append(YOLODetection(
                float(boxes_xyxy[i, 0]), float(boxes_xyxy[i, 1]),
                float(boxes_xyxy[i, 2]), float(boxes_xyxy[i, 3]),
                float(scores[i]), int(cls_ids[i]),
            ))
        return detections


# ---------- 单例 ----------

_detector_instance: Optional[YOLODetector] = None


def get_yolo_detector() -> YOLODetector:
    """返回全局 YOLODetector 单例。"""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = YOLODetector(
            pt_path=YOLO_WEIGHT_PATH,
            onnx_path=YOLO_ONNX_PATH,
            conf=YOLO_CONF,
            iou=YOLO_IOU,
            img_size=YOLO_IMG_SIZE,
            device=YOLO_DEVICE,
        )
    return _detector_instance


def reset_yolo_detector() -> None:
    """重置单例，用于测试。"""
    global _detector_instance
    _detector_instance = None
