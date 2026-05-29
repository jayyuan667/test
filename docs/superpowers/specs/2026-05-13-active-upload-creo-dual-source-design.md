# 设计文档：当前上传主流程接入 Creo 双源视觉特征

**日期**：2026-05-13  
**目标**：让当前 Web 上传主流程真实接入 Creo 截图与注释文本，降低 VLM 提取精度类特征时的幻觉率。

---

## 背景与现状

当前活动仓库的真实运行入口是 `backend/api/upload.py`。PRT 上传后的主流程为：

```text
PRT -> Onshape 转 STEP -> FreeCAD 生成 front/right/top.png -> VLM 读取三视图 -> 几何特征 + VLM特征合并
```

这条链路当前的关键事实：

- 运行入口在 `backend/api/upload.py:658` 附近调用 `prepare_prt_artifacts(...)`
- `prepare_prt_artifacts()` 定义在 `backend/prt_pipeline.py`
- 该函数内部当前固定调用：
  - `run_conversion(...)` 生成 `model.step`
  - `capture_three_views(...)` 生成 `front/right/top.png`
- `backend/pipeline/vlm_feature.py` 当前只读取三张图：`front.png`、`right.png`、`top.png`

因此，虽然系统“支持上传 Creo PRT 文件”，但这只是指输入文件格式是 `.prt` / `.prt.N`，并不代表当前运行时真的调用了 Creo 软件参与截图或注释提取。

---

## 问题定义

当前 VLM 视觉输入只有 FreeCAD 三视图。三视图对结构判断有价值，但通常不包含尺寸、公差、表面粗糙度、技术要求等标注信息，容易导致模型根据形状“猜测”精度相关数值。

而已有的 Creo 自动化链路可提供：

- 带尺寸/公差/技术要求的截图
- 额外视角截图
- 模型注释文本 `zhushi.txt`

这些信息恰好能够为 VLM 提供“真实依据”，减少对精度字段的无依据推测。

---

## 本次范围

本次只改造 **当前 Web 上传主流程**，即 `backend/api/upload.py` 所走的单文件上传链路。

明确纳入范围：

- `backend/api/upload.py`
- `backend/prt_pipeline.py`
- `backend/pipeline/vlm_feature.py`
- 与这三者直接相关的最小测试代码

明确不纳入本次范围：

- `backend/api/batch.py`
- `backend/api/kb_import.py`
- `backend/api/library.py`
- 前端页面结构调整
- 几何分析模块协议调整
- RAG / 工艺生成协议调整

原因：先让主入口低风险接上 Creo，验证是否真的降低幻觉，再把同样逻辑复制到其它入口。

---

## 设计目标

1. 当前上传主流程真实触发 Creo 路径，而不是只有 FreeCAD 三视图。
2. VLM 优先使用 FreeCAD 三视图 + Creo 图片 + `zhushi.txt` 的双源输入。
3. Creo 失败时主流程不报废，仍可退回 FreeCAD-only。
4. FreeCAD 失败时，如果 Creo 成功，则允许走 Creo-only。
5. 日志明确显示当前到底走的是：`dual` / `freecad` / `creo` / `none`。
6. 后续人工审阅、RAG、工艺生成保持兼容，不改接口协议。

---

## 方案比较

### 方案 A：双源增强 + FreeCAD 保底（推荐）

保留现有 `PRT -> STEP -> FreeCAD`，并联新增 `PRT -> Creo 截图/zhushi`。VLM 优先使用双源输入；任一路失败时进入降级逻辑。

优点：

- 风险最低
- 与当前主流程兼容性最好
- 最适合验证“Creo 是否真的降低幻觉”
- 一旦 Creo 故障，仍可继续使用 FreeCAD-only

缺点：

- 链路更长
- 需要在多个文件间增加状态传递

### 方案 B：直接切到 Creo-only

上传后直接用 Creo 截图和 `zhushi.txt`，不再依赖 FreeCAD 视觉链路。

优点：

- 表面改动更少

缺点：

- 稳定性最差
- 一旦 Creo 流程出问题，主入口直接失去视觉能力
- 丢失 FreeCAD 三视图对标准投影结构的稳定参考

### 方案 C：只注入 `zhushi.txt`，不接 Creo 图片

继续使用 FreeCAD 三视图，只把文字注释作为额外 prompt 输入。

优点：

- 改动最小

缺点：

- 无法充分利用 Creo 截图中的尺寸、公差、技术要求标注
- 降幻觉效果有限

### 推荐结论

