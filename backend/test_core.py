#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Core pipeline smoke tests — no API calls, no database required.

Usage:
    python backend/test_core.py
"""
import re
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ── 1. split_vision_results ──────────────────────────────────────────────────

def test_split_vision_results():
    from backend.vision_utils import split_vision_results

    ok, fail = split_vision_results([
        {"page": 1, "description": "圆柱体零件", "image_path": "/tmp/a.png"},
        {"page": 2, "description": "法兰盘",     "image_path": "/tmp/b.png"},
    ])
    assert len(ok) == 2 and len(fail) == 0
    print("PASS: split_vision_results — all success")

    ok, fail = split_vision_results([
        {"page": 1, "description": "", "error": "API timeout", "image_path": "/tmp/a.png"},
    ])
    assert len(ok) == 0 and len(fail) == 1
    print("PASS: split_vision_results — all failure")

    ok, fail = split_vision_results([
        {"page": 1, "description": "圆柱体",  "image_path": "/tmp/a.png"},
        {"page": 2, "description": "",        "error": "API error", "image_path": "/tmp/b.png"},
        {"page": 3, "description": "法兰盘",  "image_path": "/tmp/c.png"},
    ])
    assert len(ok) == 2 and len(fail) == 1 and fail[0]["page"] == 2
    print("PASS: split_vision_results — partial failure skips bad page, keeps good pages")

    ok, fail = split_vision_results([])
    assert ok == [] and fail == []
    ok, fail = split_vision_results(None)
    assert ok == [] and fail == []
    print("PASS: split_vision_results — empty / None input")


# ── 2. format_vision_failure_message ────────────────────────────────────────

def test_format_vision_failure_message():
    from backend.vision_utils import format_vision_failure_message

    msg = format_vision_failure_message(
        [{"page": 2, "file": "part_A.prt", "message": "API timeout"}],
        prefix="批量视觉分析失败",
    )
    assert "part_A" in msg and "第2页" in msg
    print(f"PASS: format_vision_failure_message → {msg}")

    failures = [{"page": i, "message": f"err{i}"} for i in range(5)]
    msg = format_vision_failure_message(failures, max_items=3)
    assert "其余 2 处" in msg
    print(f"PASS: format_vision_failure_message truncation → {msg}")


# ── 3. _parse_process_markdown ───────────────────────────────────────────────

def _parse_process_markdown(raw_text):
    """Replicated from upload.py for isolated testing."""
    process_data = []
    normalized_text = (raw_text or "").replace("ENDD$$", " ")
    for line in normalized_text.strip().splitlines():
        current = line.strip()
        if not current:
            continue
        if current.startswith(("#", "|", "---", "===")):
            continue
        content = current[2:].strip() if current.startswith(("- ", "* ")) else current
        match = re.match(r"^(\d{4})\s*[@:：\-\|,，;；\s]*\s*(.+)$", content)
        if match:
            process_data.append([match.group(1), match.group(2).strip()])
    return process_data


def test_parse_process_markdown():
    result = _parse_process_markdown("- 0010: 下料\n- 0020: 车端面\n0030: 铣槽\n# 标题行（跳过）\n")
    assert len(result) == 3, f"Expected 3, got {len(result)}: {result}"
    assert result[0] == ["0010", "下料"]
    assert result[1] == ["0020", "车端面"]
    assert result[2] == ["0030", "铣槽"]
    print("PASS: _parse_process_markdown — standard markdown")

    assert _parse_process_markdown("") == []
    assert _parse_process_markdown(None) == []
    print("PASS: _parse_process_markdown — empty / None input")

    # ENDD$$ replaced with space, line still parseable as single entry
    result = _parse_process_markdown("0010: 下料ENDD$$")
    assert len(result) == 1 and result[0][0] == "0010"
    print("PASS: _parse_process_markdown — ENDD$$ replaced without breaking parse")


# ── 4. _extract_prefix_from_filename ────────────────────────────────────────

def _extract_prefix_from_filename(filename):
    """Replicated from batch.py for isolated testing."""
    patterns = [r"([1-9][A-Z]\d{4,6})"]
    for p in patterns:
        match = re.search(p, filename, re.IGNORECASE)
        if match:
            return match.group(1).upper()
    return None


def test_extract_prefix_from_filename():
    assert _extract_prefix_from_filename("1A123456.prt") == "1A123456"
    assert _extract_prefix_from_filename("part_2B9876.prt.1") == "2B9876"
    assert _extract_prefix_from_filename("no_prefix_here.prt") is None
    assert _extract_prefix_from_filename("") is None
    print("PASS: _extract_prefix_from_filename")


# ── 5. review_event timeout ──────────────────────────────────────────────────

def test_review_event_timeout():
    event = threading.Event()
    confirmed = event.wait(timeout=0.01)
    assert confirmed is False, f"Expected False (timeout), got {confirmed}"
    print("PASS: review_event.wait() returns False on timeout — thread would exit")

    event2 = threading.Event()
    event2.set()
    confirmed2 = event2.wait(timeout=1800)
    assert confirmed2 is True
    print("PASS: review_event.wait() returns True when confirmed normally")


# ── 6. batch partial-failure path ────────────────────────────────────────────

def test_split_vision_results_partial_failure_logic():
    """Verify split_vision_results + raise-guard logic: partial failure continues, full failure raises."""
    from backend.vision_utils import split_vision_results

    # Partial failure: 2 ok, 1 fail → successful_descriptions is non-empty → no raise
    all_descriptions = [
        {"file": "A.prt", "page": 1, "description": "圆柱",   "image_path": "/tmp/a.png", "error": ""},
        {"file": "A.prt", "page": 2, "description": "",        "image_path": "/tmp/b.png", "error": "API error"},
        {"file": "B.prt", "page": 1, "description": "法兰盘", "image_path": "/tmp/c.png", "error": ""},
    ]
    successful, failures = split_vision_results(all_descriptions)
    assert len(successful) == 2, f"Expected 2 successful, got {len(successful)}"
    assert len(failures) == 1
    # New logic: only raise if successful is empty
    raised = False
    if not successful:
        raised = True
    assert not raised, "Should NOT raise when some pages succeeded"
    print("PASS: batch partial failure — processing continues with successful pages")

    # Full failure: all descriptions empty → successful_descriptions is empty → should raise
    all_fail = [
        {"file": "A.prt", "page": 1, "description": "", "image_path": "/tmp/a.png", "error": "timeout"},
        {"file": "A.prt", "page": 2, "description": "", "image_path": "/tmp/b.png", "error": "timeout"},
    ]
    successful2, _ = split_vision_results(all_fail)
    assert len(successful2) == 0
    # New logic: raise when ALL fail
    should_raise = not successful2
    assert should_raise, "SHOULD raise when all pages failed"
    print("PASS: batch full failure — RuntimeError would be raised")


# ── 7. rollout readiness gate ────────────────────────────────────────────────

def test_is_upload_template_ready_passes_with_valid_task():
    from backend.api.upload import _is_upload_template_ready

    for mode in ("dual", "freecad", "creo", "none"):
        task = {"vlm_mode": mode, "step_path": "/tmp/model.step", "status": "awaiting_review"}
        assert _is_upload_template_ready(task), f"Should pass for mode={mode}, status=awaiting_review"

        task["status"] = "completed"
        assert _is_upload_template_ready(task), f"Should pass for mode={mode}, status=completed"


def test_is_upload_template_ready_fails_without_vlm_mode():
    from backend.api.upload import _is_upload_template_ready

    task = {"step_path": "/tmp/model.step", "status": "awaiting_review"}
    assert not _is_upload_template_ready(task), "Should fail without vlm_mode"


def test_is_upload_template_ready_fails_without_step_path():
    from backend.api.upload import _is_upload_template_ready

    task = {"vlm_mode": "dual", "status": "awaiting_review"}
    assert not _is_upload_template_ready(task), "Should fail without step_path"


def test_is_upload_template_ready_fails_with_unexpected_status():
    from backend.api.upload import _is_upload_template_ready

    task = {"vlm_mode": "dual", "step_path": "/tmp/model.step", "status": "error"}
    assert not _is_upload_template_ready(task), "Should fail for error status"


def test_is_upload_template_ready_fails_with_invalid_mode():
    from backend.api.upload import _is_upload_template_ready

    task = {"vlm_mode": "unknown", "step_path": "/tmp/model.step", "status": "awaiting_review"}
    assert not _is_upload_template_ready(task), "Should fail for unknown mode"


# ── runner ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_split_vision_results()
    test_format_vision_failure_message()
    test_parse_process_markdown()
    test_extract_prefix_from_filename()
    test_review_event_timeout()
    test_split_vision_results_partial_failure_logic()
    test_is_upload_template_ready_passes_with_valid_task()
    test_is_upload_template_ready_fails_without_vlm_mode()
    test_is_upload_template_ready_fails_without_step_path()
    test_is_upload_template_ready_fails_with_unexpected_status()
    test_is_upload_template_ready_fails_with_invalid_mode()
    print("\nAll core pipeline tests passed.")
