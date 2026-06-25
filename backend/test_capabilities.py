from pathlib import Path

from backend.services import capabilities


def test_yolo_remote_unreachable_local_onnx_works(monkeypatch, tmp_path):
    """Remote down but local ONNX model exists → available via onnx."""
    from backend.pipeline.yolo_service_client import YOLOServiceClient

    def mock_health_fail(self):
        raise ConnectionError("timeout")

    monkeypatch.setattr(YOLOServiceClient, "health", mock_health_fail)
    onnx = tmp_path / "best.onnx"
    onnx.write_bytes(b"model")
    monkeypatch.setattr(capabilities, "YOLO_ONNX_PATH", str(onnx))
    monkeypatch.setattr(capabilities, "YOLO_WEIGHT_PATH", str(tmp_path / "best.pt"))
    monkeypatch.setattr(capabilities, "_module_available", lambda name: name == "onnxruntime")

    result = capabilities.inspect_yolo_capability()
    assert result["available"] is True
    assert result["provider"] == "onnx"


def test_pdf_prefers_pymupdf(monkeypatch):
    monkeypatch.setattr(capabilities, "_module_available", lambda name: name == "fitz")
    monkeypatch.setattr(capabilities.shutil, "which", lambda name: f"/bin/{name}")
    assert capabilities.inspect_pdf_capability() == {
        "available": True,
        "provider": "pymupdf",
        "reason": "",
    }


def test_pdf_falls_back_to_poppler(monkeypatch):
    monkeypatch.setattr(capabilities, "_module_available", lambda name: False)
    monkeypatch.setattr(capabilities.shutil, "which", lambda name: f"/bin/{name}")
    assert capabilities.inspect_pdf_capability()["provider"] == "poppler"


def test_pdf_reports_actionable_failure(monkeypatch):
    monkeypatch.setattr(capabilities, "_module_available", lambda name: False)
    monkeypatch.setattr(capabilities.shutil, "which", lambda name: None)
    result = capabilities.inspect_pdf_capability()
    assert result["available"] is False
    assert "uv sync" in result["reason"]


def test_yolo_remote_health_ok(monkeypatch):
    """When GPU service health returns ok, inspect reports available."""
    from backend.pipeline.yolo_service_client import YOLOServiceClient
    import backend.config

    def mock_health(self):
        return {"ok": True, "models_loaded": 7, "gpu_available": True, "device": "cuda:0"}

    monkeypatch.setattr(YOLOServiceClient, "health", mock_health)
    monkeypatch.setattr(backend.config, "YOLO_SERVICE_TOKEN", "test-token")
    result = capabilities.inspect_yolo_capability()
    assert result["available"] is True
    assert result["provider"] == "gpu_service"
    assert result["models_loaded"] == 7


def test_yolo_remote_health_fail_falls_back(monkeypatch, tmp_path):
    """When GPU service is unreachable, falls back to local model check."""
    from backend.pipeline.yolo_service_client import YOLOServiceClient
    import backend.config

    def mock_health_fail(self):
        raise ConnectionError("timeout")

    monkeypatch.setattr(YOLOServiceClient, "health", mock_health_fail)
    monkeypatch.setattr(backend.config, "YOLO_SERVICE_TOKEN", "test-token")
    monkeypatch.setattr(capabilities, "YOLO_ONNX_PATH", str(tmp_path / "best.onnx"))
    monkeypatch.setattr(capabilities, "YOLO_WEIGHT_PATH", str(tmp_path / "best.pt"))

    result = capabilities.inspect_yolo_capability()
    # When no local models exist either, should be unavailable
    assert result["available"] is False
    assert "GPU 服务不可用" in result["reason"]


def test_yolo_remote_models_not_ready(monkeypatch):
    """When health returns but models_loaded < 7, report unavailable."""
    from backend.pipeline.yolo_service_client import YOLOServiceClient
    import backend.config

    def mock_health_partial(self):
        return {"ok": True, "models_loaded": 3, "gpu_available": True, "device": "cuda:0"}

    monkeypatch.setattr(YOLOServiceClient, "health", mock_health_partial)
    monkeypatch.setattr(backend.config, "YOLO_SERVICE_TOKEN", "test-token")
    monkeypatch.setattr(capabilities, "YOLO_ONNX_PATH", "/nonexistent")
    monkeypatch.setattr(capabilities, "YOLO_WEIGHT_PATH", "/nonexistent")

    result = capabilities.inspect_yolo_capability()
    assert result["available"] is False
    assert "模型未就绪" in result["reason"]


def test_creo_is_not_applicable_outside_windows(monkeypatch):
    monkeypatch.setattr(capabilities.sys, "platform", "darwin")
    result = capabilities.inspect_creo_capability()
    assert result["available"] is False
    assert result["applicable"] is False


def test_collect_capabilities_never_exposes_secret_values(monkeypatch):
    monkeypatch.setenv("VISION_API_KEY", "secret-value")
    result = capabilities.collect_capabilities()
    assert "secret-value" not in repr(result)
