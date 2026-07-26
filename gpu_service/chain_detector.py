"""BinaryChainDetector — 7 模型链式推理 + 全局锁。

Detection order (empirically optimal):
  code_hole → threaded_hole → chamfer → through_hole →
  counterbore → countersink → blind_hole

After each class is detected, regions are blacked out before the next model.
"""
import threading
import numpy as np

CLASS_ORDER = [
    "code_hole",       # high-frequency first — block out early
    "threaded_hole",
    "chamfer",
    "through_hole",
    "counterbore",
    "countersink",
    "blind_hole",      # rarest last, highest confidence threshold
]

CLASS_CONF = {
    "code_hole": 0.15, "threaded_hole": 0.20, "chamfer": 0.15,
    "through_hole": 0.20, "counterbore": 0.20, "countersink": 0.20,
    "blind_hole": 0.35,
}


class BinaryChainDetector:
    """Loads 7 binary YOLO models, provides thread-safe chain detection."""

    def __init__(self, model_dir: str, device: str = "cuda:0"):
        from ultralytics import YOLO

        self.device = device
        self._lock = threading.Lock()
        self.models: dict[str, "YOLO"] = {}

        for name in CLASS_ORDER:
            path = f"{model_dir}/binary_{name}.pt"
            model = YOLO(path)
            model.to(device)
            self.models[name] = model

    def detect(self, image: np.ndarray) -> list[dict]:
        """Run full chain on a single image. Thread-safe via internal lock.

        Returns list of detections, each:
          {"class": str, "conf": float, "x1": float, "y1": float,
           "x2": float, "y2": float}
        """
        with self._lock:
            img = image.copy()
            all_dets: list[dict] = []

            for cls_name in CLASS_ORDER:
                results = self.models[cls_name](
                    img, conf=CLASS_CONF[cls_name], verbose=False
                )
                boxes: list[tuple[float, float, float, float]] = []

                if results[0].boxes is not None:
                    for b in results[0].boxes:
                        x1, y1, x2, y2 = b.xyxy[0].cpu().tolist()
                        boxes.append((x1, y1, x2, y2))
                        all_dets.append({
                            "class": cls_name,
                            "conf": round(float(b.conf[0]), 4),
                            "x1": round(x1, 1), "y1": round(y1, 1),
                            "x2": round(x2, 1), "y2": round(y2, 1),
                        })

                # Blackout detected regions for next model
                for (x1, y1, x2, y2) in boxes:
                    y1i, y2i = max(0, int(y1)), max(0, int(y2))
                    x1i, x2i = max(0, int(x1)), max(0, int(x2))
                    if y2i > y1i and x2i > x1i:
                        img[y1i:y2i, x1i:x2i] = 0

            return all_dets
