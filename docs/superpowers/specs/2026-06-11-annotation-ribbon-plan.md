# 标注工具栏 Ribbon 改造 — 实施计划

> 设计文档：`2026-06-11-annotation-ribbon-redesign.md`
> 日期：2026-06-11

## 步骤总览

| # | 步骤 | 文件 | 依赖 |
|---|------|------|------|
| 1 | CSS：新增 Ribbon + 树形列表样式 | `industrial-console.css` | 无 |
| 2 | JS：重写 ensureAnnotateFullscreen() HTML 结构 | `demo-industrial-console.js` | 无 |
| 3 | JS：重写 _renderToolbar() → Ribbon 渲染 | `annotation-tool.js` | 步骤 2 |
| 4 | JS：重写 _renderList() → 树形列表 | `annotation-tool.js` | 步骤 2 |
| 5 | JS：修改 renderAll() → 全标号显示 | `annotation-tool.js` | 步骤 2 |
| 6 | JS：新增内联重命名逻辑 | `annotation-tool.js` | 步骤 4 |
| 7 | JS：新增边界校验（重名/空名/特殊字符） | `annotation-tool.js` | 步骤 6 |
| 8 | 联调测试 | — | 全部 |

## 步骤 1：CSS 样式

**文件：** `updated_front/css/industrial-console.css`

新增样式块：

```css
/* ── Ribbon 工具栏 ── */
.annotate-fs-ribbon { ... }
.ribbon-tabs { ... }
.ribbon-tab { ... }
.ribbon-tab.active { ... }
.ribbon-groups { ... }
.ribbon-group { ... }
.ribbon-group-label { ... }
.ribbon-btn { ... }
.ribbon-btn.active { ... }
.ribbon-btn-icon { ... }
.ribbon-btn-text { ... }
.ribbon-sep { ... }  /* 分组竖线 */

/* ── 树形列表 ── */
.annotate-fs-panel { ... }
.panel-header { ... }
.panel-tree { ... }
.tree-parent { ... }
.tree-parent:hover { ... }
.tree-child { ... }
.tree-child.selected { ... }
.tree-child-name { ... }
.tree-child-name-input { ... }  /* 内联编辑输入框 */
.tree-count { ... }
```

## 步骤 2：HTML 结构重写

**文件：** `updated_front/js/demo-industrial-console.js`
**函数：** `ensureAnnotateFullscreen()`

将 `host.innerHTML` 从 `flex-row` 改为 `flex-column`，包含：
- `.annotate-fs-ribbon` — 顶部 Ribbon 容器
- `.annotate-fs-main` — 画布 + 窄列表的 flex-row

DOM id 映射（保持不变，确保 `_wireControls` 能找到）：
- `annotateFsScroll` — 画布滚动区
- `annotateFsImage` / `annotateFsSvg` — 图片/SVG
- `annotateFsLabelRow` — 移到 Ribbon 内的标注类型分组
- `annotateFsZoomInBtn` / `ZoomOutBtn` / `ZoomFitBtn` / `ZoomOneBtn` / `ZoomLabel` — 移到 Ribbon 缩放分组
- `annotateFsPagePrev` / `PageNext` / `PageCounter` — 移到右侧面板底部
- `annotateFsExportBtn` — 移到 Ribbon 导出分组
- `annotateFsAddTypeBtn` — 移到 Ribbon 标注类型分组末尾
- `annotateFsExitBtn` — 移到 Ribbon 右侧
- `annotateFsListBody` — 右侧面板树形容器（改 id 或新增 `annotateFsTreeBody`）
- `annotateFsCount` — 右侧面板计数

## 步骤 3：Ribbon 渲染

**文件：** `updated_front/js/annotation-tool.js`
**函数：** `_renderToolbar()`

改造逻辑：
- 目标容器从 `#annotateFsLabelRow` 改为 Ribbon 内的标注类型分组
- 按钮渲染：图标（SVG）+ 文字标签上下排列
- 当前 `_activeLabel` 对应按钮加 `.active` 类
- 点击调用 `setActiveLabel(key)`

SVG 图标映射：
- `chamfer` → 对角线交叉
- `threaded_hole` → 圆+十字
- `circle_hole` → 圆+中心点
- 自定义类型 → 圆+加号

## 步骤 4：树形列表

**文件：** `updated_front/js/annotation-tool.js`
**函数：** `_renderList()`

改造逻辑：
- 新增 `_expandedLabels` Set，默认全部展开
- 按 label 分组：遍历 `_annotations`，构建 `{label: [ann1, ann2, ...]}` 映射
- 渲染父节点：展开箭头 + 类型图标 + 类型名 + 计数
- 渲染子节点：图标 + 名称 + 删除按钮
- 父节点点击 → toggle `_expandedLabels` → 重新渲染
- 子节点点击 → `_selectAnnotation(id, {fromList: true})`

新增方法：
- `_groupAnnotationsByLabel()` — 分组辅助函数
- `_toggleLabelExpand(label)` — 展开/折叠

## 步骤 5：全标号显示

**文件：** `updated_front/js/annotation-tool.js`
**函数：** `renderAll()`

改造逻辑：
- 当前仅 `if (isSel)` 渲染 floating label → 改为所有框都渲染
- 未选中框标号：`font-size: 10px`，背景色 `cfg.color + 'cc'`，白色文字
- 选中框标号：`font-size: 12px`，背景色 `cfg.color`，白色文字，框边框 3px
- 标号位置：框上方 6px，左对齐

## 步骤 6：内联重命名

**文件：** `updated_front/js/annotation-tool.js`

改造逻辑：
- `_renderList()` 中，选中项的名称区域渲染为 `<input>` 而非 `<span>`
- 监听 `keydown`（Enter 保存，Escape 取消）和 `blur`（保存）
- 保存时调用 `_renameAnnotation(id, newLabel)`

新增方法：
- `_renameAnnotation(id, newLabel)` — 更新 `_annotations[].label` + `_allPages` 中同名项 → `_renderList()` + `renderAll()` + `_scheduleSave()`

## 步骤 7：边界校验

**文件：** `updated_front/js/annotation-tool.js`

在 `_renameAnnotation()` 内校验：
- 空字符串 → 拒绝，恢复原名
- 重名 → 拒绝或加后缀（prompt 用户选择）
- 特殊字符 `/\<>:` → 过滤

## 步骤 8：联调测试

验证项：
1. Ribbon 所有按钮可点击，标注类型切换生效
2. 缩放控件功能正常
3. 翻页功能正常
4. 树形列表展开/折叠
5. 双向选中联动（列表↔画布）
6. 所有画布框显示标号
7. 内联编辑名称后保存/重新加载
8. 导出 ZIP 包含正确 label
9. 右键删除功能正常
