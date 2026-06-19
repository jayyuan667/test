# EXE 安装包设计文档

**日期：** 2026-05-28  
**状态：** 待实现  
**目标：** 将工艺规程智能生成系统打包成面向工厂工人的 Windows 安装包

---

## 背景与约束

- **目标用户：** 工厂/车间工人，非技术用户，要求双击即用
- **交付方式：** U 盘拷贝，安装包单文件
- **网络环境：** 安装后正常联网，AI API Key 已预先配置
- **排除功能：** FreeCAD 三维模型功能（该批用户仅使用 2D 图纸/PDF 流程）

---

## 方案选型

选用 **Inno Setup 专业安装包**，理由：
- `setup.exe` 是工厂工人最熟悉的安装形式
- 内置进度条，安装过程可见
- 自动创建桌面快捷方式和卸载程序
- 安装路径、环境变量由脚本统一管理，用户无需手动配置

---

## 运行时目录结构

安装完成后，目标机器的目录结构：

```
C:\ProcessGen\                     ← 安装根目录（ASCII 路径）
├── python\                        # Python 3.11 Embeddable
│   └── python.exe
├── site-packages\                 # 所有 Python 包（预装，无需 pip）
├── poppler\bin\                   # PDF→图片转换二进制
├── ocr_models\                    # PaddleOCR 模型文件（预下载）
│   └── .paddleocr\
├── app\                           # 项目代码
│   ├── backend\
│   ├── updated_front\
│   └── data\
│       ├── uploads\
│       ├── output\
│       └── db_data\               # vector_map_new.db 随包携带
├── logs\                          # 运行日志
└── launcher.exe                   # 系统托盘启动器
```

**路径选择原则：** 使用 `C:\ProcessGen\` 而非含中文的路径，避免 PaddlePaddle C++ 扩展在中文路径下的已知兼容性问题。

---

## 五个实施阶段

### 阶段一：准备构建工具

在开发机上安装：

| 工具 | 用途 |
|------|------|
| Inno Setup 6 | 将文件打包为 setup.exe |
| Go 1.22+ | 编译 launcher.exe |
| Python 3.11 | 已有，确认版本 |

**产出：** 开发机具备完整构建能力

---

### 阶段二：打包 Python 环境

#### 2a. 下载 Python 3.13.5 Embeddable

> **注意：** Embeddable Python 版本必须与打包机器的系统 Python 一致（均为 3.13），否则 C 扩展（NumPy、PaddlePaddle 等）版本不匹配无法加载。

从 [python.org/downloads](https://www.python.org/ftp/python/3.13.5/python-3.13.5-embed-amd64.zip) 下载  
`python-3.13.5-embed-amd64.zip`，解压至 `build\python\`。

解压后编辑 `build\python\python313._pth`，修改为：
```
python313.zip
.
..\site-packages

import site
```
这样 Python 启动时会自动加载 site-packages 目录中的包。

#### 2b. 预装所有 Python 包

```powershell
python -m pip install -r backend\requirements.txt `
    --target build\site-packages\
```

将所有包装入 `build\site-packages\`，目标机器无需执行 pip。

#### 2b. 下载 Poppler

从 [github.com/oschwartz10612/poppler-windows](https://github.com/oschwartz10612/poppler-windows) 下载最新 Release，解压至 `build\poppler\`。

#### 2c. 预热 PaddleOCR 模型

```python
# build/download_ocr_models.py
import os
os.environ["PADDLE_PDX_CACHE_HOME"] = os.path.abspath("build/ocr_models")
from paddleocr import PaddleOCR
ocr = PaddleOCR(use_angle_cls=True, lang="ch")
# 触发模型下载后退出，模型文件已保存到 build/ocr_models/
```

**产出：** `build/` 文件夹，含 site-packages（约 1.5GB）、poppler、ocr_models

---

### 阶段三：编写 launcher.exe

用 Go 编写，编译为单个 `.exe`，约 5MB，无运行时依赖。

#### 功能流程

```
双击 launcher.exe
    ↓
检查端口 5090 是否已占用
    ↓（未占用）
以子进程启动 Python 后台：
    C:\ProcessGen\python\python.exe C:\ProcessGen\app\backend\run.py
    （FLASK_DEBUG=0，工作目录设为 C:\ProcessGen\app）
    ↓
轮询 GET http://localhost:5090/api/health
最多等待 30 秒，每 500ms 一次
    ↓（就绪）
打开默认浏览器：http://localhost:5090
    ↓
系统托盘图标常驻
    右键菜单：
      - 打开界面
      - 查看日志
      - 退出（同时终止后台子进程）
