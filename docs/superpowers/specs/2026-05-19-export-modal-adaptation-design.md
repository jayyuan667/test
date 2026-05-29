# 导出工艺文件弹窗适配

## 问题

`export-file-modal.html` 是独立 HTML，未被主页面集成；数据格式与后端 `process_flow.data`（`[code, content]` 二元数组）不匹配；图片源应改为 `creo_views/全部默认.jpg`。

## 方案

将导出弹窗嵌入 `demo-industrial-console.html`，复用 `industrial-console.css` 样式系统，去掉 jsPDF 依赖，导出由后端 `/api/export/<task_id>` 处理。

## 架构与交互

1. 点击"导出工艺文件" → 打开 modal
2. 从 `backendState` 获取 `currentProcessTaskId`
3. `GET /api/result/<task_id>` 拿数据填充预览
4. 图片走 `GET /api/result/<task_id>/asset/creo_views/全部默认.jpg`
5. 用户选 PDF → `GET /api/export/<task_id>?format=pdf`（浏览器下载）
6. 用户选 Excel → `GET /api/export/<task_id>?format=xlsx`（浏览器下载）

## 字段映射

| 后端字段 | Modal 显示 |
|----------|-----------|
| `pdf_name` / `source_name` | 文件名称 |
| `task_id` | 任务ID |
| `process_flow.data[][0]` | 工序号 |
| `process_flow.data[][1]` | 工序名称及内容 |
| `feature_report_text` | 特征信息摘要 |
| `/asset/creo_views/全部默认.jpg` | 图片预览 |

## 布局

```
┌──────────────────────────────────────────┐
│  导出工艺文件                          ✕ │
│  Task ID · 文件名称                      │
├──────────────┬───────────────────────────┤
│              │  特征摘要                 │
│  creo_views  │                           │
│  全部默认    │                           │
│  .jpg        │                           │
├──────────────┴───────────────────────────┤
│  工艺规程                                │
│  ┌──────┬──────────────────────────────┐│
│  │ 工序 │ 工序名称及内容               ││
│  ├──────┼──────────────────────────────┤│
│  │ 0010 │ 划线、划检...               ││
│  │ 0020 │ 粗车外圆及内腔...           ││
│  └──────┴──────────────────────────────┘│
├──────────────────────────────────────────┤
│                    [取消] [Excel] [PDF]  │
└──────────────────────────────────────────┘
```

## 样式要点

- 复用 `industrial-console.css` CSS 变量
- 遮罩：`rgba(16,26,40,0.48)` + `backdrop-filter: blur(6px)`
- 卡片：白色，`border-radius: 20px`，`box-shadow` 与 workspace-card 一致
- 工序号列：`--accent` (#ff6528) 橙色
- 图片预览壳：虚线边框 + `object-fit: contain`
- 按钮：复用 `.button.primary` / `.button.secondary`

## 改动范围

| 文件 | 改动 |
|------|------|
| `demo-industrial-console.html` | 新增 modal HTML |
| `demo-industrial-console.js` | 新增 modal 打开/关闭/数据填充逻辑；修改"导出工艺文件"按钮行为 |
| `industrial-console.css` | 新增 modal 样式（~60行） |
| `export-file-modal.html` | 不再使用（或删除） |

无需改动后端，`<path:filename>` 已支持子目录。
