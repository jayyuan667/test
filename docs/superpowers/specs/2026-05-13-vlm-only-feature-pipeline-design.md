# 设计文档：VLM 纯链路特征提取（去除几何提取作为特征条件）

**日期**：2026-05-13
**目标**：将三个 PRT 入口（上传、知识库导入、零件库）的特征文本来源从 STEP 几何提取切换为 VLM 输出，几何数据仅在 FreeCAD 降级路径中作为 VLM prompt 约束使用，不再作为最终入库的特征文本。

---

## 背景

当前三个入口均以 `extract_geometry_features(step_path)` 产出的结构化文本（`【尺寸】长×宽×高 / 【体积】/ 【面数】`）作为主要特征条件写入 RAG。存在的问题：

1. 几何文本是拓扑数字，语义检索效果有限（用户搜"带法兰的轴类零件"匹配不到纯数字描述）
2. kb_import / library 的 VLM 路径（`_vision_analyzer`）是旧链路，与上传流程的 `build_vlm_feature_text` 不一致
3. 几何提取和 VLM 提取结果拼接后入库，质量参差不齐

---

## 范围

**纳入：**
- `backend/api/upload.py`
- `backend/services/upload_pipeline.py`
- `backend/api/kb_import.py`
- `backend/pipeline/vlm_feature.py`
- `backend/pipeline/test_vlm_feature.py`
- `backend/api/library.py`

**不纳入：**
- `backend/prt_pipeline.py`（`extract_geometry_features` 函数保留，不删除）
- batch / 其他非 PRT 入口

---

## 设计

### 1. 新增 `extract_freecad_geo_constrained_features(views_dir, step_path)` → `vlm_feature.py`

**职责**：当 Creo 路径不可用时，使用 FreeCAD 三视图 + STEP 几何约束调用 VLM。几何数据仅注入 prompt，不进入返回值。

**逻辑：**
1. 收集 `views_dir` 下的 front/right/top.png
2. 调用 `extract_geometry_features(step_path)` 拿到几何文本
3. 若几何提取成功，构造约束 prompt：

```
【零件几何参数 · 权威来源，图中数字以此为准】
长×宽×高：...  体积：...  面数：...  形状分类：...

---
以下是该零件的 FreeCAD 标准三视图（正视图、右视图、俯视图）。
请根据上方几何参数和视图，提取零件结构特征。
- 数值以上表为准，不得从图中自行读取与上表不符的数字
- 只描述图片中明确可见的特征类型和空间分布
- 不推测未标注的数值
```

4. 若几何提取失败或 step_path 为空，使用无约束的 `_SINGLE_SOURCE_PROMPT`
5. 调用 `_call_vlm_with_images(image_paths, prompt)`，返回 VLM 输出字符串

**降级**：FreeCAD 三视图为空 → 返回 `""`

---

### 2. 更新 `build_vlm_feature_text` 路由

**新签名：**
```python
def build_vlm_feature_text(
    freecad_views_dir: str,
    creo_views_dir: str = "",
    creo_txt_path: str = "",
    step_path: str = "",          # 新增，供 freecad-geo 降级使用
) -> tuple[str, str]:
```

**新路由（4 级）：**
```
creo_views_dir 有效 → extract_creo_primary_features(creo_views_dir, creo_txt_path)
  → 返回 (text, "creo-primary")
  ↓ 失败（返回 ""）

step_path 有效 → extract_freecad_geo_constrained_features(freecad_views_dir, step_path)
  → 返回 (text, "freecad-geo")
  ↓ 失败（返回 ""）

freecad_views_dir → extract_vlm_features(freecad_views_dir)
  → 返回 (text, "freecad")
  ↓ 失败（返回 ""）

→ 返回 ("", "none")
```

---

### 3. 更新四个调用方

**`upload.py` 和 `upload_pipeline.py`（改法相同）：**

