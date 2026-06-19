# Runtime Environment Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将项目统一为可复现的 Python 3.11.15 + uv 环境，并让 PDF、YOLO、Creo、FreeCAD 等能力通过统一检测接口按核心能力或可选降级规则运行。

**Architecture:** `pyproject.toml` 是唯一手工维护的依赖源，`uv.lock` 锁定跨平台版本，`requirements.txt` 仅由 uv 导出。新增无副作用的能力检测服务和启动前检查服务；PDF上传在创建任务前执行能力门禁，YOLO优先ONNX并保留人工标注降级。平台脚本、文档与CI统一使用同一环境契约。

**Tech Stack:** Python 3.11.15、uv 0.11.22、Flask、PyMuPDF、pdf2image、ONNX Runtime、Ultralytics（可选）、pytest、GitHub Actions、React/Vite。

## Global Constraints

- Python固定为`3.11.15`，项目范围为`>=3.11,<3.12`。
- `pyproject.toml`是唯一手工维护的Python依赖清单。
- `uv.lock`必须提交；安装和CI使用`--locked`或`--frozen`。
- `requirements.txt`只能通过`uv export`生成，不允许手工维护。
- 默认核心环境不安装torch、ultralytics或pywinauto。
- PyMuPDF属于核心依赖；Poppler仅作为兼容回退。
- YOLO能力检测顺序为ONNX优先、Ultralytics/PT次之、人工标注降级。
- 不提交真实模型、数据库、密钥和运行输出。
- 不修改现有SSE事件类型、工艺流式输出和页面工作流。
- `convert_pdf_to_images`的GitNexus上游风险为HIGH；修改前必须再次运行impact并警告，完成后同时回归图纸上传和知识库PDF导入。
- 修改任何函数、类或方法前运行GitNexus impact；每次提交前运行`detect-changes --scope staged`。

---

## File Structure

### New files

- `.python-version`：固定Python 3.11.15。
- `pyproject.toml`：项目、依赖、可选组、开发组和pytest配置。
- `uv.lock`：跨平台锁文件。
- `backend/services/capabilities.py`：纯检测逻辑，不启动模型或执行业务任务。
- `backend/services/startup_checks.py`：阻断性启动检查。
- `backend/test_dependency_manifest.py`：依赖契约测试。
- `backend/test_capabilities.py`：能力组合测试。
- `backend/test_startup_checks.py`：启动阻断规则测试。
- `backend/pipeline/test_pdf_converter.py`：PDF provider选择和失败测试。
- `backend/test_upload_capability_gate.py`：PDF上传门禁测试。
- `backend/pipeline/test_yolo_detector.py`：ONNX优先级和降级测试。
- `backend/services/model_manifest.py`：模型清单解析与SHA-256校验。
- `backend/test_model_manifest.py`：模型清单测试。
- `db_data/model-manifest.example.json`：不含真实模型的示例清单。
- `scripts/runtime_smoke.py`：干净环境能力与启动烟雾检查。
- `setup.sh`：macOS/Linux首次安装。
- `start.sh`：macOS/Linux开发启动。
- `.github/workflows/runtime.yml`：macOS和Windows核心环境CI。

### Modified files

- `requirements.txt`：改为uv生成的核心兼容导出。
- `.gitignore`：允许提交模型清单示例，继续忽略运行时模型和数据库。
- `backend/api/_response.py`：增加能力不可用错误码。
- `backend/api/health.py`：增加`GET /api/system/capabilities`。
- `backend/api/upload.py`：PDF上传前执行能力门禁。
- `backend/pipeline/pdf_converter.py`：使用统一provider选择。
- `backend/pipeline/yolo_detector.py`：ONNX优先，PT回退。
- `backend/run.py`：导入Flask应用前执行启动检查。
- `backend/services/__init__.py`：仅在确有共享出口需要时导出能力函数。
- `setup.bat`：使用uv和固定Python。
- `start.ps1`：验证uv环境并通过uv启动。
- `README.md`、`INSTALL.md`、`START.md`：统一安装和故障处理说明。
- `frontend-react/package.json`：声明Node.js版本下限。
- `.nvmrc`：固定开发Node主版本。

### Deleted file

- `backend/requirements.txt`：删除第二依赖源。

---

### Task 1: Establish the Python and Dependency Contract

**Files:**
- Create: `.python-version`
- Create: `pyproject.toml`
- Create: `backend/test_dependency_manifest.py`
- Modify: `requirements.txt`
- Delete: `backend/requirements.txt`

**Interfaces:**
- Produces: uv project metadata consumed by every later task.
- Produces: extras named exactly `yolo` and `windows-creo`.
- Produces: development group named exactly `dev`.

- [ ] **Step 1: Write the failing dependency-contract test**

Create `backend/test_dependency_manifest.py`:

```python
from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]


def _pyproject():
    with (ROOT / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)


def test_python_version_is_pinned():
    assert (ROOT / ".python-version").read_text(encoding="utf-8").strip() == "3.11.15"
    assert _pyproject()["project"]["requires-python"] == ">=3.11,<3.12"


def test_core_and_optional_dependencies_are_separated():
    project = _pyproject()["project"]
    core = "\n".join(project["dependencies"]).lower()
    extras = project["optional-dependencies"]

    assert "pymupdf" in core
    assert "onnxruntime" in core
    assert "opencv-python" in core
    assert "ultralytics" not in core
    assert "torch" not in core
    assert any(item.startswith("ultralytics") for item in extras["yolo"])
    assert any("sys_platform == 'win32'" in item for item in extras["windows-creo"])


def test_only_one_hand_maintained_dependency_manifest_exists():
    assert not (ROOT / "backend" / "requirements.txt").exists()
    exported = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    assert "pymupdf==" in exported
    assert "ultralytics==" not in exported
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
.venv/bin/python -m pytest backend/test_dependency_manifest.py -q
```

Expected: FAIL because `.python-version` and `pyproject.toml` do not exist and the old backend requirements file still exists.

- [ ] **Step 3: Create the uv project manifest**

Create `.python-version`:

```text
3.11.15
```

Create `pyproject.toml`:

