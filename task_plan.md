# 任务计划：运行环境统一与基础稳定性

## 目标
将项目统一到可复现的 Python 3.11.15 环境，使 macOS 与 Windows 能从干净克隆安装并启动核心服务，同时让 PDF、YOLO、Creo 等能力按“核心必需 / 可选降级”规则运行。

## 当前阶段
阶段 3

## 各阶段

### 阶段 1：现状审计与需求确认
- [x] 核对 Python、依赖文件和平台差异
- [x] 验证 PDF、YOLO、数据库和启动行为
- [x] 确认用户选择 `uv + pyproject.toml + uv.lock`
- **状态：** complete

### 阶段 2：设计规格
- [x] 确定依赖分组、能力检测和降级边界
- [x] 确定测试层级与干净克隆验收标准
- [x] 编写设计规格
- [x] 用户复核设计规格
- **状态：** complete

### 阶段 3：实施计划
- [x] 使用 writing-plans 编写逐任务实施计划
- [x] 明确每项修改的文件、接口、测试和提交点
- [ ] 用户确认执行方式
- **状态：** in_progress

### 阶段 4：实现与增量验证
- [ ] 按 TDD 顺序实施依赖统一
- [ ] 实施能力检测接口和启动检查
- [ ] 完成跨平台脚本与文档
- [ ] 每个任务完成后运行局部测试并提交
- **状态：** pending

### 阶段 5：完整验收
- [ ] 核心后端测试通过
- [ ] 前端构建通过
- [ ] macOS 干净环境验收通过
- [ ] Windows 核心环境验收通过
- [ ] 记录可选能力的降级结果
- **状态：** pending

## 关键问题
1. Windows CI 是否具备可用执行环境；若暂时没有，先提供可重复的人工验收脚本。
2. 是否保留 `requirements.txt` 兼容导出；当前决策是保留自动生成版本，禁止手工维护。

## 已做决策
| 决策 | 理由 |
|------|------|
| 固定 Python 3.11.15 | 当前虚拟环境已验证，兼容 RapidOCR，避免系统 Python 3.9 与项目环境混用 |
| 使用 uv、pyproject.toml、uv.lock | 单一依赖源、安装快速、跨平台可复现 |
| PDF 默认使用 PyMuPDF | 不依赖系统 Poppler，适合 macOS 和 Windows 干净安装 |
| YOLO 作为可选依赖 | 缺失时仍允许人工标注和核心后端启动 |
| ONNX 为推荐路径 | 跨平台部署比 PyTorch/Ultralytics 更轻量 |
| Windows Creo 独立依赖组 | 防止 macOS 加载 Win32 API 或安装无意义依赖 |
| 第一阶段不改业务工作流 | 控制变更范围，先解决环境与交付稳定性 |

## 遇到的错误
| 错误 | 尝试次数 | 解决方案 |
|------|---------|---------|
| PDF 上传缺少 `fitz`，回退路径又缺少 Poppler | 1 | 将 PyMuPDF 纳入核心依赖，Poppler仅作为可选回退 |
| Playwright 响应式测试文件存在乱码语法错误 | 1 | 记录为后续工作流稳定性阶段问题，不纳入当前环境设计实施 |
| `backend/fix_syntax.py` 阻断全量 compileall | 1 | 记录为仓库既有问题；实施计划中使用受控测试范围并单独安排清理 |

## 备注
- 设计规格：`docs/superpowers/specs/2026-06-20-runtime-environment-unification-design.md`
- 实施计划：`docs/superpowers/plans/2026-06-20-runtime-environment-unification.md`
- 第一阶段不改变现有 SSE 流式输出效果。
- 修改任何代码符号前必须执行 GitNexus impact；提交前必须执行 detect_changes。
