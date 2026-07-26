"""
Enterprise data isolation tests.

Requires: pytest, Flask test client
Run: pytest backend/test_data_isolation.py -v
"""

import json
import io
import os
import tempfile
import threading

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

    # Use a temp history.json to protect real data
    from backend import history as history_module
    fd, hist_path = tempfile.mkstemp(suffix=".json", prefix="test_history_")
    os.close(fd)
    _original_history = history_module.HISTORY_FILE
    monkeypatch.setattr(history_module, "HISTORY_FILE", hist_path)
    # Write empty list to the temp file
    with open(hist_path, 'w') as f:
        f.write('[]')

    yield

    # Restore real history file path + clean up temp
    monkeypatch.setattr(history_module, "HISTORY_FILE", _original_history)
    try:
        os.unlink(hist_path)
    except OSError:
        pass

    # Clean up temp auth DB
    try:
        os.unlink(path)
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

    def test_history_delete_requires_login(self, client):
        """删除历史记录必须登录，避免未认证用户按 task_id 删除数据"""
        from backend.history import add_history_entry
        add_history_entry("task_to_protect", "protected.pdf", 100, "2025-01-01", enterprise_id=1)

        resp = client.delete("/api/history/task_to_protect")

        assert resp.status_code == 401

    def test_user_cannot_delete_other_enterprise_history_by_id(self, client):
        """企业 A 用户不能按 task_id 删除企业 B 的历史记录"""
        data = _create_test_data()
        from backend.history import add_history_entry, load_history_from_file
        add_history_entry("task_b_delete_probe", "b.pdf", 100, "2025-01-01",
                          enterprise_id=data["ent_b"]["id"])
        _login_as(client, "ent_a_user", "test123")

        resp = client.delete("/api/history/task_b_delete_probe")

        assert resp.status_code == 404
        assert any(h.get("task_id") == "task_b_delete_probe" for h in load_history_from_file())

    def test_user_cannot_access_other_enterprise_task_by_id(self, client):
        """企业 A 用户即使知道企业 B task_id，也不能读 status/result"""
        data = _create_test_data()

        from backend.app import tasks
        task_id = "task_b_secret"
        tasks[task_id] = {
            "task_id": task_id,
            "status": "completed",
            "progress": 100,
            "pdf_name": "secret.pdf",
            "enterprise_id": data["ent_b"]["id"],
            "result": {"enterprise_id": data["ent_b"]["id"], "secret": "hidden"},
        }
        try:
            _login_as(client, "ent_a_user", "test123")

            status_resp = client.get(f"/api/status/{task_id}")
            result_resp = client.get(f"/api/result/{task_id}")

            assert status_resp.status_code == 404
            assert result_resp.status_code == 404
        finally:
            tasks.pop(task_id, None)

    def test_public_retrieval_task_still_enforces_enterprise_access(self, client):
        """企业任务即使用 public 检索库，也不能被其他企业按 task_id 访问"""
        data = _create_test_data()

        from backend.app import tasks
        task_id = "task_b_public_retrieval_secret"
        tasks[task_id] = {
            "task_id": task_id,
            "status": "completed",
            "progress": 100,
            "pdf_name": "secret.pdf",
            "library_key": "public",
            "retrieval_library_key": "public",
            "enterprise_id": data["ent_b"]["id"],
            "result": {"enterprise_id": data["ent_b"]["id"], "secret": "hidden"},
        }
        try:
            _login_as(client, "ent_a_user", "test123")

            status_resp = client.get(f"/api/status/{task_id}")
            result_resp = client.get(f"/api/result/{task_id}")

            assert status_resp.status_code == 404
            assert result_resp.status_code == 404
        finally:
            tasks.pop(task_id, None)

    def test_unassigned_user_cannot_access_business_task_by_id(self, client):
        """未分配企业用户不能通过 task_id 访问业务任务"""
        data = _create_test_data()
        auth_store.create_user(
            "unassigned_task_probe",
            generate_password_hash("test123"),
            role="user",
            enterprise_id=None,
        )

        from backend.app import tasks
        task_id = "task_ent_a_secret"
        tasks[task_id] = {
            "task_id": task_id,
            "status": "completed",
            "progress": 100,
            "pdf_name": "a.pdf",
            "enterprise_id": data["ent_a"]["id"],
            "result": {"enterprise_id": data["ent_a"]["id"], "secret": "hidden"},
        }
        try:
            _login_as(client, "unassigned_task_probe", "test123")

            status_resp = client.get(f"/api/status/{task_id}")
            result_resp = client.get(f"/api/result/{task_id}")

            assert status_resp.status_code == 403
            assert result_resp.status_code == 403
        finally:
            tasks.pop(task_id, None)

    def test_review_retrieval_library_does_not_reclassify_task_scope(self, client):
        """审阅阶段切换检索库只应改 retrieval_library_key，不应把企业任务改成公共归属"""
        data = _create_test_data()
        _login_as(client, "ent_a_user", "test123")

        from backend.app import tasks
        task_id = "task_review_retrieval_probe"
        tasks[task_id] = {
            "task_id": task_id,
            "status": "awaiting_review",
            "progress": 50,
            "pdf_name": "a.prt",
            "library_key": "enterprise-a",
            "enterprise_id": data["ent_a"]["id"],
            "review_event": threading.Event(),
        }
        try:
            resp = client.post(
                f"/api/review/{task_id}",
                json={"review_text": "已确认", "action": "continue", "retrieval_library_key": "public"},
            )

            assert resp.status_code == 200
            assert tasks[task_id]["library_key"] == "enterprise-a"
            assert tasks[task_id]["retrieval_library_key"] == "public"
        finally:
            tasks.pop(task_id, None)

    def test_review_retrieval_rejects_other_enterprise_private_library(self, client, monkeypatch, tmp_path):
        """审阅阶段不能把检索库切到其他企业私有库"""
        data = _create_test_data()
        from backend import library_scope, vector_map_rag

        db_path = tmp_path / "vectors.db"
        monkeypatch.setattr(vector_map_rag, "DB_PATH", str(db_path))
        monkeypatch.setattr(library_scope, "DB_PATH", str(db_path))
        library_scope.initialize_library_storage()
        library_scope.ensure_scope("enterprise_a", "企业 A 私有库", scope_type="private", enterprise_id=data["ent_a"]["id"])
        library_scope.ensure_scope("enterprise_b", "企业 B 私有库", scope_type="private", enterprise_id=data["ent_b"]["id"])

        monkeypatch.setenv("PROCESS_LIBRARY_RESOLUTION_V2", "1")
        monkeypatch.setenv("PROCESS_FIX_ROLLOUT_ENTERPRISE_IDS", str(data["ent_a"]["id"]))
        _login_as(client, "ent_a_user", "test123")

        from backend.app import tasks
        task_id = "task_review_cross_enterprise_retrieval_probe"
        tasks[task_id] = {
            "task_id": task_id,
            "status": "awaiting_review",
            "progress": 50,
            "pdf_name": "a.prt",
            "library_key": "enterprise_a",
            "retrieval_library_key": "enterprise_a",
            "enterprise_id": data["ent_a"]["id"],
            "review_event": threading.Event(),
        }
        try:
            resp = client.post(
                f"/api/review/{task_id}",
                json={"review_text": "已确认", "action": "continue", "retrieval_library_key": "enterprise_b"},
            )

            assert resp.status_code == 200
            assert tasks[task_id]["library_key"] == "enterprise_a"
            assert tasks[task_id]["retrieval_library_key"] == "enterprise_a"
            assert tasks[task_id]["retrieval_library_resolution"]["source"] == "enterprise_default"
            assert tasks[task_id]["retrieval_library_resolution"]["rejected_requested_key"] == "enterprise_b"
        finally:
            tasks.pop(task_id, None)

    def test_pending_review_restore_preserves_retrieval_library(self, monkeypatch, tmp_path):
        from backend.services import review_session

        monkeypatch.setattr(review_session, "OUTPUT_FOLDER", str(tmp_path))
        task = {
            "task_id": "task_pending_retrieval_probe",
            "pdf_name": "a.prt",
            "output_dir": str(tmp_path / "task_pending_retrieval_probe"),
            "status": "awaiting_review",
            "library_key": "public",
            "retrieval_library_key": "enterprise_a",
            "retrieval_library_resolution": {
                "source": "enterprise_default",
                "scope": {"library_key": "enterprise_a", "enterprise_id": 1},
            },
            "enterprise_id": 1,
        }

        review_session.persist_review_payload(task)
        restored = review_session.restore_task_from_pending(
            task["task_id"],
            tasks={},
            event_data={},
            event_locks={},
        )

        assert restored["library_key"] == "public"
        assert restored["retrieval_library_key"] == "enterprise_a"
        assert restored["retrieval_library_resolution"]["source"] == "enterprise_default"
        assert restored["enterprise_id"] == 1

    def test_result_restore_preserves_retrieval_library(self, monkeypatch, tmp_path):
        from backend.services import review_session

        monkeypatch.setattr(review_session, "OUTPUT_FOLDER", str(tmp_path))
        task_id = "task_result_retrieval_probe"
        output_dir = tmp_path / task_id
        output_dir.mkdir()
        with open(output_dir / "result.json", "w", encoding="utf-8") as f:
            json.dump(
                {
                    "task_id": task_id,
                    "pdf_name": "a.prt",
                    "status": "completed",
                    "library_key": "public",
                    "retrieval_library_key": "enterprise_a",
                    "retrieval_library_resolution": {"source": "enterprise_default"},
                    "enterprise_id": 1,
                },
                f,
            )

        restored = review_session.restore_task_from_result(
            task_id,
            tasks={},
            event_data={},
            event_locks={},
        )

        assert restored["library_key"] == "public"
        assert restored["retrieval_library_key"] == "enterprise_a"
        assert restored["retrieval_library_resolution"]["source"] == "enterprise_default"
        assert restored["enterprise_id"] == 1

    def test_user_cannot_access_other_enterprise_library_record(self, client):
        """企业 A 用户请求知识库记录，不应返回企业 B 的记录"""
        # 这个测试依赖 vectors.db 中有实际数据
        # 如果 vectors.db 为空，测试数据库查询层面的 WHERE 过滤
        pass  # Placeholder — 需要实际数据时补全

    def test_library_preview_task_requires_task_access(self, client, monkeypatch):
        """企业 A 用户不能通过 library preview 读取企业 B 的任务结果"""
        data = _create_test_data()
        from backend.api import library as library_api
        from backend.app import tasks

        task_id = "task_preview_cross_enterprise_probe"
        tasks[task_id] = {
            "task_id": task_id,
            "status": "completed",
            "enterprise_id": data["ent_b"]["id"],
            "result": {
                "task_id": task_id,
                "pdf_name": "b.prt",
                "feature_report_text": "【图号】B1\n【零件名称】企业B零件",
                "process_flow": {"data": [["0010", "料", "备料"]]},
            },
        }
        monkeypatch.setattr(
            library_api,
            "_build_draft_from_task",
            lambda _task_id: (
                {"prefix": "B1", "feature_report_text": "企业B零件"},
                None,
                {"matches": []},
            ),
        )
        _login_as(client, "ent_a_user", "test123")
        try:
            resp = client.post(
                "/api/library/preview",
                json={"source_type": "task", "task_id": task_id},
            )
            assert resp.status_code == 404
        finally:
            tasks.pop(task_id, None)

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

    def test_unassigned_user_only_sees_public_library(self, client, monkeypatch, tmp_path):
        """未分配企业用户只能看到 scope_type='public' 的记录"""
        from backend import library_scope

        monkeypatch.setattr(library_scope, "DB_PATH", str(tmp_path / "vectors.db"))
        library_scope.ensure_scope_registry()
        library_scope.ensure_scope("enterprise_a_scope", "企业 A 私有库", scope_type="private", enterprise_id=1)
        library_scope.ensure_scope("enterprise_b_scope", "企业 B 私有库", scope_type="private", enterprise_id=2)

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

    def test_batch_upload_writes_enterprise_id(self, client):
        """批量 PRT 上传创建的父任务和子任务都应写入 enterprise_id"""
        data = _create_test_data()
        _login_as(client, "ent_a_user", "test123")

        from backend.app import tasks
        from backend.task_store import get_task

        resp = client.post(
            "/api/batch_upload",
            data={"files": [(io.BytesIO(b"dummy prt content"), "sample.prt")]},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        batch_task_id = resp.get_json()["batch_task_id"]

        try:
            assert tasks[batch_task_id]["enterprise_id"] == data["ent_a"]["id"]
            assert tasks[batch_task_id]["retrieval_library_key"] == "public"
            assert get_task(batch_task_id)["enterprise_id"] == data["ent_a"]["id"]
            child_ids = [f["task_id"] for f in tasks[batch_task_id]["files"]]
            assert child_ids
            assert all(tasks[child_id]["enterprise_id"] == data["ent_a"]["id"] for child_id in child_ids)
        finally:
            for child in tasks.get(batch_task_id, {}).get("files", []):
                tasks.pop(child.get("task_id"), None)
            tasks.pop(batch_task_id, None)

    def test_upload_defaults_retrieval_to_enterprise_private_library_when_rollout_enabled(self, client, monkeypatch, tmp_path):
        data = _create_test_data()
        from backend import library_scope, vector_map_rag

        db_path = tmp_path / "vectors.db"
        monkeypatch.setattr(vector_map_rag, "DB_PATH", str(db_path))
        monkeypatch.setattr(library_scope, "DB_PATH", str(db_path))
        library_scope.initialize_library_storage()
        library_scope.ensure_scope("enterprise_a", "企业 A 私有库", scope_type="private", enterprise_id=data["ent_a"]["id"])

        monkeypatch.setenv("PROCESS_LIBRARY_RESOLUTION_V2", "1")
        monkeypatch.setenv("PROCESS_FIX_ROLLOUT_ENTERPRISE_IDS", str(data["ent_a"]["id"]))
        _login_as(client, "ent_a_user", "test123")

        resp = client.post(
            "/api/batch_upload",
            data={"files": [(io.BytesIO(b"dummy prt content"), "sample.prt")]},
            content_type="multipart/form-data",
        )

        assert resp.status_code == 200
        batch_task_id = resp.get_json()["batch_task_id"]
        from backend.app import tasks
        try:
            assert tasks[batch_task_id]["retrieval_library_key"] == "enterprise_a"
            assert tasks[batch_task_id]["retrieval_library_resolution"]["source"] == "enterprise_default"
            assert tasks[batch_task_id]["enterprise_id"] == data["ent_a"]["id"]
        finally:
            for child in tasks.get(batch_task_id, {}).get("files", []):
                tasks.pop(child.get("task_id"), None)
            tasks.pop(batch_task_id, None)

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