```toml
[project]
name = "smart-process-system"
version = "0.1.0"
description = "AI-assisted 2D drawing process planning system"
readme = "README.md"
requires-python = ">=3.11,<3.12"
dependencies = [
  "flask>=3.1,<4",
  "flask-cors>=6,<7",
  "werkzeug>=3.1,<4",
  "python-dotenv>=1.1,<2",
  "pymupdf>=1.26,<2",
  "pdf2image>=1.17,<2",
  "pillow>=11,<13",
  "opencv-python>=4.11,<5",
  "ezdxf>=1.4,<2",
  "ezdwg>=0.9,<1",
  "matplotlib>=3.10,<4",
  "numpy>=2.2,<3",
  "rapidocr-onnxruntime>=1.4,<2",
  "onnxruntime>=1.22,<2",
  "langchain-openai>=1.0,<2",
  "langchain-core>=1.0,<2",
  "openai>=2,<3",
  "requests>=2.32,<3",
  "httpx>=0.28,<1",
  "openpyxl>=3.1,<4",
]

[project.optional-dependencies]
yolo = [
  "ultralytics>=8.3,<9",
  "torch>=2.7,<3",
  "torchvision>=0.22,<1",
]
windows-creo = [
  "pywinauto>=0.6.9,<1; sys_platform == 'win32'",
]

[dependency-groups]
dev = [
  "pytest>=8.4,<9",
  "pytest-cov>=6.2,<7",
  "ruff>=0.12,<1",
  "mypy>=1.16,<2",
  "python-docx>=1.2,<2",
]

[tool.uv]
package = false
default-groups = []

[tool.pytest.ini_options]
testpaths = ["backend"]
python_files = ["test_*.py"]
addopts = "-ra"
```

Delete `backend/requirements.txt`.

- [ ] **Step 4: Generate and validate the lock**

Run:

```bash
uv lock
uv sync --locked --group dev
uv export --locked --no-dev --no-hashes --format requirements.txt --output-file requirements.txt
```

Expected:

- `uv.lock` is created.
- `.venv/bin/python --version` reports Python 3.11.15.
- `requirements.txt` contains exact `==` versions for core dependencies only.

If `ezdwg` has no compatible wheel on either supported platform, stop this task and move it from core to a named optional `dwg` extra only after confirming the existing DWG route degrades safely.

- [ ] **Step 5: Run dependency verification**

Run:

```bash
uv run --group dev pytest backend/test_dependency_manifest.py -q
uv run python -m pip check
uv lock --check
```

Expected: all tests pass, no broken requirements, lock is current.

- [ ] **Step 6: Run GitNexus scope detection and commit**

Run:

```bash
git add .python-version pyproject.toml uv.lock requirements.txt backend/test_dependency_manifest.py
git add -u backend/requirements.txt
node .gitnexus/run.cjs detect-changes --scope staged
git commit -m "build: unify python dependencies with uv"
```

Expected: dependency files and their contract test only.

---

### Task 2: Add Pure Runtime Capability Detection

**Files:**
- Create: `backend/services/capabilities.py`
- Create: `backend/test_capabilities.py`

**Interfaces:**
- Produces: `inspect_pdf_capability() -> dict`
- Produces: `inspect_yolo_capability() -> dict`
- Produces: `collect_capabilities() -> dict`
- All returned capability objects contain `available: bool` and `reason: str`.
- Capability detection must not instantiate an ONNX session, load a PT model, contact an API, or mutate the database.

- [ ] **Step 1: Run impact checks for referenced configuration helpers**

Run:

```bash
node .gitnexus/run.cjs impact get_freecad_paths --direction upstream
node .gitnexus/run.cjs impact validate_vision_config --direction upstream
```

Expected: record risk before importing or reusing these helpers.

- [ ] **Step 2: Write failing capability tests**

Create `backend/test_capabilities.py`:

```python
from pathlib import Path

from backend.services import capabilities


def test_pdf_prefers_pymupdf(monkeypatch):
    monkeypatch.setattr(capabilities, "_module_available", lambda name: name == "fitz")
    monkeypatch.setattr(capabilities.shutil, "which", lambda name: f"/bin/{name}")
    assert capabilities.inspect_pdf_capability() == {
        "available": True,
        "provider": "pymupdf",
        "reason": "",
    }


def test_pdf_falls_back_to_poppler(monkeypatch):
    monkeypatch.setattr(capabilities, "_module_available", lambda name: False)
    monkeypatch.setattr(capabilities.shutil, "which", lambda name: f"/bin/{name}")
    assert capabilities.inspect_pdf_capability()["provider"] == "poppler"


def test_pdf_reports_actionable_failure(monkeypatch):
    monkeypatch.setattr(capabilities, "_module_available", lambda name: False)
    monkeypatch.setattr(capabilities.shutil, "which", lambda name: None)
    result = capabilities.inspect_pdf_capability()
    assert result["available"] is False
    assert "uv sync" in result["reason"]


def test_yolo_prefers_onnx_without_importing_ultralytics(monkeypatch, tmp_path):
    onnx = tmp_path / "best.onnx"
    onnx.write_bytes(b"model")
    monkeypatch.setattr(capabilities, "YOLO_ONNX_PATH", str(onnx))
    monkeypatch.setattr(capabilities, "YOLO_WEIGHT_PATH", str(tmp_path / "best.pt"))
    monkeypatch.setattr(
        capabilities,
        "_module_available",
        lambda name: name == "onnxruntime",
    )
    result = capabilities.inspect_yolo_capability()
    assert result["available"] is True
    assert result["provider"] == "onnx"


def test_yolo_missing_models_is_non_blocking(monkeypatch, tmp_path):
    monkeypatch.setattr(capabilities, "YOLO_ONNX_PATH", str(tmp_path / "best.onnx"))
    monkeypatch.setattr(capabilities, "YOLO_WEIGHT_PATH", str(tmp_path / "best.pt"))
    result = capabilities.inspect_yolo_capability()
    assert result["available"] is False
    assert "模型文件不存在" in result["reason"]


def test_creo_is_not_applicable_outside_windows(monkeypatch):
    monkeypatch.setattr(capabilities.sys, "platform", "darwin")
    result = capabilities.inspect_creo_capability()
    assert result["available"] is False
    assert result["applicable"] is False


def test_collect_capabilities_never_exposes_secret_values(monkeypatch):
    monkeypatch.setenv("VISION_API_KEY", "secret-value")
    result = capabilities.collect_capabilities()
    assert "secret-value" not in repr(result)
```

- [ ] **Step 3: Run tests and verify failure**

Run:

```bash
uv run --group dev pytest backend/test_capabilities.py -q
```

Expected: import failure because `backend.services.capabilities` does not exist.

- [ ] **Step 4: Implement the capability service**

Create `backend/services/capabilities.py` with these public functions:

