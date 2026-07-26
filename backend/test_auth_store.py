"""pytest tests for backend/auth_store.py — isolated, each test uses a temp DB."""

import os
import sqlite3
import tempfile
from datetime import datetime, timedelta

import pytest
from werkzeug.security import generate_password_hash

# Patch DB_FILE before importing auth_store
import backend.auth_store as auth_store


@pytest.fixture(autouse=True)
def _temp_db(monkeypatch):
    """Route every test to a fresh temporary SQLite file; re-init schema."""
    fd, path = tempfile.mkstemp(suffix=".db", prefix="test_auth_")
    os.close(fd)
    monkeypatch.setattr(auth_store, "DB_FILE", path)
    auth_store.init_auth_db()
    yield
    try:
        os.unlink(path)
    except OSError:
        pass


# ── Bootstrap / init ────────────────────────────────────────────────────────


def test_init_creates_admin():
    admin = auth_store.get_user_by_username("admin")
    assert admin is not None
    assert admin["username"] == "admin"
    assert admin["role"] == "super_admin"


def test_admin_password_is_hashed():
    admin = auth_store.get_user_by_username("admin")
    assert admin["password_hash"].startswith("scrypt:") or admin["password_hash"].startswith("pbkdf2:")


def test_admin_quota_is_999999():
    admin = auth_store.get_user_by_username("admin")
    q = auth_store.get_user_quota(admin["id"])
    assert q["total_granted"] == 999999
    assert q["used"] == 0


def test_init_idempotent():
    """Calling init_auth_db twice must not crash or duplicate admin."""
    auth_store.init_auth_db()
    users = auth_store.list_all_users()
    admins = [u for u in users if u["username"] == "admin"]
    assert len(admins) == 1


# ── Users ───────────────────────────────────────────────────────────────────


def test_create_user_basic():
    u = auth_store.create_user("alice", generate_password_hash("pw"))
    assert u["username"] == "alice"
    assert u["role"] == "user"
    assert u["enterprise_id"] is None
    assert u["is_active"] == 1


def test_create_user_default_quota():
    u = auth_store.create_user("bob", generate_password_hash("pw"))
    q = auth_store.get_user_quota(u["id"])
    assert q["total_granted"] == 10
    assert q["used"] == 0


def test_get_user_by_username():
    auth_store.create_user("charlie", generate_password_hash("pw"))
    u = auth_store.get_user_by_username("charlie")
    assert u is not None
    assert u["username"] == "charlie"


def test_get_user_by_username_missing():
    assert auth_store.get_user_by_username("no-one") is None


def test_get_user_by_id():
    u = auth_store.create_user("dave", generate_password_hash("pw"))
    assert auth_store.get_user_by_id(u["id"]) is not None


def test_get_user_by_id_missing():
    assert auth_store.get_user_by_id(99999) is None


def test_update_user_fields():
    u = auth_store.create_user("eve", generate_password_hash("pw"))
    auth_store.update_user(u["id"], is_active=0, role="enterprise_admin")
    u2 = auth_store.get_user_by_id(u["id"])
    assert u2["is_active"] == 0
    assert u2["role"] == "enterprise_admin"


def test_update_user_disallowed_field_ignored():
    u = auth_store.create_user("frank", generate_password_hash("pw"))
    auth_store.update_user(u["id"], bogus_field="should_be_ignored")
    # No error raised; frank is unchanged
    u2 = auth_store.get_user_by_id(u["id"])
    assert u2["username"] == "frank"


def test_list_all_users():
    auth_store.create_user("u1", generate_password_hash("pw"))
    auth_store.create_user("u2", generate_password_hash("pw"), enterprise_id=None)
    users = auth_store.list_all_users()
    usernames = {u["username"] for u in users}
    assert "admin" in usernames
    assert "u1" in usernames
    assert "u2" in usernames


def test_list_enterprise_users():
    e = auth_store.create_enterprise("Acme")
    auth_store.create_user("worker1", generate_password_hash("pw"), enterprise_id=e["id"])
    auth_store.create_user("worker2", generate_password_hash("pw"), enterprise_id=e["id"])
    auth_store.create_user("outsider", generate_password_hash("pw"))  # no enterprise
    workers = auth_store.list_enterprise_users(e["id"])
    names = {u["username"] for u in workers}
    assert names == {"worker1", "worker2"}


# ── Enterprises ─────────────────────────────────────────────────────────────


