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
      this._customLabels = {};

      this._drawState = { isDrawing: false, startX: 0, startY: 0 };
      this._draftRect = null;
      this._saveTimer = null;

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

      this._wireControls();
      this._loadPage(0);
      this._loadFromServer();
    }

    deactivate() {
      // Kick off a final save and capture its promise so callers can await.
      // SVG/state cleanup is safe to run immediately — they're not used by the save.
      const savePromise = this._autoSaveNow();
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
      return Promise.resolve(savePromise);
    }

    /** Return aggregate counts {chamfer, threaded_hole, circle_hole, pages}
     *  across all pages the user has touched in this session. Used by the host
     *  app to refresh the awaiting_annotation summary card after exit. */
    getSummary() {
      // Make sure the current page's in-memory state is reflected
      this._allPages[this._pageKey()] = this._annotations.slice();
      const sum = { chamfer: 0, threaded_hole: 0, circle_hole: 0 };
      let pages = 0;
      Object.values(this._allPages).forEach((shapes) => {
        pages += 1;
        (shapes || []).forEach((s) => {
          if (sum[s.label] != null) sum[s.label] += 1;
        });
      });
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
      const key = zh.toLowerCase().replace(/\s+/g, '_') || `label_${Date.now()}`;
      if (this._allLabels()[key]) return;
      const idx = Object.keys(this._customLabels).length;
      this._customLabels[key] = {
        id: Object.keys(LABEL_CONFIG).length + idx,
        color: EXTRA_COLORS[idx % EXTRA_COLORS.length],
        dash: null,
        zh,
      };
      this._renderToolbar();
    }

    /* ── Toolbar ────────────────────────────────────────────────────────── */

    _renderToolbar() {
      if (!this._controls) return;
      const row = this._controls.querySelector('#annotateFsLabelRow');
      if (!row) return;
      row.innerHTML = '';
      Object.entries(this._allLabels()).forEach(([key, cfg]) => {
        const btn = document.createElement('button');
        btn.className = 'annotate-label-btn' + (key === this._activeLabel ? ' active' : '');
        btn.textContent = '● ' + cfg.zh;
        btn.style.color       = cfg.color;
        btn.style.borderColor = cfg.color;
        btn.style.background  = cfg.color + '18';
        btn.onclick = () => this.setActiveLabel(key);
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

      const redraw = () => { this.renderAll(); this._renderList(); };
      if (this._img && this._img.complete && this._img.naturalWidth) {
        redraw();
      } else if (this._img) {
        this._img.addEventListener('load', redraw, { once: true });
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

      this._annotations.forEach((ann) => {
        const cfg = this._labelCfg(ann.label);
        const [dx1, dy1] = this._toDisplay(ann.points[0][0], ann.points[0][1]);
        const [dx2, dy2] = this._toDisplay(ann.points[1][0], ann.points[1][1]);
        const x = Math.min(dx1, dx2);
        const y = Math.min(dy1, dy2);
        const w = Math.abs(dx2 - dx1);
        const h = Math.abs(dy2 - dy1);

        const rect = document.createElementNS(NS, 'rect');
        rect.setAttribute('x', x);  rect.setAttribute('y', y);
        rect.setAttribute('width', w); rect.setAttribute('height', h);
        rect.setAttribute('fill',   cfg.color + '22');
        rect.setAttribute('stroke', cfg.color);
        rect.setAttribute('stroke-width', '2');
        if (cfg.dash) rect.setAttribute('stroke-dasharray', cfg.dash);
        rect.style.cursor = 'pointer';
        // Native browser tooltip (no occlusion of drawing content)
        const title = document.createElementNS(NS, 'title');
        title.textContent = cfg.zh;
        rect.appendChild(title);
        rect.addEventListener('contextmenu', (ev) => {
          ev.preventDefault();
          this._deleteAnnotation(ann.id);
        });
        this._svg.appendChild(rect);
      });
    }

    _deleteAnnotation(id) {
      this._annotations = this._annotations.filter((a) => a.id !== id);
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

      this._annotations.forEach((ann, i) => {
        const cfg = this._labelCfg(ann.label);
        const [[x1, y1], [x2, y2]] = ann.points;
        const item = document.createElement('div');
        item.className = 'annotate-list-item';
        item.style.borderLeftColor = cfg.color;
        item.style.background      = cfg.color + '18';
        item.innerHTML = `
          <div style="display:flex;justify-content:space-between;align-items:center">
            <span style="color:${cfg.color}">${cfg.zh} #${i + 1}</span>
            <span class="annotate-del-btn" style="color:#6b7280;cursor:pointer;font-size:11px">× 删除</span>
          </div>
          <div class="annotate-list-item-coords">
            x:${Math.round(x1)} y:${Math.round(y1)} w:${Math.round(x2-x1)} h:${Math.round(y2-y1)}
          </div>`;
        item.querySelector('.annotate-del-btn').addEventListener('click', () => {
          this._deleteAnnotation(ann.id);
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