采用 **方案 A：双源增强 + FreeCAD 保底**。

---

## 总体架构

### 改造前

```text
PRT
  -> Onshape STEP 转换
  -> FreeCAD 三视图
  -> VLM(仅 front/right/top)
  -> 几何特征 + VLM特征 + 图号
  -> 人工审阅 / RAG / 工艺生成
```

### 改造后

```text
PRT
  -> Onshape STEP 转换
  -> FreeCAD 三视图
  -> Creo 截图 + zhushi.txt
  -> VLM 路由选择
       - dual: FreeCAD + Creo + zhushi
       - freecad: FreeCAD only
       - creo: Creo only
       - none: 无可用图片
  -> 几何特征 + VLM特征 + 图号
  -> 人工审阅 / RAG / 工艺生成
```

---

## 组件职责

### 1. `backend/prt_pipeline.py`

职责：负责生成和汇总上传流程所需的原始视觉素材。

新增职责：

- 运行 Creo 自动化
- 等待 `done.txt`
- 复制 Creo 输出图片到任务输出目录
- 复制 `zhushi/1.txt` 为任务内 `zhushi.txt`
- 返回 Creo 相关元数据

建议由 `prepare_prt_artifacts(...)` 返回这些额外字段：

```python
{
    "views_dir": str,
    "view_paths": list[str],
    "views_generated": bool,
    "creo_views_dir": str,
    "creo_views_generated": bool,
    "creo_zhushi_path": str,
    "creo_zhushi_text": str,
}
```

### 2. `backend/pipeline/vlm_feature.py`

职责：统一管理视觉特征提取输入，不让 `upload.py` 自己判断 prompt 和图片组合。

新增职责：

- 读取 Creo 图片目录
- 构造双源 prompt
- 把 `zhushi.txt` 放到 prompt 最前面
- 提供统一选择函数，根据素材可用性决定：
  - `dual`
  - `freecad`
  - `creo`
  - `none`

建议对外提供一个统一入口，例如：

```python
def build_vlm_feature_text(
    freecad_views_dir: str,
    creo_views_dir: str = "",
    zhushi_text: str = "",
) -> tuple[str, str]:
    ...
```

返回：

- 第一个值：VLM 结果文本
- 第二个值：当前模式 `dual/freecad/creo/none`

### 3. `backend/api/upload.py`

职责：只做编排、日志、任务状态记录。

新增职责：

- 使用 `prepare_prt_artifacts(...)` 返回的 Creo 元数据
- 记录 Creo 是否成功采集
- 调用统一 VLM 入口
- 将最终模式写入日志和任务状态

不应该承担：

- prompt 拼接细节
- 图片目录扫描细节
- Creo 文件复制细节

---

## 数据流细节

### Step 1：PRT 转换与截图采集

`backend/api/upload.py` 调用：

```python
artifacts = prepare_prt_artifacts(filepath, output_dir)
```

其内部完成：

1. `run_conversion(...)` 生成 `model.step`
2. `capture_three_views(...)` 生成 FreeCAD 三视图
3. `run_creo_capture(prt_path)` 触发 Creo 自动化
4. `collect_creo_output(...)` 复制截图和 `zhushi.txt`
5. `read_creo_zhushi(...)` 读取注释文字

输出目录建议为：

```text
output/<task_id>/
  front.png
  right.png
  top.png
  model.step
  creo_views/
    *.png
    zhushi.txt
```

### Step 2：VLM 路由选择

视觉特征提取顺序：

1. 如果 FreeCAD 和 Creo 都有可用图片：
   - 走 `dual`
2. 如果只有 FreeCAD 可用：
   - 走 `freecad`
3. 如果只有 Creo 可用：
   - 走 `creo`
4. 如果都没有：
   - 走 `none`

`none` 不抛异常，只返回空字符串，让上游继续依赖几何分析结果。

### Step 3：后处理

保持当前既有逻辑不变：

```text
几何特征 + VLM特征 + 图号 -> review_text -> 人工审阅 -> RAG -> 工艺生成
```

---

## Prompt 设计

### Dual 模式

双源模式下的 prompt 原则：

- 前 3 张图视为 FreeCAD 标准三视图
- 其余视为 Creo 截图
- `zhushi.txt` 文本放在最前面
- 明确约束“不推测未标注数值”

建议表达：

