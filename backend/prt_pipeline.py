# -*- coding: utf-8 -*-
"""PRT conversion and screenshot helpers."""

import json
import os
import random
import re
import shutil
import subprocess
import sys
import threading
import time
import zipfile
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

try:
    from .pipeline.geometry_analyzer import analyze_step_geometry
except ImportError:
    try:
        from backend.pipeline.geometry_analyzer import analyze_step_geometry
    except ImportError:
        from pipeline.geometry_analyzer import analyze_step_geometry


RETRYABLE_EXCEPTIONS = (
    requests.exceptions.SSLError,
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.HTTPError,
)


class PrtConversionError(RuntimeError):
    def __init__(self, stage: str, message: str, retryable: bool = False):
        super().__init__(message)
        self.stage = stage
        self.retryable = retryable


def _log_json_line(logfile: str, request_name: str, payload: dict):
    logdir = os.path.dirname(logfile)
    if logdir:
        os.makedirs(logdir, exist_ok=True)
    entry = {
        "request": request_name,
        "response": payload,
        "time": datetime.now().isoformat(),
    }
    with open(logfile, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _request_with_retry(logfile: str, stage: str, request_fn, attempts: int = 3):
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            res = request_fn()
            # 5xx server errors are retryable; 4xx client errors are not
            if res.status_code >= 500:
                raise requests.exceptions.HTTPError(
                    f"{res.status_code} Server Error for url: {res.url}", response=res
                )
            return res
        except RETRYABLE_EXCEPTIONS as exc:
            last_error = exc
            _log_json_line(logfile, stage, {
                "error_type": type(exc).__name__,
                "error": str(exc),
                "attempt": attempt,
                "retrying": attempt < attempts,
            })
            if attempt >= attempts:
                break
            time.sleep((2 ** (attempt - 1)) + random.uniform(0, 0.3))
    assert last_error is not None
    raise PrtConversionError(stage, f"{stage} failed after retries: {last_error}", retryable=True) from last_error


def _load_freecad_modules():
    # Suppress Qt threading warnings (QObject::setParent cross-thread) that are
    # harmless noise when FreeCAD GUI runs from a background thread.
    os.environ["QT_LOGGING_RULES"] = "qt.core.qobject*=false;qt*.warning=false"

    try:
        from .config import get_freecad_paths
    except ImportError:
        from backend.config import get_freecad_paths
    lib_paths = get_freecad_paths()
    for path in lib_paths:
        if path and os.path.exists(path) and path not in sys.path:
            sys.path.append(path)

    try:
        from .config import get_freecad_qt_plugin_paths
    except ImportError:
        from backend.config import get_freecad_qt_plugin_paths
    qt_plugin_candidates = get_freecad_qt_plugin_paths()
    for plugin_root in qt_plugin_candidates:
        platforms_dir = os.path.join(plugin_root, "platforms")
        if os.path.exists(platforms_dir):
            os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", platforms_dir)
            os.environ.setdefault("QT_PLUGIN_PATH", plugin_root)
            break

    try:
        import FreeCAD as App
        import FreeCADGui as Gui
        import Part
        import Import
    except ImportError as exc:
        raise RuntimeError("FreeCAD modules not found; PRT conversion is unavailable") from exc

    return App, Gui, Part, Import


def _onshape_credentials():
    credential = os.getenv("onshape_credentials")
    did = os.getenv("onshape_did")
    wid = os.getenv("onshape_wid")
    if not credential:
        raise RuntimeError("missing environment variable: onshape_credentials")
    if not (did and wid):
        raise RuntimeError("missing environment variable: onshape_did or onshape_wid")
    return credential, did, wid


class OnshapeBasicClient:
    def __init__(self, logfile: str = "logs/onshape_api.jsonl"):
        self.credential, self.did, self.wid = _onshape_credentials()
        self.base_url = "https://cad.onshape.com"
        self.logfile = logfile

    def upload_file(self, file_path: str):
        url = f"{self.base_url}/api/v6/translations/d/{self.did}/w/{self.wid}"
        headers = {
            "accept": "application/json;charset=UTF-8; qs=0.09",
            "Authorization": f"Basic {self.credential}",
        }
        data = {
            "storeInDocument": "true",
            "flattenAssemblies": "true",
        }

        def _send_request():
            with open(file_path, "rb") as f:
                files = {"file": (os.path.basename(file_path), f)}
                return requests.post(url, headers=headers, data=data, files=files, timeout=60)

        res = _request_with_retry(self.logfile, "upload_file", _send_request)
        resp_data = res.json() if res.ok else res.text
        _log_json_line(self.logfile, "upload_file", resp_data if isinstance(resp_data, dict) else {"response": resp_data})
        res.raise_for_status()
        return resp_data.get("id")

    def start_translation(self, eid: str, format_name: str = "STEP"):
        format_lower = format_name.lower()
        url = f"{self.base_url}/api/v11/partstudios/d/{self.did}/w/{self.wid}/e/{eid}/export/{format_lower}"
        headers = {
            "Accept": "application/json;charset=UTF-8; qs=0.09",
            "Content-Type": "application/json;charset=UTF-8; qs=0.09",
            "Authorization": f"Basic {self.credential}",
        }
        payload = {"storeInDocument": True}

        res = _request_with_retry(
            self.logfile,
            "start_translation",
            lambda: requests.post(url, headers=headers, json=payload, timeout=60),
        )
        resp_data = res.json() if res.ok else res.text
        _log_json_line(self.logfile, "start_translation", resp_data if isinstance(resp_data, dict) else {"response": resp_data})
        res.raise_for_status()
        return res.json().get("id")

    def poll_status(self, tid: str):
        url = f"{self.base_url}/api/v14/translations/{tid}"
        headers = {
            "accept": "application/json;charset=UTF-8; qs=0.09",
            "Authorization": f"Basic {self.credential}",
        }

        while True:
            time.sleep(5)
            res = _request_with_retry(
                self.logfile,
                "poll_status",
                lambda: requests.get(url, headers=headers, timeout=30),
            )
            resp_data = res.json() if res.ok else res.text
            _log_json_line(self.logfile, "poll_status", resp_data if isinstance(resp_data, dict) else {"response": resp_data})
            res.raise_for_status()
            data = res.json()
            state = data.get("requestState")
            if state == "DONE":
                result_ids = data.get("resultElementIds", [])
                return result_ids[0] if result_ids else None
            if state == "FAILED":
                print(f"Translation failed: {data.get('failureReason')}")
                return None

    def download(self, tid: str, output_path: str):
        url = f"{self.base_url}/api/v6/blobelements/d/{self.did}/w/{self.wid}/e/{tid}"
        headers = {
            "accept": "application/octet-stream",
            "Authorization": f"Basic {self.credential}",
        }

        res = _request_with_retry(
            self.logfile,
            "download",
            lambda: requests.get(url, headers=headers, stream=True, timeout=60),
        )
        _log_json_line(self.logfile, "download", {"status_code": res.status_code, "action": "downloading_binary_stream"})
        res.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in res.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)


