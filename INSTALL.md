# 迁移到新机器 - 安装指南

## 前置软件（手动安装，共 6 个）

| # | 软件 | 版本要求 | 必要性 | 下载地址 |
|---|------|---------|--------|---------|
| 1 | Python | >= 3.11 | 必须 | https://www.python.org/downloads/ |
| 2 | FreeCAD | 1.1 | 必须 | https://www.freecad.org/downloads.php |
| 3 | Node.js | >=18 LTS | 必须 | https://nodejs.org/ |
| 4 | Git | 任意 | 必须 | https://git-scm.com/downloads |
| 5 | Creo Parametric | 9.0 | 可选 | PTC 官方渠道 |

> 安装 Python 时务必勾选 **"Add Python to PATH"**。
> Creo 仅 PRT 转换时需要。
> PDF 转 PNG 由 PyMuPDF 处理（pip 自动安装），无需单独安装 Poppler。
>
> Creo 默认路径: `C:\Program Files\PTC\Creo 9.0.0.0\Parametric\bin\parametric.exe`
> 若安装在其他位置，需在 `.env` 中设置 `CREO_EXE` / `CREO_BASE_DIR` / `CREO_OUT_DIR`。

### 依赖包统计

| 类别 | 数量 | 安装方式 |
|------|------|---------|
| Python 包 | 15 | `pip install -r backend\requirements.txt` |
| Node.js 包 | 1 | `npm install`（pptxgenjs，PPT 生成） |
| 外部软件 | 6 | 手动下载安装（见上表） |
| **合计** | **22** | — |

**Python 包明细：**

| 分类 | 包名 | 用途 |
|------|------|------|
| Web 框架 | flask, flask-cors, werkzeug | HTTP 服务 |
| AI/ML | langchain-openai, langchain-core, openai, numpy | LLM 推理 + 向量 |
| OCR | paddlepaddle, paddleocr | 工程图标注识别 |
| PDF | pdf2image, Pillow | PDF 转图片 |
| 环境 | python-dotenv | .env 配置加载 |
| Excel | openpyxl | Excel 读写 |
| HTTP | requests | OnShape API 调用 |
| 自动化 | pywinauto | Creo 窗口自动确认 |

---

## 快速开始

### 第一步：获取代码

```bat
git clone <仓库地址>
cd my_working
```

或者直接复制整个项目文件夹（需包含 `db_data\` 目录）。

### 第二步：一键初始化环境

双击或在 cmd 中运行：

```bat
setup.bat
```

脚本会自动完成：
- 创建 Python 虚拟环境 `.venv`
- 安装所有依赖（`backend\requirements.txt`）
- 从 `.env.example` 生成 `.env`
- 检查 FreeCAD 安装路径

### 第三步：启动系统

```bat
updated_front\start_flask_demo.bat
```

浏览器会自动打开 `http://127.0.0.1:5000`。

---

## FreeCAD 路径不在默认位置

如果 FreeCAD 安装在非默认路径，编辑 `.env` 加入：

```
FREECAD_BIN=D:\你的路径\FreeCAD 1.1\bin
FREECAD_LIB=D:\你的路径\FreeCAD 1.1\lib
```

---

## 迁移注意事项

| 文件/目录 | 是否在 git 中 | 说明 |
|-----------|--------------|------|
| `db_data\vector_map_new.db` | 是，`git clone` 自动获取 | 若原机器有未提交的新数据，需手动 `git push` 后再 `clone` |
| `.env` | **否** | `setup.bat` 会自动从 `.env.example` 生成 |

---

## 常见问题

**Q: `setup.bat` 报"Python未找到"**  
A: 安装 Python (>= 3.11) 时勾选 **"Add Python to PATH"**，然后重新打开 cmd。

**Q: 启动后上传 PRT 文件报错**  
A: 检查 FreeCAD 路径是否正确，查看 `backend.log` 获取详细错误。

**Q: 知识库检索返回空**  
A: 确认 `db_data\vector_map_new.db` 存在（`git clone` 自动获取；若原机器有新数据需先 `git push`）。