```text
以下是从模型注释中直接提取的文字说明，请优先以此为准，不要与图片矛盾：
{zhushi_text}

---

以下图片来自同一个机械零件：
前 3 张是 FreeCAD 标准三视图（front/right/top）。
后面的若干张是 Creo 截图（包含尺寸标注、公差符号、技术要求等）。
请综合所有图片和注释文字提取零件结构特征。
优先使用 FreeCAD 判断投影结构，用 Creo 图和注释文字确认真实尺寸和公差。
只描述图片中明确可见或注释文字中明确标注的特征，不要推测或估算任何未标注的数值。
```

### Creo-only 模式

建议表达：

```text
以下是从模型注释中直接提取的文字说明，请优先以此为准，不要与图片矛盾：
{zhushi_text}

---

以下图片是同一个机械零件的 Creo 截图（包含尺寸标注、公差符号、技术要求等）。
请根据图片和注释文字提取零件结构特征。
只描述图片中明确可见或注释文字中明确标注的特征，不要推测或估算任何未标注的数值。
```

### FreeCAD-only 模式

保持现有行为，不扩大范围。

---

## 日志与可观测性

为了避免再次出现“到底有没有用 Creo”的不透明问题，必须加明确日志。

建议日志：

### Step 1 阶段

- `Creo 截图与注释已采集`
- `Creo 截图未生成，将按降级路径继续`

### Step 2 阶段

- `正在调用VLM提取视觉特征（优先 FreeCAD + Creo 双源）...`
- `VLM双源特征提取完成: ...`
- `VLM FreeCAD-only 特征提取完成: ...`
- `VLM Creo-only 特征提取完成: ...`
- `VLM特征提取跳过（无图或API失败）`
- `FreeCAD 与 Creo 图片都不可用，跳过VLM特征提取`

### 控制台模式标记

- `VLM mode: FreeCAD + Creo`
- `VLM mode: FreeCAD only`
- `VLM mode: Creo only`
- `VLM mode: none`

---

## 错误处理与降级策略

### Creo 失败

如果 Creo 启动失败、超时、无图片、无 `zhushi.txt`：

- 记录日志
- 不中断主流程
- 若 FreeCAD 图片可用，退回 `freecad`

### FreeCAD 失败

如果 FreeCAD 三视图缺失：

- 若 Creo 图片可用，退回 `creo`
- 否则为 `none`

### `zhushi.txt` 缺失

- 允许 dual / creo 模式继续运行
- `zhushi_text = ""`
- 不抛异常

### VLM API 失败

- 返回空字符串
- 记录 warn 日志
- 仍保留几何分析结果

---

## 测试与验收

### 1. 导入与静态验证

需要确认以下模块可以正常导入：

- `backend/prt_pipeline.py`
- `backend/pipeline/vlm_feature.py`
- `backend/api/upload.py`

### 2. 最小自动化验证

补充最小 smoke tests：

- 没有 VLM 环境变量时安全返回 `""`
- 没有 Creo 图片时双源函数安全降级
- `zhushi.txt` 缺失时安全返回空字符串
- FreeCAD/Creo 都无图时返回 `mode == "none"`

### 3. 主流程手动验证

上传真实 `.prt` 后，确认：

- 日志出现 `Creo 截图与注释已采集` 或明确降级日志
- 日志出现 `VLM mode: ...`
- 输出目录中出现：
  - `front.png/right.png/top.png`
  - `creo_views/*.png`
  - `creo_views/zhushi.txt`

### 4. 效果验收

对比改造前后同一零件的特征文本，重点关注：

- 孔径
- 公差
- 粗糙度
- 配合代号
- 技术要求中的数字型字段

验收标准：

- 这些数值更少“凭空出现”
- 大部分精度类信息能在 Creo 图或 `zhushi.txt` 中找到依据
- 后续人工审阅、RAG、工艺生成不需要改协议即可继续运行

---

## 本次不做的事

本次设计明确不包含：

- 把所有其它入口一起统一为 Creo 双源
- 修改前端展示 Creo 图片画廊
- 修改几何分析算法
- 让 batch / kb_import / library 共享统一的抽象层
- 删除 FreeCAD 逻辑

这些都属于下一阶段的复制或收敛工作，不应阻塞这次主入口验证。

---

## 后续扩展路径

如果主入口验证有效，下一阶段可以按相同模式扩展到：

1. `backend/api/batch.py`
2. `backend/api/kb_import.py`
3. `backend/api/library.py`

届时优先复用本次在 `prt_pipeline.py` 和 `vlm_feature.py` 中形成的通用函数，而不是在各入口重复拼 prompt 或重复扫描目录。