def _merge_step_folder(folder: str, output_step: str):
    App, _, Part, Import = _load_freecad_modules()
    valid_extensions = {".step", ".stp"}
    files = [f for f in os.listdir(folder) if os.path.splitext(f)[1].lower() in valid_extensions]
    if not files:
        print(f"No STEP files found in {folder}")
        return False

    doc_name = "MergeDoc"
    doc = App.newDocument(doc_name)
    export_objects = []
    try:
        for filename in files:
            file_path = os.path.join(folder, filename)
            try:
                shape = Part.read(file_path)
                if shape and not shape.isNull() and shape.isValid():
                    obj = doc.addObject("Part::Feature", filename.replace(".", "_"))
                    obj.Shape = shape
                    export_objects.append(obj)
            except Exception as exc:
                print(f"Failed to read {filename}: {exc}")

        if not export_objects:
            print("No valid parts loaded")
            return False

        Import.export(export_objects, output_step)
        return True
    finally:
        try:
            App.closeDocument(doc_name)
        except Exception:
            pass


def zip2step(file_path: str, output_step: str, clean: bool = True):
    target_folder = os.path.splitext(file_path)[0]
    if not os.path.exists(target_folder):
        os.makedirs(target_folder)

    if clean or not os.path.exists(target_folder):
        with zipfile.ZipFile(file_path, "r") as zip_ref:
            zip_ref.extractall(target_folder)

    try:
        success = _merge_step_folder(target_folder, output_step)
    except RuntimeError:
        # FreeCAD not available — use first .step/.stp in the extracted zip directly
        step_candidates = sorted(
            [f for f in os.listdir(target_folder) if f.lower().endswith(('.step', '.stp'))]
        )
        if step_candidates:
            shutil.copy2(os.path.join(target_folder, step_candidates[0]), output_step)
            print(f"[zip2step] FreeCAD unavailable, using raw step: {step_candidates[0]}")
            success = True
        else:
            print("[zip2step] FreeCAD unavailable and no step file found in zip")
            success = False

    if clean and os.path.exists(target_folder):
        shutil.rmtree(target_folder)

    return success


