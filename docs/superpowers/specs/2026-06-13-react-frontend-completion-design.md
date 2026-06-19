# React 前端功能补齐设计

> 智能工艺系统 React 18 前端 — 对齐 H5 前端功能，补齐缺失组件

---

## 1. 概述

### 1.1 背景

React 前端（`frontend/`）已有 4 个页面的基本功能，但相比 H5 前端（`updated_front/`）缺少以下核心功能：

| 功能 | H5 | React | 优先级 |
|------|-----|-------|--------|
| 标注工具 | ✅ 全屏弹窗 | ❌ 缺失 | P0 |
| 导出弹窗 | ✅ 预览+下载 | ❌ 只有下载按钮 | P1 |
| 配置页 | ✅ 独立页 | ❌ 缺失 | P1 |
| 批处理上传 | ✅ 多文件 | ❌ 单文件 | P1 |
| annotation_required SSE | ✅ | ❌ | P1 |
| DB 页锁定机制 | ✅ session lock | ❌ | P2 |
| 3D 模型查看器 | ✅ Three.js | ❌ | 跳过 |

### 1.2 约束

- **不可修改** H5 前端（`updated_front/`）和后端（`backend/`）
- **风格统一** 保持 React 现有暗色玻璃态风格（navy/slate + 毛玻璃 + flame 强调色）
- **先 UI 后接口** 先搭完整 UI 壳子，用户测评后再接入后端 API
- **实施顺序** 先大后小：标注工具 → 导出弹窗 → 配置页 → 批处理 → SSE 补全 → DB 锁定

### 1.3 技术栈

React 18 + TypeScript + Vite 6 + Tailwind CSS 3 + GSAP 3

---

## 2. 标注工具 Tab

### 2.1 架构

标注工具作为 GeneratePage 的第三个 Tab（特征审阅 / 工艺规程 / 标注工具），而非全屏弹窗。

```
GeneratePage
  ├── Tab Bar: [特征审阅] [工艺规程] [标注工具]
  ├── WorkflowHUD
  ├── UploadPanel
  └── Content Area
      ├── ReviewPanel      (tab=review)
      ├── ProcessPanel     (tab=process)
      └── AnnotationPanel  (tab=annotate)
          ├── AnnotationToolbar
          │   ├── 标签按钮组 (chamfer / threaded_hole / circle_hole / 自定义)
          │   ├── 缩放控件 (适应 / 100% / 放大 / 缩小 / 当前比例)
          │   ├── 页码导航 (上一页 / 下一页 / 页码显示)
          │   └── 操作按钮 (导出 ZIP)
          ├── 图片 + SVG 绘制区
          │   ├── <img> 图片本体
          │   └── <svg> 绝对定位覆盖，用于绘制矩形
          └── LabelTree 标签树侧栏
              ├── 按标签类型分组 (parent nodes)
              ├── 标注项列表 (child nodes, 带颜色标识)
              ├── 内联重命名
              └── 删除按钮
```

### 2.2 文件结构

| 文件 | 职责 |
|------|------|
| `src/components/annotate/AnnotationPanel.tsx` | 标注工具主体，管理状态、绘制逻辑、auto-save |
| `src/components/annotate/AnnotationToolbar.tsx` | 工具栏：标签选择、缩放、页码、导出 |
| `src/components/annotate/LabelTree.tsx` | 标签树侧栏：分组列表、重命名、删除 |
| `src/types/annotate.ts` | 标注相关类型定义 |

### 2.3 类型定义

```typescript
// src/types/annotate.ts

interface AnnotationShape {
  id: string              // uuid
  label: string           // 标签类型: 'chamfer' | 'threaded_hole' | 'circle_hole' | 自定义
  x: number               // real 坐标 (图片自然像素)
  y: number
  width: number
  height: number
}

interface AnnotationPage {
  pageNumber: number
  shapes: AnnotationShape[]
  imageWidth: number      // 图片自然宽度
  imageHeight: number     // 图片自然高度
  imagePath: string       // 后端图片路径
}

interface AnnotationLabel {
  name: string
  color: string
  borderStyle: string     // 'solid' | '6,3' (虚线)
  isCustom: boolean
}

// 内置标签
const BUILT_IN_LABELS: AnnotationLabel[] = [
  { name: 'chamfer',       color: '#f59e0b', borderStyle: 'solid', isCustom: false },
  { name: 'threaded_hole', color: '#6366f1', borderStyle: '6,3',   isCustom: false },
  { name: 'circle_hole',   color: '#10b981', borderStyle: 'solid', isCustom: false },
]
```

### 2.4 坐标系统

和 H5 一致，所有标注坐标存储为"real"（图片自然像素）值：

- `_toReal(displayX, displayY)` → 将屏幕坐标转为图片坐标：`realX = displayX / zoom`
- `_toDisplay(realX, realY)` → 将图片坐标转为屏幕坐标：`displayX = realX * zoom`

