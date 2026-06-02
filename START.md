# 快速启动指南

## 第一次使用

### 步骤 1：初始化环境

**Windows（推荐）：** 双击根目录的 `setup.bat`，自动完成以下所有操作：
- 创建 `.venv` 虚拟环境
- 安装全部依赖
- 从 `.env.example` 生成 `.env`
- 检测 FreeCAD 安装路径

**Linux：** 手动执行：
```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
```

`.env.example` 已包含可用的 API Key，复制后**无需修改**即可启动。

如需切换 API 配置，编辑 `.env` 或运行 `switch_mode.bat`（Windows）。

---

### 步骤 2：安装 Poppler（Windows 必需，Linux 跳过）

1. 下载：https://github.com/oschwartz10612/poppler-windows/releases/
2. 解压，记下 `Library\bin` 的完整路径
3. 在 `.env` 末尾添加：
   ```
   POPPLER_PATH=D:\你的路径\poppler\Library\bin
   ```

Linux 一行搞定：
```bash
sudo apt install poppler-utils
```

---

### 步骤 3：安装 FreeCAD 1.1（三视图功能必需）

- **Windows**：从 https://www.freecad.org 下载安装，系统自动找到路径
- **Linux**：
  ```bash
  sudo add-apt-repository ppa:freecad-maintainers/freecad-stable
  sudo apt update && sudo apt install freecad xvfb
  ```

---

## 日常启动

### Windows

```bat
updated_front\start_flask_demo.bat
```

脚本自动等待服务就绪后打开浏览器，无需手动访问地址。

> 手动启动：`.venv\Scripts\python -m backend.run`，然后访问 **http://localhost:5000/dev/demo-industrial-console**

### Linux 服务器

```bash
source .venv/bin/activate
xvfb-run -a python -m backend.run
```

> `xvfb-run` 为 FreeCAD 提供虚拟显示，无此命令截图功能会失败。

---

## 基本操作

### 上传 PRT 文件生成工艺

1. 打开 http://localhost:5000/dev/demo-industrial-console
2. 点击左侧「**上传 PRT**」，选择 `.prt` 或 `.prt.N` 文件
3. 右侧进度条依次显示：
   - OnShape 转换（约 30–60 秒）
   - FreeCAD 三视图截图（约 20–40 秒）
   - 几何 + VLM 特征提取（约 10–30 秒）
4. 弹出「**特征审阅**」界面，可编辑提取的特征文本
5. 点击「**确认并生成**」
6. 等待工艺生成（约 20–60 秒）
7. 在「工艺规程」标签页查看结果，点击「**导出 Excel**」下载

### 上传 PDF 文件

流程与 PRT 相同，跳过 OnShape 和 FreeCAD 步骤，直接进行视觉分析。

### 批量导入知识库（ZIP）

1. 准备 ZIP：每个零件需包含 `.prt`/`.prt.N` + 对应的 `.xlsx` 工艺
2. 左侧面板切换到「**知识库导入**」标签
3. 上传 ZIP，选择目标工艺库
4. 等待处理完成

### 切换云模式 / 本地模式（Windows）

双击运行 `switch_mode.bat`：
- **选 1**：使用云端 DeepSeek + 豆包（需联网）
- **选 2**：使用本地 vLLM（需内网服务器 192.168.2.24:8000）

---

## 排查问题

| 现象 | 原因 | 解决 |
|------|------|------|
| 页面打不开 | 服务未启动 | 确认 `python backend/app.py` 在运行，端口 5000 未被占用 |
| OnShape 转换超时 | 网络或凭证问题 | 检查 `.env` 中 `onshape_credentials/did/wid`，确认能访问 cad.onshape.com |
| 三视图截图失败（Linux） | 无虚拟显示 | 用 `xvfb-run -a` 启动 |
| PDF 报 Poppler 错误 | Poppler 未安装或路径错 | Windows：配置 `POPPLER_PATH`；Linux：`apt install poppler-utils` |
| VLM 特征提取跳过 | API 未配置 | 确认 `.env` 中 `VISION_API_KEY/BASE/MODEL_ID` 有值 |
| RAG 检索无结果 | 数据库缺失 | 确认 `db_data/vector_map_new.db` 存在 |