- 删除 `extract_geometry_features` 调用和 `geo_text` 变量
- `build_vlm_feature_text` 调用增加 `step_path=artifacts.get("step_path", "")`
- `full_feature_text` 合并逻辑改为：
  ```python
  parts = []
  if vlm_text:
      parts.append(vlm_text)
  parts.append(f"【图号】{prefix_hint or filename}")
  full_feature_text = "\n".join(parts)
  ```
- `_is_upload_template_ready` 有效模式集加入 `"freecad-geo"`

**`kb_import.py`（`_parse_prt_document`）：**

- 删除 geo 优先块（含 `extract_geometry_features` 调用）
- 删除 `_vision_analyzer` fallback（旧视觉链路）
- **保留 `export_gltf` 调用**（原本在 geo 块内，需独立提出，供 3D 预览使用）
- 替换为：
  ```python
  artifacts = prepare_prt_artifacts(prt_path, prt_dir)
  vlm_text, vlm_mode = build_vlm_feature_text(
      freecad_views_dir=artifacts.get("views_dir", ""),
      creo_views_dir=artifacts.get("creo_views_dir", ""),
      creo_txt_path=artifacts.get("creo_zhushi_path", ""),
      step_path=artifacts.get("step_path", ""),
  )
  feature_text = (vlm_text + f"\n【图号】{stem}") if vlm_text else f"【图号】{stem}"
  ```
- 返回字典中 `"text"` 和 `"feature_report_text"` 均用 `feature_text`

**`library.py`（PRT 入库分支）：**

- 删除 geo 优先块 + 旧视觉分析
- 替换为 `build_vlm_feature_text`（同 kb_import 模式）
- `source_text` 和 `draft["feature_report_text"]` 均用 VLM 输出

---

### 4. 更新测试

**`test_vlm_feature.py` 新增：**
- `extract_freecad_geo_constrained_features` 目录为空 → 返回 `""`
- geo 提取成功时 prompt 含 `"权威来源"` 和几何数字
- geo 提取失败时降级为无约束 prompt（不崩溃）
- `build_vlm_feature_text` 路由测试补充 `freecad-geo` 分支（`_patch_vlm_paths` 扩展）

---

## 数据流

```
PRT 上传 / kb_import / library
  → prepare_prt_artifacts()
      → FreeCAD: STEP + front/right/top.png + model.glb
      → Creo: creo_views/*.jpg + zhushi.txt (= CREO_TASK.txt)
  → build_vlm_feature_text(views_dir, creo_views_dir, creo_txt_path, step_path)
      → creo-primary  ：Creo 图 + txt 约束 → VLM
      → freecad-geo   ：FreeCAD 三视图 + 几何约束 → VLM
      → freecad       ：FreeCAD 三视图（无约束）→ VLM
      → none          ：全部失败
  → full_feature_text = vlm_text + 【图号】
  → 写入 RAG / task["feature_report_text"]
```

---

## 日志

| 情形 | 日志 |
|---|---|
| Creo 主路径成功 | `VLM mode: creo-primary` |
| FreeCAD + 几何约束 | `VLM mode: freecad-geo` |
| 纯 FreeCAD 三视图 | `VLM mode: freecad` |
| 全部失败 | `VLM mode: none`，warn 级别 |

---

## 错误处理

| 情形 | 处理 |
|---|---|
| Creo 截图目录为空 | 进入 freecad-geo 降级 |
| STEP 文件不存在 | 跳过几何约束，用纯 FreeCAD prompt |
| `extract_geometry_features` 抛异常 | 捕获，降级为无约束 prompt |
| VLM API 失败 | 返回 `""`，继续下一级降级 |
| 全部失败 | feature_text = `【图号】{图号}` |

---

## 不做的事

- 不删除 `extract_geometry_features` 函数（保留供未来引用）
- 不修改 `prt_pipeline.py`
- 不扩展到 PDF / Excel 入口
- 不修改几何数据的前端展示字段（`step_path`、`gltf_path` 等不变）
