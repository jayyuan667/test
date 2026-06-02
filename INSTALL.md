# 迁移到新机器 - 安装指南

## 前置软件（手动安装）

| 软件 | 版本要求 | 下载地址 |
|------|---------|---------|
| Python | 3.11.x | https://www.python.org/downloads/release/python-3119/ |
| FreeCAD | 1.1 | https://www.freecad.org/downloads.php |
| Git | 任意 | https://git-scm.com/downloads |

> Poppler（PDF转图片）可选，仅在处理 PDF 时需要。

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
A: 安装 Python 3.11 时勾选 **"Add Python to PATH"**，然后重新打开 cmd。

**Q: 启动后上传 PRT 文件报错**  
A: 检查 FreeCAD 路径是否正确，查看 `backend.log` 获取详细错误。

**Q: 知识库检索返回空**  
A: 确认 `db_data\vector_map_new.db` 存在（`git clone` 自动获取；若原机器有新数据需先 `git push`）。
