# -*- coding: utf-8 -*-
"""History endpoint for managing task history."""

import os
import shutil
from flask import Blueprint, jsonify, request

from ..history import get_history, delete_history_entry
from ..auth_utils import login_required
from ..config import OUTPUT_FOLDER
from ._utils import get_enterprise_scope

history_bp = Blueprint("history", __name__)


@history_bp.route("/history", methods=["GET"])
@login_required
def list_history():
    ent_id, is_super = get_enterprise_scope()
    if is_super:
        scope = request.args.get("scope", "")
        filter_id = request.args.get("enterprise_id", type=int)
        if scope == "all":
            history = get_history()
        elif filter_id is not None:
            history = get_history(enterprise_id=filter_id)
        else:
            # Default: return empty unless explicitly requested
            history = []
    else:
        history = get_history(enterprise_id=ent_id)
    return jsonify({"history": history})


@history_bp.route("/history/<task_id>", methods=["DELETE"])
def delete_history(task_id):
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
