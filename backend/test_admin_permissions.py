import os
import tempfile

import pytest
from werkzeug.security import generate_password_hash

from backend import auth_store
from backend.app import app


@pytest.fixture(autouse=True)
def setup_db(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db", prefix="test_admin_permissions_")
    os.close(fd)
    monkeypatch.setattr(auth_store, "DB_FILE", path)
    auth_store.init_auth_db()
    yield
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture
def make_enterprise():
    def _make_enterprise(name: str):
        return auth_store.create_enterprise(name)

    return _make_enterprise


@pytest.fixture
def make_user():
    def _make_user(username: str, *, role: str = "user", enterprise_id=None, password: str = "test123"):
        return auth_store.create_user(
            username,
            generate_password_hash(password),
            role=role,
            enterprise_id=enterprise_id,
        )

    return _make_user


@pytest.fixture
def login_as(client):
    def _login_as(user: dict, password: str = "test123"):
        response = client.post(
            "/api/auth/login",
            json={"username": user["username"], "password": password},
        )
        assert response.status_code == 200

    return _login_as


def test_enterprise_admin_can_list_unassigned_users(client, login_as, make_enterprise, make_user):
    ent = make_enterprise("Acme")
    admin = make_user("acme_admin", role="enterprise_admin", enterprise_id=ent["id"])
    unassigned = make_user("new_user", role="user", enterprise_id=None)
    make_user("other_admin", role="enterprise_admin", enterprise_id=None)

    login_as(admin)
    response = client.get("/api/admin/users?scope=unassigned")

    assert response.status_code == 200
    usernames = [u["username"] for u in response.get_json()["data"]["users"]]
    assert usernames == [unassigned["username"]]


def test_enterprise_admin_can_claim_only_unassigned_user(client, login_as, make_enterprise, make_user):
    ent = make_enterprise("Acme")
    other = make_enterprise("Other")
    admin = make_user("acme_admin", role="enterprise_admin", enterprise_id=ent["id"])
    target = make_user("new_user", role="user", enterprise_id=None)
    other_user = make_user("other_user", role="user", enterprise_id=other["id"])

    login_as(admin)
    ok_response = client.put(
        f"/api/admin/users/{target['id']}",
        json={"enterprise_id": ent["id"]},
    )
    forbidden_response = client.put(
        f"/api/admin/users/{other_user['id']}",
        json={"enterprise_id": ent["id"]},
    )

    assert ok_response.status_code == 200
    assert ok_response.get_json()["data"]["user"]["enterprise_id"] == ent["id"]
    assert forbidden_response.status_code == 403


def test_enterprise_admin_without_enterprise_cannot_claim_unassigned_user(client, login_as, make_user):
    admin = make_user("no_enterprise_admin", role="enterprise_admin", enterprise_id=None)
    target = make_user("unassigned_user", role="user", enterprise_id=None)

    login_as(admin)
    response = client.put(
        f"/api/admin/users/{target['id']}",
        json={"enterprise_id": None},
    )

    assert response.status_code == 403


def test_config_requires_login(client):
    response = client.get("/api/config")

    assert response.status_code == 401


def test_config_rejects_regular_user(client, login_as, make_enterprise, make_user):
    ent = make_enterprise("Acme")
    user = make_user("acme_user", role="user", enterprise_id=ent["id"])

    login_as(user)
    response = client.get("/api/config")

    assert response.status_code == 403


def test_enterprise_admin_can_read_config(client, login_as, make_enterprise, make_user):
    ent = make_enterprise("Acme")
    admin = make_user("acme_admin_config", role="enterprise_admin", enterprise_id=ent["id"])

    login_as(admin)
    response = client.get("/api/config")

    assert response.status_code == 200
    assert "vision_mode" in response.get_json()
