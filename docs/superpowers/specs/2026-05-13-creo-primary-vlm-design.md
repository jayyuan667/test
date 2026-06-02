# 设计文档：Creo 截图 + 结构化尺寸作为 VLM 主输入

**日期**：2026-05-13
**目标**：将 VLM 特征提取的主输入从 FreeCAD 三视图切换为 Creo 截图 + 解析后的 CREO_TASK.txt，消除 VLM 对图中数字的自行识别风险；FreeCAD 只保留 glTF 生成职责。

---

## 背景

当前双源模式（FreeCAD + Creo）已接通，但 VLM 仍以 FreeCAD 三视图为主、Creo 为辅。存在两个问题：

1. FreeCAD 三视图无尺寸标注，VLM 读不到精度数值，只能靠形状判断。
2. Creo 截图有标注，但 VLM 读取图中数字存在识别错误风险（幻觉）。

已有的 `CREO_TASK.txt`（DLL 从 Creo 3D 模型导出）包含：
- 466 条标准尺寸（symbol + displayed_value）
- 2 条 3D 注释（技术要求全文）

这些数值是权威来源，可以作为约束注入 prompt，消除 VLM 数字幻觉。

---

## 范围

**纳入：**
- `backend/pipeline/vlm_feature.py`
- `backend/api/upload.py`

**不纳入：**
- `backend/prt_pipeline.py`（不动，CREO_TASK.txt 的复制路径已通过 `creo_zhushi_path` 传出）
- FreeCAD 相关逻辑（保留，供降级和 glTF 生成）
- batch / kb_import / library 入口

---

## 设计

### 1. 新增 `parse_creo_task_txt(txt_path: str) -> dict`

位置：`backend/pipeline/vlm_feature.py`

**职责**：读取 CREO_TASK.txt，解析并分类所有尺寸与注释，返回压缩后的结构化字典。

**解析规则：**

| 桶 | 判断条件 | 说明 |
|---|---|---|
| `主要外形尺寸` | `displayed_value > 50` | 总长、总宽、总高等 |
| `特征尺寸` | `2 < displayed_value ≤ 50` | 孔径、槽宽、台阶高等 |
| `倒角圆角` | `displayed_value ≤ 2` 或 `dimension_text` 含 `{0:R}` | 圆角半径、倒角 |
| `技术要求` | `3D NOTES` 段原文 | GB 公差、表面处理要求等 |

**去重压缩**：同值合并计数，输出格式 `"0.9 × 15"`，将 466 条压缩至约 20-40 行。

**返回示例：**
```python
{
    "主要外形尺寸": ["249", "177.98", "77.75"],
    "特征尺寸": ["12.0 × 3", "8.5 × 2", "25"],
    "倒角圆角": ["0.9 × 15", "1.5 × 8", "1.0 × 6"],
    "技术要求": [
        "技术要求：\n1,去除毛刺飞边…\n2,未注公差 GB/T 1804-2000 m 级…",
        "全部清根"
    ]
}
```

---

### 2. 新增 `extract_creo_primary_features(creo_dir: str, txt_path: str) -> str`

位置：`backend/pipeline/vlm_feature.py`

**职责**：取 Creo 截图目录 + CREO_TASK.txt 路径，构建带权威数值约束的 prompt，调用 VLM，返回特征文本。

**Prompt 结构：**

```
【技术要求 · 权威来源】
{3D Notes 原文，每条换行}

【尺寸数值 · 权威来源，图中标注数字以此为准】
主要外形尺寸：{values}
特征尺寸：{values}
倒角圆角：{values}

---
以下图片是该零件的 Creo 截图（含标注）。
请根据上方权威数值和截图，提取零件结构特征。
- 数值以上表为准，不得从图中自行读取与上表不符的数字
- 只描述图片中明确可见的特征类型和空间分布
- 不推测未标注的数值
```

**图片**：`_collect_creo_images(creo_dir)` 收集全部 Creo 截图（主视图、仰视图等 8 张）。

**降级**：若 Creo 截图为空，返回 `""`。若 txt_path 不存在，跳过尺寸节，只用图片+简单 prompt。

---

### 3. 修改 `build_vlm_feature_text()` 路由