```python
from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from pathlib import Path

from backend.config import (
    YOLO_ONNX_PATH,
    YOLO_WEIGHT_PATH,
    get_freecad_paths,
    get_config,
)

REQUIRED_PYTHON = (3, 11, 15)


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def inspect_python_capability(version_info=None) -> dict:
    info = version_info or sys.version_info
    version = f"{info.major}.{info.minor}.{info.micro}"
    available = (info.major, info.minor, info.micro) == REQUIRED_PYTHON
    return {
        "available": available,
        "version": version,
        "required": "3.11.15",
        "reason": "" if available else "需要Python 3.11.15，请执行 uv python install 3.11.15 && uv sync",
    }


def inspect_pdf_capability() -> dict:
    if _module_available("fitz"):
        return {"available": True, "provider": "pymupdf", "reason": ""}
    if shutil.which("pdfinfo") and shutil.which("pdftoppm"):
        return {"available": True, "provider": "poppler", "reason": ""}
    return {
        "available": False,
        "provider": None,
        "reason": "PDF转换不可用，请执行 uv sync 安装PyMuPDF，或安装Poppler兼容工具。",
    }


def inspect_yolo_capability() -> dict:
    onnx = Path(YOLO_ONNX_PATH)
    pt = Path(YOLO_WEIGHT_PATH)
    if onnx.is_file() and _module_available("onnxruntime"):
        return {"available": True, "provider": "onnx", "reason": ""}
    if pt.is_file() and _module_available("ultralytics") and _module_available("torch"):
        return {"available": True, "provider": "ultralytics", "reason": ""}
    missing = []
    if not onnx.is_file() and not pt.is_file():
        missing.append("模型文件不存在")
    elif onnx.is_file() and not _module_available("onnxruntime"):
        missing.append("onnxruntime未安装")
    elif pt.is_file():
        missing.append("ultralytics或torch未安装，请执行 uv sync --extra yolo")
    return {"available": False, "provider": None, "reason": "；".join(missing)}


def inspect_vision_api_capability() -> dict:
    config = get_config()
    mode = str(config.get("vision_mode") or "doubao").lower()
    if mode == "local":
        local_module_dir = Path(__file__).resolve().parents[2] / "v_model_test"
        available = all(
            (local_module_dir / f"{name}.py").is_file()
            for name in ("ppstructure_extractor", "rule_engine", "semantic_enhancer")
        )
        return {
            "available": available,
            "provider": "local",
            "reason": "" if available else "本地视觉分析依赖不完整",
        }
    available = all(
        str(config.get(name) or "").strip()
        for name in ("vision_api_key", "vision_api_base", "vision_model_id")
    )
    return {
        "available": available,
        "provider": mode,
        "reason": "" if available else "视觉模型配置不完整",
    }


def inspect_creo_capability() -> dict:
    if sys.platform != "win32":
        return {
            "available": False,
            "applicable": False,
            "reason": "当前平台不支持Creo自动化",
        }
    config = get_config()
    exe = Path(str(config.get("creo_exe") or ""))
    available = exe.is_file() and _module_available("pywinauto")
    return {
        "available": available,
        "applicable": True,
        "reason": "" if available else "Creo路径或Windows自动化依赖不完整",
    }


def inspect_freecad_capability() -> dict:
    paths = get_freecad_paths()
    available = bool(paths)
    return {
        "available": available,
        "reason": "" if available else "未检测到FreeCAD",
    }


def inspect_database_capability() -> dict:
    from backend.library_scope import DB_PATH

    db_path = Path(DB_PATH)
    existing_parent = db_path.parent
    while not existing_parent.exists() and existing_parent != existing_parent.parent:
        existing_parent = existing_parent.parent
    writable = os.access(existing_parent, os.W_OK)
    return {
        "available": writable,
        "schema_ready": db_path.exists(),
        "reason": "" if writable else f"数据库目录不可写：{existing_parent}",
    }


def collect_capabilities() -> dict:
    return {
        "ok": True,
        "python": inspect_python_capability(),
        "database": inspect_database_capability(),
        "pdf": inspect_pdf_capability(),
        "vision_api": inspect_vision_api_capability(),
        "yolo": inspect_yolo_capability(),
        "creo": inspect_creo_capability(),
        "freecad": inspect_freecad_capability(),
    }
```

During implementation, keep the return shape exact. Do not add local paths or configuration values.

- [ ] **Step 5: Run tests**

Run:

```bash
uv run --group dev pytest backend/test_capabilities.py -q
```

Expected: all capability combination tests pass without loading a model.

- [ ] **Step 6: Commit**

Run:

```bash
git add backend/services/capabilities.py backend/test_capabilities.py
node .gitnexus/run.cjs detect-changes --scope staged
git commit -m "feat: add runtime capability detection"
```

---

### Task 3: Expose Capabilities and Add Blocking Startup Checks

**Files:**
- Create: `backend/services/startup_checks.py`
- Create: `backend/test_startup_checks.py`
- Create: `backend/test_capabilities_api.py`
- Modify: `backend/api/health.py`
- Modify: `backend/run.py`

**Interfaces:**
- Consumes: `collect_capabilities()` from Task 2.
- Produces: `run_startup_checks() -> dict`.
- Produces: `GET /api/system/capabilities`.
- The capability endpoint always returns HTTP 200 when collection succeeds, even when optional capabilities are unavailable.

- [ ] **Step 1: Run impact analysis**

Run:

```bash
node .gitnexus/run.cjs impact health --direction upstream
node .gitnexus/run.cjs impact startup_token --direction upstream
```

Expected: LOW risk. Record any change before editing.

- [ ] **Step 2: Write failing startup and API tests**

Create `backend/test_startup_checks.py`:

```python
from pathlib import Path

import pytest

from backend.services import startup_checks


def test_wrong_python_version_is_blocking():
    with pytest.raises(RuntimeError, match="Python 3.11.15"):
        startup_checks.run_startup_checks(version_info=(3, 11, 14))


def test_runtime_directories_are_created(monkeypatch, tmp_path):
    monkeypatch.setattr(startup_checks, "RUNTIME_DIRECTORIES", [tmp_path / "a", tmp_path / "b"])
    monkeypatch.setattr(startup_checks, "initialize_library_storage", lambda: None)
    result = startup_checks.run_startup_checks(version_info=(3, 11, 15))
    assert result["database"]["available"] is True
    assert all(path.is_dir() for path in startup_checks.RUNTIME_DIRECTORIES)


def test_database_initialization_failure_is_blocking(monkeypatch, tmp_path):
    monkeypatch.setattr(startup_checks, "RUNTIME_DIRECTORIES", [tmp_path])
    monkeypatch.setattr(
        startup_checks,
        "initialize_library_storage",
        lambda: (_ for _ in ()).throw(RuntimeError("schema failed")),
    )
    with pytest.raises(RuntimeError, match="schema failed"):
        startup_checks.run_startup_checks(version_info=(3, 11, 15))
```

Create `backend/test_capabilities_api.py`:

