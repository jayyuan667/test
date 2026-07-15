import os
import tempfile

import pytest
from werkzeug.security import generate_password_hash

from backend import auth_store, task_store
from backend.app import app


@pytest.fixture
def client(monkeypatch):
    auth_fd, auth_path = tempfile.mkstemp(suffix=".db")
    task_fd, task_path = tempfile.mkstemp(suffix=".db")
    os.close(auth_fd)
    os.close(task_fd)
    monkeypatch.setattr(auth_store, "DB_FILE", auth_path)
    monkeypatch.setattr(task_store, "DB_FILE", task_path)
    auth_store.init_auth_db()
    task_store.init_db()
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client
    os.unlink(auth_path)
    os.unlink(task_path)


def _enterprise_user(name):
    enterprise = auth_store.create_enterprise(name)
    auth_store.create_user(
        f"{name}-user",
        generate_password_hash("secret"),
        enterprise_id=enterprise["id"],
    )
    return enterprise


def _login(client, name):
    response = client.post(
        "/api/auth/login", json={"username": f"{name}-user", "password": "secret"}
    )
    assert response.status_code == 200


def test_snapshot_requires_login(client):
    assert client.get("/api/v1/tasks/missing").status_code == 401


def test_owned_task_returns_v1_snapshot(client):
    enterprise = _enterprise_user("owned")
    task_store.insert_task("task-owned", pdf_name="drawing.pdf", enterprise_id=enterprise["id"])
    _login(client, "owned")

    response = client.get("/api/v1/tasks/task-owned")

    assert response.status_code == 200
    assert response.get_json()["schema_version"] == "1.0"


def test_other_enterprise_task_is_hidden(client):
    owner = _enterprise_user("owner")
    _enterprise_user("outsider")
    task_store.insert_task("task-secret", pdf_name="secret.pdf", enterprise_id=owner["id"])
    _login(client, "outsider")

    assert client.get("/api/v1/tasks/task-secret").status_code == 404