SVG overlay 的 `viewBox` 设为 `0 0 imageNaturalWidth imageNaturalHeight`，通过 CSS `width/height` 控制显示大小，实现无损缩放。

### 2.5 绘制流程

1. `mousedown` on SVG → 记录起点 `(startX, startY)`，创建临时矩形
2. `mousemove` → 更新临时矩形大小
3. `mouseup` → 如果宽高 >= 6px，创建 `AnnotationShape`，加入当前页 shapes
4. 选择标签后才能开始绘制（默认选中第一个标签）

### 2.6 缩放

- **Ctrl+wheel**: 以光标为中心缩放，步进 0.1，范围 0.05x ~ 8x
- **工具栏按钮**: 适应窗口 / 100% / 放大 (+0.2) / 缩小 (-0.2)
- 缩放通过设置 `<img>` 的 `width/height` 实现（非 CSS transform），SVG overlay 同步尺寸

### 2.7 多页支持

- 从 `result.preview_images` 获取页列表
- 切换页时：保存当前页 shapes → 加载目标页 shapes
- `_allPages: Record<number, AnnotationPage>` 存储所有页数据
- 页码导航：上一页 / 下一页 / 显示 "1 / 3"

### 2.8 标签系统

- 内置 3 种：chamfer (橙)、threaded_hole (靛, 虚线)、circle_hole (绿)
- 自定义标签：用户在标签树中重命名时自动注册，颜色从轮转调色板取
- 自定义标签持久化到 `localStorage` key `annotate.customLabels.v1`

### 2.9 标签树 (LabelTree)

```
▼ chamfer (2)
    ├── [橙色图标] 倒角1          [×]
    └── [橙色图标] 倒角2          [×]
▼ threaded_hole (1)
    └── [靛色图标] 螺纹孔1        [×]
```

- 点击子项 → 选中对应矩形（canvas 高亮 + 滚动到可视）
- 点击 canvas 矩形 → 选中对应树节点（树滚动到可视）
- 选中项可内联重命名：点击名称 → input，Enter 保存，Escape 取消
- 重命名为新标签名 → 自动注册为自定义标签
- 父节点可折叠/展开

### 2.10 自动保存

- shapes 变化后 1 秒 debounce → POST `/api/annotations/{taskId}/save`
- 请求体：`{ page: pageNumber, shapes, imageWidth, imageHeight, imagePath }`
- 页面卸载时用 `navigator.sendBeacon` 兜底保存

### 2.11 导出

- 工具栏"导出"按钮 → GET `/api/annotations/{taskId}/export` → 下载 ZIP

### 2.12 GSAP 动画

- 标注矩形创建时 `gsap.from(shape, { scale: 0.8, opacity: 0, duration: 0.2 })`
- 标签树项入场 `gsap.from(item, { x: -10, opacity: 0, duration: 0.15 })`

---

## 3. 导出弹窗 (ExportModal)

### 3.1 组件结构

```
ExportModal (fixed inset-0 z-50)
├── 背景遮罩 (backdrop-blur + 半透明黑色)
└── 居中卡片 (max-w-3xl, 暗色毛玻璃风格)
    ├── 标题栏: "导出工艺文件" + 关闭按钮
    ├── 内容区 (flex)
    │   ├── 左: 预览图片 (preview_image_urls[0], 可切换)
    │   └── 右: 信息 + 工序表预览
    │       ├── 模型名称、状态、页数
    │       ├── 工序表 (<table>, 只读预览)
    │       └── 专家判定摘要
    └── 操作栏
        ├── 下载 PDF 按钮 (btn-primary)
        └── 下载 XLSX 按钮 (btn-secondary)
```

### 3.2 使用场景

1. **GeneratePage**: 完成后点击"导出"按钮打开
2. **HistoryPage**: 快照弹窗中点击"导出"按钮打开

### 3.3 Props

```typescript
interface ExportModalProps {
  taskId: string
  result: TaskResult       // 包含 preview_image_urls, process_flow 等
  onClose: () => void
}
```

### 3.4 API

- 下载复用现有 `downloadExport(taskId, format)` — GET `/api/export/{taskId}?format=pdf|xlsx`
- 预览数据来自 `result` prop，无需额外请求

---

## 4. 配置页 (SettingsPage)

### 4.1 架构

第 5 个页面，侧栏新增"设置"导航项（齿轮图标）。

```
SettingsPage
├── 页面标题: "系统配置"
└── 配置卡片 (card-solid 风格)
    ├── 视觉模型配置组
    │   ├── vision_mode (下拉: doubao / local)
    │   ├── vision_api_key (password input)
    │   ├── vision_api_base (text input)
    │   └── vision_model_id (text input)
    ├── LLM 配置组
    │   ├── llm_api_key (password input)
    │   ├── llm_base_url (text input)
    │   └── llm_model (text input)
    ├── 路径配置组
    │   ├── poppler_path (text input)
    │   ├── creo_exe (text input)
    │   ├── creo_base_dir (text input)
    │   └── creo_out_dir (text input)
    └── 保存按钮 (btn-primary) + 状态提示
```

