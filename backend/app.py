# -*- coding: utf-8 -*-
"""
Main Flask application - PDF Process Analysis System.

This is a thin facade that assembles all modules.
All business logic is in dedicated modules:
- config.py: Configuration management
- history.py: History file operations
- models.py: Data models
- pipeline/: PDF processing pipeline (pdf_converter, vision_analyzer, expert_judge, process_gen)
- api/: Flask API routes (upload, batch, status, events, result, history, config, export)
"""

import sys
import io
import os
import json
import uuid

# Fix stdout encoding for Chinese output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from flask import Flask, Response, jsonify, request, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler("backend.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

print("Pre-loading modules...")
logger.info("Starting backend service...")

# Import configuration and initialize (support package and direct execution)
try:
    from .config import init_config, ensure_poppler_path
except ImportError:
    from backend.config import init_config, ensure_poppler_path

# Initialize configuration from config.json to environment variables
init_config()
ensure_poppler_path()

# Create Flask app
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024
CORS(app, resources={r"/api/*": {"origins": "*"}})


@app.route("/api/startup_token")
def startup_token_route():
    return jsonify({"token": STARTUP_TOKEN})


@app.route("/dev/demo-industrial-console")
def dev_demo_industrial_console():
    """Serve the industrial demo page through Flask for hot-reload debugging."""
    template_path = os.path.join(BASE_DIR, "updated_front", "demo-industrial-console.html")
    if not os.path.exists(template_path):
        return Response("demo-industrial-console.html not found", status=404, mimetype="text/plain")

    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Cache-busting: use file mtime so browser always gets latest JS/CSS
    js_path = os.path.join(BASE_DIR, "updated_front", "js", "demo-industrial-console.js")
    js_mtime = int(os.path.getmtime(js_path)) if os.path.exists(js_path) else 0
    html = html.replace(
        'src="js/demo-industrial-console.js"',
        f'src="/dev/js/demo-industrial-console.js?v={js_mtime}"',
        1
    )
    css_path = os.path.join(BASE_DIR, "updated_front", "css", "industrial-console.css")
    css_mtime = int(os.path.getmtime(css_path)) if os.path.exists(css_path) else 0
    html = html.replace(
        'href="css/industrial-console.css"',
        f'href="/dev/css/industrial-console.css?v={css_mtime}"',
        1
    )

    bootstrap = (
        "<script>"
        f"window.__API_BASE__ = {json.dumps('/api')};"
        "window.__DEV_BACKEND_DEMO__ = true;"
        "</script>"
    )
    html = html.replace("</head>", f"{bootstrap}</head>", 1)
    return Response(html, mimetype="text/html")


@app.route("/dev/css/<path:filename>")
def dev_css(filename):
    """Serve demo CSS assets."""
    css_dir = os.path.join(BASE_DIR, "updated_front", "css")
    resp = send_from_directory(css_dir, filename)
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@app.route("/dev/js/<path:filename>")
def dev_js(filename):
    """Serve demo JS assets."""
    js_dir = os.path.join(BASE_DIR, "updated_front", "js")
    resp = send_from_directory(js_dir, filename)
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

# Shared state for tasks and events - injected into API modules
tasks = {}
event_data = {}
event_locks = {}

# Startup cleanup: mark tasks interrupted by previous process as cancelled
try:
    from .task_store import init_db, cancel_stale_tasks as _cancel_stale
except ImportError:
    from backend.task_store import init_db, cancel_stale_tasks as _cancel_stale
init_db()
_stale_count = _cancel_stale()
if _stale_count:
    logger.info("Startup: cancelled %d stale tasks from previous session", _stale_count)

STARTUP_TOKEN = uuid.uuid4().hex

# Import and inject shared state into all API modules (relative imports with fallback)
try:
    from .api.upload import set_shared_state as set_upload_shared
    from .api.batch import set_shared_state as set_batch_shared
    from .api.status import set_tasks as set_status_tasks
    from .api.events import set_shared_state as set_events_shared
    from .api.result import set_tasks as set_result_tasks
    from .api.export import set_tasks as set_export_tasks
    from .api.library import set_shared_state as set_library_shared
except ImportError:
    from backend.api.upload import set_shared_state as set_upload_shared
    from backend.api.batch import set_shared_state as set_batch_shared
    from backend.api.status import set_tasks as set_status_tasks
    from backend.api.events import set_shared_state as set_events_shared
    from backend.api.result import set_tasks as set_result_tasks
    from backend.api.export import set_tasks as set_export_tasks
    from backend.api.library import set_shared_state as set_library_shared

# All API modules share the same state
set_upload_shared(tasks, event_data, event_locks)
set_batch_shared(tasks, event_data, event_locks)
set_status_tasks(tasks)
set_events_shared(tasks, event_data, event_locks)
set_result_tasks(tasks)
set_export_tasks(tasks)
set_library_shared(tasks, event_data, event_locks)

# Register API routes
try:
    from .api import register_routes
except ImportError:
    from backend.api import register_routes

register_routes(app)

# Ensure directories exist
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
OUTPUT_FOLDER = os.path.join(BASE_DIR, "output")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

print("Modules loaded and app initialized")


if __name__ == "__main__":
    print("=" * 50)
    print("PDF Process Analysis System")
    print("=" * 50)
    debug_mode = os.getenv("FLASK_DEBUG", "1") != "0"
    app.config["TEMPLATES_AUTO_RELOAD"] = debug_mode
    app.run(host="0.0.0.0", port=5090, debug=debug_mode, use_reloader=debug_mode, threaded=True)
