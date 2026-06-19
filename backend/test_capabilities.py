from pathlib import Path

from backend.services import capabilities


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


def test_yolo_prefers_onnx_without_importing_ultralytics(monkeypatch, tmp_path):
    onnx = tmp_path / "best.onnx"
    onnx.write_bytes(b"model")
    monkeypatch.setattr(capabilities, "YOLO_ONNX_PATH", str(onnx))
    monkeypatch.setattr(capabilities, "YOLO_WEIGHT_PATH", str(tmp_path / "best.pt"))
    monkeypatch.setattr(
        capabilities,
        "_module_available",
        lambda name: name == "onnxruntime",
    )
    result = capabilities.inspect_yolo_capability()
    assert result["available"] is True
    assert result["provider"] == "onnx"


def test_yolo_missing_models_is_non_blocking(monkeypatch, tmp_path):
    monkeypatch.setattr(capabilities, "YOLO_ONNX_PATH", str(tmp_path / "best.onnx"))
    monkeypatch.setattr(capabilities, "YOLO_WEIGHT_PATH", str(tmp_path / "best.pt"))
    result = capabilities.inspect_yolo_capability()
    assert result["available"] is False
    assert "模型文件不存在" in result["reason"]


def test_creo_is_not_applicable_outside_windows(monkeypatch):
    monkeypatch.setattr(capabilities.sys, "platform", "darwin")
    result = capabilities.inspect_creo_capability()
    assert result["available"] is False
    assert result["applicable"] is False


def test_collect_capabilities_never_exposes_secret_values(monkeypatch):
    monkeypatch.setenv("VISION_API_KEY", "secret-value")
    result = capabilities.collect_capabilities()
    assert "secret-value" not in repr(result)
