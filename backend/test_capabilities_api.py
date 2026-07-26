def test_capabilities_endpoint_returns_structured_status(monkeypatch):
    from backend.services import capabilities as cap_mod
    from backend.app import app

    monkeypatch.setattr(
        cap_mod,
        "collect_capabilities",
        lambda: {"ok": True, "pdf": {"available": False, "reason": "missing"}},
    )
    response = app.test_client().get("/api/system/capabilities")
    assert response.status_code == 200
    assert response.get_json()["pdf"]["available"] is False
