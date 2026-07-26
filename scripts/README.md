# scripts — 批量工具脚本

## import_pdf_xlsx.py

将 ZIP 包（PDF 图纸 + XLSX 工艺）批量导入知识库（`db_data/2d-v.db`）。

### 前置条件

| 条件 | 说明 |
|------|------|
| Python 虚拟环境 | 已执行 `setup.bat` 或 `pip install -r backend/requirements.txt` |
| `.env` 配置 | `VISION_API_KEY` / `VISION_API_BASE` / `VISION_MODEL_ID` 已填写 |
| Poppler | Windows 需配置 `POPPLER_PATH`（PDF 转图片依赖） |

### 快速开始

```bat
:: 激活虚拟环境（项目根目录）
.venv\Scripts\activate

:: 导入 ZIP 包（自动创建工艺库）
python scripts\import_pdf_xlsx.py D:\data\myparts.zip

:: 先预览配对情况，不写数据库
python scripts\import_pdf_xlsx.py D:\data\myparts.zip --dry-run
```

### ZIP 包结构

```
archive.zip
├── drawing/          ← PDF 图纸（必须在 drawing / drawings / 图纸 子目录）
│   ├── Y1.pdf
│   └── Y2.pdf
└── craft/            ← XLSX 工艺（任意位置均可）
    ├── Y1.xlsx
    └── Y2.xlsx
```

**配对规则**：图纸与工艺文件去掉所有扩展名后名称相同即匹配，大小写不敏感。  
示例：`Y1.pdf` ↔ `Y1.xlsx`，`01.prt.5` ↔ `01.xlsx`。

### 命令行选项

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `zip_file` | （必填） | ZIP 文件路径 |
| `--library-key KEY` | 自动生成 | 写入已有工艺库的标识符 |
| `--library-name NAME` | 空 | 新建库时的显示名称 |
| `--conflict MODE` | `replace` | 同图号冲突处理：`replace` 覆盖 / `keep` 保留旧 / `skip` 跳过 |
| `--library-mode MODE` | `private_seed_public` | 新建库模式 |
| `--dry-run` | 关 | 仅扫描配对，不写入数据库 |
| `--env PATH` | `.env` | 指定 env 文件路径 |
| `--db PATH` | `db_data/2d-v.db` | 指定数据库路径 |

### 常用示例

```bat
:: 写入指定工艺库
python scripts\import_pdf_xlsx.py myparts.zip --library-key workshop_A

:: 新建库并命名
python scripts\import_pdf_xlsx.py myparts.zip --library-name "一车间2025批次"

:: 重复图号保留旧记录
python scripts\import_pdf_xlsx.py myparts.zip --conflict keep

:: 指定非默认 env 和数据库
python scripts\import_pdf_xlsx.py myparts.zip --env C:\conf\.env --db D:\prod\2d-v.db
```

### 输出说明

脚本运行完成后打印汇总表，例如：

```
============================================================
  入库完成
============================================================
  批次 ID    : kb_20250610_143022_001234
  目标库     : 一车间2025批次  [workshop_A]
  ZIP 文件   : myparts.zip
  扫描文件数 : 20
    图纸 PDF : 10
    工艺 XLSX: 10
------------------------------------------------------------
  配对成功   : 10
  已导入     : 9
  已跳过     : 1
  错误数     : 0
============================================================
```

详细报告（JSON）保存在 `output/kb_imports/<批次ID>/report.json`。

### 退出码

| 码 | 含义 |
|----|------|
| `0` | 全部成功 |
| `1` | 启动失败（文件不存在 / 模块加载失败） |
| `2` | 导入完成但有部分错误（见报告详情） |

---

## 其他脚本

| 文件 | 说明 |
|------|------|
| `batch_regenerate_vectors.py` | 重新生成所有知识库记录的向量索引 |
| `process_pdf_to_vector.py` | 单个 PDF 工艺文件向量化入库 |
| `generate_kb_import_selftest.py` | 生成自测用 ZIP 样例包 |
| `run_kb_import_selftest.py` | 运行知识库导入自测 |
| `generate_zip_kb_design_doc.py` | 生成 ZIP 包格式设计文档 |
