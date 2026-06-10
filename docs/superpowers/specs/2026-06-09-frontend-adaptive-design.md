# 前端自适应布局设计文档

**日期**：2026-06-09  
**分支**：2d  
**范围**：`updated_front/css/industrial-console.css` + `updated_front/demo-industrial-console.html`

---

## 背景与目标

当前前端按桌面宽屏（1920px）设计，侧边栏固定 296px，面板内边距 22px，工具栏按钮使用全长文字。笔记本用户（1366px～1440px）出现横向溢出和整体挤压问题。

**目标**：在 1366px～1920px 全分辨率范围内无横向溢出，布局比例协调，视觉呼吸感好。

**原则**：所有收紧规则限定在 `@media (max-width: 1500px)` 内，宽屏（>1500px）完全不变，零 breaking change。

---

## 模块一：侧边栏流式宽度

**策略**：CSS `clamp()` 替代固定值，无断点跳变。

```css
/* industrial-console.css — CSS 变量区 */
--sidebar-width: clamp(160px, 18.5vw, 296px);
```

| 视口宽度 | 侧边栏宽度 |
|---------|-----------|
| ≥1600px | 296px（满值）|
| 1366px  | ~252px |
| 1200px  | ~222px |
| ≤865px  | 160px（下限）|

导航文字防溢出：

```css
.nav-title, .nav-subtitle {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
```

---

## 模块二：工具栏双文字切换

宽屏显示全称，≤1500px 显示简称，纯 CSS 实现。

**HTML**（4 个按钮各加两个 span）：

```html
<button class="button primary" id="uploadGenerateBtn">
  <span class="btn-full">⤴ 上传文件</span><span class="btn-short">⤴ 上传</span>
</button>
<button class="button secondary" id="retrievalLibraryBtn">
  <span class="btn-full">◉ 检索库：公共工艺库</span><span class="btn-short">◉ 工艺库</span>
</button>
<button class="button secondary" id="featureCacheToggleBtn">
  <span class="btn-full">⚡ 特征缓存：关</span><span class="btn-short">⚡ 缓存</span>
</button>
<button class="button secondary" id="resetGenerateBtn">
  <span class="btn-full">↺ 重置工作区</span><span class="btn-short">↺</span>
</button>
```

**CSS**：

```css
.btn-short { display: none; }

@media (max-width: 1500px) {
  .btn-full  { display: none; }
  .btn-short { display: inline; }
}
```

> 注：`featureCacheToggleBtn` 的文字由 JS 动态切换（"开"/"关"），JS 逻辑改为同时更新 `.btn-full` 和 `.btn-short` 的文字。

---

## 模块三：顶栏紧凑化

```css
@media (max-width: 1500px) {
  .unified-topbar { padding: 7px 12px; }
  .toolbar-actions .button { height: 26px; padding: 0 8px; font-size: 12px; }
}
```

**HUD 自动折叠**：页面加载时检测视口宽度，≤1500px 自动折叠进度 HUD，复用已有的展开/收起切换逻辑。在 `demo-industrial-console.js` 初始化区块末尾加：

```js
if (window.innerWidth <= 1500) {
  document.getElementById('workflowHudCard')?.classList.add('hud-collapsed');
}
```

---

## 模块四：面板内边距收紧

```css
@media (max-width: 1500px) {
  .upload-panel-body,
  .result-panel-body {
    padding: 14px;
  }
}
```

---

## 模块五：workbench 列比例调整

```css
@media (max-width: 1500px) {
  .workbench {
    grid-template-columns: minmax(320px, 0.82fr) 14px minmax(420px, 1.18fr);
  }
}
```

结果区（特征审阅 / 工艺规程）从 1.08fr 升至 1.18fr，表格和工艺步骤有更多水平空间。

---

## 模块六：面板字号流式缩放

```css
@media (max-width: 1500px) {
  .review-board,
  .result-panel-body,
  .upload-panel-body {
    font-size: clamp(11px, 0.85vw, 14px);
  }
  .dropzone-title {
    font-size: clamp(14px, 1.1vw, 18px);
  }
}
```

---

## 保底规则

```css
body { overflow-x: hidden; }
```

---

## 改动量汇总

| 文件 | 改动内容 | 行数 |
|------|---------|------|
| `css/industrial-console.css` | 6 个模块的 media query + clamp | ~40 行 |
| `demo-industrial-console.html` | 4 个按钮加 span | ~12 行 |
| `js/demo-industrial-console.js` | HUD 自动折叠 + featureCache 按钮文字逻辑 | ~8 行 |

**不改动**：其他页面（历史记录、数据库浏览、工艺入库）、折叠侧边栏逻辑、现有 980px 断点、后端代码。

---

## 验收标准

- [ ] 1366×768 视口下无横向滚动条
- [ ] 1366px 下工具栏 4 个按钮全部可见（显示短文字）
- [ ] workbench 两侧面板均可见且比例合理
- [ ] 宽屏（1920px）显示效果与改动前一致
- [ ] HUD 在 1366px 下默认折叠，可手动展开