def run_conversion(input_path: str, output_zip: str, output_step: str) -> bool:
    client = OnshapeBasicClient()
    try:
        upload_tid = client.upload_file(input_path)
        eid = client.poll_status(upload_tid)
        if not eid:
            raise PrtConversionError("upload", "conversion failed: missing element id")
        export_id = client.start_translation(eid)
        dls_eid = client.poll_status(export_id)
        if not dls_eid:
            raise PrtConversionError("export", "export failed: missing blob element id")
        client.download(dls_eid, output_zip)
        return zip2step(output_zip, output_step)
    except PrtConversionError:
        raise
    except Exception as exc:
        raise PrtConversionError("workflow", str(exc), retryable=False) from exc


_WORKER_SCRIPT = Path(__file__).parent / "pipeline" / "freecad_worker.py"
_CREO_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
_creo_lock = threading.Lock()  # only one Creo process at a time

def _creo_exe() -> str:
    return os.getenv("CREO_EXE", "")

def _creo_base_dir() -> Path:
    return Path(os.getenv("CREO_BASE_DIR", r"D:\project\DLL2"))

def _creo_out_dir() -> Path:
    return Path(os.getenv("CREO_OUT_DIR", r"D:\project\DLL2\out"))

def _creo_task_file() -> Path:
    return _creo_base_dir() / "task.txt"

def _creo_done_file() -> Path:
    return _creo_out_dir() / "done.txt"


def _clean_creo_out_directory():
    creo_out = _creo_out_dir()
    if creo_out.exists():
        for item in creo_out.iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
    else:
        creo_out.mkdir(parents=True, exist_ok=True)


def _clean_creo_trail_files():
    """Delete accumulated trail files so Creo skips the 'replay trail?' dialog."""
    base = _creo_base_dir()
    if not base.exists():
        return
    count = 0
    for f in base.iterdir():
        if f.is_file() and f.name.startswith("trail.txt"):
            try:
                f.unlink()
                count += 1
            except OSError:
                pass
    if count:
        print(f"[creo] 已删除 {count} 个 trail 文件")


def _normalize_prt_path(prt_path: str) -> tuple[str, Path | None]:
    """Return (path_to_pass_to_dll, temp_copy_or_None).

    Creo model names must be ≤31 chars and contain only A-Za-z0-9_.
    UUID-prefixed upload filenames (e.g. 'abc123-..._part.prt.3') contain
    hyphens that cause ProMdlRetrieve to crash.  We always copy the source
    to CREO_BASE_DIR/creo_task.prt — a guaranteed-safe 9-char model name.
    Creo runs serially in this pipeline so the fixed name is safe.
    """
    prt = Path(prt_path).resolve()

    is_prt = prt.suffix.lower() == ".prt"
    is_versioned = prt.with_suffix("").suffix.lower() == ".prt"
    if not is_prt and not is_versioned:
        print(f"[creo] 警告: 未识别的 PRT 扩展名 {prt.suffix!r}，直接传入")
        return str(prt), None

    base = _creo_base_dir()
    base.mkdir(parents=True, exist_ok=True)
    temp = base / "creo_task.prt"
    shutil.copy2(prt, temp)
    print(f"[creo] PRT 副本: {prt.name} → {temp.name}")
    return str(temp), temp


