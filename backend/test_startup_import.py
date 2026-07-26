import importlib
import sys


def test_backend_app_imports_without_windows_win32_apis():
    sys.modules.pop("backend.app", None)
    sys.modules.pop("backend.prt_pipeline", None)
    importlib.import_module("backend.app")
