# v2 安装包实现计划

**关联设计文档：** `2026-06-03-v2-installer-design.md`  
**打包项目根目录：** `F:\Work_Dir\package_install_t`  
**关键文件：**
- `build\installer.iss` — Inno Setup 脚本
- `build\launcher\main.go` — Go 系统托盘程序
- `build\site-packages\` — 内嵌 Python 包目录

---

## 执行顺序

```
Step 1 → version.txt + build.bat（构建基础设施）
Step 2 → launcher/main.go（Go 程序改造）
Step 3 → installer.iss（Inno Setup 改造）
Step 4 → site-packages 清理
Step 5 → 联调验证
```

---

## Step 1：构建基础设施

### 1.1 创建 version.txt

文件路径：`F:\Work_Dir\package_install_t\version.txt`

```
2.0
```

### 1.2 创建 build.bat

文件路径：`F:\Work_Dir\package_install_t\build.bat`

```bat
@echo off
chcp 65001 >nul
setlocal

:: 读取版本号
set /p VERSION=<version.txt
echo [build] 版本：v%VERSION%

:: 1. 编译 launcher
echo [1/3] 编译 launcher...
cd build\launcher
go build -ldflags "-X main.Version=v%VERSION%" -o ..\SmartProcess.exe .
if errorlevel 1 (
    echo [ERROR] launcher 编译失败
    exit /b 1
)
cd ..\..
echo [1/3] OK — build\SmartProcess.exe

:: 2. 运行 Inno Setup
echo [2/3] 打包安装程序...
iscc /DAppVersion=%VERSION% build\installer.iss
if errorlevel 1 (
    echo [ERROR] Inno Setup 编译失败（确认 iscc 在 PATH 中）
    exit /b 1
)
echo [2/3] OK — dist\SmartProcess_v%VERSION%_Setup.exe

echo.
echo [3/3] 完成！
echo   输出：dist\SmartProcess_v%VERSION%_Setup.exe
pause
```

**依赖条件：** `iscc.exe` 需在系统 PATH（Inno Setup 6 安装后默认添加）；`go` 命令需在 PATH。

---

## Step 2：launcher/main.go 改造

文件路径：`F:\Work_Dir\package_install_t\build\launcher\main.go`

### 2.1 添加版本变量（文件顶部 var 块）

```go
// 编译时由 build.bat 注入：-ldflags "-X main.Version=v2.0"
var Version = "dev"
```

### 2.2 清理 startBackend() 中的 PADDLE 环境变量

找到 `startBackend()` 函数，删除以下两行：

```go
// 删除这两行
"PADDLE_PDX_CACHE_HOME="+filepath.Join(dir, "ocr_models"),
"PADDLEOCR_VERSION=PP-OCRv4",
```

修改后 `cmd.Env` 只保留：

```go
cmd.Env = append(os.Environ(), "FLASK_DEBUG=0")
```

### 2.3 添加 stopBackend() 函数

在 `startBackend()` 之后添加：

```go
func stopBackend() {
    if backendCmd != nil && backendCmd.Process != nil {
        backendCmd.Process.Kill()
        backendCmd.Wait()
        backendCmd = nil
    }
}
```

### 2.4 添加 showMachineIDDialog() 函数

```go
func showMachineIDDialog() {
    id := getMachineID()
    showMsgBox("本机机器码",
        "请将以下机器码发送给管理员以获取授权文件：\n\n"+
            id+"\n\n"+
            "（可直接全选此对话框中的文本并复制）",
        mbIconInfo|mbOK)
}
```

### 2.5 添加 openLog() 函数

```go
func openLog() {
    logPath := filepath.Join(installDir(), "logs", "backend.log")
    exec.Command("notepad.exe", logPath).Start()
}
```

### 2.6 改造 onReady()：更新托盘菜单

用以下内容替换现有的 `onReady()` 函数：

```go
func onReady() {
    systray.SetIcon(iconData)
    systray.SetTitle("智能工艺系统")
    systray.SetTooltip("智能工艺系统 " + Version + " - 正在启动...")

    // 标题项（不可点击）
    mTitle := systray.AddMenuItem("智能工艺系统 "+Version, "")
    mTitle.Disable()
    systray.AddSeparator()

    mOpen := systray.AddMenuItem("打开界面", "在浏览器中打开系统")
    mOpen.Disable()
    systray.AddSeparator()

    mMachineID := systray.AddMenuItem("查看机器码", "显示本机授权机器码")
    mLog := systray.AddMenuItem("打开日志", "用记事本打开后端日志")
    mRestart := systray.AddMenuItem("重启后端", "重新启动后端服务")
    systray.AddSeparator()

    mQuit := systray.AddMenuItem("退出", "关闭程序并停止后台服务")

    go func() {
        if !isReady() {
            startBackend()
            waitReady(60 * time.Second)
        }
        systray.SetTooltip("智能工艺系统 " + Version + " - 运行中")
        mOpen.Enable()
        openBrowser(fmt.Sprintf("http://localhost:%d/dev/demo-industrial-console", port))

        for {
            select {
            case <-mOpen.ClickedCh:
                openBrowser(fmt.Sprintf("http://localhost:%d/dev/demo-industrial-console", port))
            case <-mMachineID.ClickedCh:
                showMachineIDDialog()
            case <-mLog.ClickedCh:
                openLog()
            case <-mRestart.ClickedCh:
                stopBackend()
                startBackend()
                waitReady(30 * time.Second)
                systray.SetTooltip("智能工艺系统 " + Version + " - 运行中")
            case <-mQuit.ClickedCh:
                systray.Quit()
            }
        }
    }()
}
```

### 2.7 更新 onExit()

```go
func onExit() {
    stopBackend()
}
```

（原来是直接 `Kill`，现在复用 `stopBackend()`）

---

## Step 3：installer.iss 改造

文件路径：`F:\Work_Dir\package_install_t\build\installer.iss`

### 3.1 文件头：版本号改为外部传入，删除绝对路径

```iss
; 版本号由 build.bat 通过 /DAppVersion=x.x 传入
#ifndef AppVersion
  #define AppVersion "dev"
