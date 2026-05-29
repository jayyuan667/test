# -*- coding: utf-8 -*-
"""API routes module."""

from flask import Blueprint


def register_routes(app):
    """Register all API blueprints with the Flask app.

    Note: This function is called from app.py after shared state is injected.
    """
    from .upload import upload_bp
    from .batch import batch_bp
    from .status import status_bp
    from .events import events_bp
    from .result import result_bp
    from .history import history_bp
    from .config import config_bp
    from .export import export_bp
    from .health import health_bp
    from .image import image_bp
    from .library import library_bp
    from .kb_import import kb_import_bp

    app.register_blueprint(upload_bp, url_prefix="/api")
    app.register_blueprint(batch_bp, url_prefix="/api")
    app.register_blueprint(status_bp, url_prefix="/api")
    app.register_blueprint(events_bp, url_prefix="/api")
    app.register_blueprint(result_bp, url_prefix="/api")
    app.register_blueprint(history_bp, url_prefix="/api")
    app.register_blueprint(config_bp, url_prefix="/api")
    app.register_blueprint(export_bp, url_prefix="/api")
    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(image_bp, url_prefix="/api")
    app.register_blueprint(library_bp, url_prefix="/api")
    app.register_blueprint(kb_import_bp, url_prefix="/api")