### 4.2 API

- GET `/api/config` → 加载配置
- POST `/api/config` → 保存配置

### 4.3 密码字段

API key 字段用 `type="password"`，带"显示/隐藏"切换按钮。加载时脱敏显示（后端返回的值可能已脱敏）。

---

## 5. 批处理上传

### 5.1 改动范围

修改 GeneratePage 的 UploadPanel：

- `<input type="file">` 增加 `multiple` 属性
- 支持 `accept=".pdf,.png,.jpg,.jpeg,.dxf,.dwg,.prt"`
- 多文件选择后显示文件列表（名称、大小、删除按钮）
- 上传时调用批量或单个接口

### 5.2 上传逻辑

```typescript
// 单文件 → 现有逻辑 POST /api/upload 或 /api/upload_drawing
// 多文件 PRT → POST /api/batch_upload
// 多文件图纸 → 逐个 POST /api/upload_drawing（后端无批量图纸接口）
```

### 5.3 UI

文件列表显示在 dropzone 下方：

```
┌──────────────────────────────┐
│  📄 part1.prt    1.2MB   [×] │
│  📄 part2.prt    0.8MB   [×] │
│  📄 drawing.pdf  2.1MB   [×] │
└──────────────────────────────┘
       [开始处理]  [清空]
```

---

## 6. annotation_required SSE 补全

### 6.1 改动

在 `src/api/client.ts` 的 `connectSSE` 函数中增加 `annotation_required` 事件类型：

```typescript
// 现有 SSEHandlers 接口
interface SSEHandlers {
  // ... 已有事件
  annotation_required?: (data: {
    task_id: string
    summary: Record<string, number>
    pages: number
  }) => void
}
```

### 6.2 GeneratePage 处理

收到 `annotation_required` 事件后：

1. 自动切换到标注 Tab
2. 存储 annotation task 信息
3. 加载已有标注数据（GET `/api/annotations/{taskId}`）

---

## 7. DB 页锁定机制

### 7.1 逻辑

和 H5 一致的 session-based lock：

```typescript
// ZipPage 导入成功后设置
sessionStorage.setItem('zip_unlocked', 'true')
sessionStorage.setItem('active_scope', libraryKey)

// DbPage 进入时检查
const locked = !sessionStorage.getItem('zip_unlocked')
```

### 7.2 LockShell UI

锁定状态显示一个居中提示卡片：

```
┌─────────────────────────────────┐
│         🔒 数据库未解锁          │
│                                 │
│  请先完成知识库导入操作           │
│                                 │
│  [前往导入]  [查看公共库]         │
└─────────────────────────────────┘
```

---

## 8. 文件变更清单

| 操作 | 文件 | 说明 |
|------|------|------|
| **新增** | `src/types/annotate.ts` | 标注类型定义 |
| **新增** | `src/components/annotate/AnnotationPanel.tsx` | 标注工具主体 |
| **新增** | `src/components/annotate/AnnotationToolbar.tsx` | 标注工具栏 |
| **新增** | `src/components/annotate/LabelTree.tsx` | 标签树侧栏 |
| **新增** | `src/components/shared/ExportModal.tsx` | 导出弹窗 |
| **新增** | `src/pages/SettingsPage.tsx` | 配置页 |
| **修改** | `src/pages/GeneratePage.tsx` | 新增标注 Tab、集成导出弹窗、批处理支持 |
| **修改** | `src/pages/ZipPage.tsx` | 多文件上传支持 |
| **修改** | `src/pages/DbPage.tsx` | 锁定机制 |
| **修改** | `src/App.tsx` | 新增 SettingsPage 路由、设置导航项 |
| **修改** | `src/components/layout/Sidebar.tsx` | 新增设置导航项 |
| **修改** | `src/api/client.ts` | 补全 annotation API、batch upload、config API |
| **修改** | `src/types/index.ts` | 新增配置相关类型 |
| **修改** | `src/index.css` | 标注工具相关样式 |

### 8.1 不改动项

| 项 | 原因 |
|---|------|
| `updated_front/` | 约束：不可修改 |
| `backend/` | 约束：不可修改 |
| 3D 查看器 | 用户明确跳过 |
| 现有 4 页功能逻辑 | 已对齐，不改动 |
| Tailwind 配置 | 现有 token 足够 |

---

## 9. 实施顺序

| 阶段 | 功能 | 复杂度 | 预估文件数 |
|------|------|--------|-----------|
| 1 | 标注工具 Tab | 高 | 新增 4 + 改 1 |
| 2 | 导出弹窗 | 中 | 新增 1 + 改 2 |
| 3 | 配置页 | 低 | 新增 1 + 改 3 |
| 4 | 批处理上传 | 低 | 改 2 |
| 5 | annotation_required SSE | 低 | 改 2 |
| 6 | DB 页锁定 | 低 | 改 1 |

每个阶段完成后用户测评，通过后再进入下一阶段。全部完成后统一接入后端 API。

---

*最后更新：2026-06-13*