```python
def test_capabilities_endpoint_returns_structured_status(monkeypatch):
    from backend.api import health as health_api
    from backend.app import app

    monkeypatch.setattr(
        health_api,
        "collect_capabilities",
        lambda: {"ok": True, "pdf": {"available": False, "reason": "missing"}},
    )
    response = app.test_client().get("/api/system/capabilities")
    assert response.status_code == 200
    assert response.get_json()["pdf"]["available"] is False
```

- [ ] **Step 3: Verify tests fail**

Run:

```bash
uv run --group dev pytest backend/test_startup_checks.py backend/test_capabilities_api.py -q
```

Expected: import failure for `startup_checks` and 404 for capability endpoint.

- [ ] **Step 4: Implement blocking startup checks**

Create `backend/services/startup_checks.py`:

```python
from __future__ import annotations

import sys
from pathlib import Path

from backend.config import OUTPUT_FOLDER, UPLOAD_FOLDER
from backend.library_scope import initialize_library_storage

REQUIRED_PYTHON = (3, 11, 15)
RUNTIME_DIRECTORIES = [
    Path(OUTPUT_FOLDER),
    Path(UPLOAD_FOLDER),
    Path(OUTPUT_FOLDER).parent / "db_data",
]


def _version_tuple(version_info) -> tuple[int, int, int]:
    if isinstance(version_info, tuple):
        return tuple(version_info[:3])
    return version_info.major, version_info.minor, version_info.micro


def run_startup_checks(version_info=None) -> dict:
    current = _version_tuple(version_info or sys.version_info)
    if current != REQUIRED_PYTHON:
        found = ".".join(str(part) for part in current)
        raise RuntimeError(
            f"需要Python 3.11.15，当前为{found}。"
            "请执行 uv python install 3.11.15 && uv sync。"
        )

    for directory in RUNTIME_DIRECTORIES:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()

    try:
        initialize_library_storage()
    except Exception as exc:
        raise RuntimeError(f"数据库初始化失败：{exc}") from exc

    return {
        "python": {"available": True, "version": "3.11.15"},
        "database": {"available": True},
    }
```

- [ ] **Step 5: Add the capability API**

Modify `backend/api/health.py`:

```python
from backend.services.capabilities import collect_capabilities


@health_bp.route("/system/capabilities", methods=["GET"])
def system_capabilities():
    return jsonify(collect_capabilities())
```

Keep existing `/health` and `/startup_token` responses unchanged.

- [ ] **Step 6: Run checks before importing the Flask app**

Modify `backend/run.py` so `backend.app` is imported after preflight:

```python
def main():
    from backend.services.startup_checks import run_startup_checks

    run_startup_checks()
    from backend.app import app

    print("=" * 50)
    print("PDF Process Analysis System")
    print("=" * 50)
    debug_mode = os.getenv("FLASK_DEBUG", "1") != "0"
    app.run(
        host="0.0.0.0",
        port=5190,
        debug=debug_mode,
        use_reloader=debug_mode,
        threaded=True,
    )


if __name__ == "__main__":
    main()
```

Do not make direct `import backend.app` perform exact patch-version enforcement; tests and tooling may import the app. The blocking check belongs to the supported launcher.

- [ ] **Step 7: Run tests and startup smoke**

Run:

```bash
uv run --group dev pytest \
  backend/test_startup_checks.py \
  backend/test_capabilities_api.py \
  backend/test_startup_import.py \
  -q
FLASK_DEBUG=0 uv run python -m backend.run
```

In a second terminal:

```bash
curl -fsS http://127.0.0.1:5190/api/health
curl -fsS http://127.0.0.1:5190/api/system/capabilities
```

Expected: health is 200; capabilities contain no secrets or absolute model paths.

- [ ] **Step 8: Commit**

```bash
git add backend/services/startup_checks.py backend/api/health.py backend/run.py \
  backend/test_startup_checks.py backend/test_capabilities_api.py
node .gitnexus/run.cjs detect-changes --scope staged
git commit -m "feat: add startup preflight and capabilities api"
```

---

### Task 4: Make PDF Conversion Deterministic and Gate PDF Uploads

**Risk:** HIGH. This task affects drawing uploads and knowledge-base PDF imports.

**Files:**
- Create: `backend/pipeline/test_pdf_converter.py`
- Create: `backend/test_upload_capability_gate.py`
- Modify: `backend/pipeline/pdf_converter.py`
- Modify: `backend/api/upload.py`
- Modify: `backend/api/_response.py`

**Interfaces:**
- Consumes: `inspect_pdf_capability()` from Task 2.
- Produces: `PDFConversionUnavailable(RuntimeError)`.
- PDF upload returns error code `CAPABILITY_UNAVAILABLE` before task creation when no provider exists.
- PNG/JPG behavior remains unchanged.

- [ ] **Step 1: Repeat required HIGH-risk impact analysis and warn before editing**

Run:

```bash
node .gitnexus/run.cjs impact convert_pdf_to_images --direction upstream
node .gitnexus/run.cjs context convert_pdf_to_images
```

Expected: HIGH risk with callers in `backend/api/upload.py` and `backend/api/kb_import.py`. Do not proceed silently if the result changes.

- [ ] **Step 2: Write failing provider tests**

Create `backend/pipeline/test_pdf_converter.py`:

```python
import pytest

from backend.pipeline import pdf_converter


def test_converter_uses_pymupdf_provider(monkeypatch, tmp_path):
    monkeypatch.setattr(
        pdf_converter,
        "inspect_pdf_capability",
        lambda: {"available": True, "provider": "pymupdf", "reason": ""},
    )
    monkeypatch.setattr(pdf_converter, "_convert_with_fitz", lambda *args: ["page.png"])
    assert pdf_converter.convert_pdf_to_images("a.pdf", str(tmp_path)) == ["page.png"]


def test_converter_uses_poppler_provider(monkeypatch, tmp_path):
    monkeypatch.setattr(
        pdf_converter,
        "inspect_pdf_capability",
        lambda: {"available": True, "provider": "poppler", "reason": ""},
    )
    monkeypatch.setattr(pdf_converter, "_convert_with_pdf2image", lambda *args: ["page.png"])
    assert pdf_converter.convert_pdf_to_images("a.pdf", str(tmp_path)) == ["page.png"]


def test_converter_raises_actionable_error_without_provider(monkeypatch, tmp_path):
    monkeypatch.setattr(
        pdf_converter,
        "inspect_pdf_capability",
        lambda: {"available": False, "provider": None, "reason": "run uv sync"},
    )
    with pytest.raises(pdf_converter.PDFConversionUnavailable, match="uv sync"):
        pdf_converter.convert_pdf_to_images("a.pdf", str(tmp_path))
```

Create `backend/test_upload_capability_gate.py`:

