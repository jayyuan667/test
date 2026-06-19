# GeneratePage 七项增强设计（第二轮）

> 工艺生成页第二轮增强设计文档
> 日期：2026-06-13

---

## 1. 问题概览

| # | 问题 | 根因 | 修复方向 |
|---|------|------|---------|
| 1 | 右侧标注栏无序号 | LabelTree 只显示标签名，未计算分组内序号 | 复用 SVG 序号逻辑 |
| 2 | 退出标注页数据可能丢失 | 关闭时无立即保存，仅靠1秒防抖 | 关闭时强制保存一次 |
| 3 | Ctrl+滚轮缩放有上限 | 需排查实际行为（代码上限800%） | 启动服务器实测修复 |
| 4 | 图纸预览不支持Ctrl+滚轮缩放 | UploadPanel 无缩放，FullscreenPreview 无Ctrl检查 | 统一Ctrl+滚轮缩放+拖拽平移 |
| 5 | 无法添加新工序 | ProcessPanel 无添加行功能 | 底部追加+中间插入+自动编号 |
| 6 | 工种字段不可编辑 | trade列为静态badge | 改为contentEditable |
| 7 | 无入库功能 | 前端无入库入口，后端已有API | 入库按钮+选库弹窗 |

---

## 2. 修复 1：右侧标注栏序号

### 2.1 当前状态

`AnnotationPanel.tsx:489-496` 中 SVG 渲染使用以下逻辑计算序号：

```typescript
let seq = 0
for (let j = 0; j < shapes.indexOf(shape); j++) {
  if (shapes[j].label === shape.label) seq++
}
seq++
const tagText = `${displayName} ${seq}`
```

`LabelTree.tsx` 中每个子项只显示标签名，无序号。

### 2.2 修复方案

在 LabelTree 渲染子项时，使用相同的逻辑计算分组内序号：

```tsx
// 在 shapes 分组后，对每个组内的 items 计算序号
items.map((shape, idx) => {
  const seq = idx + 1  // 已按 label 分组，组内索引即序号
  const displayName = LABEL_DISPLAY_NAMES[shape.label] || shape.label
  // 显示: "倒角 1"、"倒角 2"
})
```

**注意**：LabelTree 中 shapes 已按 label 分组（`Map<string, AnnotationShape[]>`），组内索引即为序号。但需确保排序与 SVG 渲染一致（按 shapes 数组中的出现顺序）。

### 2.3 涉及文件

| 文件 | 修改内容 |
|------|---------|
| `frontend/src/components/annotate/LabelTree.tsx` | 子项显示分组内序号 |

---

## 3. 修复 2：退出标注页保存

### 3.1 当前状态

`AnnotationPanel.tsx:140-155` 已有1秒防抖自动保存。关闭标注面板时（`handleCloseAnnotate`）没有立即保存。

### 3.2 修复方案

在 `handleCloseAnnotate` 中，关闭前立即调用一次 `saveAnnotation`：

```tsx
const handleCloseAnnotate = useCallback(async () => {
  // 立即保存当前标注数据
  if (currentPage?.shapes) {
    await saveAnnotation(taskId, pages)
  }
  setIsAnnotating(false)
}, [taskId, pages, currentPage])
```

### 3.3 涉及文件

| 文件 | 修改内容 |
|------|---------|
| `frontend/src/components/annotate/AnnotationPanel.tsx` | 关闭时立即保存 |

---

## 4. 修复 3：Ctrl+滚轮缩放上限排查

### 4.1 当前状态

代码中上限为 800%（`Math.min(z * factor, 8)`），理论上不会在 57%/50% 卡住。

### 4.2 排查方向

1. 启动开发服务器实际测试
2. 检查 `fitToViewport` 是否设置了较低的初始值
3. 检查滚动容器 CSS 是否限制了可见区域
4. 检查图片 CSS `max-width` / `max-height` 是否限制了实际渲染尺寸

### 4.3 涉及文件

| 文件 | 修改内容 |
|------|---------|
| `frontend/src/components/annotate/AnnotationPanel.tsx` | 根据排查结果修复 |

---

## 5. 修复 4：图纸预览页支持 Ctrl+滚轮缩放

### 5.1 当前状态

- `UploadPanel.tsx`：内嵌预览无任何缩放功能
- `FullscreenPreview.tsx`：普通滚轮缩放（无Ctrl检查），范围 0.3x-4.0x，使用加法 ±0.15

### 5.2 修复方案

**UploadPanel 内嵌预览：**

采用与 AnnotationPanel 相同的方案：
- 原生 `addEventListener('wheel', handler, { passive: false })`
- 乘法缩放 ×1.15 + 光标锚定
- 拖拽平移（mousedown/mousemove/mouseup）
- 缩放范围 0.1x-10x

**FullscreenPreview：**

- 添加 `e.ctrlKey` 检查，仅 Ctrl+滚轮触发缩放
- 普通滚轮恢复为页面滚动（不 preventDefault）
- 改为乘法缩放 ×1.15 + 光标锚定
- 缩放范围 0.1x-10x

### 5.3 涉及文件

| 文件 | 修改内容 |
|------|---------|
| `frontend/src/components/generate/UploadPanel.tsx` | 添加 Ctrl+滚轮缩放 + 拖拽平移 |
| `frontend/src/components/generate/FullscreenPreview.tsx` | 改为 Ctrl+滚轮触发 + 乘法缩放 |

