/* annotation-tool.js — Manual bounding-box annotation tool */
(function (global) {
  'use strict';

  const LABEL_CONFIG = {
    chamfer:       { id: 2, color: '#f59e0b', dash: null,  zh: '倒角'  },
    threaded_hole: { id: 0, color: '#6366f1', dash: '6,3', zh: '螺纹孔' },
    circle_hole:   { id: 1, color: '#10b981', dash: null,  zh: '光孔'  },
  };

  const EXTRA_COLORS = ['#ec4899', '#14b8a6', '#f97316', '#8b5cf6', '#06b6d4'];

  const NS = 'http://www.w3.org/2000/svg';

  /* ── AnnotationTool ────────────────────────────────────────────────────── */
  class AnnotationTool {
    constructor(container, apiBase) {
      this._container = container;
      this._apiBase   = apiBase;

      this._taskId     = null;
      this._imageStem  = 'page_1';
      this._allPages   = {};   // pageKey → shapes[]
      this._pageIndex  = 0;   // 0-based index into _pageUrls
      this._pageUrls   = [];  // ordered list of full image URLs

      this._annotations = [];  // current page shapes
      this._activeLabel = 'chamfer';
      this._customLabels = {};  // key → {id, color, zh}

      this._drawState = { isDrawing: false, startX: 0, startY: 0 };
      this._draftRect = null;
      this._saveTimer = null;

      this._img = null;
      this._svg = null;
    }

    /* ── Public API ─────────────────────────────────────────────────────── */

    init(taskId, previewImageUrls, baseUrl) {
      this._taskId   = taskId;
      this._baseUrl  = baseUrl || '';
      this._pageUrls = Array.isArray(previewImageUrls) ? previewImageUrls : [];
      this._pageIndex = 0;
      this._allPages  = {};

      this._renderToolbar();
      this._renderCanvas();
      this._renderList();
      this._loadFromServer();
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

    /* ── DOM construction ───────────────────────────────────────────────── */

    _renderToolbar() {
      const row = this._container.querySelector('#annotateLabelRow');
      if (!row) return;
      row.innerHTML = '';
      Object.entries(this._allLabels()).forEach(([key, cfg]) => {
        const btn = document.createElement('button');
        btn.className = 'annotate-label-btn' + (key === this._activeLabel ? ' active' : '');
        btn.textContent = '● ' + cfg.zh;
        btn.style.color        = cfg.color;
        btn.style.borderColor  = cfg.color;
        btn.style.background   = cfg.color + '18';
        btn.addEventListener('click', () => this.setActiveLabel(key));
        row.appendChild(btn);
      });
    }

    _renderCanvas() {
      this._img = this._container.querySelector('#annotateImage');
      this._svg = this._container.querySelector('#annotateSvg');
      if (!this._img || !this._svg) return;

      this._loadPage(this._pageIndex);

      // ── SVG mouse events ──────────────────────────────────────────────
      this._svg.addEventListener('mousedown', (e) => this._onMouseDown(e));
      this._svg.addEventListener('mousemove', (e) => this._onMouseMove(e));
      this._svg.addEventListener('mouseup',   (e) => this._onMouseUp(e));
      this._svg.addEventListener('mouseleave',(e) => {
        if (this._drawState.isDrawing) this._onMouseUp(e);
      });
      this._svg.addEventListener('contextmenu', (e) => e.preventDefault());

      // ── Page nav buttons ──────────────────────────────────────────────
      const prev = this._container.querySelector('#annotatePagePrev');
      const next = this._container.querySelector('#annotatePageNext');
      if (prev) prev.addEventListener('click', () => this._goPage(this._pageIndex - 1));
      if (next) next.addEventListener('click', () => this._goPage(this._pageIndex + 1));

      // ── Export button ─────────────────────────────────────────────────
      const exp = this._container.querySelector('#annotateExportBtn');
      if (exp) exp.addEventListener('click', () => this._exportZip());

      // ── Add type button ───────────────────────────────────────────────
      const add = this._container.querySelector('#annotateAddTypeBtn');
      if (add) add.addEventListener('click', () => {
        const zh = prompt('新标签名称（中文）：');
        if (zh && zh.trim()) this.addCustomLabel(zh.trim());
      });
    }

    _loadPage(idx) {
      if (idx < 0 || (this._pageUrls.length > 0 && idx >= this._pageUrls.length)) return;
      this._pageIndex = idx;

      // persist current page annotations
      this._allPages[this._pageKey()] = this._annotations.slice();

      this._annotations = this._allPages[this._pageKey()] || [];

      const url = this._pageUrls[idx] ? this._baseUrl + this._pageUrls[idx] : '';
      if (this._img) {
        this._img.onload = () => { this.renderAll(); this._renderList(); };
        this._img.src = url || '';
      }
      this._renderPageCounter();
    }

    _goPage(idx) {
      this._autoSaveNow();
      this._loadPage(idx);
    }

    _pageKey() {
      return String(this._pageIndex + 1);
    }

    _renderPageCounter() {
      const el = this._container.querySelector('#annotatePageCounter');
      if (!el) return;
      const total = this._pageUrls.length || 1;
      el.textContent = `页 ${this._pageIndex + 1} / ${total}`;
    }

    /* ── Scale helpers ──────────────────────────────────────────────────── */

    _scaleX() {
      if (!this._img || !this._img.naturalWidth) return 1;
      const rect = this._img.getBoundingClientRect();
      const rendered = this._img.offsetWidth || rect.width;
      // account for object-fit: contain letterboxing
      const scale = rendered / this._img.naturalWidth;
      const scaledH = this._img.naturalHeight * scale;
      const containerH = this._img.offsetHeight || rect.height;
      this._offsetX = 0;
      this._offsetY = Math.max(0, (containerH - scaledH) / 2);
      return scale;
    }

    _scaleY() {
      if (!this._img || !this._img.naturalHeight) return 1;
      const rect = this._img.getBoundingClientRect();
      const rendered = this._img.offsetWidth || rect.width;
      return (rendered / this._img.naturalWidth);
    }

    _toReal(displayX, displayY) {
      const sx = this._scaleX();
      const ox = this._offsetX || 0;
      const oy = this._offsetY || 0;
      return [(displayX - ox) / sx, (displayY - oy) / sx];
    }

    _toDisplay(realX, realY) {
      const sx = this._scaleX();
      const ox = this._offsetX || 0;
      const oy = this._offsetY || 0;
      return [realX * sx + ox, realY * sx + oy];
    }

    /* ── Drawing ────────────────────────────────────────────────────────── */

    _onMouseDown(e) {
      if (e.button !== 0) return;
      const svgRect = this._svg.getBoundingClientRect();
      this._drawState = {
        isDrawing: true,
        startX: e.clientX - svgRect.left,
        startY: e.clientY - svgRect.top,
      };
      this._draftRect = document.createElementNS(NS, 'rect');
      const cfg = this._labelCfg(this._activeLabel);
      this._draftRect.setAttribute('fill', cfg.color + '22');
      this._draftRect.setAttribute('stroke', cfg.color);
      this._draftRect.setAttribute('stroke-width', '2');
      if (cfg.dash) this._draftRect.setAttribute('stroke-dasharray', cfg.dash);
      this._draftRect.setAttribute('pointer-events', 'none');
      this._svg.appendChild(this._draftRect);
    }

    _onMouseMove(e) {
      if (!this._drawState.isDrawing || !this._draftRect) return;
      const svgRect = this._svg.getBoundingClientRect();
      const curX = e.clientX - svgRect.left;
      const curY = e.clientY - svgRect.top;
      const { startX, startY } = this._drawState;
      this._draftRect.setAttribute('x',      Math.min(startX, curX));
      this._draftRect.setAttribute('y',      Math.min(startY, curY));
      this._draftRect.setAttribute('width',  Math.abs(curX - startX));
      this._draftRect.setAttribute('height', Math.abs(curY - startY));
    }

    _onMouseUp(e) {
      if (!this._drawState.isDrawing) return;
      this._drawState.isDrawing = false;

      const svgRect = this._svg.getBoundingClientRect();
      const endX = e.clientX - svgRect.left;
      const endY = e.clientY - svgRect.top;
      const { startX, startY } = this._drawState;

      if (this._draftRect) {
        this._svg.removeChild(this._draftRect);
        this._draftRect = null;
      }

      // Ignore tiny accidental clicks
      if (Math.abs(endX - startX) < 6 || Math.abs(endY - startY) < 6) return;

      const [rx1, ry1] = this._toReal(Math.min(startX, endX), Math.min(startY, endY));
      const [rx2, ry2] = this._toReal(Math.max(startX, endX), Math.max(startY, endY));

      this._annotations.push({
        id:     Date.now(),
        label:  this._activeLabel,
        points: [[rx1, ry1], [rx2, ry2]],
      });

      this.renderAll();
      this._renderList();
      this._scheduleSave();
    }

    /* ── Render all annotations ─────────────────────────────────────────── */

    renderAll() {
      if (!this._svg) return;
      this._svg.innerHTML = '';

      this._annotations.forEach((ann) => {
        const cfg = this._labelCfg(ann.label);
        const [dx1, dy1] = this._toDisplay(ann.points[0][0], ann.points[0][1]);
        const [dx2, dy2] = this._toDisplay(ann.points[1][0], ann.points[1][1]);
        const x = Math.min(dx1, dx2);
        const y = Math.min(dy1, dy2);
        const w = Math.abs(dx2 - dx1);
        const h = Math.abs(dy2 - dy1);

        // Box
        const rect = document.createElementNS(NS, 'rect');
        rect.setAttribute('x',      x);
        rect.setAttribute('y',      y);
        rect.setAttribute('width',  w);
        rect.setAttribute('height', h);
        rect.setAttribute('fill',   cfg.color + '22');
        rect.setAttribute('stroke', cfg.color);
        rect.setAttribute('stroke-width', '2');
        if (cfg.dash) rect.setAttribute('stroke-dasharray', cfg.dash);
        rect.style.cursor = 'pointer';
        rect.addEventListener('contextmenu', (e) => {
          e.preventDefault();
          this._deleteAnnotation(ann.id);
        });
        this._svg.appendChild(rect);

        // Label text
        const txt = document.createElementNS(NS, 'text');
        txt.setAttribute('x', x + 2);
        txt.setAttribute('y', Math.max(y - 4, 12));
        txt.setAttribute('fill', cfg.color);
        txt.setAttribute('font-size', '11');
        txt.setAttribute('font-family', 'sans-serif');
        txt.setAttribute('pointer-events', 'none');
        txt.textContent = cfg.zh;
        this._svg.appendChild(txt);
      });
    }

    _deleteAnnotation(id) {
      this._annotations = this._annotations.filter((a) => a.id !== id);
      this.renderAll();
      this._renderList();
      this._scheduleSave();
    }

    /* ── Right panel list ───────────────────────────────────────────────── */

    _renderList() {
      const body = this._container.querySelector('#annotateListBody');
      const count = this._container.querySelector('#annotateCount');
      if (!body) return;

      if (count) count.textContent = `(${this._annotations.length})`;

      body.innerHTML = '';
      this._annotations.forEach((ann, i) => {
        const cfg = this._labelCfg(ann.label);
        const [[x1, y1], [x2, y2]] = ann.points;

        const item = document.createElement('div');
        item.className = 'annotate-list-item';
        item.style.borderLeftColor = cfg.color;
        item.style.background = cfg.color + '18';
        item.innerHTML = `
          <div style="display:flex;justify-content:space-between;align-items:center">
            <span style="color:${cfg.color}">${cfg.zh} #${i + 1}</span>
            <span class="annotate-del-btn" style="color:#6b7280;cursor:pointer;font-size:11px">× 删除</span>
          </div>
          <div class="annotate-list-item-coords">
            x:${Math.round(x1)} y:${Math.round(y1)} w:${Math.round(x2 - x1)} h:${Math.round(y2 - y1)}
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
      if (!this._taskId || !this._img) return;
      const imgSrc = this._img.src || '';
      const imgFilename = imgSrc.split('/').pop().split('?')[0] || 'page_1.png';

      const payload = {
        page:        this._pageIndex + 1,
        shapes:      this._annotations.map((a) => ({ label: a.label, points: a.points })),
        imageWidth:  this._img.naturalWidth  || 0,
        imageHeight: this._img.naturalHeight || 0,
        imagePath:   imgFilename,
      };

      fetch(`${this._apiBase}/annotations/${this._taskId}/save`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(payload),
      }).catch((err) => console.warn('[annotation-tool] save failed:', err));
    }

    _loadFromServer() {
      if (!this._taskId) return;
      fetch(`${this._apiBase}/annotations/${this._taskId}`)
        .then((r) => r.json())
        .then((data) => {
          if (!data.pages) return;
          Object.entries(data.pages).forEach(([pageN, labelme]) => {
            const shapes = (labelme.shapes || []).map((s) => ({
              id:     Date.now() + Math.random(),
              label:  s.label,
              points: s.points,
            }));
            this._allPages[pageN] = shapes;
          });
          // Load current page shapes
          this._annotations = this._allPages[this._pageKey()] || [];
          this.renderAll();
          this._renderList();
        })
        .catch(() => {});
    }

    _exportZip() {
      if (!this._taskId) return;
      this._autoSaveNow();
      // short delay to let save complete before export
      setTimeout(() => {
        const a = document.createElement('a');
        a.href = `${this._apiBase}/annotations/${this._taskId}/export`;
        a.download = `annotations_${this._taskId}.zip`;
        document.body.appendChild(a);
        a.click();
        setTimeout(() => document.body.removeChild(a), 1000);
      }, 600);
    }
  }

  global.AnnotationTool = AnnotationTool;
})(window);
