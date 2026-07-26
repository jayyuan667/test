import importlib
import sys
import sqlite3

import pytest


class DummyResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class DummySession:
    instances = []

    def __init__(self):
        self.trust_env = True
        self.post_calls = []
        DummySession.instances.append(self)

    def post(self, url, headers=None, json=None, timeout=None):
        self.post_calls.append(
            {
                "url": url,
                "headers": headers or {},
                "json": json or {},
                "timeout": timeout,
            }
        )
        return DummyResponse({"data": {"embedding": [0.1, 0.2, 0.3]}})


class DummyCursor:
    def __init__(self, rows):
        self._rows = rows
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchall(self):
        return self._rows


class DummyConnection:
    def __init__(self, rows):
        self._cursor = DummyCursor(rows)
        self.closed = False

    def cursor(self):
        return self._cursor

    def close(self):
        self.closed = True


def _load_module(monkeypatch, embedding_trust_env=None):
    DummySession.instances.clear()
    monkeypatch.setattr("requests.Session", DummySession)
    if embedding_trust_env is None:
        monkeypatch.delenv("EMBEDDING_TRUST_ENV", raising=False)
    else:
        monkeypatch.setenv("EMBEDDING_TRUST_ENV", embedding_trust_env)
    monkeypatch.setenv("EMBEDDING_API_KEY", "test-key")
    monkeypatch.setenv("EMBEDDING_BASE_URL", "https://example.com/v1/embeddings")
    monkeypatch.setenv("EMBEDDING_MODEL", "demo-embedding-model")
    sys.modules.pop("backend.vector_map_rag", None)
    return importlib.import_module("backend.vector_map_rag")


def test_embedding_session_defaults_to_env(monkeypatch):
    module = _load_module(monkeypatch)

    session = module._embedding_session()

    assert session.trust_env is True


def test_embedding_session_can_disable_env(monkeypatch):
    module = _load_module(monkeypatch, "0")

    session = module._embedding_session()

    assert session.trust_env is False


def test_create_query_vector_uses_embedding_session(monkeypatch):
    module = _load_module(monkeypatch, "0")

    vector = module.create_query_vector("hello world")

    assert vector.tolist() == pytest.approx([0.1, 0.2, 0.3])
    assert len(DummySession.instances) == 1
    call = DummySession.instances[0].post_calls[0]
    assert call["url"] == "https://example.com/v1/embeddings"
    assert call["timeout"] == 60
    assert DummySession.instances[0].trust_env is False


def test_query_by_vector_similarity_uses_embedding_session(monkeypatch):
    module = _load_module(monkeypatch, "0")

    dummy_rows = [
        (
            "Y1",
            (module.np.array([0.1, 0.2, 0.3], dtype=module.np.float32)).tobytes(),
            '["step1"]',
            "ctx",
        )
    ]
    dummy_conn = DummyConnection(dummy_rows)

    monkeypatch.setattr(module.sqlite3, "connect", lambda *args, **kwargs: dummy_conn)

    results = module.query_by_vector_similarity("hello world", top_k=5, min_similarity=0.0)

    assert results and results[0]["drawing_id"] == "Y1"
    assert len(DummySession.instances) == 1
    call = DummySession.instances[0].post_calls[0]
    assert call["url"] == "https://example.com/v1/embeddings"
    assert call["timeout"] == 60
    assert DummySession.instances[0].trust_env is False