def test_create_and_get_enterprise():
    e = auth_store.create_enterprise("Foo Corp")
    assert e["name"] == "Foo Corp"
    assert e["is_active"] == 1


def test_get_enterprise_missing():
    assert auth_store.get_enterprise(99999) is None


def test_list_enterprises():
    auth_store.create_enterprise("A")
    auth_store.create_enterprise("B")
    all_ent = auth_store.list_enterprises()
    assert len(all_ent) >= 2


def test_list_enterprises_active_filter():
    auth_store.create_enterprise("ActiveCo")
    e = auth_store.create_enterprise("InactiveCo")
    auth_store.update_enterprise(e["id"], is_active=0)
    active = auth_store.list_enterprises(is_active=True)
    names = {ent["name"] for ent in active}
    assert "ActiveCo" in names
    assert "InactiveCo" not in names


def test_update_enterprise():
    e = auth_store.create_enterprise("OldName")
    auth_store.update_enterprise(e["id"], name="NewName", is_active=0)
    e2 = auth_store.get_enterprise(e["id"])
    assert e2["name"] == "NewName"
    assert e2["is_active"] == 0


# ── Quotas ──────────────────────────────────────────────────────────────────


def test_get_or_create_existing():
    u = auth_store.create_user("q_user", generate_password_hash("pw"))
    q = auth_store.get_or_create_quota(u["id"], initial=50)
    assert q["total_granted"] == 10  # already created by create_user with default 10
    assert q["used"] == 0


def test_get_or_create_creates_when_missing():
    # create_user auto-creates a quota; to test the "create" path,
    # delete the auto-quota first so get_or_create_quota fires the INSERT branch
    u = auth_store.create_user("temp_q_user", generate_password_hash("pw"))
    db = sqlite3.connect(auth_store.DB_FILE)
    db.execute("PRAGMA foreign_keys=OFF")
    db.execute("DELETE FROM quotas WHERE user_id=?", (u["id"],))
    db.commit()
    db.close()
    q = auth_store.get_or_create_quota(u["id"], initial=5)
    assert q["total_granted"] == 5


def test_consume_quota_success():
    u = auth_store.create_user("consumer", generate_password_hash("pw"))
    auth_store.set_quota(u["id"], 5)
    for _ in range(5):
        assert auth_store.consume_quota(u["id"]) is True
    q = auth_store.get_user_quota(u["id"])
    assert q["used"] == 5


def test_consume_quota_exhausted():
    u = auth_store.create_user("exhausted", generate_password_hash("pw"))
    auth_store.set_quota(u["id"], 1)
    assert auth_store.consume_quota(u["id"]) is True
    assert auth_store.consume_quota(u["id"]) is False  # no quota left


def test_set_quota():
    u = auth_store.create_user("reset_me", generate_password_hash("pw"))
    auth_store.set_quota(u["id"], 100)
    q = auth_store.get_user_quota(u["id"])
    assert q["total_granted"] == 100
    assert q["used"] == 0  # used reset to 0 per upsert


# ── Enterprise Admin Grants ─────────────────────────────────────────────────


def test_create_and_get_grant():
    e = auth_store.create_enterprise("GrantCo")
    u = auth_store.create_user("grant_admin", generate_password_hash("pw"),
                                role="enterprise_admin", enterprise_id=e["id"])
    expires = (datetime.utcnow() + timedelta(days=365)).isoformat()
    g = auth_store.create_enterprise_admin_grant(u["id"], e["id"], 1, expires)
    assert g["user_id"] == u["id"]
    assert g["enterprise_id"] == e["id"]


def test_get_enterprise_admin_grant_missing():
    assert auth_store.get_enterprise_admin_grant(99999) is None


def test_is_enterprise_admin_expired():
    e = auth_store.create_enterprise("ExpireCo")
    u = auth_store.create_user("exp_admin", generate_password_hash("pw"),
                                role="enterprise_admin", enterprise_id=e["id"])
    past = (datetime.utcnow() - timedelta(days=1)).isoformat()
    auth_store.create_enterprise_admin_grant(u["id"], e["id"], 1, past)
    assert auth_store.is_enterprise_admin_expired(u["id"]) is True


def test_is_enterprise_admin_not_expired():
    e = auth_store.create_enterprise("ValidCo")
    u = auth_store.create_user("valid_admin", generate_password_hash("pw"),
                                role="enterprise_admin", enterprise_id=e["id"])
    future = (datetime.utcnow() + timedelta(days=365)).isoformat()
    auth_store.create_enterprise_admin_grant(u["id"], e["id"], 1, future)
    assert auth_store.is_enterprise_admin_expired(u["id"]) is False


