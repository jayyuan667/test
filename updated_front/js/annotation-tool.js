/* annotation-tool.js — Manual bounding-box annotation tool */
(function (global) {
  'use strict';

  const LABEL_CONFIG = {
    chamfer:       { id: 2, color: '#f59e0b', dash: null,  zh: '倒角'  },
    threaded_hole: { id: 0, color: '#6366f1', dash: '6,3', zh: '螺纹孔' },
    circle_hole:   { id: 1, color: '#10b981', dash: null,  zh: '圆孔'  },
  };

  const EXTRA_COLORS = ['#ec4899', '#14b8a6', '#f97316', '#8b5cf6', '#06b6d4'];
  const NS = 'http://www.w3.org/2000/svg';

  // localStorage key for user-added label types. Experiment scope:
  // 不写后端 class_id 映射，纯前端缓存；后续整理数据集时再做正式映射。
  const LS_CUSTOM_LABELS = 'annotate.customLabels.v1';

  function loadCustomLabelsFromLS() {
    try {
      const raw = localStorage.getItem(LS_CUSTOM_LABELS);
      const obj = raw ? JSON.parse(raw) : {};
      return (obj && typeof obj === 'object') ? obj : {};
    } catch (_) { return {}; }
  }
  function saveCustomLabelsToLS(map) {
    try { localStorage.setItem(LS_CUSTOM_LABELS, JSON.stringify(map || {})); } catch (_) {}
  }
  // Expose so demo-industrial-console can render summary cards with custom colors/zh.
  global.getAnnotationLabelMeta = function () {
    const builtins = {};
    Object.entries(LABEL_CONFIG).forEach(([k, v]) => { builtins[k] = { zh: v.zh, color: v.color }; });
    const customs = loadCustomLabelsFromLS();
    const merged = { ...builtins };
    Object.entries(customs).forEach(([k, v]) => { merged[k] = { zh: v.zh || k, color: v.color || '#9ca3af' }; });
    return merged;
  };

  /* ── AnnotationTool ────────────────────────────────────────────────────── */
  class AnnotationTool {
    /**
     * @param {Element} controlsEl  Right-sidebar controls container
     * @param {string}  apiBase     API base URL, e.g. "/api"
     */
    constructor(controlsEl, apiBase) {
      this._controls = controlsEl;
      this._apiBase  = apiBase;

      this._taskId       = null;
      this._allPages     = {};
      this._pageIndex    = 0;
      this._pageUrls     = [];
      this._annotations  = [];
      this._activeLabel  = 'chamfer';
      this._customLabels = loadCustomLabelsFromLS();

      this._drawState = { isDrawing: false, startX: 0, startY: 0 };
      this._draftRect = null;
      this._saveTimer = null;
      this._selectedId = null;
      this._zoom = 1.0;        // Current zoom factor: 1 = 100% pixel-perfect
      this._fitZoom = 1.0;     // Last computed "fit" zoom for the loaded image

      // Set by activate()
      this._img = null;   // <img> inside annotate-fs-img-wrap
      this._svg = null;   // <svg> sibling of img (same wrapper)

      this._boundMouseDown   = this._onMouseDown.bind(this);
      this._boundMouseMove   = this._onMouseMove.bind(this);
      this._boundMouseUp     = this._onMouseUp.bind(this);
      this._boundMouseLeave  = (e) => { if (this._drawState.isDrawing) this._onMouseUp(e); };
      this._boundContextMenu = (e) => e.preventDefault();
    }

    /* ── activate / deactivate ──────────────────────────────────────────── */

    /**
     * Start annotation mode.
     * @param {string}   taskId          Backend task ID
     * @param {string[]} previewImageUrls Server-relative URLs for each page
     * @param {HTMLImageElement} imgEl   The <img> to draw annotations on
     * @param {SVGSVGElement}    svgEl   SVG sibling positioned over imgEl
     */
    activate(taskId, previewImageUrls, imgEl, svgEl) {
      this._taskId    = taskId;
      this._img       = imgEl;
      this._svg       = svgEl;
      this._pageUrls  = Array.isArray(previewImageUrls) ? previewImageUrls : [];
      this._pageIndex = 0;
      this._allPages  = {};
      this._annotations = [];

      this._svg.addEventListener('mousedown',   this._boundMouseDown);
      this._svg.addEventListener('mousemove',   this._boundMouseMove);
      this._svg.addEventListener('mouseup',     this._boundMouseUp);
      this._svg.addEventListener('mouseleave',  this._boundMouseLeave);
      this._svg.addEventListener('contextmenu', this._boundContextMenu);

      // Ctrl+wheel zoom centered on cursor; plain wheel still scrolls the container.
      this._boundWheel = (ev) => {
        if (!ev.ctrlKey && !ev.metaKey) return;
        ev.preventDefault();
        const scroll = document.getElementById('annotateFsScroll');
        if (!scroll || !this._img || !this._img.naturalWidth) return;
        const factor = ev.deltaY < 0 ? 1.15 : 1 / 1.15;
        const newZoom = Math.max(0.05, Math.min(8.0, this._zoom * factor));
        if (newZoom === this._zoom) return;

        // Pixel under the cursor (natural coord) — keep it under cursor after zoom
        const imgRect = this._img.getBoundingClientRect();
        const sxOld   = imgRect.width / this._img.naturalWidth;
        const pxNat   = (ev.clientX - imgRect.left) / sxOld;
        const pyNat   = (ev.clientY - imgRect.top)  / sxOld;

        this.setZoom(newZoom);

        // After re-layout, scroll so that (pxNat, pyNat) is at cursor screen pos
        const newImgRect = this._img.getBoundingClientRect();
        const scrollRect = scroll.getBoundingClientRect();
        const sxNew = newImgRect.width / this._img.naturalWidth;
        const desiredScreenX = ev.clientX - scrollRect.left;
        const desiredScreenY = ev.clientY - scrollRect.top;
        const targetLeft = (newImgRect.left - scrollRect.left) + scroll.scrollLeft + pxNat * sxNew - desiredScreenX;
        const targetTop  = (newImgRect.top  - scrollRect.top)  + scroll.scrollTop  + pyNat * sxNew - desiredScreenY;
        scroll.scrollLeft = Math.max(0, targetLeft);
        scroll.scrollTop  = Math.max(0, targetTop);
      };
      const scrollEl = document.getElementById('annotateFsScroll');
      if (scrollEl) scrollEl.addEventListener('wheel', this._boundWheel, { passive: false });

      this._wireControls();
      this._loadPage(0);
      this._loadFromServer();
    }

    deactivate() {
      // Sync current page into _allPages before saving
      this._allPages[this._pageKey()] = this._annotations.slice();

      // Save ALL pages that have annotations, not just the current one
      const savePromises = [];
      Object.entries(this._allPages).forEach(([pageKey, shapes]) => {
        if (!shapes || shapes.length === 0) return;
        const pageNum = parseInt(pageKey, 10);
        const imgSrc = this._pageUrls[pageNum - 1] || this._img?.src || '';
        const imgFilename = imgSrc.split('/').pop().split('?')[0] || `page_${pageNum}.png`;
        const payload = {
          page:        pageNum,
          shapes:      shapes.map((a) => ({ label: a.label, points: a.points })),
          imageWidth:  this._img?.naturalWidth  || 0,
          imageHeight: this._img?.naturalHeight || 0,
          imagePath:   imgFilename,
        };
        savePromises.push(
          fetch(`${this._apiBase}/annotations/${this._taskId}/save`, {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify(payload),
          }).catch((err) => console.warn('[annotation-tool] save page', pageNum, 'failed:', err))
        );
      });

      const allSaved = savePromises.length > 0 ? Promise.all(savePromises) : Promise.resolve();

      const scrollEl = document.getElementById('annotateFsScroll');
      if (scrollEl && this._boundWheel) {
        scrollEl.removeEventListener('wheel', this._boundWheel);
      }
      if (this._svg) {
        this._svg.removeEventListener('mousedown',   this._boundMouseDown);
        this._svg.removeEventListener('mousemove',   this._boundMouseMove);
        this._svg.removeEventListener('mouseup',     this._boundMouseUp);
        this._svg.removeEventListener('mouseleave',  this._boundMouseLeave);
        this._svg.removeEventListener('contextmenu', this._boundContextMenu);
        this._svg.innerHTML = '';
        this._svg = null;
      }
      this._drawState.isDrawing = false;
      this._draftRect = null;
      clearTimeout(this._saveTimer);
      return allSaved;
    }

    /** Return aggregate counts {chamfer, threaded_hole, circle_hole, pages}
     *  across all pages the user has touched in this session. Used by the host
     *  app to refresh the awaiting_annotation summary card after exit. */
    getSummary() {
      // 保证当前页 in-memory 状态被算进去
      this._allPages[this._pageKey()] = this._annotations.slice();
      const sum = {};
      let pages = 0;
      Object.values(this._allPages).forEach((shapes) => {
        pages += 1;
        (shapes || []).forEach((s) => {
          if (!s || !s.label) return;
          sum[s.label] = (sum[s.label] || 0) + 1;
        });
      });
      // 内建三类即使为 0 也保留占位，让卡片始终显示它们
      if (sum.chamfer === undefined) sum.chamfer = 0;
      if (sum.threaded_hole === undefined) sum.threaded_hole = 0;
      if (sum.circle_hole === undefined) sum.circle_hole = 0;
      return { ...sum, pages };
    }

    /** Synchronous best-effort save for page-unload paths. Uses sendBeacon
     *  which the browser guarantees to send even after the document unloads. */
    sendBeaconSave() {
      if (!this._taskId || !this._img) return;
      if (typeof navigator === 'undefined' || !navigator.sendBeacon) return;
      const imgSrc = this._img.src || '';
      const payload = {
        page:        this._pageIndex + 1,
        shapes:      this._annotations.map((a) => ({ label: a.label, points: a.points })),
        imageWidth:  this._img.naturalWidth  || 0,
        imageHeight: this._img.naturalHeight || 0,
        imagePath:   imgSrc.split('/').pop().split('?')[0] || 'page_1.png',
      };
      try {
        const blob = new Blob([JSON.stringify(payload)], { type: 'application/json' });
        navigator.sendBeacon(
          `${this._apiBase}/annotations/${this._taskId}/save`,
          blob,
        );
      } catch (_) { /* best-effort */ }
    }

    /* ── Controls wiring ────────────────────────────────────────────────── */

    _wireControls() {
      if (!this._controls) return;
      this._renderToolbar();
      this._renderList();
      this._renderPageCounter();

      const prev = this._controls.querySelector('#annotateFsPagePrev');
      const next = this._controls.querySelector('#annotateFsPageNext');
      if (prev) prev.onclick = () => this._goPage(this._pageIndex - 1);
      if (next) next.onclick = () => this._goPage(this._pageIndex + 1);

      const exp = this._controls.querySelector('#annotateFsExportBtn');
      if (exp) exp.onclick = () => this._exportZip();

      const add = this._controls.querySelector('#annotateFsAddTypeBtn');
      if (add) add.onclick = () => {
        const zh = prompt('新标签名称（中文）：');
        if (zh && zh.trim()) this.addCustomLabel(zh.trim());
      };

      const zIn  = this._controls.querySelector('#annotateFsZoomInBtn');
      const zOut = this._controls.querySelector('#annotateFsZoomOutBtn');
      const zFit = this._controls.querySelector('#annotateFsZoomFitBtn');
      const zOne = this._controls.querySelector('#annotateFsZoomOneBtn');
      if (zIn)  zIn.onclick  = () => this.setZoom(this._zoom * 1.25);
      if (zOut) zOut.onclick = () => this.setZoom(this._zoom / 1.25);
      if (zFit) zFit.onclick = () => this.fitToViewport();
      if (zOne) zOne.onclick = () => this.setZoom(1.0);
    }

    /* ── Zoom ───────────────────────────────────────────────────────────── */

    setZoom(z) {
      z = Math.max(0.05, Math.min(8.0, z));
      this._zoom = z;
      this._applyZoom();
      this.renderAll();          // re-render boxes — getBoundingClientRect picks up new sizes
      this._updateZoomLabel();
    }

    fitToViewport() {
      if (!this._img || !this._img.naturalWidth) return;
      const scroll = document.getElementById('annotateFsScroll');
      if (!scroll) return;
      // .annotate-fs-scroll has padding: 28px (see CSS). Account for both sides.
      const pad = 28;
      const availW = scroll.clientWidth  - pad * 2;
      const availH = scroll.clientHeight - pad * 2;
      const sx = availW / this._img.naturalWidth;
      const sy = availH / this._img.naturalHeight;
      const fit = Math.min(sx, sy);
      this._fitZoom = fit;
      this.setZoom(fit);
    }

    _applyZoom() {
      if (!this._img || !this._img.naturalWidth) return;
      // Override CSS max-width/max-height — we control size directly now.
      this._img.style.maxWidth  = 'none';
      this._img.style.maxHeight = 'none';
      this._img.style.width  = (this._img.naturalWidth  * this._zoom) + 'px';
      this._img.style.height = (this._img.naturalHeight * this._zoom) + 'px';
    }

    _updateZoomLabel() {
      if (!this._controls) return;
      const el = this._controls.querySelector('#annotateFsZoomLabel');
      if (el) el.textContent = Math.round(this._zoom * 100) + '%';
    }

    /* ── Label management ───────────────────────────────────────────────── */

    _allLabels() {
      return { ...LABEL_CONFIG, ...this._customLabels };
    }

    _labelCfg(key) {
      return this._allLabels()[key] || { id: 99, color: '#9ca3af', dash: null, zh: key };
    }

    setActiveLabel(key) {
      this._activeLabel = key;
      this._renderToolbar();
    }

    addCustomLabel(zh) {
      // 允许中文做 key — 避免 toLowerCase 把中文吃成空串
      const safeKey = (s) => {
        const k = String(s || '').trim().replace(/\s+/g, '_');
        return k || `label_${Date.now()}`;
      };
      const key = safeKey(zh);
      if (this._allLabels()[key]) {
        this.setActiveLabel(key);
        return;
      }
      const idx = Object.keys(this._customLabels).length;
      this._customLabels[key] = {
        id: Object.keys(LABEL_CONFIG).length + idx,
        color: EXTRA_COLORS[idx % EXTRA_COLORS.length],
        dash: null,
        zh: String(zh).trim(),
      };
      saveCustomLabelsToLS(this._customLabels);
      this._activeLabel = key;
      this._renderToolbar();
    }

    removeCustomLabel(key) {
      if (!this._customLabels[key]) return;
      // 拒绝删除有标注引用的类型；让用户先把那些框清掉或改成别的类型，免得静默丢标签
      let usedPages = 0;
      this._allPages[this._pageKey()] = this._annotations.slice();
      Object.values(this._allPages).forEach((shapes) => {
        if ((shapes || []).some((s) => s.label === key)) usedPages += 1;
      });
      if (usedPages > 0) {
        alert(`无法删除「${this._customLabels[key].zh}」：仍有 ${usedPages} 页存在此类型的标注框`);
        return;
      }
      delete this._customLabels[key];
      saveCustomLabelsToLS(this._customLabels);
      if (this._activeLabel === key) this._activeLabel = 'chamfer';
      this._renderToolbar();
    }

    /* ── Toolbar ────────────────────────────────────────────────────────── */

    _renderToolbar() {
      if (!this._controls) return;
      const row = this._controls.querySelector('#annotateFsLabelRow');
      if (!row) return;
      row.innerHTML = '';
      const isCustom = (key) => Object.prototype.hasOwnProperty.call(this._customLabels, key);
      Object.entries(this._allLabels()).forEach(([key, cfg]) => {
        const btn = document.createElement('button');
        btn.className = 'annotate-label-btn' + (key === this._activeLabel ? ' active' : '');
        btn.textContent = (isCustom(key) ? '◆ ' : '● ') + cfg.zh;
        btn.style.color       = cfg.color;
        btn.style.borderColor = cfg.color;
        btn.style.background  = cfg.color + '18';
        btn.title = isCustom(key) ? `自定义类型 · 右键删除` : cfg.zh;
        btn.onclick = () => this.setActiveLabel(key);
        if (isCustom(key)) {
          btn.oncontextmenu = (e) => {
            e.preventDefault();
            if (confirm(`删除自定义类型「${cfg.zh}」？\n（若已被标注框使用将拒绝删除）`)) {
              this.removeCustomLabel(key);
            }
          };
        }
        row.appendChild(btn);
      });
    }

    /* ── Page handling ──────────────────────────────────────────────────── */

    _loadPage(idx) {
      if (idx < 0 || (this._pageUrls.length > 0 && idx >= this._pageUrls.length)) return;

      this._allPages[this._pageKey()] = this._annotations.slice();
      this._pageIndex   = idx;
      this._annotations = this._allPages[this._pageKey()] || [];

      const relUrl = this._pageUrls[idx] || '';
      if (this._img && relUrl) {
        if (this._img.getAttribute('src') !== relUrl) {
          this._img.src = relUrl;
        }
        this._img.style.display = 'block';
      }

      this._renderPageCounter();

      const onReady = () => {
        // First fit the image to viewport (sets _zoom + img.width/height)
        this.fitToViewport();
        this._renderList();
      };
      if (this._img && this._img.complete && this._img.naturalWidth) {
        onReady();
      } else if (this._img) {
        this._img.addEventListener('load', onReady, { once: true });
      }
    }

    _goPage(idx) {
      this._autoSaveNow();
      this._loadPage(idx);
    }

    _pageKey() { return String(this._pageIndex + 1); }

    _renderPageCounter() {
      if (!this._controls) return;
      const el = this._controls.querySelector('#annotateFsPageCounter');
      if (!el) return;
      el.textContent = `${this._pageIndex + 1} / ${this._pageUrls.length || 1}`;
    }

    /* ── Coordinate math ────────────────────────────────────────────────── */
    // SVG is position:absolute; inset:0 inside the same inline-block wrapper as
    // the image. getBoundingClientRect() of both should be nearly identical (dx≈0,
    // dy≈0). Using getBoundingClientRect() instead of clientWidth so that any CSS
    // transform on a parent doesn't break the math.

    _imgOffset() {
      if (!this._img || !this._svg) return { dx: 0, dy: 0, sx: 1, sy: 1 };
      const ir = this._img.getBoundingClientRect();
      const sr = this._svg.getBoundingClientRect();
      return {
        dx: ir.left - sr.left,
        dy: ir.top  - sr.top,
        sx: ir.width  / (this._img.naturalWidth  || 1),
        sy: ir.height / (this._img.naturalHeight || 1),
      };
    }

    _toReal(svgX, svgY) {
      const { dx, dy, sx, sy } = this._imgOffset();
      return [(svgX - dx) / sx, (svgY - dy) / sy];
    }

    _toDisplay(realX, realY) {
      const { dx, dy, sx, sy } = this._imgOffset();
      return [realX * sx + dx, realY * sy + dy];
    }

    /* ── Drawing ────────────────────────────────────────────────────────── */

    _onMouseDown(e) {
      if (e.button !== 0) return;
      const sr = this._svg.getBoundingClientRect();
      this._drawState = {
        isDrawing: true,
        startX: e.clientX - sr.left,
        startY: e.clientY - sr.top,
      };
      this._draftRect = document.createElementNS(NS, 'rect');
      const cfg = this._labelCfg(this._activeLabel);
      this._draftRect.setAttribute('fill',         cfg.color + '22');
      this._draftRect.setAttribute('stroke',       cfg.color);
      this._draftRect.setAttribute('stroke-width', '2');
      if (cfg.dash) this._draftRect.setAttribute('stroke-dasharray', cfg.dash);
      this._draftRect.setAttribute('pointer-events', 'none');
      this._svg.appendChild(this._draftRect);
    }

    _onMouseMove(e) {
      if (!this._drawState.isDrawing || !this._draftRect) return;
      const sr = this._svg.getBoundingClientRect();
      const cx = e.clientX - sr.left;
      const cy = e.clientY - sr.top;
      const { startX, startY } = this._drawState;
      this._draftRect.setAttribute('x',      Math.min(startX, cx));
      this._draftRect.setAttribute('y',      Math.min(startY, cy));
      this._draftRect.setAttribute('width',  Math.abs(cx - startX));
      this._draftRect.setAttribute('height', Math.abs(cy - startY));
    }

    _onMouseUp(e) {
      if (!this._drawState.isDrawing) return;
      this._drawState.isDrawing = false;

      const sr = this._svg.getBoundingClientRect();
      const ex = e.clientX - sr.left;
      const ey = e.clientY - sr.top;
      const { startX, startY } = this._drawState;

      if (this._draftRect) {
        this._svg.removeChild(this._draftRect);
        this._draftRect = null;
      }

      if (Math.abs(ex - startX) < 6 || Math.abs(ey - startY) < 6) return;

      const [rx1, ry1] = this._toReal(Math.min(startX, ex), Math.min(startY, ey));
      const [rx2, ry2] = this._toReal(Math.max(startX, ex), Math.max(startY, ey));

      this._annotations.push({
        id:     Date.now(),
        label:  this._activeLabel,
        points: [[rx1, ry1], [rx2, ry2]],
      });

      this.renderAll();
      this._renderList();
      this._scheduleSave();
    }

    /* ── Render ─────────────────────────────────────────────────────────── */

    renderAll() {
      if (!this._svg) return;
      Array.from(this._svg.childNodes).forEach((c) => {
        if (c !== this._draftRect) c.remove();
      });

      // Per-label sequence counter — every annotation gets "倒角 N" / "螺纹孔 N"
      const seqCounters = {};

      // Render selected LAST so its highlight is on top of other rects
      const order = this._annotations.slice().sort((a, b) => {
        const aSel = a.id === this._selectedId ? 1 : 0;
        const bSel = b.id === this._selectedId ? 1 : 0;
        return aSel - bSel;
      });

      // First pass: assign per-label seq numbers in the ORIGINAL order so the
      // SVG label "螺纹孔 3" matches the right-panel list "螺纹孔 3"
      const seqById = new Map();
      this._annotations.forEach((ann) => {
        seqCounters[ann.label] = (seqCounters[ann.label] || 0) + 1;
        seqById.set(ann.id, seqCounters[ann.label]);
      });

      order.forEach((ann) => {
        const cfg = this._labelCfg(ann.label);
        const seq = seqById.get(ann.id) || 1;
        const [dx1, dy1] = this._toDisplay(ann.points[0][0], ann.points[0][1]);
        const [dx2, dy2] = this._toDisplay(ann.points[1][0], ann.points[1][1]);
        const x = Math.min(dx1, dx2);
        const y = Math.min(dy1, dy2);
        const w = Math.abs(dx2 - dx1);
        const h = Math.abs(dy2 - dy1);

        const isSel = ann.id === this._selectedId;

        // ── Selection halo: white outline rect just behind the colored rect ──
        if (isSel) {
          const halo = document.createElementNS(NS, 'rect');
          const pad = 6;
          halo.setAttribute('x', x - pad);
          halo.setAttribute('y', y - pad);
          halo.setAttribute('width',  w + 2 * pad);
          halo.setAttribute('height', h + 2 * pad);
          halo.setAttribute('fill', 'none');
          halo.setAttribute('stroke', '#ffffff');
          halo.setAttribute('stroke-width', '6');
          halo.setAttribute('pointer-events', 'none');
          halo.setAttribute('rx', '4');
          this._svg.appendChild(halo);

          const ring = document.createElementNS(NS, 'rect');
          ring.setAttribute('x', x - pad);
          ring.setAttribute('y', y - pad);
          ring.setAttribute('width',  w + 2 * pad);
          ring.setAttribute('height', h + 2 * pad);
          ring.setAttribute('fill', 'none');
          ring.setAttribute('stroke', '#111827');
          ring.setAttribute('stroke-width', '2.5');
          ring.setAttribute('stroke-dasharray', '6 4');
          ring.setAttribute('pointer-events', 'none');
          ring.setAttribute('rx', '4');
          this._svg.appendChild(ring);
        }

        // ── The actual labeled rect ──
        const rect = document.createElementNS(NS, 'rect');
        rect.setAttribute('data-ann-id', String(ann.id));
        rect.setAttribute('x', x);  rect.setAttribute('y', y);
        rect.setAttribute('width', w); rect.setAttribute('height', h);
        rect.setAttribute('fill',   cfg.color + (isSel ? '55' : '22'));
        rect.setAttribute('stroke', cfg.color);
        rect.setAttribute('stroke-width', isSel ? '4' : '2');
        if (cfg.dash) rect.setAttribute('stroke-dasharray', cfg.dash);
        rect.style.cursor = 'pointer';
        const title = document.createElementNS(NS, 'title');
        title.textContent = `${cfg.zh} ${seq}`;
        rect.appendChild(title);
        rect.addEventListener('mousedown', (ev) => {
          if (ev.button === 0) ev.stopPropagation();
        });
        rect.addEventListener('click', (ev) => {
          if (ev.button !== 0) return;
          ev.stopPropagation();
          this._selectAnnotation(ann.id, { fromCanvas: true });
        });
        rect.addEventListener('contextmenu', (ev) => {
          ev.preventDefault();
          this._deleteAnnotation(ann.id);
        });
        this._svg.appendChild(rect);

        // ── Floating label "螺纹孔 3" — always visible ──
        // Selected boxes get full opacity; unselected get a translucent pill.
        {
          const labelText = `${cfg.zh} ${seq}`;
          const tagH = isSel ? 22 : 18;
          const tagFontSize = isSel ? 13 : 11;
          const tagW = Math.max(isSel ? 60 : 48, labelText.length * (isSel ? 12 : 10) + 14);
          const tagX = x;
          const tagY = Math.max(y - tagH - 6, 4);

          const tagBg = document.createElementNS(NS, 'rect');
          tagBg.setAttribute('x', tagX);
          tagBg.setAttribute('y', tagY);
          tagBg.setAttribute('width',  tagW);
          tagBg.setAttribute('height', tagH);
          tagBg.setAttribute('rx', '4');
          tagBg.setAttribute('fill', cfg.color);
          tagBg.setAttribute('opacity', isSel ? '1' : '0.7');
          tagBg.setAttribute('pointer-events', 'none');
          this._svg.appendChild(tagBg);

          const tagTxt = document.createElementNS(NS, 'text');
          tagTxt.setAttribute('x', tagX + tagW / 2);
          tagTxt.setAttribute('y', tagY + tagH / 2 + (isSel ? 5 : 4));
          tagTxt.setAttribute('text-anchor', 'middle');
          tagTxt.setAttribute('opacity', isSel ? '1' : '0.85');
          tagTxt.setAttribute('fill', '#ffffff');
          tagTxt.setAttribute('font-size', String(tagFontSize));
          tagTxt.setAttribute('font-weight', '700');
          tagTxt.setAttribute('font-family', 'sans-serif');
          tagTxt.setAttribute('pointer-events', 'none');
          tagTxt.textContent = labelText;
          this._svg.appendChild(tagTxt);
        }
      });
    }

    /* ── Bi-directional selection ───────────────────────────────────────── */

    _selectAnnotation(id, opts = {}) {
      this._selectedId = id;
      this.renderAll();
      this._renderList();
      // Scroll the OTHER side into view; don't fight the user's own click target
      if (opts.fromCanvas) {
        this._scrollListToAnnotation(id);
      } else if (opts.fromList) {
        this._scrollCanvasToAnnotation(id);
      } else {
        this._scrollListToAnnotation(id);
        this._scrollCanvasToAnnotation(id);
      }
    }

    _scrollCanvasToAnnotation(id) {
      const ann = this._annotations.find((a) => a.id === id);
      if (!ann || !this._svg) return;
      const scroll = document.getElementById('annotateFsScroll');
      if (!scroll) return;
      const [[rx1, ry1], [rx2, ry2]] = ann.points;
      const [dcx, dcy] = this._toDisplay((rx1 + rx2) / 2, (ry1 + ry2) / 2);
      // dcx/dcy are inside the SVG (which sits inside .annotate-fs-img-wrap which
      // sits inside .annotate-fs-scroll). Convert to scroll-container coords.
      const svgRect    = this._svg.getBoundingClientRect();
      const scrollRect = scroll.getBoundingClientRect();
      const targetX = (svgRect.left - scrollRect.left) + scroll.scrollLeft + dcx - scroll.clientWidth  / 2;
      const targetY = (svgRect.top  - scrollRect.top)  + scroll.scrollTop  + dcy - scroll.clientHeight / 2;
      try {
        scroll.scrollTo({ left: Math.max(0, targetX), top: Math.max(0, targetY), behavior: 'smooth' });
      } catch (_) {
        scroll.scrollLeft = Math.max(0, targetX);
        scroll.scrollTop  = Math.max(0, targetY);
      }
    }

    _scrollListToAnnotation(id) {
      if (!this._controls) return;
      const item = this._controls.querySelector(`#annotateFsListBody [data-ann-id="${id}"]`);
      if (item && typeof item.scrollIntoView === 'function') {
        item.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      }
    }

    _deleteAnnotation(id) {
      this._annotations = this._annotations.filter((a) => a.id !== id);
      if (this._selectedId === id) this._selectedId = null;
      this.renderAll();
      this._renderList();
      this._scheduleSave();
    }

    /* ── List ───────────────────────────────────────────────────────────── */

    _renderList() {
      if (!this._controls) return;
      const body  = this._controls.querySelector('#annotateFsListBody');
      const count = this._controls.querySelector('#annotateFsCount');
      if (!body) return;

      if (count) count.textContent = `(${this._annotations.length})`;
      body.innerHTML = '';

      // Per-label sequence: "螺纹孔 1, 2, 3..." instead of global "#17, #18..."
      const seqCounters = {};

      this._annotations.forEach((ann) => {
        const cfg = this._labelCfg(ann.label);
        const [[x1, y1], [x2, y2]] = ann.points;
        seqCounters[ann.label] = (seqCounters[ann.label] || 0) + 1;
        const seq = seqCounters[ann.label];
        const isSel = ann.id === this._selectedId;
        const item = document.createElement('div');
        item.className = 'annotate-list-item' + (isSel ? ' selected' : '');
        item.setAttribute('data-ann-id', String(ann.id));
        item.style.borderLeftColor = cfg.color;
        item.style.background      = cfg.color + (isSel ? '55' : '18');
        item.style.cursor          = 'pointer';
        item.innerHTML = `
          <div style="display:flex;justify-content:space-between;align-items:center">
            <span style="color:${cfg.color};font-weight:${isSel ? 700 : 600}">${cfg.zh} ${seq}</span>
            <span class="annotate-del-btn" style="color:#6b7280;cursor:pointer;font-size:11px">× 删除</span>
          </div>
          <div class="annotate-list-item-coords">
            x:${Math.round(x1)} y:${Math.round(y1)} w:${Math.round(x2-x1)} h:${Math.round(y2-y1)}
          </div>`;
        item.querySelector('.annotate-del-btn').addEventListener('click', (ev) => {
          ev.stopPropagation();
          this._deleteAnnotation(ann.id);
        });
        item.addEventListener('click', () => {
          this._selectAnnotation(ann.id, { fromList: true });
        });
        body.appendChild(item);
      });
    }

    /* ── Persistence ────────────────────────────────────────────────────── */

    _scheduleSave() {
      clearTimeout(this._saveTimer);
      this._saveTimer = setTimeout(() => this._autoSaveNow(), 1000);
    }

    _autoSaveNow() {
      clearTimeout(this._saveTimer);
      if (!this._taskId || !this._img) return Promise.resolve();
      const imgSrc      = this._img.src || '';
      const imgFilename = imgSrc.split('/').pop().split('?')[0] || 'page_1.png';
      const payload = {
        page:        this._pageIndex + 1,
        shapes:      this._annotations.map((a) => ({ label: a.label, points: a.points })),
        imageWidth:  this._img.naturalWidth  || 0,
        imageHeight: this._img.naturalHeight || 0,
        imagePath:   imgFilename,
      };
      this._lastSavePromise = fetch(`${this._apiBase}/annotations/${this._taskId}/save`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(payload),
      }).catch((err) => console.warn('[annotation-tool] save failed:', err));
      return this._lastSavePromise;
    }

    /** Public: force-flush any pending save and wait for it to finish.
     *  Returns a Promise that resolves when the backend has the latest state.
     *  Safe to call after deactivate() — uses cached _img/_taskId. */
    flushSave() {
      return Promise.resolve(this._autoSaveNow())
        .then(() => this._lastSavePromise || null);
    }

    _loadFromServer() {
      if (!this._taskId) return;
      fetch(`${this._apiBase}/annotations/${this._taskId}`)
        .then((r) => r.json())
        .then((data) => {
          if (!data.pages) return;
          Object.entries(data.pages).forEach(([pageN, labelme]) => {
            this._allPages[pageN] = (labelme.shapes || []).map((s) => ({
              id:     Date.now() + Math.random(),
              label:  s.label,
              points: s.points,
            }));
          });
          this._annotations = this._allPages[this._pageKey()] || [];
          this.renderAll();
          this._renderList();
        })
        .catch(() => {});
    }

    _exportZip() {
      if (!this._taskId) return;
      this._autoSaveNow();
      setTimeout(() => {
        const a = document.createElement('a');
        a.href     = `${this._apiBase}/annotations/${this._taskId}/export`;
        a.download = `annotations_${this._taskId}.zip`;
        document.body.appendChild(a);
        a.click();
        setTimeout(() => document.body.removeChild(a), 1000);
      }, 600);
    }
  }

  global.AnnotationTool = AnnotationTool;
})(window);
