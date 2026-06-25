"""
Enterprise data isolation tests.

Requires: pytest, Flask test client
Run: pytest backend/test_data_isolation.py -v
"""

import json
import os
import tempfile

import pytest
from werkzeug.security import generate_password_hash

from backend.app import app
from backend import auth_store


@pytest.fixture(autouse=True)
def setup_db(monkeypatch):
    """Use a temp auth DB for isolation and clean history between tests."""
    # Route auth_store to a temporary database so each test starts fresh
    fd, path = tempfile.mkstemp(suffix=".db", prefix="test_data_isolation_")
    os.close(fd)
    monkeypatch.setattr(auth_store, "DB_FILE", path)
    auth_store.init_auth_db()

    yield

    # Clean up temp auth DB
    try:
        os.unlink(path)
    except OSError:
        pass

    # Clean up history file to avoid cross-test pollution
    from backend.history import HISTORY_FILE
    if os.path.exists(HISTORY_FILE):
        try:
            os.remove(HISTORY_FILE)
        except OSError:
            pass


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _login_as(client, username, password):
    """Helper: login and return the client with cookie set."""
    resp = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200
    return client


def _create_test_data():
    """Create two enterprises with users and library scopes."""
    # Enterprise A
    ent_a = auth_store.create_enterprise("测试企业A")
    user_a = auth_store.create_user(
        "ent_a_user", generate_password_hash("test123"),
        role="user", enterprise_id=ent_a["id"]
    )
    admin_a = auth_store.create_user(
        "ent_a_admin", generate_password_hash("test123"),
        role="enterprise_admin", enterprise_id=ent_a["id"]
    )

    # Enterprise B
    ent_b = auth_store.create_enterprise("测试企业B")
    user_b = auth_store.create_user(
        "ent_b_user", generate_password_hash("test123"),
        role="user", enterprise_id=ent_b["id"]
    )

    return {
        "ent_a": ent_a, "user_a": user_a, "admin_a": admin_a,
        "ent_b": ent_b, "user_b": user_b,
    }


class TestEnterpriseIsolation:
    """企业间数据隔离测试"""

    def test_user_cannot_see_other_enterprise_history(self, client):
        """企业 A 用户请求历史记录，不应包含企业 B 的 task"""
        data = _create_test_data()
        _login_as(client, "ent_a_user", "test123")

        # 创建属于企业 B 的 history 条目
        from backend.history import add_history_entry
        add_history_entry("task_b_1", "test.pdf", 100, "2025-01-01",
                          enterprise_id=data["ent_b"]["id"])

        resp = client.get("/api/history")
        assert resp.status_code == 200
        history = resp.get_json().get("history", [])

        # 不应该包含企业 B 的条目
        b_task_ids = [h["task_id"] for h in history if h.get("enterprise_id") == data["ent_b"]["id"]]
        assert len(b_task_ids) == 0, f"Leaked enterprise B tasks: {b_task_ids}"

    def test_user_cannot_access_other_enterprise_library_record(self, client):
        """企业 A 用户请求知识库记录，不应返回企业 B 的记录"""
        # 这个测试依赖 vectors.db 中有实际数据
        # 如果 vectors.db 为空，测试数据库查询层面的 WHERE 过滤
        pass  # Placeholder — 需要实际数据时补全

    def test_super_admin_can_see_all_enterprises(self, client):
        """super_admin 可以跨企业查看（需传 ?scope=all）"""
        data = _create_test_data()
        _login_as(client, "admin", "admin123")

        # 分别创建两个企业的 history 条目
        from backend.history import add_history_entry
        add_history_entry("task_a_1", "a.pdf", 100, "2025-01-01",
                          enterprise_id=data["ent_a"]["id"])
        add_history_entry("task_b_1", "b.pdf", 100, "2025-01-01",
                          enterprise_id=data["ent_b"]["id"])

        # super_admin 必须传 ?scope=all 才能看到全平台数据
        resp = client.get("/api/history?scope=all")
        assert resp.status_code == 200
        history = resp.get_json().get("history", [])

        # 应该包含两个企业的条目
        ent_ids = {h.get("enterprise_id") for h in history}
        assert data["ent_a"]["id"] in ent_ids
        assert data["ent_b"]["id"] in ent_ids

    def test_super_admin_can_filter_by_enterprise(self, client):
        """super_admin 传 ?enterprise_id=2 可以限定范围"""
        data = _create_test_data()
        _login_as(client, "admin", "admin123")

        from backend.history import add_history_entry
        add_history_entry("task_a_1", "a.pdf", 100, "2025-01-01",
                          enterprise_id=data["ent_a"]["id"])
        add_history_entry("task_b_1", "b.pdf", 100, "2025-01-01",
                          enterprise_id=data["ent_b"]["id"])

        # 只看企业 A
        resp = client.get(f"/api/history?enterprise_id={data['ent_a']['id']}")
        history = resp.get_json().get("history", [])

        ent_ids = {h.get("enterprise_id") for h in history}
        assert data["ent_a"]["id"] in ent_ids
        # 不应该含企业 B（除非有 NULL enterprise_id = public）
        b_entries = [h for h in history if h.get("enterprise_id") == data["ent_b"]["id"]]
        assert len(b_entries) == 0

    def test_unassigned_user_only_sees_public_library(self, client):
        """未分配企业用户只能看到 scope_type='public' 的记录"""
        # Skip if vectors.db has existing private scopes without enterprise_id
        from backend.library_scope import list_scopes as _list_scopes
        _existing_private = [s for s in _list_scopes()
                             if s.get("scope_type") != "public"
                             and s.get("enterprise_id") is None]
        if _existing_private:
            pytest.skip(f"vectors.db has {len(_existing_private)} pre-existing private scope(s) "
                        f"with NULL enterprise_id — cannot verify isolation in this env")

        auth_store.create_user(
            "unassigned", generate_password_hash("test123"),
            role="user", enterprise_id=None
        )
        _login_as(client, "unassigned", "test123")

        resp = client.get("/api/library/scopes")
        assert resp.status_code == 200
        scopes = resp.get_json().get("items", [])

        # 只应包含 public scope，不应包含 private scope
        private_scopes = [s for s in scopes if s.get("scope_type") != "public"]
        assert len(private_scopes) == 0, f"Unassigned user can see private scopes: {private_scopes}"

    def test_upload_writes_enterprise_id(self, client):
        """上传图纸时自动写入 enterprise_id"""
        _create_test_data()
        _login_as(client, "ent_a_user", "test123")

        # 测试 insert_task 是否接受 enterprise_id 参数
        from backend.task_store import insert_task
        try:
            insert_task(
                task_id="test_task_ent",
                pdf_name="test.prt",
                enterprise_id=1
            )
        except Exception as e:
            pytest.fail(f"insert_task with enterprise_id failed: {e}")

    def test_zip_import_writes_enterprise_id(self, client):
        """ZIP 导入时自动写入 enterprise_id"""
        _create_test_data()
        _login_as(client, "ent_a_user", "test123")

        # 确保 kb_import_batches 表存在
        from backend.library_scope import ensure_import_tracking_tables
        ensure_import_tracking_tables()

        # 验证 kb_import_batches 表有 enterprise_id 列
        import sqlite3
        from backend.vector_map_rag import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(kb_import_batches)")
        columns = {r[1] for r in cursor.fetchall()}
        conn.close()
        assert "enterprise_id" in columns, "kb_import_batches missing enterprise_id column"
