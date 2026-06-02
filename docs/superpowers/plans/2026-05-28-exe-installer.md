# 实施计划：EXE 安装包

**关联设计文档：** `docs/superpowers/specs/2026-05-28-exe-installer-design.md`  
**日期：** 2026-05-28

---

## 任务列表

### 阶段一：准备构建工具

- [ ] **T1** 安装 Inno Setup 6  
  下载地址：https://jrsoftware.org/isdl.php  
  安装完成后确认 `iscc` 命令可用（加入 PATH 或记录安装路径）

- [ ] **T2** 安装 Go 1.22+  
  下载地址：https://go.dev/dl/  
  安装后运行 `go version` 确认

- [ ] **T3** 确认 Python 3.11 可用  
  运行 `python --version`，确认输出为 3.11.x

---

### 阶段二：打包 Python 环境

- [ ] **T4** 在项目根目录创建 `build/` 构建目录结构  
  ```
  build/
  ├── python/          ← 放 Embeddable Python
  ├── site-packages/   ← 放预装的包
  ├── poppler/         ← 放 Poppler 二进制
  ├── ocr_models/      ← 放 PaddleOCR 模型
  └── launcher/        ← launcher Go 源码
  ```

- [ ] **T5** 下载 Python 3.11.9 Embeddable  
  URL：https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip  
  解压至 `build/python/`  
  编辑 `build/python/python311._pth`，在文件末尾追加一行：
  ```
  ..\site-packages
  ```

- [ ] **T6** 预装所有 Python 包至 `build/site-packages/`  
  ```powershell
  python -m pip install -r backend\requirements.txt --target build\site-packages\
  ```
  预计耗时 10-20 分钟（PaddlePaddle 约 700MB）

- [x] **T7** ~~下载 Poppler~~ → 跳过，改用 PyMuPDF  
  `pdf_converter.py` 优先用 `fitz`，Poppler 仅备选。  
  已额外安装 `pymupdf 1.27.2` 至 site-packages，无需 Poppler 二进制。

- [ ] **T8** 预热并导出 PaddleOCR 模型  
  新建脚本 `build/download_ocr_models.py`：
  ```python
  import os, sys
  sys.path.insert(0, os.path.abspath("build/site-packages"))
  os.environ["PADDLEOCR_HOME"] = os.path.abspath("build/ocr_models")
  from paddleocr import PaddleOCR
  print("正在下载中文模型...")
  ocr = PaddleOCR(use_angle_cls=True, lang="ch")
  print("模型下载完成，保存至 build/ocr_models/")
  ```
  运行：`python build/download_ocr_models.py`

- [x] **T9** API Key 处理 → 通过 `.env` 文件  
  `backend/app.py` 的 `load_dotenv()` 从工作目录自动查找 `.env`。  
  Inno Setup 将项目根目录的 `.env` 复制到 `{app}\app\.env`；  
  launcher 启动后台时设 `WorkDir = {app}\app`，Key 自动生效，无需改代码。  
  **注意：** 打包前确认 `.env` 文件在项目根目录且包含真实 Key。

---

### 阶段三：编写 launcher.exe

- [ ] **T10** 创建 launcher Go 项目  
  新建文件 `build/launcher/main.go`（见下方完整代码）  
  新建文件 `build/launcher/go.mod`

- [ ] **T11** 实现 launcher 核心功能  
  `build/launcher/main.go` 完整内容：

  ```go
  package main

  import (
      "fmt"
      "net/http"
      "os"
      "os/exec"
      "path/filepath"
      "runtime"
      "time"

      "github.com/getlantern/systray"
  )

  const (
      port    = 5090
      appName = "工艺规程系统"
  )

  var backendCmd *exec.Cmd

  func main() {
      systray.Run(onReady, onExit)
  }

  func onReady() {
      systray.SetTitle(appName)
      systray.SetTooltip(appName + " - 正在启动...")

      mOpen := systray.AddMenuItem("打开界面", "在浏览器中打开系统")
      mQuit := systray.AddMenuItem("退出", "停止服务并退出")

      go func() {
          if !isPortInUse(port) {
              startBackend()
              waitForBackend(30 * time.Second)
          }
          systray.SetTooltip(appName + " - 运行中")
          openBrowser(fmt.Sprintf("http://localhost:%d", port))

          for {
              select {
              case <-mOpen.ClickedCh:
                  openBrowser(fmt.Sprintf("http://localhost:%d", port))
              case <-mQuit.ClickedCh:
                  systray.Quit()
              }
          }
      }()
  }

  func onExit() {
      if backendCmd != nil && backendCmd.Process != nil {
          backendCmd.Process.Kill()
      }
  }

  func installDir() string {
      exe, _ := os.Executable()
      return filepath.Dir(exe)
  }

  func startBackend() {
      dir := installDir()
      pythonExe := filepath.Join(dir, "python", "python.exe")
      script := filepath.Join(dir, "app", "backend", "run.py")

      cmd := exec.Command(pythonExe, script)
      cmd.Dir = filepath.Join(dir, "app")  // load_dotenv() 在此目录找 .env
      cmd.Env = append(os.Environ(),
          "FLASK_DEBUG=0",
          "PADDLEOCR_HOME="+filepath.Join(dir, "ocr_models"),
          "POPPLER_PATH="+filepath.Join(dir, "poppler", "bin"),
      )

      logPath := filepath.Join(dir, "logs", "backend.log")
      os.MkdirAll(filepath.Join(dir, "logs"), 0755)
      logFile, _ := os.OpenFile(logPath, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0644)
      if logFile != nil {
          cmd.Stdout = logFile
          cmd.Stderr = logFile
      }

      backendCmd = cmd
      cmd.Start()
  }

  func isPortInUse(port int) bool {
      resp, err := http.Get(fmt.Sprintf("http://localhost:%d/api/health", port))
      if err != nil {
          return false
      }
      resp.Body.Close()
      return resp.StatusCode < 500
  }

  func waitForBackend(timeout time.Duration) {
      deadline := time.Now().Add(timeout)
      for time.Now().Before(deadline) {
          if isPortInUse(port) {
              return
          }
          time.Sleep(500 * time.Millisecond)
      }
  }

  func openBrowser(url string) {
      switch runtime.GOOS {
      case "windows":
          exec.Command("rundll32", "url.dll,FileProtocolHandler", url).Start()
      }
  }
  ```