```python
import io


def test_pdf_upload_is_rejected_before_task_creation(monkeypatch):
    from backend.api import upload as upload_api
    from backend.app import app

    monkeypatch.setattr(
        upload_api,
        "inspect_pdf_capability",
        lambda: {"available": False, "provider": None, "reason": "请执行 uv sync"},
    )
    client = app.test_client()
    response = client.post(
        "/api/upload_drawing",
        data={"file": (io.BytesIO(b"%PDF-1.4"), "drawing.pdf")},
        content_type="multipart/form-data",
    )
    body = response.get_json()
    assert response.status_code == 422
    assert body["error"]["code"] == "CAPABILITY_UNAVAILABLE"
    assert upload_api.tasks == {}
```

- [ ] **Step 3: Verify tests fail**

```bash
uv run --group dev pytest \
  backend/pipeline/test_pdf_converter.py \
  backend/test_upload_capability_gate.py \
  -q
```

Expected: missing exception, missing capability import, and upload still creates or validates a task differently.

- [ ] **Step 4: Implement deterministic provider selection**

Modify `backend/pipeline/pdf_converter.py`:

```python
from backend.services.capabilities import inspect_pdf_capability


class PDFConversionUnavailable(RuntimeError):
    pass


def convert_pdf_to_images(
    pdf_path: str,
    output_dir: str,
    dpi: int = 200,
    on_image_ready=None,
) -> list[str]:
    os.makedirs(output_dir, exist_ok=True)
    capability = inspect_pdf_capability()
    provider = capability.get("provider")
    if provider == "pymupdf":
        return _convert_with_fitz(pdf_path, output_dir, dpi, on_image_ready)
    if provider == "poppler":
        return _convert_with_pdf2image(pdf_path, output_dir, dpi, on_image_ready)
    raise PDFConversionUnavailable(capability.get("reason") or "PDF转换不可用")
```

Do not catch every PyMuPDF runtime exception and silently retry Poppler. Fallback is for provider absence, not for corrupt or invalid PDFs.

- [ ] **Step 5: Add the upload gate**

Add to `backend/api/_response.py`:

```python
ERR_CAPABILITY = "CAPABILITY_UNAVAILABLE"
```

In `backend/api/upload.py`, import `inspect_pdf_capability` and add immediately after file-type validation:

```python
if filename.lower().endswith(".pdf"):
    pdf_capability = inspect_pdf_capability()
    if not pdf_capability["available"]:
        return fail(
            ERR_CAPABILITY,
            pdf_capability["reason"],
            422,
            {"capability": "pdf"},
        )
```

This check must run before `validate_vision_config()`, UUID creation, file saving, and task insertion.

- [ ] **Step 6: Run focused and downstream regression tests**

```bash
uv run --group dev pytest \
  backend/pipeline/test_pdf_converter.py \
  backend/test_upload_capability_gate.py \
  backend/test_kb_import_formats.py \
  backend/test_library_storage_init.py \
  -q
```

Expected: provider tests, upload gate, knowledge import formats, and database storage tests pass.

- [ ] **Step 7: Perform real PyMuPDF smoke conversion**

Use an existing tracked or temporary valid PDF:

```bash
uv run python - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory
from backend.pipeline.pdf_converter import convert_pdf_to_images

pdfs = list(Path("backend/sample_zip").rglob("*.pdf"))
if not pdfs:
    print("SKIP: no local sample PDF")
else:
    with TemporaryDirectory() as out:
        pages = convert_pdf_to_images(str(pdfs[0]), out, dpi=72)
        assert pages and all(Path(page).exists() for page in pages)
        print(f"PASS: {len(pages)} page(s)")
PY
```

Expected: conversion uses `pymupdf` and produces at least one PNG when a sample exists.

- [ ] **Step 8: Commit**

```bash
git add backend/pipeline/pdf_converter.py backend/api/upload.py backend/api/_response.py \
  backend/pipeline/test_pdf_converter.py backend/test_upload_capability_gate.py
node .gitnexus/run.cjs detect-changes --scope staged
git commit -m "fix: make pdf conversion capability-aware"
```

---

### Task 5: Prefer ONNX and Validate Model Delivery Metadata

**Files:**
- Create: `backend/services/model_manifest.py`
- Create: `backend/test_model_manifest.py`
- Create: `backend/pipeline/test_yolo_detector.py`
- Create: `db_data/model-manifest.example.json`
- Modify: `backend/pipeline/yolo_detector.py`
- Modify: `backend/services/capabilities.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `load_model_manifest(path: Path) -> dict`.
- Produces: `verify_model_file(model_path: Path, manifest: dict) -> tuple[bool, str]`.
- `YOLODetector` tries ONNX before PT.
- A malformed optional manifest disables that model with an actionable reason; absence of a runtime manifest does not block manual fallback.

- [ ] **Step 1: Run impact analysis**

```bash
node .gitnexus/run.cjs impact get_yolo_detector --direction upstream
node .gitnexus/run.cjs impact YOLODetector --direction upstream
```

Expected: LOW risk, primarily `_run_yolo_prelabel`.

- [ ] **Step 2: Write failing manifest and backend-order tests**

Create `backend/test_model_manifest.py`:

```python
import hashlib
import json

from backend.services.model_manifest import load_model_manifest, verify_model_file


def test_model_manifest_verifies_sha256(tmp_path):
    model = tmp_path / "best.onnx"
    model.write_bytes(b"model-bytes")
    digest = hashlib.sha256(model.read_bytes()).hexdigest()
    manifest_path = tmp_path / "model-manifest.json"
    manifest_path.write_text(
        json.dumps({
            "name": "drawing-yolo",
            "version": "1.0.0",
            "format": "onnx",
            "sha256": digest,
            "classes": ["threaded_hole", "circle_hole"],
            "input_size": 1280,
            "confidence_threshold": 0.25,
            "released_at": "2026-06-20",
        }),
        encoding="utf-8",
    )
    manifest = load_model_manifest(manifest_path)
    assert verify_model_file(model, manifest) == (True, "")


def test_model_manifest_rejects_hash_mismatch(tmp_path):
    model = tmp_path / "best.onnx"
    model.write_bytes(b"wrong")
    ok, reason = verify_model_file(model, {"sha256": "0" * 64})
    assert ok is False
    assert "SHA-256" in reason
```

Create `backend/pipeline/test_yolo_detector.py`:

```python
from backend.pipeline import yolo_detector


def test_detector_prefers_onnx(monkeypatch):
    calls = []
    monkeypatch.setattr(
        yolo_detector.YOLODetector,
        "_load_onnx",
        lambda self, path: calls.append(("onnx", path)) or True,
    )
    monkeypatch.setattr(
        yolo_detector.YOLODetector,
        "_load_ultralytics",
        lambda self, path: calls.append(("pt", path)) or True,
    )
    detector = yolo_detector.YOLODetector(pt_path="best.pt", onnx_path="best.onnx")
    assert calls == [("onnx", "best.onnx")]
    assert detector is not None


