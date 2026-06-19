from backend.pipeline import yolo_detector


def test_detector_prefers_onnx(monkeypatch):
    calls = []
    monkeypatch.setattr(
        yolo_detector.YOLODetector,
        "_load_onnx",
        lambda self, path: calls.append(("onnx", path)) or True,
    )
    monkeypatch.setattr(
        yolo_detector.YOLODetector,
        "_load_ultralytics",
        lambda self, path: calls.append(("pt", path)) or True,
    )
    detector = yolo_detector.YOLODetector(pt_path="best.pt", onnx_path="best.onnx")
    assert calls == [("onnx", "best.onnx")]
    assert detector is not None


def test_detector_falls_back_to_pt(monkeypatch):
    calls = []
    monkeypatch.setattr(
        yolo_detector.YOLODetector,
        "_load_onnx",
        lambda self, path: calls.append(("onnx", path)) or False,
    )
    monkeypatch.setattr(
        yolo_detector.YOLODetector,
        "_load_ultralytics",
        lambda self, path: calls.append(("pt", path)) or True,
    )
    yolo_detector.YOLODetector(pt_path="best.pt", onnx_path="best.onnx")
    assert calls == [("onnx", "best.onnx"), ("pt", "best.pt")]