- [ ] **T12** 创建 `build/launcher/go.mod`  
  ```
  module launcher

  go 1.22

  require github.com/getlantern/systray v1.2.2
  ```

- [ ] **T13** 下载依赖并编译  
  ```powershell
  cd build\launcher
  go mod tidy
  go build -ldflags="-H windowsgui" -o ..\..\dist\launcher.exe .
  ```
  确认 `dist/launcher.exe` 生成，大小约 5-10MB

---

### 阶段四：编写 Inno Setup 脚本

- [ ] **T14** 创建 `dist/` 输出目录

- [ ] **T15** 新建 `build/installer.iss`，内容如下：

  ```ini
  [Setup]
  AppName=工艺规程智能生成系统
  AppVersion=1.0
  AppPublisher=内部工具
  DefaultDirName=C:\ProcessGen
  DefaultGroupName=工艺规程系统
  AllowNoIcons=yes
  OutputDir=..\dist
  OutputBaseFilename=工艺规程系统_v1.0_Setup
  Compression=lzma2/ultra64
  SolidCompression=yes
  CloseApplications=yes
  PrivilegesRequired=admin

  [Languages]
  Name: "chinese"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

  [Tasks]
  Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务:"; Flags: checked

  [Files]
  Source: "python\*"; DestDir: "{app}\python"; Flags: ignoreversion recursesubdirs createallsubdirs
  Source: "site-packages\*"; DestDir: "{app}\site-packages"; Flags: ignoreversion recursesubdirs createallsubdirs
  Source: "poppler\*"; DestDir: "{app}\poppler"; Flags: ignoreversion recursesubdirs createallsubdirs
  Source: "ocr_models\*"; DestDir: "{app}\ocr_models"; Flags: ignoreversion recursesubdirs createallsubdirs
  Source: "..\backend\*"; DestDir: "{app}\app\backend"; Flags: ignoreversion recursesubdirs createallsubdirs
  Source: "..\updated_front\*"; DestDir: "{app}\app\updated_front"; Flags: ignoreversion recursesubdirs createallsubdirs
  Source: "..\db_data\*"; DestDir: "{app}\app\data\db_data"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist
  Source: "..\.env"; DestDir: "{app}\app"; Flags: ignoreversion
  Source: "..\dist\launcher.exe"; DestDir: "{app}"; Flags: ignoreversion

  [Dirs]
  Name: "{app}\app\data\uploads"
  Name: "{app}\app\data\output"
  Name: "{app}\logs"

  [Icons]
  Name: "{group}\工艺规程系统"; Filename: "{app}\launcher.exe"
  Name: "{group}\卸载工艺规程系统"; Filename: "{uninstallexe}"
  Name: "{commondesktop}\工艺规程系统"; Filename: "{app}\launcher.exe"; Tasks: desktopicon

  [Registry]
  Root: HKLM; Subkey: "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"; ValueType: string; ValueName: "PADDLEOCR_HOME"; ValueData: "{app}\ocr_models"; Flags: preservestringtype

  [UninstallDelete]
  Type: filesandordirs; Name: "{app}\logs"
  Type: filesandordirs; Name: "{app}\app\data\uploads"
  Type: filesandordirs; Name: "{app}\app\data\output"

  [Run]
  Filename: "{app}\launcher.exe"; Description: "立即启动系统"; Flags: postinstall nowait skipifsilent
  ```

- [ ] **T16** 编译安装包  
  ```powershell
  # 从 build/ 目录运行
  cd build
  & "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
  ```
  成功后 `dist/工艺规程系统_v1.0_Setup.exe` 生成

---

### 阶段五：测试验收

- [ ] **T17** 准备测试环境  
  使用全新 Windows 10/11 虚拟机（或快照），确认未安装 Python、FreeCAD 等

- [ ] **T18** 安装测试  
  - 双击 setup.exe，走完安装向导
  - 确认 `C:\ProcessGen\` 目录结构正确
  - 确认桌面快捷方式存在

- [ ] **T19** 功能验收  
  - 双击桌面图标 → 30 秒内浏览器打开系统界面
  - 上传一张 PDF 图纸 → OCR 正常提取
  - 触发 AI 分析 → API 调用成功，返回工艺规程
  - 系统托盘右键 → 退出 → 后台进程停止

- [ ] **T20** 卸载测试  
  - 控制面板 → 卸载程序 → 卸载系统
  - 确认 `C:\ProcessGen\` 目录已清理（uploads/output 按设计保留）

---

## 预计工时

| 阶段 | 预计时间 |
|------|----------|
| 阶段一：准备工具 | 1-2 小时 |
| 阶段二：打包环境 | 2-3 小时（含下载等待） |
| 阶段三：launcher | 2-4 小时 |
| 阶段四：Inno Setup | 1-2 小时 |
| 阶段五：测试 | 2-4 小时 |
| **合计** | **约 2 天** |

## 开始顺序建议

先完成 **T1-T3**（装工具），再并行推进 **T4-T9**（准备素材）和 **T10-T13**（写 launcher）。launcher 编译成功、`build/` 目录就绪后，T15-T16（Inno Setup）半天内可完成。
