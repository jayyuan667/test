# -*- coding: utf-8 -*-
"""Health check endpoint."""

from flask import Blueprint, jsonify
from datetime import datetime
import uuid

health_bp = Blueprint("health", __name__)

# 进程启动时生成一次；重启后变化，前端用此检测后端是否重启
_STARTUP_TOKEN = str(uuid.uuid4())


@health_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})


@health_bp.route("/startup_token", methods=["GET"])
def startup_token():
    return jsonify({"token": _STARTUP_TOKEN})


@health_bp.route("/system/capabilities", methods=["GET"])
def system_capabilities():
    from backend.services.capabilities import collect_capabilities

    return jsonify(collect_capabilities())
