# -*- coding: utf-8 -*-
"""Unified API response helpers."""

from flask import jsonify


def ok(data=None, status=200):
    """Return a success response."""
    body = {"success": True}
    if data is not None:
        body["data"] = data
    return jsonify(body), status


def fail(code: str, message: str, status: int = 400, detail: dict = None):
    """Return an error response with a machine-readable code."""
    body = {"success": False, "error": {"code": code, "message": message}}
    if detail:
        body["error"]["detail"] = detail
    return jsonify(body), status


# Common error codes
ERR_FILE_MISSING = "FILE_MISSING"
ERR_FILE_TYPE = "FILE_TYPE"
ERR_TASK_NOT_FOUND = "TASK_NOT_FOUND"
ERR_TASK_STATUS = "TASK_STATUS"
ERR_CONFIG = "CONFIG_ERROR"
ERR_INTERNAL = "INTERNAL_ERROR"
ERR_VALIDATION = "VALIDATION_ERROR"
