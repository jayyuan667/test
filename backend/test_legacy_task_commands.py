from flask import Response, jsonify

from backend.app import app


def test_adapter_invokes_unwrapped_handler_once():
    from backend.services.legacy_task_commands import invoke_request_handler

    calls = {"wrapper": 0, "handler": 0}

    def handler():
        calls["handler"] += 1
        return jsonify({"ok": True})

    def login_wrapper():
        calls["wrapper"] += 1
        return handler()

    login_wrapper.__wrapped__ = handler
    with app.test_request_context("/"):
        result = invoke_request_handler(login_wrapper)

    assert result.status_code == 200
    assert calls == {"wrapper": 0, "handler": 1}


def test_adapter_normalizes_response_two_and_three_tuples():
    from backend.services.legacy_task_commands import invoke_request_handler

    cases = [
        (lambda: Response("response", status=201), 201, "response", None),
        (lambda: ({"kind": "two"}, 202), 202, '{"kind":"two"}\n', None),
        (lambda: ({"kind": "three"}, 203, {"X-Seam": "yes"}), 203, '{"kind":"three"}\n', "yes"),
    ]
    with app.test_request_context("/"):
        for handler, status, body, header in cases:
            result = invoke_request_handler(handler, unwrap_login=False)
            assert result.status_code == status
            assert result.response.get_data(as_text=True) == body
            assert result.response.headers.get("X-Seam") == header
