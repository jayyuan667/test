# 交付报告：运行环境统一与基础稳定性

> **项目：** yolo-react（二维工艺系统）  
> **日期：** 2026-06-20  
> **分支：** `yolo-react`  
> **实施者：** Claude Code 代理  

---

## 一、目标回顾

将项目从不可复现的 pip + 双 requirements.txt 模式，统一到 **Python 3.11.15 + uv + pyproject.toml + uv.lock** 的可复现环境，同时引入**运行时能力检测机制**，让 PDF、YOLO、Creo、FreeCAD 等能力按「核心必需 / 可选降级」规则运行，macOS 和 Windows 均可从干净克隆安装并启动。

---

## 二、交付成果

### 2.1 文件变更统计

| 类别 | 数量 | 说明 |
|------|------|------|
| 新增文件 | 18 | pyproject.toml, uv.lock, 能力检测, 测试, 脚本, CI |
| 修改文件 | 11 | 后端核心, API, 文档, 构建脚本 |
| 删除文件 | 1 | `backend/requirements.txt`（消除第二依赖源） |
| 新增代码行 | ~2,200 | 不含 uv.lock 自动生成内容 |

### 2.2 8 项实施任务

| # | 提交 | 内容 |
|---|------|------|
| 1 | `84ab309` | 建立 Python 和依赖契约（pyproject.toml, uv.lock） |
| 2 | `8ce7102` | 纯运行时能力检测（7 项能力，不加载模型） |
| 3 | `cbbe8c4` | 能力 API（/api/system/capabilities）+ 启动阻断检查 |
| 4 | `6e1c53e` | PDF 转换确定性 provider 选择 + 上传门禁（⚠️ HIGH RISK） |
| 5 | `ef30f9b` | ONNX 优先 + 模型清单 SHA-256 校验 |
| 6 | `deb3eaa` | 统一跨平台安装/启动脚本 |
| 7 | `74ccd52` | 运行时烟雾检查 + GitHub Actions CI（macOS + Windows） |
| 8 | `9ff08f4` | 文档重写 + 最终验收 |

### 2.3 测试结果

**44 项测试全部通过**，覆盖：

- 依赖契约验证（单一依赖源、Python 版本固定、Core/YOLO/Creo 分离）
- 能力检测组合测试（PDF provider 选择、ONNX 优先、Creo 平台判定、密钥不泄露）
- 启动阻断规则（版本检查、目录可写、数据库初始化失败）
- PDF 上传门禁（预任务 422、provider 路由）
- 模型清单校验（SHA-256 匹配/不匹配）
- YOLO 检测器 ONNX 优先级
- 安装脚本契约
- 知识库导入和数据库初始化回归

---

## 三、环境契约

| 契约项 | 值 |
|--------|-----|
| Python 版本 | 固定 3.11.15（`>=3.11,<3.12`） |
| 依赖管理 | uv 0.11.22 |
| 锁文件 | `uv.lock`（提交 Git，121 packages） |
| 核心依赖 | 20 个（Flask, PyMuPDF, ONNX Runtime, OpenCV 等） |
| 可选：YOLO | `uv sync --extra yolo`（PyTorch + Ultralytics） |
| 可选：Creo | `uv sync --extra windows-creo`（仅 Windows） |
| Node.js | 20.x（`.nvmrc` + `engines` 字段） |
| 导出兼容 | `requirements.txt`（uv 自动生成，不含 YOLO） |

---

## 四、能力检测矩阵

| 能力 | 检测方式 | 不可用时行为 |
|------|----------|-------------|
| Python | 版本号精确比对 | **阻断启动** |
| 数据库 | 目录可写 + 模式初始化 | **阻断启动** |
| PDF | PyMuPDF → Poppler 回退 | **阻断 PDF 上传**（422），不影响图片 |
| YOLO | ONNX 优先 → PT 兜底 → 人工标注 | 降级为人工标注 |
| Vision API | 键/URL/模型 ID 完整性 | 视觉分析不可用 |
| Creo | 仅 Windows 适用 | 返回不适用 |
| FreeCAD | 路径检测 | 几何分析不可用 |

---

## 五、关键质量决策

1. **PDF 选择 `inspect_pdf_capability()` 而非 try/except ImportError**：避免 PyMuPDF 运行时异常时静默回退 Poppler 产生不可预期的输出差异
2. **ONNX 设为 YOLO 默认后端**：跨平台一致，体积更小，不依赖 PyTorch 大型依赖
3. **模型清单 SHA-256 校验**：防止模型文件损坏或替换后仍静默运行
4. **`uv sync` 不自动安装可选依赖**：保持核心环境最小化，Windows CI 不安装 pywinauto

---

## 六、风险处置

| 风险项 | 等级 | 处置 |
|--------|------|------|
| `convert_pdf_to_images` 上游影响 | HIGH | 影响分析确认 4 个调用者，回归测试覆盖 kb_import + upload |
| macOS CI 通过，Windows CI 待运行 | MEDIUM | CI 工作流已提交，Windows runner 验证等待 GitHub Actions 执行 |
| Playwright E2E 测试乱码 | LOW | 已记录，后续工作流稳定性阶段修复 |
| `ezdwg` 平台兼容性 | — | 已验证有 macOS/Linux/Windows wheel，无问题 |

---

## 七、快速验证

```bash
# 依赖完整性
uv lock --check && uv run python -m pip check

# 能力状态
uv run python scripts/runtime_smoke.py
curl http://127.0.0.1:5190/api/system/capabilities

# 全量测试
uv run pytest backend/ -q  # 44 passed

# 前端构建
npm --prefix frontend-react run build
```

---

## 八、后续建议

1. Windows CI 首次运行后确认通过
2. 可考虑将 `scripts/runtime_smoke.py` 作为 Dockerfile ENTRYPOINT 预检查
3. `model-manifest.json` 可在生产部署时添加不含密码的 LICENSE/来源记录
4. `backend/fix_syntax.py` 和 Playwright 乱码文件建议后续清理
