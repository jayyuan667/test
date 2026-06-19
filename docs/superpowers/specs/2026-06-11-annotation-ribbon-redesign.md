# 标注工具栏 Ribbon 改造设计文档

> 日期：2026-06-11
> 状态：已确认

## 背景

当前标注工具采用右侧边栏布局，工具按钮、缩放控件、标签选择、标注列表全部挤在 272px 宽的侧边栏中，画布面积被压缩，工具层次不清晰。参考专业 CAD 界面（Creo/SolidWorks），改造为顶部 Ribbon 工具栏 + 树形标注列表的布局。

## 改造范围

### 前端（3 个区域）

| 区域 | 改动 | 影响文件 |
|------|------|---------|
| 顶部 Ribbon | 侧边栏工具区 → 画布顶部水平工具栏 | `demo-industrial-console.js` (ensureAnnotateFullscreen) |
| 树形列表 | 平铺列表 → 按类型分组树形 + 展开/折叠 | `annotation-tool.js` (_renderList) |
| 画布标号 | 仅选中框显示标号 → 所有框都显示标号 | `annotation-tool.js` (renderAll) |

### 后端（保障兼容）

| 点位 | 状态 |
|------|------|
| 保存 API 格式 `{label, points}` | 不变 |
| 导出 ZIP 格式（LabelMe JSON） | 不变 |
| 自定义标签持久化 | 保持 localStorage，不改后端 |
| 标号序号 | 前端实时计算，不持久化 |

### 不改的部分

- `POST /api/annotations/{task_id}/save` 路径和参数格式
- `GET /api/annotations/{task_id}` 返回格式
- `GET /api/annotations/{task_id}/export` 导出逻辑
- 标注数据模型 `{label, points}`

## 前端详细设计

### HTML 结构重构

**当前结构（右侧边栏）：**

```
annotateFullscreen
  └─ annotate-fs-layout (flex row)
       ├─ annotate-fs-scroll (画布)
       └─ annotate-fs-sidebar (272px，工具+列表+翻页)
```

**新结构（顶部 Ribbon + 窄列表）：**

```
annotateFullscreen
  └─ annotate-fs-layout (flex column)
       ├─ annotate-fs-ribbon (顶部工具栏，固定高度)
       │    ├─ ribbon-tabs (开始/注释/视图)
       │    └─ ribbon-groups (工具分组)
       └─ annotate-fs-main (flex row)
            ├─ annotate-fs-scroll (画布，flex:1)
            └─ annotate-fs-panel (220px，仅列表+翻页)
                 ├─ panel-header (搜索 + 计数)
                 ├─ panel-tree (树形标注列表)
                 └─ panel-footer (添加类型 + 导出 + 翻页 + 退出)
```

### Ribbon 工具栏

| 分组 | 按钮 | 行为 |
|------|------|------|
| 标注类型 | 倒角 / 螺纹孔 / 圆孔 / +添加 | 切换 `_activeLabel`，高亮当前选中 |
| 框选工具 | 矩形 / 多边形 | 切换绘制模式（多边形为预留） |
| 缩放 | − / 百分比 / + / 适配 / 1:1 | 复用 setZoom / fitToViewport |
| 操作 | 撤销 / 重做 | 预留 |
| 导出 | 标注包按钮 | 复用 _exportZip |
| 右侧 | 翻页 + 退出 | 复用现有逻辑 |

Ribbon 按钮采用图标（SVG）+ 文字标签上下排列，分组之间用竖线分隔。背景渐变 `linear-gradient(180deg, #fff, #f6f8fb)`。

### 树形列表

```
▼ 倒角 (3)
    倒角 1 [×]      ← 选中态：蓝色背景 + 名称可编辑
    倒角 2 [×]
    倒角 3 [×]
▼ 螺纹孔 (2)
    螺纹孔 1 [×]
    螺纹孔 2 [×]
▶ 圆孔 (1)          ← 折叠态
```

**交互规则：**

- 父节点：点击展开/折叠，右侧显示计数
- 子节点：点击选中 → 画布高亮 + 滚动定位
- 选中态：蓝色背景 + 左侧蓝色边框 + 名称变为 `<input>` 可编辑
- 删除：子节点右侧 `×` 按钮，调用 `_deleteAnnotation`
- 展开状态：前端内存态 `_expandedLabels` Set，不持久化，默认全部折叠

**内联重命名规则：**

- 选中后点击名称 → 变为 `<input>`
- 回车/失焦保存 → 更新 `_annotations[].label` + `_allPages` 中同名项 → 触发 `_scheduleSave()`
- 校验：拒绝空名称、拒绝重名（自动加后缀）、trim + 过滤 `/\<>:` 字符

### 画布标号显示

**修改 `renderAll()`：**

- 移除 `if (isSel)` 条件，**所有标注框**都渲染标号标签
- 标号位置：框的正上方，左对齐
- 未选中：`font-size: 10px`，半透明背景，框边框 2px
- 选中：标号背景色更深、字号略大，框边框 3px
- 标号颜色与类型颜色一致（倒角=橙、螺纹孔=紫、圆孔=绿）

## 后端同步保障

### 保存接口兼容

| 场景 | 风险 | 保障 |
|------|------|------|
| Ribbon 切换标签后画框 | `_activeLabel` 传入非法值 | 前端 `_allLabels()` 白名单校验 |
| 树形列表重命名 label | 旧 label 引用断裂 | 重命名时同步更新所有同名项，再触发 save |
| 自定义标签删除后有引用 | 后端保存已删除的 label key | 已有 `removeCustomLabel` 检查引用并拒绝删除 |
| 导出含自定义 label | LabelMe JSON 中 label 非标准 | LabelMe 格式允许任意 label 字符串，不影响 |

### 标号序号

序号是前端渲染时实时计算（`seqCounters`），不持久化到后端。保存的 shape 只有 `label`（如"倒角"），无序号。删除后剩余项重新编号是预期行为。

### 边界 Case 防御

| Case | 处理 |
|------|------|
| 空标注列表 | 树形列表显示空状态 |
| 重命名为已存在名称 | 拒绝或自动加后缀 |
| 重命名为空字符串 | 拒绝，回退原值 |
| 标签名含特殊字符 | trim + 过滤 `/\<>:` |

## 影响文件清单

| 文件 | 改动类型 |
|------|---------|
| `updated_front/js/demo-industrial-console.js` | 重写 ensureAnnotateFullscreen() HTML 结构 |
| `updated_front/js/annotation-tool.js` | 重写 _renderToolbar(), _renderList(), renderAll()，新增树形逻辑 |
| `updated_front/css/industrial-console.css` | 新增 Ribbon 样式、树形列表样式 |
| `updated_front/demo-industrial-console.html` | 无改动（HTML 由 JS 动态生成） |
| `backend/` | 无改动 |

## 验收标准

1. 顶部 Ribbon 工具栏显示 5 个分组，按钮图标+文字布局
2. 标注类型按钮切换后，画框使用对应 label
3. 树形列表按类型分组，展开/折叠正常
4. 点击树形子节点 → 画布对应框高亮 + 滚动定位
5. 点击画布框 → 树形列表对应项高亮 + 滚动定位
6. 所有画布标注框都显示标号标签
7. 选中框内联编辑名称 → 保存后重新加载名称保持
8. 保存/加载/导出功能不受影响
9. 右键删除、翻页、缩放功能正常