#endif
#define MyAppName "智能工艺系统"
#define MyAppExeName "SmartProcess.exe"
```

**删除**以下三行（绝对路径）：
```iss
#define BuildDir "F:\Work_Dir\package_install_t\build"
#define ProjectDir "F:\Work_Dir\2D-v"
#define DistDir "F:\Work_Dir\package_install_t\dist"
```

### 3.2 [Setup] 节修改

```iss
[Setup]
AppName={#MyAppName}
AppVersion={#AppVersion}
AppPublisher=内部工具
DefaultDirName=C:\SmartProcess
DefaultGroupName=智能工艺系统
AllowNoIcons=yes
OutputDir=..\dist
OutputBaseFilename=SmartProcess_v{#AppVersion}_Setup
Compression=lzma2/ultra64
SolidCompression=yes
CloseApplications=yes
PrivilegesRequired=admin
DisableDirPage=no
DisableProgramGroupPage=yes
SetupIconFile=launcher\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
WizardStyle=modern
WizardImageFile=wizard_banner.bmp
WizardSmallImageFile=wizard_small.bmp
```

> `WizardImageFile` 为左侧大图（164×314px），`WizardSmallImageFile` 为顶部小图（55×58px）。
> 如暂不提供自定义位图，删除这两行，使用 Inno Setup 默认图。

### 3.3 [Files] 节修改

路径改为相对于 installer.iss 所在目录的相对路径，并**删除** ocr_models 那一行：

```iss
[Files]
; Python 运行时
Source: "python\*"; DestDir: "{app}\python"; Flags: ignoreversion recursesubdirs createallsubdirs

; Python 包（已换为 RapidOCR）
Source: "site-packages\*"; DestDir: "{app}\site-packages"; Flags: ignoreversion recursesubdirs createallsubdirs

; 删除原来的 ocr_models 行（PaddleOCR 模型，不再需要）
; Source: "ocr_models\*"; ...  ← 整行删除

; 项目后端（相对路径，需在打包时将 backend 复制到 build\app\backend）
Source: "app\backend\*"; DestDir: "{app}\app\backend"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "task_store.db,task_store.db-shm,task_store.db-wal,*.pyc,__pycache__"

; 项目前端
Source: "app\updated_front\*"; DestDir: "{app}\app\updated_front"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "start_flask_demo.bat"

; 知识库数据库
Source: "2d-v.db"; DestDir: "{app}\app\db_data"; Flags: ignoreversion

; API Key 配置
Source: "app\.env"; DestDir: "{app}\app"; Flags: ignoreversion

; 启动器（build.bat 编译输出到 build\SmartProcess.exe）
Source: "SmartProcess.exe"; DestDir: "{app}"; Flags: ignoreversion
```

### 3.4 [Dirs] 节：新增 kb_previews 目录

```iss
[Dirs]
Name: "{app}\app\uploads"
Name: "{app}\app\output"
Name: "{app}\app\db_data\kb_previews"
Name: "{app}\logs"
```

### 3.5 [Registry] 节：删除全部 PADDLE 相关条目

**删除整个** `[Registry]` 节（v1 只有一条 PADDLE_PDX_CACHE_HOME）。

### 3.6 [Icons] 节：更新 exe 名称

```iss
[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
```

### 3.7 [Run] 节：更新 exe 名称

```iss
[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "立即启动系统"; Flags: postinstall nowait skipifsilent
```

### 3.8 [UninstallDelete] 节：删除 ocr_models 行，保留 kb_previews

```iss
[UninstallDelete]
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\app\uploads"
Type: filesandordirs; Name: "{app}\app\output"
; 注意：db_data\kb_previews 不删除（用户数据）
Type: filesandordirs; Name: "{app}\site-packages"
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\app"
Type: dirifempty; Name: "{app}"
```

### 3.9 [Code] 节：更新卸载函数中的 exe 名称

```pascal
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;
begin
  if CurUninstallStep = usUninstall then
  begin
    Exec('taskkill', '/f /im SmartProcess.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Exec('taskkill', '/f /im python.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
end;
```

（`launcher.exe` → `SmartProcess.exe`）

---

## Step 4：site-packages 清理

**目录：** `F:\Work_Dir\package_install_t\build\site-packages\`

### 4.1 删除 PaddleOCR 相关目录

在 `site-packages\` 下删除（如存在）：
- `paddle\`
- `paddleocr\`
- `paddlepaddle\`
- `paddlepaddle_gpu\`
- 任何 `paddlepaddle*.dist-info\` 目录
- `paddleocr*.dist-info\`

同时删除：
- `F:\Work_Dir\package_install_t\build\ocr_models\`（整个目录，PaddleOCR 模型）

### 4.2 添加 RapidOCR 相关包

从主项目 `.venv` 复制到 `site-packages\`：

```
F:\Work_Dir\2D-v\.venv\Lib\site-packages\rapidocr_onnxruntime\  →  build\site-packages\rapidocr_onnxruntime\
F:\Work_Dir\2D-v\.venv\Lib\site-packages\onnxruntime\           →  build\site-packages\onnxruntime\        （若不存在）
F:\Work_Dir\2D-v\.venv\Lib\site-packages\pyclipper\             →  build\site-packages\pyclipper\          （若不存在）
```

**验证方法：** 在 build 环境用内嵌 Python 测试：
```bat
build\python\python.exe -c "from rapidocr_onnxruntime import RapidOCR; print('OK')"
```

---

## Step 5：联调验证

### 5.1 构建验证

```bat
cd F:\Work_Dir\package_install_t
build.bat
```

预期输出：
- `build\SmartProcess.exe` 生成
- `dist\SmartProcess_v2.0_Setup.exe` 生成

### 5.2 安装验证

1. 运行 `SmartProcess_v2.0_Setup.exe`
2. 确认向导共 5 步（欢迎 → 目录 → 激活 → 安装 → 完成）
3. 安装至测试目录，勾选"立即启动"
4. 确认托盘图标出现，标题显示"智能工艺系统 v2.0"
5. 测试各托盘菜单项：
   - 打开界面 → 浏览器打开
   - 查看机器码 → 弹窗显示 16 位 HEX 机器码
   - 打开日志 → 记事本打开 logs\backend.log
   - 重启后端 → 后端进程重启，约 5s 后恢复可用
6. 确认 `{app}\app\db_data\kb_previews\` 目录存在
7. 确认 `{app}\ocr_models\` 目录不存在

### 5.3 卸载验证

1. 控制面板卸载
2. 确认 `SmartProcess.exe` 进程已终止（无残留）
3. 确认安装目录已清理（如为空目录则删除）

---

## 风险与注意事项

| 风险 | 对策 |
|------|------|
| installer.iss 相对路径问题 | iscc 以 iss 文件所在目录为基准；build.bat 中 `iscc` 调用时不需要 `cd`，直接 `iscc build\installer.iss` |
| site-packages 包依赖不完整 | 先用内嵌 Python 跑 `python -c "from rapidocr_onnxruntime import RapidOCR"` 验证，缺包时逐一从 .venv 补充 |
| Go 编译环境 | 确认 `go env GOARCH` 为 `amd64`，目标机器须是 64-bit Windows |
| 旧安装残留 | 测试时先彻底卸载 v1，避免注册表 / 进程冲突 |