# ── Win32 helpers for Creo dialog automation ──────────────────────────────────
if os.name == "nt":
    import ctypes
    import ctypes.wintypes as _W

    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, _W.HWND, _W.LPARAM)

    _INPUT_MOUSE = 0
    _INPUT_KEYBOARD = 1
    _MOUSEEVENTF_MOVE = 0x0001
    _MOUSEEVENTF_LEFTDOWN = 0x0002
    _MOUSEEVENTF_LEFTUP = 0x0004
    _MOUSEEVENTF_ABSOLUTE = 0x8000
    _KEYEVENTF_KEYUP = 0x0002
    _VK_RETURN = 0x0D

    class _MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                    ("mouseData", _W.DWORD), ("dwFlags", _W.DWORD),
                    ("time", _W.DWORD), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

    class _KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", _W.WORD), ("wScan", _W.WORD),
                    ("dwFlags", _W.DWORD), ("time", _W.DWORD),
                    ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

    class _INPUT_UNION(ctypes.Union):
        _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT)]

    class _INPUT(ctypes.Structure):
        _fields_ = [("type", _W.DWORD), ("_u", _INPUT_UNION)]

    def _creo_enum_windows(substring: str) -> list:
        found = []

        @_WNDENUMPROC
        def cb(hwnd, _):
            buf = ctypes.create_unicode_buffer(512)
            _user32.GetWindowTextW(hwnd, buf, 512)
            if substring in buf.value:
                r = _W.RECT()
                _user32.GetWindowRect(hwnd, ctypes.byref(r))
                found.append((hwnd, buf.value, r))
            return True

        _user32.EnumWindows(cb, 0)
        return found

    def _creo_send_click(x: int, y: int):
        sw = _user32.GetSystemMetrics(0)
        sh = _user32.GetSystemMetrics(1)
        nx = int(x * 65535 / sw)
        ny = int(y * 65535 / sh)
        mk = lambda flags: _INPUT(type=_INPUT_MOUSE,
                                   _u=_INPUT_UNION(mi=_MOUSEINPUT(
                                       dx=nx, dy=ny, mouseData=0, dwFlags=flags,
                                       time=0, dwExtraInfo=None)))
        arr = (_INPUT * 3)(
            mk(_MOUSEEVENTF_MOVE | _MOUSEEVENTF_ABSOLUTE),
            mk(_MOUSEEVENTF_LEFTDOWN | _MOUSEEVENTF_ABSOLUTE),
            mk(_MOUSEEVENTF_LEFTUP | _MOUSEEVENTF_ABSOLUTE),
        )
        _user32.SendInput(3, arr, ctypes.sizeof(_INPUT))

    def _creo_send_enter():
        mk = lambda flags: _INPUT(type=_INPUT_KEYBOARD,
                                   _u=_INPUT_UNION(ki=_KEYBDINPUT(
                                       wVk=_VK_RETURN, wScan=0, dwFlags=flags,
                                       time=0, dwExtraInfo=None)))
        arr = (_INPUT * 2)(mk(0), mk(_KEYEVENTF_KEYUP))
        _user32.SendInput(2, arr, ctypes.sizeof(_INPUT))

    def _creo_force_click(hwnd: int, x: int, y: int):
        """AttachThreadInput → BringWindowToTop → SetForegroundWindow → SendInput click + Enter."""
        tid_t = _user32.GetWindowThreadProcessId(hwnd, None)
        tid_s = _kernel32.GetCurrentThreadId()
        _user32.AttachThreadInput(tid_s, tid_t, True)
        try:
            _user32.BringWindowToTop(hwnd)
            _user32.SetForegroundWindow(hwnd)
            _user32.SetFocus(hwnd)
            time.sleep(0.15)
            _creo_send_click(x, y)
            time.sleep(0.12)
            _creo_send_enter()
        finally:
            _user32.AttachThreadInput(tid_s, tid_t, False)

    def _creo_pick_dialog(title_exact: str, max_w: int, max_h: int):
        """Find a small top-level dialog with exact title match; return (hwnd, rect) or (0, None)."""
        for hwnd, title, r in _creo_enum_windows(title_exact):
            w = r.right - r.left
            h = r.bottom - r.top
            if title.strip() == title_exact and w < max_w and h < max_h:
                return hwnd, r
        return 0, None
else:
    _user32 = None
    _kernel32 = None

    def _creo_enum_windows(substring: str) -> list:
        return []

    def _creo_send_click(x: int, y: int):
        return None

    def _creo_send_enter():
        return None

    def _creo_force_click(hwnd: int, x: int, y: int):
        return None

    def _creo_pick_dialog(title_exact: str, max_w: int, max_h: int):
        return 0, None
# ──────────────────────────────────────────────────────────────────────────────


def _auto_confirm_creo_dialogs(stop_event, timeout: int = 120):
    """Background thread: auto-click Creo startup dialogs (AttachThreadInput + SendInput)."""
    clicked_handles: set = set()
    deadline = time.time() + timeout

    # Button relative positions per dialog title (rel_x, rel_y) — candidates tried in order
    _DIALOG_BUTTONS = {
        "检索": [(0.75, 0.87), (0.83, 0.87), (0.70, 0.85)],   # crash-recovery → 继续
        "选取启动目录": [(0.35, 0.87), (0.50, 0.87), (0.35, 0.82)],  # startup dir → 确定
    }

    while not stop_event.is_set() and time.time() < deadline:
        for dialog_title, candidates in _DIALOG_BUTTONS.items():
            hwnd, r = _creo_pick_dialog(dialog_title, max_w=700, max_h=500)
            if not hwnd or hwnd in clicked_handles:
                continue
            w = r.right - r.left
            h = r.bottom - r.top
            for rel_x, rel_y in candidates:
                btn_x = r.left + int(w * rel_x)
                btn_y = r.top  + int(h * rel_y)
                _creo_force_click(hwnd, btn_x, btn_y)
                time.sleep(0.4)
                hwnd2, _ = _creo_pick_dialog(dialog_title, max_w=700, max_h=500)
                if not hwnd2:
                    print(f"[creo-auto] '{dialog_title}' 已关闭 rel=({rel_x:.2f},{rel_y:.2f})")
                    clicked_handles.add(hwnd)
                    break
            else:
                clicked_handles.add(hwnd)
        time.sleep(0.4)


