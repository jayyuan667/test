# -*- coding: utf-8 -*-
"""History endpoint for managing task history."""

import os
import shutil
from flask import Blueprint, jsonify, request

from ..history import get_history, delete_history_entry, load_history_from_file
from ..auth_utils import login_required
from ..config import OUTPUT_FOLDER
from ._utils import get_enterprise_scope

history_bp = Blueprint("history", __name__)


@history_bp.route("/history", methods=["GET"])
@login_required
def list_history():
    ent_id, is_super = get_enterprise_scope()
    if is_super:
        filter_id = request.args.get("enterprise_id", type=int)
        history = get_history(enterprise_id=filter_id) if filter_id is not None else get_history()
    elif ent_id is None:
        history = [h for h in get_history() if h.get("enterprise_id") is None]
    else:
        history = get_history(enterprise_id=ent_id)
    return jsonify({"history": history})


@history_bp.route("/history/<task_id>", methods=["DELETE"])
@login_required
def delete_history(task_id):
    ent_id, is_super = get_enterprise_scope()
    entry = next((h for h in load_history_from_file() if h.get("task_id") == task_id), None)
    if not entry:
        return jsonify({"error": "Record not found"}), 404
    if not is_super:
        if ent_id is None:
            return jsonify({"error": "未分配企业，无权访问"}), 403
        if entry.get("enterprise_id") != ent_id:
            return jsonify({"error": "Record not found"}), 404

    deleted = delete_history_entry(task_id)
    if not deleted:
        return jsonify({"error": "Record not found"}), 404

    # Clean up task_store records and output directory
    try:
        from ..task_store import delete_task_with_files
        delete_task_with_files(task_id)
    except Exception as e:
        print(f"Warning: task_store cleanup failed for {task_id}: {e}")
        # Fallback: at least try to delete the output dir by convention
        output_dir = os.path.join(OUTPUT_FOLDER, task_id)
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir, ignore_errors=True)

    return jsonify({"success": True, "message": "Deleted"})
