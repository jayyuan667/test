from backend.api.upload import _resolve_feature_cache_policy


def test_feature_cache_off_skips_read_but_still_writes_successful_extraction():
    assert _resolve_feature_cache_policy("0") == {"read": False, "write": True}
    assert _resolve_feature_cache_policy("false") == {"read": False, "write": True}
    assert _resolve_feature_cache_policy("") == {"read": False, "write": True}


def test_feature_cache_on_reads_and_writes():
    assert _resolve_feature_cache_policy("1") == {"read": True, "write": True}
    assert _resolve_feature_cache_policy("true") == {"read": True, "write": True}