**签名变更：**
```python
def build_vlm_feature_text(
    freecad_views_dir: str,
    creo_views_dir: str = "",
    creo_txt_path: str = "",    # 新增，替代原 zhushi_text 字符串
) -> tuple[str, str]:
```

**新路由：**
```
creo_primary（creo_views_dir + creo_txt_path 均有效）
  → freecad（降级：Creo 不可用时用 FreeCAD 三视图）
  → none（FreeCAD 三视图也不可用）
```

旧的 `dual` 路径和 `extract_dual_source_vlm_features` 函数保留但不再作为主路径调用。

---

### 4. 修改两处调用方

`build_vlm_feature_text` 有两个调用方，均需同步修改：

**`backend/api/upload.py:597`**
```python
# 旧
vlm_text, vlm_mode = build_vlm_feature_text(
    views_dir, creo_views_dir, zhushi_text=artifacts.get("creo_zhushi_text", "")
)

# 新
vlm_text, vlm_mode = build_vlm_feature_text(
    views_dir,
    creo_views_dir=creo_views_dir,
    creo_txt_path=artifacts.get("creo_zhushi_path", ""),
)
```

**`backend/services/upload_pipeline.py:86`**
```python
# 旧
vlm_text, vlm_mode = build_vlm_feature_text(
    freecad_views_dir=artifacts.get("views_dir", ""),
    creo_views_dir=artifacts.get("creo_views_dir", ""),
    zhushi_text=artifacts.get("creo_zhushi_text", ""),
)

# 新
vlm_text, vlm_mode = build_vlm_feature_text(
    freecad_views_dir=artifacts.get("views_dir", ""),
    creo_views_dir=artifacts.get("creo_views_dir", ""),
    creo_txt_path=artifacts.get("creo_zhushi_path", ""),
)
```

两处调用方中的 `mode_label` 映射同步更新，加入 `creo-primary` → "Creo主路径"。

`artifacts["creo_zhushi_text"]`（字符串）不再被调用方使用，但 `prt_pipeline.py` 可保留该返回字段，不做删除，避免破坏其他可能读取它的代码。

### 5. 更新测试文件

**`backend/pipeline/test_vlm_feature.py`** 中所有 `zhushi_text=` 调用改为 `creo_txt_path=`，并补充：
- `parse_creo_task_txt` 的单元测试（空文件、只有3D注释、466条尺寸）
- `build_vlm_feature_text` 使用 `creo_txt_path` 时的路由测试

---

## 数据流

```
PRT 上传
  → prt_pipeline.prepare_prt_artifacts()
      → FreeCAD: front/right/top.png + model.glb（3D 演示用）
      → Creo: creo_views/*.jpg + creo_views/zhushi.txt (= CREO_TASK.txt)
  → upload.py
      → build_vlm_feature_text(views_dir, creo_views_dir, creo_txt_path)
          → parse_creo_task_txt(creo_txt_path) → dict
          → extract_creo_primary_features(creo_views_dir, creo_txt_path)
              → 构建 prompt（权威尺寸 + 技术要求 + 截图）
              → _call_vlm_with_images(8 张截图, prompt)
          → 若失败 → extract_vlm_features(freecad_views_dir)
  → 后续几何分析 / 人工审阅 / RAG 不变
```

---

## 日志

| 情形 | 日志 |
|---|---|
| Creo 主路径成功 | `VLM mode: creo-primary (8 images, 466 dims)` |
| txt 缺失，仅用截图 | `VLM mode: creo-images-only (txt not found)` |
| 降级到 FreeCAD | `VLM mode: freecad (Creo unavailable)` |
| 全部失败 | `VLM mode: none` |

---

## 错误处理

| 情形 | 处理 |
|---|---|
| `creo_txt_path` 不存在 | 跳过尺寸节，仅用截图 + 简单 prompt |
| Creo 截图目录为空 | 返回 `""`，进入降级 |
| VLM API 失败 | 返回 `""`，进入降级 |
| FreeCAD 三视图缺失 | 返回 `"none"` 模式 |

---

## 不做的事

- 不修改 `prt_pipeline.py`（Creo 文件已就位）
- 不删除 FreeCAD VLM 相关代码（保留供降级）
- 不修改几何分析、RAG、工艺生成接口
- 不扩展到 batch / kb_import / library（下一阶段）