```

#### 关键环境变量（launcher 启动子进程时注入）

```
PADDLE_PDX_CACHE_HOME = C:\ProcessGen\ocr_models
POPPLER_PATH    = C:\ProcessGen\poppler\bin
FLASK_DEBUG     = 0
```

> Python 的包搜索路径通过 `python311._pth` 文件配置（见阶段二），无需在此设置 PYTHONPATH。

#### API Key 预置

构建安装包前，需将已配好的 API Key 填入 `backend\config.json`，该文件会被 Inno Setup 原样复制到 `{app}\app\backend\config.json`。目标机器安装完成后 Key 即生效，无需工人手动配置。

#### 构建命令

```powershell
cd build\launcher
go build -ldflags="-H windowsgui" -o ..\..\dist\launcher.exe .
```

`-H windowsgui` 确保启动时不弹出黑色命令行窗口。

**产出：** `dist\launcher.exe`

---

### 阶段四：编写 Inno Setup 脚本

文件：`build\installer.iss`

#### 关键配置节

```ini
[Setup]
AppName=工艺规程智能生成系统
AppVersion=1.0
DefaultDirName=C:\ProcessGen
DefaultGroupName=工艺规程系统
OutputDir=dist
OutputBaseFilename=工艺规程系统_v1.0_Setup
Compression=lzma2/ultra64

[Files]
; Python 运行时
Source: "build\python\*"; DestDir: "{app}\python"; Flags: recursesubdirs

; Python 包
Source: "build\site-packages\*"; DestDir: "{app}\site-packages"; Flags: recursesubdirs

; Poppler
Source: "build\poppler\*"; DestDir: "{app}\poppler"; Flags: recursesubdirs

; OCR 模型
Source: "build\ocr_models\*"; DestDir: "{app}\ocr_models"; Flags: recursesubdirs

; 项目代码
Source: "..\backend\*"; DestDir: "{app}\app\backend"; Flags: recursesubdirs
Source: "..\updated_front\*"; DestDir: "{app}\app\updated_front"; Flags: recursesubdirs
Source: "..\backend\config.json"; DestDir: "{app}\app\backend"; Flags: skipifsourcedoesntexist

; 数据库（知识库）
Source: "..\db_data\*"; DestDir: "{app}\app\data\db_data"; Flags: recursesubdirs skipifsourcedoesntexist

; 启动器
Source: "dist\launcher.exe"; DestDir: "{app}"

[Icons]
Name: "{commondesktop}\工艺规程系统"; Filename: "{app}\launcher.exe"
Name: "{group}\工艺规程系统"; Filename: "{app}\launcher.exe"
Name: "{group}\卸载"; Filename: "{uninstallexe}"

[Registry]
; 设置系统级环境变量，所有用户生效
Root: HKLM; Subkey: "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"; \
    ValueType: string; ValueName: "PADDLE_PDX_CACHE_HOME"; ValueData: "{app}\ocr_models"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\app\data\uploads"
Type: filesandordirs; Name: "{app}\app\data\output"
```

**产出：** 运行 `iscc build\installer.iss` → `dist\工艺规程系统_v1.0_Setup.exe`（约 1.5GB）

---

### 阶段五：测试验收

在**全新 Windows 10/11 机器**（或快照虚拟机）上：

| 测试项 | 预期结果 |
|--------|----------|
| 双击 setup.exe，走完安装流程 | 无报错，桌面出现快捷方式 |
| 双击桌面快捷方式 | 30 秒内浏览器打开系统界面 |
| 上传一张 PDF 图纸 | OCR 正常提取尺寸信息 |
| AI 分析一张图纸 | API 调用成功，返回工艺规程 |
| 系统托盘右键 → 退出 | 后台服务正常停止 |
| 控制面板卸载 | 文件清理完整 |

---

## 体积预估

| 组成 | 压缩前 | 压缩后（lzma2） |
|------|--------|----------------|
| Python 3.11 Embeddable | 30 MB | ~15 MB |
| site-packages（PaddlePaddle 为主） | ~1.5 GB | ~700 MB |
| Poppler 二进制 | 30 MB | ~15 MB |
| PaddleOCR 模型（中文+英文） | 400 MB | ~350 MB |
| 项目代码 | 20 MB | ~5 MB |
| **合计** | **~2 GB** | **~1.1 GB** |

最终 setup.exe 约 **1.1–1.3 GB**，U 盘可放。

---

## 关键风险与缓解

| 风险 | 缓解方案 |
|------|----------|
| PaddlePaddle 在目标机器路径下报 DLL 错误 | 安装路径强制 ASCII（`C:\ProcessGen`），测试多台机器验证 |
| OCR 模型路径未生效 | 通过注册表写入系统环境变量，launcher 启动时再次注入 |
| 工人双击没反应（Flask 启动慢） | launcher 显示启动进度提示："正在启动，请稍候..." |
| 安装包在某台机器上解压失败 | lzma2 压缩稳定；备选方案：降级为 zip 压缩 |
| 旧版本升级安装 | Inno Setup 配置 `CloseApplications=yes`，安装前自动关闭旧进程 |