def _write_creo_task_file(prt_path: str):
    prt = Path(prt_path).resolve()
    if not prt.exists():
        raise FileNotFoundError(f"PRT 文件不存在: {prt}")

    base = _creo_base_dir()
    base.mkdir(parents=True, exist_ok=True)
    _creo_task_file().write_text(str(prt), encoding="utf-8")
    print(f"[creo] task.txt 已写入: {prt}")


def _start_creo() -> subprocess.Popen:
    exe = _creo_exe()
    base = _creo_base_dir()
    print(f"[creo] 启动 Creo: {exe}")
    return subprocess.Popen([exe], cwd=str(base))


def _wait_for_creo_done_file(timeout: int = 180) -> bool:
    print("[creo] 等待 done.txt ...")
    done_file = _creo_done_file()
    start_time = time.time()
    while time.time() - start_time < timeout:
        if done_file.exists():
            print("[creo] 检测到 done.txt")
            return True
        time.sleep(1)
    print("[creo] 等待 done.txt 超时")
    return False


def _close_creo(proc: subprocess.Popen):
    # Give Creo a chance to exit cleanly (DLL may call ProEngineerEnd itself)
    try:
        proc.wait(timeout=10)
        print("[creo] Creo 已自行退出")
        return
    except subprocess.TimeoutExpired:
        pass
    print("[creo] 正在强制关闭 Creo...")
    try:
        subprocess.run(
            ["taskkill", "/f", "/t", "/pid", str(proc.pid)],
            capture_output=True,
            check=True,
        )
        print("[creo] Creo 已关闭")
    except subprocess.CalledProcessError as exc:
        print(f"[creo] 关闭 Creo 失败: {exc}")


def run_creo_capture(prt_path: str) -> bool:
    import threading
    if os.name != "nt":
        print("[creo] 非 Windows 环境，跳过 Creo 截图")
        return False
    norm_path, temp_copy = _normalize_prt_path(prt_path)
    try:
        _clean_creo_trail_files()
        _clean_creo_out_directory()
        _write_creo_task_file(norm_path)
        proc = _start_creo()

        # Auto-click startup dialogs in background
        stop_event = threading.Event()
        dialog_thread = threading.Thread(
            target=_auto_confirm_creo_dialogs,
            args=(stop_event,),
            daemon=True,
        )
        dialog_thread.start()

        time.sleep(5)
        done = _wait_for_creo_done_file()
        stop_event.set()
        _close_creo(proc)
        if done:
            print("[creo] Creo 截图任务完成")
        return done
    except Exception as exc:
        print(f"[creo] Creo capture failed: {exc}")
        return False
    finally:
        if temp_copy and temp_copy.exists():
            try:
                temp_copy.unlink()
            except OSError:
                pass


def collect_creo_output(dest_dir: str, zhushi_dest: str) -> bool:
    creo_out = _creo_out_dir()
    if not creo_out.exists():
        print(f"[creo] OUT_DIR 不存在: {creo_out}")
        return False

    dest_path = Path(dest_dir)
    zhushi_path = Path(zhushi_dest)
    dest_path.mkdir(parents=True, exist_ok=True)

    copied_images = 0
    for item in creo_out.iterdir():
        if item.is_file() and item.suffix.lower() in _CREO_IMAGE_EXTENSIONS:
            shutil.copy2(item, dest_path / item.name)
            copied_images += 1
            print(f"[creo] 复制截图: {item.name}")

    zhushi_dir = creo_out / "zhushi"
    zhushi_src = None
    if zhushi_dir.exists():
        candidates = [f for f in zhushi_dir.iterdir() if f.suffix.lower() == ".txt"]
        if candidates:
            zhushi_src = candidates[0]
    if zhushi_src:
        shutil.copy2(zhushi_src, zhushi_path)
        print(f"[creo] 复制注释文本: {zhushi_src.name} -> {zhushi_path}")
    else:
        print(f"[creo] 注释文本不存在，跳过: {creo_out / 'zhushi'}")

    print(f"[creo] 共复制 {copied_images} 张截图到 {dest_path}")
    return copied_images > 0


def capture_creo_views(prt_path: str, output_dir: str) -> tuple[bool, str, str]:
    creo_dir = Path(output_dir) / "creo_views"
    zhushi_path = creo_dir / "zhushi.txt"

    exe = _creo_exe()
    print(f"[creo] CREO_EXE={exe!r}  CREO_BASE_DIR={_creo_base_dir()}  CREO_OUT_DIR={_creo_out_dir()}")
    if not exe:
        print("[creo] CREO_EXE 未配置，跳过 Creo 截图")
        return False, str(creo_dir), str(zhushi_path)

    existing_images = [
        p for p in creo_dir.iterdir()
        if p.is_file() and p.suffix.lower() in _CREO_IMAGE_EXTENSIONS
    ] if creo_dir.exists() else []
    if existing_images:
        print(f"[creo] Existing Creo views found, skipping capture: {creo_dir}")
        return True, str(creo_dir), str(zhushi_path)

    with _creo_lock:
        captured = run_creo_capture(prt_path)
        if not captured:
            return False, str(creo_dir), str(zhushi_path)
        copied = collect_creo_output(str(creo_dir), str(zhushi_path))
    return copied, str(creo_dir), str(zhushi_path)


