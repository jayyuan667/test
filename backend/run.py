# -*- coding: utf-8 -*-
"""Entry point for running the Flask application."""

import os
import sys

# Ensure project root is in path so backend can be imported as a package
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

def main():
    from backend.services.startup_checks import run_startup_checks

    run_startup_checks()
    from backend.app import app

    print("=" * 50)
    print("PDF Process Analysis System")
    print("=" * 50)
    debug_mode = os.getenv("FLASK_DEBUG", "1") != "0"
    app.run(host="0.0.0.0", port=5190, debug=debug_mode, use_reloader=debug_mode, threaded=True)


if __name__ == "__main__":
    main()
