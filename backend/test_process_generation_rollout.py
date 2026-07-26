import pytest

from backend.services import process_rollout


def test_env_flag_enabled_accepts_common_truthy_values(monkeypatch):
    for value in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv("PROCESS_QUALITY_GATE_V2", value)
        assert process_rollout.env_flag_enabled("PROCESS_QUALITY_GATE_V2") is True


def test_env_flag_enabled_rejects_falsey_values(monkeypatch):
    for value in ("", "0", "false", "no", "off"):
        monkeypatch.setenv("PROCESS_QUALITY_GATE_V2", value)
        assert process_rollout.env_flag_enabled("PROCESS_QUALITY_GATE_V2") is False


def test_enterprise_rollout_allow_list(monkeypatch):
    monkeypatch.setenv("PROCESS_FIX_ROLLOUT_ENTERPRISE_IDS", "1, 3")

    assert process_rollout.enterprise_in_rollout(1) is True
    assert process_rollout.enterprise_in_rollout(3) is True
    assert process_rollout.enterprise_in_rollout(2) is False
    assert process_rollout.enterprise_in_rollout(None) is False


def test_enterprise_rollout_star_allows_all(monkeypatch):
    monkeypatch.setenv("PROCESS_FIX_ROLLOUT_ENTERPRISE_IDS", "*")

    assert process_rollout.enterprise_in_rollout(1) is True
    assert process_rollout.enterprise_in_rollout(99) is True
    assert process_rollout.enterprise_in_rollout(None) is False


@pytest.fixture()
def temp_library_db(monkeypatch, tmp_path):
    from backend import library_scope
    from backend import vector_map_rag

    db_path = tmp_path / "vectors.db"
    monkeypatch.setattr(vector_map_rag, "DB_PATH", str(db_path))
    monkeypatch.setattr(library_scope, "DB_PATH", str(db_path))
    library_scope.initialize_library_storage()
    library_scope.ensure_scope("cjy", "cjy-测试数据库", scope_type="private", enterprise_id=1)
    library_scope.ensure_scope("wjs", "wjs-测试库", scope_type="private", enterprise_id=2)
    return db_path


def test_resolver_defaults_enterprise_user_to_own_private_library(monkeypatch, temp_library_db):
    monkeypatch.setenv("PROCESS_LIBRARY_RESOLUTION_V2", "1")
    monkeypatch.setenv("PROCESS_FIX_ROLLOUT_ENTERPRISE_IDS", "1")

    key, meta = process_rollout.resolve_generation_library_key(
        requested_key=None,
        user={"role": "user", "enterprise_id": 1},
    )

    assert key == "cjy"
    assert meta["source"] == "enterprise_default"


def test_resolver_respects_explicit_accessible_library(monkeypatch, temp_library_db):
    monkeypatch.setenv("PROCESS_LIBRARY_RESOLUTION_V2", "1")
    monkeypatch.setenv("PROCESS_FIX_ROLLOUT_ENTERPRISE_IDS", "1")

    key, meta = process_rollout.resolve_generation_library_key(
        requested_key="public",
        user={"role": "user", "enterprise_id": 1},
    )

    assert key == "public"
    assert meta["source"] == "explicit"


def test_resolver_rejects_cross_enterprise_explicit_library(monkeypatch, temp_library_db):
    monkeypatch.setenv("PROCESS_LIBRARY_RESOLUTION_V2", "1")
    monkeypatch.setenv("PROCESS_FIX_ROLLOUT_ENTERPRISE_IDS", "1")

    key, meta = process_rollout.resolve_generation_library_key(
        requested_key="wjs",
        user={"role": "user", "enterprise_id": 1},
    )

    assert key == "cjy"
    assert meta["source"] == "enterprise_default"
    assert meta["rejected_requested_key"] == "wjs"


def test_resolver_keeps_public_when_rollout_disabled(monkeypatch, temp_library_db):
    monkeypatch.delenv("PROCESS_LIBRARY_RESOLUTION_V2", raising=False)
    monkeypatch.setenv("PROCESS_FIX_ROLLOUT_ENTERPRISE_IDS", "1")

    key, meta = process_rollout.resolve_generation_library_key(
        requested_key=None,
        user={"role": "user", "enterprise_id": 1},
    )

    assert key == "public"
    assert meta["source"] == "legacy_default"


def test_resolver_super_admin_defaults_public(monkeypatch, temp_library_db):
    monkeypatch.setenv("PROCESS_LIBRARY_RESOLUTION_V2", "1")
    monkeypatch.setenv("PROCESS_FIX_ROLLOUT_ENTERPRISE_IDS", "*")

    key, meta = process_rollout.resolve_generation_library_key(
        requested_key=None,
        user={"role": "super_admin", "enterprise_id": None},
    )

    assert key == "public"
    assert meta["source"] == "super_admin_default"


def test_quality_gate_flags_single_row_nontrivial_process():
    feature_text = "【毛坯类型】板料\n【螺纹与螺孔】6×φ2.2；2×M2.5\n【表面处理与镀层特征】彩虹色导电氧化"

    result = process_rollout.evaluate_process_quality(
        process_rows=[["0010", "料", "备料"]],
        feature_text=feature_text,
        constraints={
            "hard_constraints": {
                "material_form": "板料",
                "surface_treatment": "彩虹色导电氧化",
            },
            "soft_features": {"holes_threads": "6×φ2.2"},
        },
        vision_degraded=False,
    )

    assert result["ok"] is False
    assert "too_few_rows" in result["reasons"]
    assert "holes_or_threads" in result["reasons"]
    assert "surface_treatment" in result["reasons"]


def test_quality_gate_allows_degraded_single_row():
    result = process_rollout.evaluate_process_quality(
        process_rows=[["0010", "料", "备料"]],
        feature_text="【系统提示】视觉分析已降级",
        constraints={"hard_constraints": {}, "soft_features": {}},
        vision_degraded=True,
    )

    assert result["ok"] is True
    assert result["degraded"] is True


def test_detect_missing_pages_warning_when_text_mentions_second_page():
    warning = process_rollout.detect_missing_pages_warning(
        "【其他特征】本图纸共2张，此为第1张；G面(第2张)",
        processed_pages=1,
    )

    assert warning["expected_pages"] == 2
    assert warning["processed_pages"] == 1
    assert "第2张" in warning["message"]


def test_detect_missing_pages_warning_is_none_when_pages_match():
    warning = process_rollout.detect_missing_pages_warning(
        "【页数】2\n【其他特征】本图纸共2张",
        processed_pages=2,
    )

    assert warning is None
