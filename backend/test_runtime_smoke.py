from scripts import runtime_smoke


def test_smoke_returns_zero_when_blocking_checks_pass(monkeypatch):
    monkeypatch.setattr(runtime_smoke, "run_startup_checks", lambda: {"database": {"available": True}})
    monkeypatch.setattr(
        runtime_smoke,
        "collect_capabilities",
        lambda: {
            "ok": True,
            "pdf": {"available": True, "provider": "pymupdf", "reason": ""},
            "yolo": {"available": False, "provider": None, "reason": "missing model"},
            "creo": {"available": False, "applicable": False, "reason": ""},
            "freecad": {"available": False, "reason": ""},
            "vision_api": {"available": True, "provider": "doubao", "reason": ""},
        },
    )
    assert runtime_smoke.main() == 0
