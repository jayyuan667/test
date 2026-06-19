# 前端自适应布局 — 实施计划

**对应设计**：`2026-06-09-frontend-adaptive-design.md`  
**分支**：2d  
**回退基点**：`9ead6ec`（设计文档提交）

---

## 执行顺序

```
步骤 1（CSS 基础）─► 步骤 2（CSS 密度）─► 步骤 3（HTML 按钮）─► 步骤 4（JS）─► 步骤 5（验收）
```

全部在同一文件组内，无外部依赖，可线性执行。

---

## 步骤 1：侧边栏 clamp + 导航文字防溢出

**文件**：`updated_front/css/industrial-console.css`

**1.1** 找到 CSS 变量区（约第 27 行），替换侧边栏宽度：

```css
/* 改前 */
--sidebar-width: 296px;

/* 改后 */
--sidebar-width: clamp(160px, 18.5vw, 296px);
```

**1.2** 在 `.nav-item` 相关样式附近补充文字截断规则：

```css
.nav-title,
.nav-subtitle {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
```

**1.3** 在文件末尾（`prefers-reduced-motion` 规则之前）添加保底规则：

```css
body { overflow-x: hidden; }
```

**验证**：浏览器缩放到 1366px 宽，侧边栏应收窄且导航文字不溢出。

---

## 步骤 2：笔记本密度优化（media query 集中写在文件末尾）

**文件**：`updated_front/css/industrial-console.css`

在步骤 1.3 保底规则之后，追加一个统一的 `@media (max-width: 1500px)` 块：

```css
/* ── 笔记本自适应（≤1500px）── */
@media (max-width: 1500px) {

  /* 2a. 工具栏按钮双文字切换 */
  .btn-short { display: none; }
  .btn-full  { display: inline; }

  /* 2b. 顶栏紧凑化 */
  .unified-topbar {
    padding: 7px 12px;
  }
  .toolbar-actions .button {
    height: 26px;
    padding: 0 8px;
    font-size: 12px;
  }

  /* 2c. 面板内边距收紧 */
  .upload-panel-body,
  .result-panel-body {
    padding: 14px;
  }

  /* 2d. workbench 列比例 — 结果区更宽 */
  .workbench {
    grid-template-columns: minmax(320px, 0.82fr) 14px minmax(420px, 1.18fr);
  }

  /* 2e. 面板字号流式缩放 */
  .review-board,
  .result-panel-body,
  .upload-panel-body {
    font-size: clamp(11px, 0.85vw, 14px);
  }
  .dropzone-title {
    font-size: clamp(14px, 1.1vw, 18px);
  }
}

/* 宽屏默认：btn-short 隐藏 */
.btn-short { display: none; }
```

> 注意：`.btn-short { display: none }` 需要同时在 media query 外声明，确保宽屏默认隐藏短文字。

**验证**：1500px 以上无变化；1366px 下顶栏更紧凑，面板内边距收小，结果区更宽。

---

## 步骤 3：工具栏按钮加双文字 span

**文件**：`updated_front/demo-industrial-console.html`

找到 `class="toolbar-actions"` 内的 4 个按钮，各加 `.btn-full` / `.btn-short` 两个 span：

```html
<!-- 改前 -->
<button class="button primary" id="uploadGenerateBtn">⤴ 上传文件</button>
<button class="button secondary" id="retrievalLibraryBtn">◉ 检索库：公共工艺库</button>
<button class="button secondary" id="featureCacheToggleBtn" ...>⚡ 特征缓存：关</button>
<button class="button secondary" id="resetGenerateBtn">↺ 重置工作区</button>

<!-- 改后 -->
<button class="button primary" id="uploadGenerateBtn">
  <span class="btn-full">⤴ 上传文件</span><span class="btn-short">⤴ 上传</span>
</button>
<button class="button secondary" id="retrievalLibraryBtn">
  <span class="btn-full">◉ 检索库：公共工艺库</span><span class="btn-short">◉ 工艺库</span>
</button>
<button class="button secondary" id="featureCacheToggleBtn" ...>
  <span class="btn-full">⚡ 特征缓存：关</span><span class="btn-short">⚡ 缓存</span>
</button>
<button class="button secondary" id="resetGenerateBtn">
  <span class="btn-full">↺ 重置工作区</span><span class="btn-short">↺</span>
</button>
```

**验证**：1366px 下显示短文字，1920px 下显示全文字。

---

## 步骤 4：JS 两处联动修改

**文件**：`updated_front/js/demo-industrial-console.js`

**4.1 HUD 自动折叠**：在页面初始化完成后（DOMContentLoaded 或等效位置末尾）加：

```js
// 笔记本视口自动折叠进度 HUD
if (window.innerWidth <= 1500) {
  const hudCard = document.getElementById('workflowHudCard');
  if (hudCard) {
    // 找到现有的折叠切换逻辑使用的 class/方法，触发一次折叠
    // 若现有逻辑是 toggleHud() 函数，调用 toggleHud()
    // 若是直接操作 class，补加对应 class
    hudCard.classList.add('hud-collapsed');
  }
}
```

> ⚠️ 实施前需先搜索 `workflowHudToggleBtn` 的点击处理逻辑，确认折叠时实际操作的 class 名称，将 `hud-collapsed` 替换为正确的 class。

**4.2 特征缓存按钮文字同步**：找到 `featureCacheToggleBtn` 的点击处理，将文字更新逻辑改为同时更新两个 span：

```js
// 改前（示意）
featureCacheToggleBtn.textContent = `⚡ 特征缓存：${state}`;

// 改后
featureCacheToggleBtn.querySelector('.btn-full').textContent = `⚡ 特征缓存：${state}`;
featureCacheToggleBtn.querySelector('.btn-short').textContent = `⚡ ${state === '开' ? '缓存' : '缓存'}`;
```

**验证**：点击缓存按钮，短文字版本同步更新；HUD 在 1366px 下默认折叠。

---

## 步骤 5：验收检查清单

| 检查项 | 方法 |
|--------|------|
| 1366×768 无横向滚动条 | 浏览器 DevTools 调到 1366px，检查 body 无 overflow |
| 工具栏 4 按钮全部可见 | 1366px 下确认显示短文字，无截断 |
| workbench 两侧面板比例合理 | 结果区更宽，上传区不被压垮（min 320px）|
| 宽屏（1920px）与改前一致 | 切回 1920px，全文字显示，侧边栏 296px |
| HUD 默认折叠（1366px）| 可手动展开，展开后正常工作 |
| featureCache 按钮文字同步 | 切换缓存开/关，短文字版本正确更新 |

---

## 回退方式

```bash
git checkout 9ead6ec -- updated_front/css/industrial-console.css
git checkout 9ead6ec -- updated_front/demo-industrial-console.html
git checkout 9ead6ec -- updated_front/js/demo-industrial-console.js
```