def read_creo_zhushi(zhushi_path: str) -> str:
    if not zhushi_path:
        return ""
    path = Path(zhushi_path)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def is_creo_configured() -> bool:
    return bool(os.getenv("CREO_EXE", "").strip())




def create_screenshot_glb(creo_views_dir: str, output_dir: str) -> str:
    """Build a lightweight GLB from Creo screenshot PNGs — no FreeCAD needed.

    Creates up to 3 textured quads (front/right/top) arranged as orthographic
    views in 3-D space.  Returns the path to model.glb.
    Raises ValueError when no PNG screenshots are found.
    """
    import struct
    import json as _json
    import io
    from PIL import Image as _Image

    creo_dir = Path(creo_views_dir)
    if not creo_dir.exists():
        raise ValueError(f"creo_views_dir not found: {creo_views_dir}")

    VIEW_PATTERNS = [
        ("front", ["主视图"]),
        ("right", ["右视图", "左视图"]),
        ("top",   ["俯视图", "横剖视图"]),
    ]
    classified: dict = {}
    extras: list = []
    for img_path in sorted(creo_dir.glob("*.png")) + sorted(creo_dir.glob("*.jpg")):
        name = img_path.name
        matched = False
        for vid, kwds in VIEW_PATTERNS:
            if any(k in name for k in kwds) and vid not in classified:
                classified[vid] = str(img_path)
                matched = True
                break
        if not matched:
            extras.append(str(img_path))

    views: list = []  # [(label, path)]
    for vid in ["front", "right", "top"]:
        if vid in classified:
            views.append((vid, classified[vid]))
    for extra in extras:
        if len(views) >= 3:
            break
        views.append(("extra", extra))
    if not views:
        raise ValueError(f"No PNG screenshots found in {creo_views_dir}")

    # Binary accumulator — all data 4-byte aligned
    bin_chunks: list = []

    def _append(data: bytes) -> int:
        offset = sum(len(c) for c in bin_chunks)
        bin_chunks.append(data)
        pad = (-len(data)) % 4
        if pad:
            bin_chunks.append(b"\x00" * pad)
        return offset

    accessors: list = []
    buffer_views: list = []
    images_gltf: list = []
    textures_gltf: list = []
    materials_gltf: list = []
    meshes_gltf: list = []
    nodes_gltf: list = []

    def _bv(data: bytes, target=None) -> int:
        off = _append(data)
        bv: dict = {"buffer": 0, "byteOffset": off, "byteLength": len(data)}
        if target:
            bv["target"] = target
        buffer_views.append(bv)
        return len(buffer_views) - 1

    def _acc(bv_idx, comp, count, typ, mn=None, mx=None) -> int:
        a: dict = {"bufferView": bv_idx, "componentType": comp, "count": count, "type": typ}
        if mn is not None:
            a["min"] = mn; a["max"] = mx
        accessors.append(a)
        return len(accessors) - 1

    GAP = 0.15
    INDICES = [0, 1, 2, 0, 2, 3]
    UVS = [(0.0, 1.0), (1.0, 1.0), (1.0, 0.0), (0.0, 0.0)]

    for mi, (label, img_path) in enumerate(views):
        with _Image.open(img_path) as img:
            w, h = img.size
            asp = h / w
            buf = io.BytesIO()
            img.convert("RGBA").save(buf, format="PNG")
            png_bytes = buf.getvalue()

        hw, hh = 1.0, asp
        if label == "front":
            verts = [(-hw, -hh, 0.0), (hw, -hh, 0.0), (hw, hh, 0.0), (-hw, hh, 0.0)]
        elif label == "right":
            x = hw * 2 + GAP
            verts = [(x, -hh, -hw), (x, -hh, hw), (x, hh, hw), (x, hh, -hw)]
        else:
            y = hh * 2 + GAP
            verts = [(-hw, y, -hh), (hw, y, -hh), (hw, y, hh), (-hw, y, hh)]

        xs = [v[0] for v in verts]; ys = [v[1] for v in verts]; zs = [v[2] for v in verts]
        acc_pos = _acc(_bv(struct.pack(f"<{len(verts)*3}f", *[c for v in verts for c in v]), 34962),
                       5126, 4, "VEC3", [min(xs), min(ys), min(zs)], [max(xs), max(ys), max(zs)])
        acc_uv  = _acc(_bv(struct.pack(f"<{len(UVS)*2}f",  *[c for uv in UVS for c in uv]), 34962),
                       5126, 4, "VEC2")
        acc_idx = _acc(_bv(struct.pack("<6H", *INDICES), 34963), 5123, 6, "SCALAR")

        bv_img = _bv(png_bytes)
        images_gltf.append({"bufferView": bv_img, "mimeType": "image/png"})
        textures_gltf.append({"sampler": 0, "source": mi})
        materials_gltf.append({
            "name": label,
            "pbrMetallicRoughness": {
                "baseColorTexture": {"index": mi},
                "metallicFactor": 0.0,
                "roughnessFactor": 1.0,
            },
            "doubleSided": True,
        })
        meshes_gltf.append({
            "name": label,
            "primitives": [{"attributes": {"POSITION": acc_pos, "TEXCOORD_0": acc_uv},
                            "indices": acc_idx, "material": mi, "mode": 4}],
        })
        nodes_gltf.append({"mesh": mi, "name": label})

    bin_data = b"".join(bin_chunks)
    gltf_dict = {
        "asset": {"version": "2.0", "generator": "creo-screenshot-glb"},
        "scene": 0,
        "scenes": [{"nodes": list(range(len(nodes_gltf)))}],
        "nodes": nodes_gltf, "meshes": meshes_gltf, "materials": materials_gltf,
        "textures": textures_gltf, "images": images_gltf,
        "samplers": [{"magFilter": 9729, "minFilter": 9987, "wrapS": 33648, "wrapT": 33648}],
        "accessors": accessors, "bufferViews": buffer_views,
        "buffers": [{"byteLength": len(bin_data)}],
    }
    j = _json.dumps(gltf_dict, separators=(",", ":")).encode("utf-8")
    j += b" " * ((-len(j)) % 4)
    total = 12 + 8 + len(j) + 8 + len(bin_data)
    glb = struct.pack("<III", 0x46546C67, 2, total)
    glb += struct.pack("<II", len(j),        0x4E4F534A)  # JSON chunk
    glb += j
    glb += struct.pack("<II", len(bin_data), 0x004E4942)  # BIN chunk
    glb += bin_data

    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, "model.glb")
    with open(out_path, "wb") as fh:
        fh.write(glb)
    print(f"[screenshot-glb] {len(views)} view(s) → {out_path} ({len(glb):,} bytes)")
    return out_path