def test_get_enterprise_admin_grant_by_enterprise():
    e = auth_store.create_enterprise("LookupCo")
    u = auth_store.create_user("lookup_admin", generate_password_hash("pw"),
                                role="enterprise_admin", enterprise_id=e["id"])
    future = (datetime.utcnow() + timedelta(days=365)).isoformat()
    auth_store.create_enterprise_admin_grant(u["id"], e["id"], 1, future)
    g = auth_store.get_enterprise_admin_grant_by_enterprise(e["id"])
    assert g is not None
    assert g["user_id"] == u["id"]


# ── check_user_can_infer ────────────────────────────────────────────────────


def test_can_infer_super_admin():
    admin = auth_store.get_user_by_username("admin")
    assert auth_store.check_user_can_infer(admin["id"]) is None


def test_can_infer_missing_user():
    result = auth_store.check_user_can_infer(99999)
    assert result == "用户不存在"


def test_can_infer_inactive_user():
    u = auth_store.create_user("inactive", generate_password_hash("pw"))
    auth_store.update_user(u["id"], is_active=0)
    result = auth_store.check_user_can_infer(u["id"])
    assert "停用" in result


def test_can_infer_no_enterprise():
    u = auth_store.create_user("no_ent", generate_password_hash("pw"))
    result = auth_store.check_user_can_infer(u["id"])
    assert "尚未分配" in result


def test_can_infer_enterprise_inactive():
    e = auth_store.create_enterprise("DeadCo")
    auth_store.update_enterprise(e["id"], is_active=0)
    u = auth_store.create_user("dead_worker", generate_password_hash("pw"),
                                enterprise_id=e["id"])
    result = auth_store.check_user_can_infer(u["id"])
    assert "停用" in result


def test_can_infer_enterprise_admin_expired():
    e = auth_store.create_enterprise("ExpiredAdminCo")
    admin_u = auth_store.create_user("exp_ent_admin", generate_password_hash("pw"),
                                      role="enterprise_admin", enterprise_id=e["id"])
    past = (datetime.utcnow() - timedelta(days=1)).isoformat()
    auth_store.create_enterprise_admin_grant(admin_u["id"], e["id"], 1, past)
    # Enterprise admin with expired grant
    result = auth_store.check_user_can_infer(admin_u["id"])
    assert "到期" in result


def test_can_infer_quota_exhausted():
    e = auth_store.create_enterprise("QuotaCo")
    u = auth_store.create_user("quota_out", generate_password_hash("pw"),
                                enterprise_id=e["id"])
    auth_store.set_quota(u["id"], 1)
    auth_store.consume_quota(u["id"])
    result = auth_store.check_user_can_infer(u["id"])
    assert "用完" in result


def test_can_infer_normal_user_ok():
    e = auth_store.create_enterprise("NormalCo")
    u = auth_store.create_user("normal_user", generate_password_hash("pw"),
                                enterprise_id=e["id"])
    result = auth_store.check_user_can_infer(u["id"])
    assert result is None


def test_can_infer_enterprise_admin_active_ok():
    e = auth_store.create_enterprise("ActiveAdminCo")
    admin_u = auth_store.create_user("ok_ent_admin", generate_password_hash("pw"),
                                      role="enterprise_admin", enterprise_id=e["id"])
    future = (datetime.utcnow() + timedelta(days=365)).isoformat()
    auth_store.create_enterprise_admin_grant(admin_u["id"], e["id"], 1, future)
    assert auth_store.check_user_can_infer(admin_u["id"]) is None


def test_step7_user_enterprise_admin_expired():
    """Step 7: regular user whose enterprise admin's grant has expired."""
    e = auth_store.create_enterprise("Step7Co")
    ent_admin = auth_store.create_user("step7_admin", generate_password_hash("pw"),
                                        role="enterprise_admin", enterprise_id=e["id"])
    past = (datetime.utcnow() - timedelta(days=1)).isoformat()
    auth_store.create_enterprise_admin_grant(ent_admin["id"], e["id"], 1, past)
    reg_user = auth_store.create_user("step7_user", generate_password_hash("pw"),
                                       enterprise_id=e["id"])
    result = auth_store.check_user_can_infer(reg_user["id"])
    assert result is not None
    assert "企业管理员" in result
    assert "到期" in result
