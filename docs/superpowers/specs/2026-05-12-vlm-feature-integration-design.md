# VLM 三视图特征集成设计

**日期：** 2026-05-12  
**分支：** 3d-version  
**状态：** 已批准，待实现

---

## 背景

当前 PRT 上传流程中，`geometry_analyzer.py` 通过 FreeCAD 的 OpenCASCADE 对 STEP 文件做程序化分析，输出面/边/孔的统计数据（精确数字，如孔径、面积）。这段文本直接作为 RAG 查询输入。

问题：程序化分析的描述过于底层（"圆柱面半径 5.0mm × 3 个"），缺乏机械加工语义（"旋转体带台阶"、"薄壁型腔"），导致 RAG 关键词命中率低，检索到的工序参考质量不佳。

FreeCAD 三视图截图（front/right/top.png）在 `prepare_prt_artifacts()` 中已经生成，但目前只用于前端 Three.js 查看器，未传入任何视觉模型。

---

## 目标

在不改动 RAG 检索逻辑的前提下，通过 VLM 分析三视图截图，生成语义丰富的机械特征描述，与程序化 geo_text 合并后送入 RAG，提升检索质量。

---

## 不在范围内

- 不改动 `vector_map_rag.py` 的检索逻辑
- 不新增 embedding 相似度匹配路径
- 不新增 API Key 或环境变量配置项
- 不改动 `geometry_analyzer.py`、`prt_pipeline.py`

---

## 数据流

### 改动前

```
prepare_prt_artifacts()
  → artifacts { step_path, views_dir, view_paths, views_generated, ... }

extract_geometry_features(step_path)
  → geo_text（程序化，数字精确）

full_feature_text = geo_text + "\n【图号】{prefix}"
  → RAG → 工序
```

### 改动后

```
prepare_prt_artifacts()
  → artifacts { step_path, views_dir, view_paths, views_generated, ... }

extract_geometry_features(step_path)          ← 不变
  → geo_text

extract_vlm_features(views_dir)               ← 新增
  → vlm_text（三视图 → VLM → 语义特征描述）
  → "" 若截图缺失或 API 失败（静默降级）

full_feature_text = merge(geo_text, vlm_text) + "\n【图号】{prefix}"
  → RAG → 工序（不变）
```

---

## 新模块：`backend/pipeline/vlm_feature.py`

### 对外接口

```python
def extract_vlm_features(views_dir: str) -> str:
    """
    读取 views_dir 下的 front/right/top.png，
    发 VLM multimodal 请求，返回语义特征文本。
    图片缺失或 API 失败时返回空字符串。
    """
```

### VLM 调用

- **API 配置：** 复用现有环境变量 `api_base` / `api_key` / `model_id`，与 PDF 视觉分析走同一接口，不新增配置
- **请求格式：** OpenAI-compatible multimodal chat，三张图 base64 编码 + system prompt，单次调用
- **Prompt：** 移植自 featurizer `feature.py` 的 `PROMPT_REGONIZE` + `PROMPT_FEAT`，覆盖：
  - 棱柱体/平面类特征（平面、台阶、型腔、槽、凸台、肋）
  - 孔系特征（简单孔、阶梯孔、螺纹孔、沉头孔、埋头孔、中心孔）
  - 旋转体特征（外圆、内孔、圆锥、外螺纹、退刀槽）
  - 过渡特征（倒角、圆角）

### 内部流程

1. 检查 `front.png` / `right.png` / `top.png` 是否均存在；任一缺失则返回 `""`
2. 读取三张图，base64 编码
3. 构造 `messages`，POST 到 `{api_base}/chat/completions`
4. 解析 `choices[0].message.content` 返回
5. 任何异常捕获后记 warn 日志，返回 `""`

HTTP 请求超时设为 120s（与 featurizer 保持一致）。

---

## 合并策略（`upload.py` 改动）

**合并格式：**

```
{geo_text}

【VLM视觉特征】
{vlm_text}

【图号】{prefix_hint}
```

geo_text 在前（RAG 关键词命中），vlm_text 在后（语义补充）。`vlm_text` 为空时跳过该段，输出格式与现在完全一致。

**改动位置：** `backend/api/upload.py` 第 812–834 行

```python
# 现在
geo_text = extract_geometry_features(artifacts["step_path"])
full_feature_text = geo_text + "\n" + f"【图号】{prefix_hint or ...}"

# 改后
geo_text = extract_geometry_features(artifacts["step_path"])

vlm_text = ""
if artifacts.get("views_generated") and artifacts.get("views_dir"):
    emit_log(task_id, event_data, event_locks, 2, "正在调用VLM提取视觉特征...")
    vlm_text = extract_vlm_features(artifacts["views_dir"])
    if vlm_text:
        emit_log(task_id, event_data, event_locks, 2, "VLM视觉特征提取完成")
    else:
        emit_log(task_id, event_data, event_locks, 2, "VLM特征提取跳过（无图或API失败）", level="warn")

parts = [geo_text]
if vlm_text:
    parts.append(f"【VLM视觉特征】\n{vlm_text}")
parts.append(f"【图号】{prefix_hint or os.path.basename(file.filename)}")
full_feature_text = "\n".join(parts)
```

---

## 错误处理

| 场景 | 处理 |
|------|------|
| 三视图 PNG 缺失（FreeCAD 失败） | `views_generated=False`，跳过 VLM，不调用 |
| `api_base` / `api_key` 未配置 | 返回 `""`，打印一次警告，不 raise |
| VLM API 超时 / 网络错误 | `try/except`，记 warn 日志，返回 `""` |
| VLM 返回空内容 | 返回 `""`，geo_text 照常使用 |

所有降级路径最终 `vlm_text = ""`，`full_feature_text` 退化为与现在完全相同的格式，不引入新的任务失败路径。

---

## 测试

提供烟雾测试脚本 `backend/pipeline/test_vlm_feature.py`：

```bash
# 需要 .env 里配好 api_base / api_key / model_id
python backend/pipeline/test_vlm_feature.py <views_dir>
```

输出 VLM 返回的原始特征文本，用于手动验证 prompt 质量和 API 连通性。

---

## 改动文件清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `backend/pipeline/vlm_feature.py` | 新建 | VLM 三视图特征提取，约 80 行 |
| `backend/api/upload.py` | 修改 | 第 812–834 行，加 VLM 调用 + 合并逻辑，约 +10 行 |
| `backend/pipeline/test_vlm_feature.py` | 新建 | 烟雾测试脚本 |