---

## 6. 修复 5：添加新工序

### 6.1 当前状态

ProcessPanel 无添加行功能。表格只有3列：工序号(80px)、工种(90px)、工序名称及内容(flex)。

### 6.2 修复方案

**底部追加：**
- 表格下方显示"+ 添加工序"按钮
- 点击后在 rows 末尾追加新行
- 工序号 = 最后一行工序号 + 10

**中间插入：**
- 鼠标悬停某行时，行右侧显示"在下方插入"图标按钮
- 点击后在该行下方插入新行
- 所有工序号自动重排（从10开始，步长10）

**工序号重排逻辑：**

```tsx
const renumberRows = (rows: ProcessRow[]) => {
  return rows.map((row, i) => ({ ...row, code: String((i + 1) * 10) }))
}
```

**新行默认值：**

```tsx
const emptyRow: ProcessRow = { code: '', trade: '', content: '' }
```

### 6.3 涉及文件

| 文件 | 修改内容 |
|------|---------|
| `frontend/src/components/generate/ProcessPanel.tsx` | 添加行按钮 + 插入逻辑 + 重排 |

---

## 7. 修复 6：工种字段可编辑

### 7.1 当前状态

工种列（trade）渲染为静态 badge（`tradeBadgeClass()`），不可编辑。工序名称及内容列（content）使用 `contentEditable`。

### 7.2 修复方案

将工种列也改为 `contentEditable`：

```tsx
<td
  contentEditable
  suppressContentEditableWarning
  onBlur={(e) => handleCellEdit(i, 'trade', e.currentTarget.textContent || '')}
  className="..."
>
  {row.trade}
</td>
```

编辑时移除 badge 样式，显示为纯文本输入框。失焦后保存并恢复 badge 样式。

### 7.3 涉及文件

| 文件 | 修改内容 |
|------|---------|
| `frontend/src/components/generate/ProcessPanel.tsx` | trade 列改为 contentEditable |

---

## 8. 修复 7：入库按钮

### 8.1 当前状态

- 前端无入库入口
- 后端已有 API：
  - `GET /api/library/scopes` — 获取可用库列表
  - `POST /api/library/commit` — 提交记录入库

### 8.2 修复方案

**UI 交互流程：**

1. ProcessPanel 表格下方显示"入库"按钮
2. 点击后调用 `getLibraryScopes` 获取可用库列表
3. 弹出 `CommitToLibraryModal`：
   - 显示库列表（名称 + 描述）
   - 用户选择目标库
   - 点击"确认入库"
4. 调用 `/api/library/commit`，传入：
   - `draft`: 当前工艺数据（工序列表、特征信息等）
   - `action`: "replace"（替换已有）或 "keep"（保留重复）
   - `scope`: 用户选择的库
5. 成功 → toast 提示"入库成功"
6. 失败 → toast 提示错误信息

**数据结构：**

```typescript
interface CommitDraft {
  prefix: string           // 零件名称
  content: string          // 工艺规程文本
  process_summary: string  // 工序摘要
  feature_report: string   // 特征报告
}
```

### 8.3 涉及文件

| 文件 | 修改内容 |
|------|---------|
| `frontend/src/components/generate/ProcessPanel.tsx` | 添加入库按钮 |
| `frontend/src/components/generate/CommitToLibraryModal.tsx` | 新建：选库弹窗 |
| `frontend/src/api/client.ts` | 添加 `commitToLibrary` API 函数 |

---

## 9. 涉及文件总览

| 文件 | 修改内容 |
|------|---------|
| `frontend/src/components/annotate/LabelTree.tsx` | 序号显示 |
| `frontend/src/components/annotate/AnnotationPanel.tsx` | 关闭时保存 + 缩放上限排查 |
| `frontend/src/components/generate/UploadPanel.tsx` | Ctrl+滚轮缩放 + 拖拽平移 |
| `frontend/src/components/generate/FullscreenPreview.tsx` | Ctrl+滚轮触发 + 乘法缩放 |
| `frontend/src/components/generate/ProcessPanel.tsx` | 添加行 + 工种编辑 + 入库按钮 |
| `frontend/src/components/generate/CommitToLibraryModal.tsx` | 新建：选库弹窗 |
| `frontend/src/api/client.ts` | commitToLibrary API |

---

## 10. 验证清单

- [ ] 右侧标注栏：每个标注项显示序号（如"倒角 1"），与图片一致
- [ ] 标注页：关闭面板时数据立即保存
- [ ] 标注页：Ctrl+滚轮缩放无明显上限限制
- [ ] 图纸预览：Ctrl+滚轮可缩放图片
- [ ] 图纸预览：拖拽图片可平移
- [ ] 全屏预览：Ctrl+滚轮缩放，普通滚轮恢复滚动
- [ ] 工艺表格：底部"+ 添加工序"按钮可追加新行
- [ ] 工艺表格：悬停行显示"在下方插入"按钮
- [ ] 工艺表格：插入/删除后工序号自动重排(10,20,30...)
- [ ] 工艺表格：工种列可编辑
- [ ] 工艺表格：点击"入库"弹出选库弹窗
- [ ] 入库弹窗：显示可用库列表，选择后入库成功
