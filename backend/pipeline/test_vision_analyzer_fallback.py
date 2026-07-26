from backend.pipeline.vision_analyzer import VisionAnalyzer


class DummyClient:
    class chat:
        class completions:
            @staticmethod
            def create(*args, **kwargs):
                raise RuntimeError("remote down")


def _make_analyzer():
    analyzer = VisionAnalyzer.__new__(VisionAnalyzer)
    analyzer.client = DummyClient()
    analyzer.model = "demo-model"
    analyzer.max_tokens = 32
    analyzer._local_analyzer = None
    return analyzer


def test_analyze_image_falls_back_to_local(monkeypatch, tmp_path):
    img = tmp_path / "demo.png"
    img.write_bytes(b"fake-png-bytes")
    analyzer = _make_analyzer()

    monkeypatch.setenv("VISION_SHARPEN", "0")
    monkeypatch.setattr(analyzer, "_should_fallback_locally", lambda exc: True)
    monkeypatch.setattr(analyzer, "_fallback_to_local", lambda paths, reason, annotation_text="": {
        "image_path": paths[0],
        "description": "local result",
        "ok": True,
        "fallback_used": "local",
        "fallback_reason": reason,
    })

    result = analyzer.analyze_image(str(img))

    assert result["ok"] is True
    assert result["description"] == "local result"
    assert result["fallback_used"] == "local"


def test_analyze_drawing_falls_back_to_local(monkeypatch, tmp_path):
    img = tmp_path / "demo.png"
    img.write_bytes(b"fake-png-bytes")
    analyzer = _make_analyzer()

    monkeypatch.setattr(analyzer, "_call_vlm_batch", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("remote down")))
    monkeypatch.setattr(analyzer, "_should_fallback_locally", lambda exc: True)
    monkeypatch.setattr(analyzer, "_fallback_to_local", lambda paths, reason, annotation_text="": {
        "image_path": paths[0],
        "description": "local drawing result",
        "ok": True,
        "fallback_used": "local",
        "fallback_reason": reason,
    })

    result = analyzer.analyze_drawing([str(img)], annotation_text="note")

    assert result["ok"] is True
    assert result["description"] == "local drawing result"
    assert result["fallback_used"] == "local"
