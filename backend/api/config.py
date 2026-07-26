# -*- coding: utf-8 -*-
"""Config endpoint for managing system configuration."""

from flask import Blueprint, jsonify, request

from ..auth_utils import login_required, require_role
from ..config import get_config, update_config_from_request

config_bp = Blueprint("config", __name__)


@config_bp.route("/config", methods=["GET"])
@login_required
@require_role("super_admin", "enterprise_admin")
def get_config_handler():
    config = get_config()
    return jsonify(config)


@config_bp.route("/config", methods=["POST"])
@login_required
@require_role("super_admin", "enterprise_admin")
def update_config_handler():
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400

    update_config_from_request(data)
    return jsonify({"success": True, "message": "Config saved"})