def test_detector_falls_back_to_pt(monkeypatch):
    calls = []
    monkeypatch.setattr(
        yolo_detector.YOLODetector,
        "_load_onnx",
        lambda self, path: calls.append(("onnx", path)) or False,
    )
    monkeypatch.setattr(
        yolo_detector.YOLODetector,
        "_load_ultralytics",
        lambda self, path: calls.append(("pt", path)) or True,
    )
    yolo_detector.YOLODetector(pt_path="best.pt", onnx_path="best.onnx")
    assert calls == [("onnx", "best.onnx"), ("pt", "best.pt")]
```

- [ ] **Step 3: Verify tests fail**

```bash
uv run --group dev pytest \
  backend/test_model_manifest.py \
  backend/pipeline/test_yolo_detector.py \
  -q
```

Expected: missing module and current PT-first assertion failure.

- [ ] **Step 4: Implement model manifest validation**

Create `backend/services/model_manifest.py`:

```python
from __future__ import annotations

import hashlib
import json
from pathlib import Path

REQUIRED_FIELDS = {
    "name",
    "version",
    "format",
    "sha256",
    "classes",
    "input_size",
    "confidence_threshold",
    "released_at",
}


def load_model_manifest(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    missing = sorted(REQUIRED_FIELDS - payload.keys())
    if missing:
        raise ValueError(f"模型清单缺少字段：{', '.join(missing)}")
    if payload["format"] not in {"onnx", "pt"}:
        raise ValueError("模型清单format必须是onnx或pt")
    return payload


def verify_model_file(model_path: Path, manifest: dict) -> tuple[bool, str]:
    if not model_path.is_file():
        return False, "模型文件不存在"
    expected = str(manifest.get("sha256") or "").lower()
    actual = hashlib.sha256(model_path.read_bytes()).hexdigest()
    if expected and actual != expected:
        return False, "模型SHA-256与清单不一致"
    return True, ""
```

- [ ] **Step 5: Change YOLO backend order**

In `YOLODetector.__init__`:

```python
if onnx_path and self._load_onnx(onnx_path):
    return
if pt_path and self._load_ultralytics(pt_path):
    return
logger.warning("YOLO不可用：ONNX和ultralytics/PT均加载失败")
```

Update the module and class docstrings from “PT优先” to “ONNX优先”.

- [ ] **Step 6: Add the model manifest example and ignore rules**

Replace the broad final `db_data/` ignore rule with:

```gitignore
db_data/*
!db_data/model-manifest.example.json
```

Keep explicit database, preview, and generated-output rules.

Create `db_data/model-manifest.example.json`:

```json
{
  "name": "drawing-yolo",
  "version": "1.0.0",
  "format": "onnx",
  "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
  "classes": ["threaded_hole", "circle_hole"],
  "input_size": 1280,
  "confidence_threshold": 0.25,
  "released_at": "2026-06-20"
}
```

Runtime deployments copy this to `db_data/model-manifest.json`, which remains ignored.

- [ ] **Step 7: Integrate optional manifest status into capabilities**

Update `inspect_yolo_capability()`:

- Prefer `best.onnx`.
- If `db_data/model-manifest.json` exists, load and verify the selected model.
- Return `available: false` with the manifest error when validation fails.
- Never instantiate `YOLODetector` in capability collection.

Add tests to `backend/test_capabilities.py` for valid and invalid manifest cases.

- [ ] **Step 8: Run tests**

```bash
uv run --group dev pytest \
  backend/test_model_manifest.py \
  backend/pipeline/test_yolo_detector.py \
  backend/test_capabilities.py \
  -q
```

Expected: ONNX is selected first, manifest mismatch is reported, missing models remain non-blocking.

- [ ] **Step 9: Commit**

```bash
git add .gitignore db_data/model-manifest.example.json \
  backend/services/model_manifest.py backend/services/capabilities.py \
  backend/pipeline/yolo_detector.py backend/test_model_manifest.py \
  backend/pipeline/test_yolo_detector.py backend/test_capabilities.py
node .gitnexus/run.cjs detect-changes --scope staged
git commit -m "feat: prefer onnx yolo model delivery"
```

---

### Task 6: Unify Local Setup and Startup Scripts

**Files:**
- Create: `setup.sh`
- Create: `start.sh`
- Create: `.nvmrc`
- Create: `backend/test_installation_contract.py`
- Modify: `setup.bat`
- Modify: `start.ps1`
- Modify: `frontend-react/package.json`

**Interfaces:**
- `setup.sh` and `setup.bat` produce `.venv`, `.env`, runtime directories, and frontend dependencies.
- `start.sh` and `start.ps1` run the same backend module and frontend command.
- Optional environment variable `INSTALL_YOLO=1` installs the `yolo` extra.

- [ ] **Step 1: Write failing script-contract tests**

Create `backend/test_installation_contract.py`:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_install_scripts_use_uv_and_fixed_python():
    for path in ("setup.sh", "setup.bat"):
        text = _read(path).lower()
        assert "uv" in text
        assert "3.11.15" in text
        assert "backend/requirements.txt" not in text
        assert "backend\\requirements.txt" not in text


def test_start_scripts_use_supported_launcher():
    for path in ("start.sh", "start.ps1"):
        text = _read(path).lower()
        assert "backend.run" in text
        assert "uv" in text


def test_node_version_contract():
    assert _read(".nvmrc").strip() == "20"
```

- [ ] **Step 2: Run tests and verify failure**

```bash
uv run --group dev pytest backend/test_installation_contract.py -q
```

Expected: missing shell scripts and old pip-based Windows setup.

- [ ] **Step 3: Implement macOS/Linux setup**

Create executable `setup.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

command -v uv >/dev/null || {
  echo "uv未安装：https://docs.astral.sh/uv/getting-started/installation/"
  exit 1
}
command -v node >/dev/null || { echo "需要Node.js 20+"; exit 1; }
command -v npm >/dev/null || { echo "需要npm"; exit 1; }

uv python install 3.11.15
if [[ "${INSTALL_YOLO:-0}" == "1" ]]; then
  uv sync --locked --extra yolo
else
  uv sync --locked
fi

[[ -f .env ]] || cp .env.example .env
mkdir -p db_data uploads output
npm --prefix frontend-react ci

uv run python scripts/runtime_smoke.py
echo "安装完成。编辑.env后运行 ./start.sh"
```

- [ ] **Step 4: Migrate Windows setup**

Replace Python discovery, venv creation, and pip installation in `setup.bat` with:

```bat
where uv >nul 2>&1
if errorlevel 1 (
    echo [ERROR] uv is required: https://docs.astral.sh/uv/
    exit /b 1
)

uv python install 3.11.15
if "%INSTALL_YOLO%"=="1" (
    uv sync --locked --extra yolo
) else (
    uv sync --locked
)
if errorlevel 1 exit /b 1
```

Keep Node/npm checks, `.env` copy, runtime directory creation, and frontend `npm ci`.

- [ ] **Step 5: Implement platform start scripts**

Create executable `start.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

command -v uv >/dev/null || {
  echo "uv未安装：https://docs.astral.sh/uv/getting-started/installation/"
  exit 1
}
uv run python scripts/runtime_smoke.py

BACKEND_PID=""
FRONTEND_PID=""

FLASK_DEBUG="${FLASK_DEBUG:-0}" uv run python -m backend.run &
BACKEND_PID=$!

cleanup() {
  [[ -n "$BACKEND_PID" ]] && kill "$BACKEND_PID" 2>/dev/null || true
  [[ -n "$FRONTEND_PID" ]] && kill "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

npm --prefix frontend-react run dev -- --host 127.0.0.1 &
FRONTEND_PID=$!
wait
```

Update `start.ps1` to resolve uv with `Get-Command uv`, run:

```powershell
$backend = Start-Process -FilePath $uv.Source `
    -ArgumentList "run", "python", "-m", "backend.run" `
    -WorkingDirectory $ROOT `
    -PassThru -NoNewWindow `
    -RedirectStandardOutput "$ROOT\backend_stdout.log" `
    -RedirectStandardError "$ROOT\backend_stderr.log"
```

Before starting, execute `uv run python scripts/runtime_smoke.py` and fail if it returns nonzero. Dependency synchronization remains the responsibility of `setup.sh`/`setup.bat`, so starting the application does not silently remove optional extras installed earlier.

- [ ] **Step 6: Pin Node contract**

Create `.nvmrc`:

```text
20
```

Add to `frontend-react/package.json`:

```json
"engines": {
  "node": ">=20 <21",
  "npm": ">=10"
}
```

- [ ] **Step 7: Run script-contract and static checks**

```bash
chmod +x setup.sh start.sh
uv run --group dev pytest backend/test_installation_contract.py -q
bash -n setup.sh start.sh
```

On Windows, execute:

```powershell
PowerShell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1
```

Stop after health check succeeds; do not leave background processes.

- [ ] **Step 8: Commit**

```bash
git add setup.sh start.sh setup.bat start.ps1 .nvmrc \
  frontend-react/package.json backend/test_installation_contract.py
node .gitnexus/run.cjs detect-changes --scope staged
git commit -m "build: unify cross-platform setup scripts"
```

---

### Task 7: Add Runtime Smoke Verification and Cross-Platform CI

**Files:**
- Create: `scripts/runtime_smoke.py`
- Create: `backend/test_runtime_smoke.py`
- Create: `.github/workflows/runtime.yml`

**Interfaces:**
- `scripts/runtime_smoke.py` exits 0 when blocking checks pass.
- It prints optional capability failures without treating them as fatal.
- CI tests core environment only; it does not download models or call external AI APIs.

- [ ] **Step 1: Write the failing smoke-script test**

Create `backend/test_runtime_smoke.py`:

```python
from scripts import runtime_smoke


def test_smoke_returns_zero_when_blocking_checks_pass(monkeypatch):
    monkeypatch.setattr(runtime_smoke, "run_startup_checks", lambda: {"database": {"available": True}})
    monkeypatch.setattr(
        runtime_smoke,
        "collect_capabilities",
        lambda: {
            "ok": True,
            "pdf": {"available": True, "provider": "pymupdf", "reason": ""},
            "yolo": {"available": False, "provider": None, "reason": "missing model"},
        },
    )
    assert runtime_smoke.main() == 0
```

- [ ] **Step 2: Verify the test fails**

```bash
uv run --group dev pytest backend/test_runtime_smoke.py -q
```

Expected: module missing.

- [ ] **Step 3: Implement the smoke script**

Create `scripts/runtime_smoke.py`:

```python
from __future__ import annotations

import json

from backend.services.capabilities import collect_capabilities
from backend.services.startup_checks import run_startup_checks


def main() -> int:
    run_startup_checks()
    capabilities = collect_capabilities()
    print(json.dumps(capabilities, ensure_ascii=False, indent=2))
    optional_unavailable = [
        name
        for name in ("yolo", "creo", "freecad", "vision_api")
        if not capabilities[name]["available"]
    ]
    if optional_unavailable:
        print("可选能力不可用：" + ", ".join(optional_unavailable))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Add the CI workflow**

Create `.github/workflows/runtime.yml` using currently documented official action versions:

```yaml
name: Runtime

on:
  push:
    branches: [main, yolo-react]
  pull_request:

jobs:
  core:
    strategy:
      fail-fast: false
      matrix:
        os: [macos-latest, windows-latest]
    runs-on: ${{ matrix.os }}

    steps:
      - uses: actions/checkout@v6

      - uses: actions/setup-python@v6
        with:
          python-version-file: .python-version

      - name: Install uv
        uses: astral-sh/setup-uv@08807647e7069bb48b6ef5acd8ec9567f424441b # v8.1.0
        with:
          version: "0.11.22"
          enable-cache: true

      - name: Validate lock
        run: uv lock --check

      - name: Install core and development dependencies
        run: uv sync --locked --group dev

      - name: Runtime smoke
        run: uv run python scripts/runtime_smoke.py

      - name: Backend tests
        run: >
          uv run pytest
          backend/test_dependency_manifest.py
          backend/test_capabilities.py
          backend/test_startup_checks.py
          backend/test_capabilities_api.py
          backend/pipeline/test_pdf_converter.py
          backend/test_upload_capability_gate.py
          backend/test_model_manifest.py
          backend/pipeline/test_yolo_detector.py
          backend/test_library_storage_init.py
          backend/test_startup_import.py
          -q

      - uses: actions/setup-node@v6
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: frontend-react/package-lock.json

      - name: Install frontend
        working-directory: frontend-react
        run: npm ci

      - name: Build frontend
        working-directory: frontend-react
        run: npm run build
```

Do not run browser E2E in this workflow because the existing responsive test contains a separate syntax defect and E2E depends on workflow-state fixtures outside this phase.

- [ ] **Step 5: Run local verification**

```bash
uv run --group dev pytest backend/test_runtime_smoke.py -q
uv run python scripts/runtime_smoke.py
npm --prefix frontend-react ci
npm --prefix frontend-react run build
```

Expected: smoke exits 0; optional missing YOLO/Creo is printed but nonfatal; frontend builds.

- [ ] **Step 6: Commit**

```bash
git add scripts/runtime_smoke.py backend/test_runtime_smoke.py .github/workflows/runtime.yml
node .gitnexus/run.cjs detect-changes --scope staged
git commit -m "ci: verify runtime on macos and windows"
```

---

### Task 8: Rewrite Installation Documentation and Perform Final Acceptance

**Files:**
- Modify: `README.md`
- Modify: `INSTALL.md`
- Modify: `START.md`
- Modify: `task_plan.md`
- Modify: `progress.md`

**Interfaces:**
- Documentation exposes one primary installation flow per platform.
- Every Python command uses uv.
- Documentation distinguishes core, YOLO, and Windows Creo installations.

- [ ] **Step 1: Extend the installation-contract test**

Add to `backend/test_installation_contract.py`:

```python
def test_docs_use_only_the_uv_install_contract():
    for path in ("README.md", "INSTALL.md", "START.md"):
        text = _read(path)
        assert "backend/requirements.txt" not in text
        assert "python3 -m venv" not in text
        assert "python -m venv" not in text
        assert "uv sync" in text


def test_docs_explain_optional_yolo_and_capabilities():
    combined = "\n".join(_read(path) for path in ("README.md", "INSTALL.md", "START.md"))
    assert "uv sync --extra yolo" in combined
    assert "/api/system/capabilities" in combined
```

- [ ] **Step 2: Verify documentation tests fail**

```bash
uv run --group dev pytest backend/test_installation_contract.py -q
```

Expected: old pip and backend requirements references remain.

- [ ] **Step 3: Rewrite the docs**

Required README quick start:

```bash
uv python install 3.11.15
uv sync --locked
cp .env.example .env
npm --prefix frontend-react ci
./start.sh
```

Required Windows quick start:

```powershell
uv python install 3.11.15
uv sync --locked
Copy-Item .env.example .env
.\start.bat
```

Document optional installs:

```bash
uv sync --locked --extra yolo
uv sync --locked --extra windows-creo
```

Document diagnostics:

```bash
uv run python scripts/runtime_smoke.py
curl http://127.0.0.1:5190/api/system/capabilities
```

Explicitly state:

- Real model files stay in `db_data/` and are not committed.
- ONNX is recommended.
- Missing YOLO falls back to manual annotation.
- Missing PyMuPDF and Poppler blocks PDF uploads but not image uploads.
- Creo is not applicable on macOS.

- [ ] **Step 4: Run full focused backend verification**

```bash
uv run --group dev pytest \
  backend/test_dependency_manifest.py \
  backend/test_capabilities.py \
  backend/test_startup_checks.py \
  backend/test_capabilities_api.py \
  backend/pipeline/test_pdf_converter.py \
  backend/test_upload_capability_gate.py \
  backend/test_model_manifest.py \
  backend/pipeline/test_yolo_detector.py \
  backend/test_installation_contract.py \
  backend/test_runtime_smoke.py \
  backend/test_library_storage_init.py \
  backend/test_startup_import.py \
  backend/test_kb_import_formats.py \
  -q
```

Expected: zero failures.

- [ ] **Step 5: Run dependency and frontend verification**

```bash
uv lock --check
uv sync --locked --group dev
uv run python -m pip check
uv run python scripts/runtime_smoke.py
npm --prefix frontend-react ci
npm --prefix frontend-react run build
git diff --check
```

Expected: all commands exit 0.

- [ ] **Step 6: Perform a clean-clone macOS acceptance**

Use a temporary sibling directory, not the working tree:

```bash
TMP_DIR="$(mktemp -d)"
git clone --local . "$TMP_DIR/test-runtime"
cd "$TMP_DIR/test-runtime"
uv python install 3.11.15
uv sync --locked
cp .env.example .env
uv run python scripts/runtime_smoke.py
npm --prefix frontend-react ci
npm --prefix frontend-react run build
```

Expected:

- Python 3.11.15.
- Core environment installs without YOLO/Creo extras.
- PDF provider is `pymupdf`.
- YOLO can be unavailable without failure.
- Database initializes.
- React builds.

- [ ] **Step 7: Perform Windows acceptance**

On a Windows runner or machine:

```powershell
$repo = git remote get-url origin
git clone $repo test-runtime
Set-Location test-runtime
uv python install 3.11.15
uv sync --locked
Copy-Item .env.example .env
uv run python scripts/runtime_smoke.py
Set-Location frontend-react
npm ci
npm run build
```

If no Windows machine is available locally, require the GitHub Actions Windows job to pass before marking this phase complete.

- [ ] **Step 8: Update persistent project tracking**

Update:

- `task_plan.md`: mark stages 3–5 complete only after all acceptance checks pass.
- `progress.md`: record exact test counts, build result, clean-clone result, CI URLs, and any skipped platform checks.
- `findings.md`: record final resolved package versions and any dependency moved to an optional extra.

- [ ] **Step 9: Final GitNexus review and commit**

```bash
node .gitnexus/run.cjs detect-changes --scope compare --base-ref main
git add README.md INSTALL.md START.md backend/test_installation_contract.py \
  task_plan.md findings.md progress.md
git diff --cached --check
node .gitnexus/run.cjs detect-changes --scope staged
git commit -m "docs: finalize reproducible runtime setup"
```

Expected: only runtime environment, capability detection, tests, scripts, CI, and documentation are affected. No SSE or frontend workflow symbols should appear.

---

## Final Definition of Done

- [ ] `.python-version` is exactly `3.11.15`.
- [ ] `uv lock --check` passes.
- [ ] `uv sync --locked` installs core without YOLO and Creo.
- [ ] `uv sync --locked --extra yolo` resolves on the supported development platform.
- [ ] `backend/requirements.txt` no longer exists.
- [ ] `requirements.txt` is an exported core-only compatibility file.
- [ ] PDF defaults to PyMuPDF.
- [ ] PDF absence produces a pre-task 422 response.
- [ ] `/api/system/capabilities` returns stable, non-sensitive JSON.
- [ ] ONNX is preferred over PT.
- [ ] Missing model still enters manual annotation.
- [ ] macOS imports no Win32 API.
- [ ] SQLite initializes from an empty runtime directory.
- [ ] macOS and Windows CI core jobs pass.
- [ ] Frontend production build passes.
- [ ] Clean-clone acceptance passes.
- [ ] Existing SSE stream behavior is unchanged.

## Primary References

- Runtime design: `docs/superpowers/specs/2026-06-20-runtime-environment-unification-design.md`
- Astral uv GitHub Actions guide: https://docs.astral.sh/uv/guides/integration/github/
- GitHub setup-python: https://github.com/actions/setup-python
- GitHub setup-node: https://github.com/actions/setup-node
