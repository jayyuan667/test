# v2 安装包设计文档

**日期：** 2026-06-03  
**项目：** 智能工艺系统  
**目标版本：** v2.0  
**打包项目路径：** `F:\Work_Dir\package_install_t`

---

## 背景与目标

v1 安装包存在以下问题：

1. **OCR 引擎遗留**：`installer.iss` 注册表项写入 `PADDLE_PDX_CACHE_HOME` / `PADDLEOCR_VERSION`；launcher 启动后端时注入同名环境变量；`site-packages/` 包含 paddle/paddleocr；`ocr_models/` 保存 PaddleOCR 模型（占用大量空间）。主项目已完成 PaddleOCR → RapidOCR 迁移，安装包须同步。
2. **安装体验简陋**：无欢迎页、无步骤导航、版本号硬编码为 "1"、路径硬编码绝对值。
3. **用户可维护性差**：托盘菜单只有"打开界面"和"退出"，用户遇到授权或故障问题无自助手段。
4. **构建流程分散**：版本号、launcher 编译、Inno Setup 编译须手动分别执行，易出错。

---

## 设计决策摘要

| 维度 | 决策 |
|------|------|
| 产品名称 | 智能工艺系统（内部工具，保持原名） |
| 安装向导风格 | B 方案：左侧深蓝步骤导航栏 + 右侧白色内容区 |
| 托盘菜单增强 | 查看机器码 + 打开日志 + 重启后端 |
| 构建流程 | `version.txt` 单一版本源 + `build.bat` 一键构建 |

---

## 模块一：安装向导（installer.iss）

### 视觉方案

B 方案：左侧窄边栏（深蓝渐变 `#0d2137 → #1a4a7a`）展示步骤进度点，右侧白色内容区展示当前步骤内容。通过 Inno Setup Pascal 脚本在每个 WizardPage 的 `OnPaint` 事件绘制侧边栏，或通过自定义位图背景实现。

### 5 步骤流程

| # | 页面类型 | 标题 | 关键内容 |
|---|---------|------|---------|
| 1 | `wpWelcome` | 欢迎 | 产品亮点 4 条（AI 特征提取、RAG+LLM、支持 PDF/PNG/JPG、离线运行无需安装 Python） |
| 2 | `wpSelectDir` | 安装目录 | 标准目录浏览器 + 所需空间（约 1.2 GB）+ 可用空间 |
| 3 | Custom Page | 产品激活 | 检测同级 `license.lic`：存在则提示"已检测到，将自动激活"；否则提示跳过，安装后从托盘"查看机器码"获取授权 |
| 4 | `wpInstalling` | 安装中 | Inno Setup 默认进度条 + StatusLabel 显示当前复制项 |
| 5 | `wpFinished` | 完成 | 勾选框"立即启动系统"（默认勾选），点击"完成"后若勾选则运行 `{app}\SmartProcess.exe` |

### v1 遗留清理

```
[Registry] 删除：
  PADDLE_PDX_CACHE_HOME
  PADDLEOCR_VERSION

[Dirs] 新增：
  {app}\db_data\kb_previews   （卸载时保留，UninstallNeverUninstallDir）

[Setup] 修改：
  AppVersion={#AppVersion}    （由 build.bat 通过 /DAppVersion= 传入）
  所有硬编码绝对路径 → {app}、{userappdata} 等 Inno 常量
```

---

## 模块二：系统托盘（launcher/main.go）

### 菜单结构

```
智能工艺系统 v2.0          ← 标题项（灰色，不可点击，版本从编译时 ldflags 注入）
─────────────────
🌐  打开界面
─────────────────
🔑  查看机器码
📋  打开日志
🔄  重启后端
─────────────────
✕  退出
```

### 各项行为

| 菜单项 | 实现 |
|--------|------|
| 打开界面 | `open.Start("http://127.0.0.1:5090")` 或 `ShellExecute` |
| 查看机器码 | 调用现有 `getMachineID()` → `walk.MsgBox` 弹窗展示，全选可复制 |
| 打开日志 | `exec.Command("notepad.exe", filepath.Join(appDir, "logs", "backend.log")).Start()` |
| 重启后端 | `stopBackend()` → `startBackend()`，期间托盘图标可短暂变灰提示 |
| 退出 | `stopBackend()` → `systray.Quit()` |

### v1 遗留清理

`startBackend()` 中删除：
```go
// 删除这两行
cmd.Env = append(os.Environ(), "PADDLE_PDX_CACHE_HOME="+...)
cmd.Env = append(cmd.Env, "PADDLEOCR_VERSION="+...)
```

版本号注入（编译时）：
```go
var Version = "dev"  // build.bat 通过 -ldflags "-X main.Version=v2.0" 覆盖
```

---

## 模块三：构建流程

### 目录结构

```
package_install_t/
├── version.txt              ← 唯一版本号来源，内容示例: 2.0
├── build.bat                ← 一键构建入口
└── build/
    ├── installer.iss        ← 接受 /DAppVersion 参数
    ├── launcher/
    │   └── main.go          ← var Version = "dev"（编译时注入）
    ├── site-packages/       ← 清理 paddle*，加入 rapidocr-onnxruntime
    └── ocr_models/          ← 整目录删除
```

### build.bat 逻辑

```bat
@echo off
set /p VERSION=<version.txt
echo [build] Version = %VERSION%

echo [1/3] Compiling launcher...
cd build\launcher
go build -ldflags "-X main.Version=v%VERSION%" -o ..\SmartProcess.exe .
if errorlevel 1 ( echo FAILED & exit /b 1 )
cd ..\..

echo [2/3] Running Inno Setup...
iscc /DAppVersion=%VERSION% build\installer.iss
if errorlevel 1 ( echo FAILED & exit /b 1 )

echo [3/3] Done. Output: SmartProcess_v%VERSION%_Setup.exe
```

输出文件名：`SmartProcess_v2.0_Setup.exe`（由 installer.iss `OutputBaseFilename` 使用 `{#AppVersion}` 构造）。

### site-packages 清理

删除：
- `paddle/`
- `paddleocr/`
- `paddlepaddle*/`（含 dist-info）
- `../ocr_models/`（PaddleOCR 模型目录，整体删除）

添加（从主项目 `.venv` 中复制）：
- `rapidocr_onnxruntime/`
- `onnxruntime/`（若未包含）
- `pyclipper/`（若未包含）

---

## 不在本次范围内

- 安装包代码签名（EV 证书）
- 自动更新机制
- 卸载时清理 db_data 数据（当前设计保留用户数据）
- Linux / macOS 打包
