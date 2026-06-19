# 发现与决策

## 需求
- 统一 Python 环境；无法完全统一的平台能力必须明确兼容和降级。
- macOS 与 Windows 均可从干净克隆启动核心服务。
- 缺少 YOLO、Creo、FreeCAD 等可选能力时不能拖垮后端启动。
- 环境状态必须能由后端检查并由前端读取。
- 当前阶段不调整工艺生成工作流、页面按钮和 SSE 流式输出。

## 研究发现
- 系统 `/usr/bin/python3` 为 3.9.6，项目 `.venv` 为 Python 3.11.15。
- 项目缺少 `.python-version`、`pyproject.toml` 和 Python 锁文件。
- 根 `requirements.txt` 与 `backend/requirements.txt` 内容不一致。
- 根依赖包含 Ultralytics，后端依赖不包含；后端依赖包含 Windows 专属 pywinauto。
- 两份依赖均未声明 PyMuPDF，但 PDF 转换代码优先导入 `fitz`。
- macOS 未安装 Poppler 时，缺少 PyMuPDF 会导致 PDF 上传失败。
- 当前 `.venv` 的基础依赖一致性检查通过，但 torch 和 ultralytics 未安装。
- ONNX Runtime 已安装，模型文件缺失时系统会降级到人工标注。
- macOS 启动兼容修改已在本地提交 `8cd8775`。
- 数据库空库初始化测试通过。

## 技术决策
| 决策 | 理由 |
|------|------|
| `pyproject.toml` 是唯一手工维护的依赖清单 | 消除双 requirements 漂移 |
| `uv.lock` 提供具体版本锁定 | 保证团队和 CI 复现 |
| `requirements.txt` 由 uv 导出 | 兼容不能使用 uv 的部署方式 |
| `core` 包含 PyMuPDF | PDF 是核心输入能力 |
| `yolo` 包含 Ultralytics/PyTorch | 大体积且平台差异明显，按需安装 |
| `windows-creo` 使用 `sys_platform == 'win32'` | macOS 不应安装或加载 Win32 依赖 |
| `/api/system/capabilities` 返回结构化能力状态 | 前端不再依赖终端日志判断降级 |
| 核心能力失败阻止启动，可选能力失败允许降级 | 区分系统不可用与局部能力不可用 |

## 遇到的问题
| 问题 | 解决方案 |
|------|---------|
| 开发机存在多个 Python 命令来源 | 所有项目命令统一通过 `uv run` 或 `.venv` 解释器执行 |
| PDF 有两套运行时路径 | PyMuPDF 作为默认；Poppler仅保留兼容回退 |
| YOLO模型不进入 Git | 使用模型清单记录路径、哈希、版本、类别和阈值 |
| Creo仅适用 Windows | 能力检测返回“不适用”，不是异常 |

## 资源
- `README.md`
- `INSTALL.md`
- `START.md`
- `requirements.txt`
- `backend/requirements.txt`
- `backend/pipeline/pdf_converter.py`
- `backend/pipeline/yolo_detector.py`
- `backend/prt_pipeline.py`
- `backend/test_startup_import.py`

## 视觉/浏览器发现
- 本阶段不修改视觉设计。
- 后续工作流阶段需要处理按钮越序、重复提交和页面错误吞没问题。

---
*该文件记录环境统一设计的事实依据，实施前应重新读取。*