def _run_freecad_worker(cmd: str, step_file: str, output_dir: str, timeout: int = 300) -> subprocess.CompletedProcess:
    """
    Run a FreeCAD operation in an isolated subprocess.

    Using a subprocess ensures Qt/GUI objects are always created on that
    process's main thread, which eliminates QObject::setParent cross-thread
    warnings and guarantees clean FreeCAD document state for every call.
    """
    try:
        from .config import get_freecad_paths, get_freecad_qt_plugin_paths
    except ImportError:
        from backend.config import get_freecad_paths, get_freecad_qt_plugin_paths

    env = os.environ.copy()
    env["FREECAD_PATHS_JSON"] = json.dumps(get_freecad_paths())

    for plugin_root in get_freecad_qt_plugin_paths():
        platforms_dir = os.path.join(plugin_root, "platforms")
        if os.path.exists(platforms_dir):
            env.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", platforms_dir)
            env.setdefault("QT_PLUGIN_PATH", plugin_root)
            break

    return subprocess.run(
        [sys.executable, str(_WORKER_SCRIPT), cmd, step_file, output_dir],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


def capture_three_views(step_file: str, output_dir: str) -> bool:
    """Capture front/top/right views of a STEP file via an isolated subprocess."""
    if not os.path.exists(step_file):
        raise FileNotFoundError(f"{step_file} must exist")

    print(f"[shot] starting FreeCAD capture subprocess: {step_file}")
    try:
        result = _run_freecad_worker("capture_views", step_file, output_dir)
    except subprocess.TimeoutExpired:
        print("[shot] FreeCAD capture timed out")
        return False
    except Exception as exc:
        print(f"[shot] subprocess error: {exc}")
        return False

    if result.stdout:
        print(result.stdout, end="", flush=True)
    if result.returncode != 0:
        err = result.stderr.strip()
        print(f"[shot] worker exited {result.returncode}: {err[:500]}")
        return False
    return True


def export_gltf(step_file: str, output_dir: str, creo_views_dir: str = "") -> str:
    """Export to GLB — Creo screenshots first, FreeCAD STEP as fallback.

    If creo_views_dir contains PNG screenshots, generate a lightweight
    textured-quad GLB without launching FreeCAD.  Falls back to the
    FreeCAD STEP→GLB pipeline only when no screenshots are available.
    """
    # Primary path: screenshot-based GLB (no FreeCAD subprocess)
    if creo_views_dir:
        try:
            return create_screenshot_glb(creo_views_dir, output_dir)
        except Exception as _e:
            print(f"[export_gltf] screenshot GLB failed ({_e}), falling back to FreeCAD")

    # Fallback: FreeCAD STEP→GLB
    if not os.path.exists(step_file):
        raise FileNotFoundError(f"No screenshots and no STEP file at {step_file}")

    try:
        result = _run_freecad_worker("export_gltf", step_file, output_dir)
    except subprocess.TimeoutExpired:
        raise RuntimeError("glTF export timed out")

    if result.returncode != 0:
        raise RuntimeError(f"glTF export failed: {result.stderr.strip()[:500]}")

    for line in result.stdout.splitlines():
        if line.startswith("GLTF_PATH:"):
            return line[len("GLTF_PATH:"):]

    gltf_path = os.path.join(output_dir, "model.glb")
    if os.path.exists(gltf_path):
        return gltf_path
    raise RuntimeError("glTF file not found after export")


def extract_geometry_features(step_file: str) -> str:
    """Extract geometric features from STEP file as structured text."""
    try:
        from .geometry_analyzer import extract_features_from_step
    except ImportError:
        try:
            from backend.pipeline.geometry_analyzer import extract_features_from_step
        except ImportError:
            from pipeline.geometry_analyzer import extract_features_from_step
    return extract_features_from_step(step_file)


def extract_prt_name(filename: str) -> str:
    stem = Path(filename or "").stem.strip()
    return stem or "prt_model"


def prepare_prt_artifacts(prt_path: str, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    source_name = os.path.basename(prt_path)
    step_path = os.path.join(output_dir, "model.step")
    zip_path = os.path.join(output_dir, "model.zip")
    views_dir = output_dir

    # Thread A: OnShape conversion → STEP only (FreeCAD views deferred below)
    _a_exc: list = []

    def _thread_a():
        try:
            if not os.path.exists(step_path):
                run_conversion(prt_path, zip_path, step_path)
        except Exception as exc:
            _a_exc.append(exc)

    # Thread B: Creo capture (only needs PRT, independent of STEP)
    _b_result: list = []
    _b_exc: list = []

    def _thread_b():
        try:
            _b_result.extend(capture_creo_views(prt_path, output_dir))
        except Exception as exc:
            _b_exc.append(exc)

    ta = threading.Thread(target=_thread_a, daemon=True, name="prt-thread-a")
    tb = threading.Thread(target=_thread_b, daemon=True, name="prt-thread-b")
    ta.start()
    tb.start()
    ta.join()
    tb.join()

    if _a_exc:
        raise _a_exc[0]
    if _b_exc:
        print(f"[prepare_prt_artifacts] Creo thread failed: {_b_exc[0]}")
    if not os.path.exists(step_path):
        raise RuntimeError("STEP artifact was not generated after conversion")

    creo_generated, creo_views_dir, zhushi_path = _b_result or (False, str(Path(output_dir) / "creo_views"), "")

    # FreeCAD three-view rendering: skip when Creo already produced screenshots
    # (VLM uses Creo views preferentially; FreeCAD views are only needed as fallback)
    view_paths = [os.path.join(views_dir, f"{name}.png") for name in ("front", "right", "top")]
    if creo_generated:
        views_generated = False  # FreeCAD views skipped — Creo views will be used by VLM
        view_paths = []
        print("[prepare_prt_artifacts] Creo views available — skipping FreeCAD capture")
    else:
        try:
            capture_three_views(step_path, views_dir)
        except Exception as _fc_exc:
            print(f"[prepare_prt_artifacts] FreeCAD capture failed: {_fc_exc}")
        views_generated = all(os.path.isfile(p) for p in view_paths)
        if not views_generated:
            print("[prepare_prt_artifacts] FreeCAD views unavailable")
            view_paths = []

    # geo_data: computed here so process generation can read from cache
    geo_data = None
    try:
        _geo = analyze_step_geometry(step_path)
        if "error" not in _geo:
            geo_data = _geo
    except Exception as _geo_exc:
        print(f"[prepare_prt_artifacts] geo_data skipped: {_geo_exc}")

    zhushi_text = read_creo_zhushi(zhushi_path)

    return {
        "source_name": source_name,
        "step_path": step_path,
        "zip_path": zip_path,
        "views_dir": views_dir,
        "view_paths": view_paths,
        "views_generated": views_generated,
        "creo_views_dir": creo_views_dir,
        "creo_views_generated": creo_generated,
        "creo_zhushi_path": zhushi_path,
        "creo_zhushi_text": zhushi_text,
        "geo_data": geo_data,
    }
