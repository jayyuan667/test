
    // ── Toast 通知系统 ──
    let _toastStack = null;
    function ensureToastStack() {
      if (!_toastStack || !document.contains(_toastStack)) {
        _toastStack = document.createElement('div');
        _toastStack.className = 'toast-stack';
        document.body.appendChild(_toastStack);
      }
      return _toastStack;
    }
    function showToast(message, type) {
      var stack = ensureToastStack();
      var el = document.createElement('div');
      el.className = 'toast-item toast-' + (type || 'error');
      el.textContent = message;
      stack.appendChild(el);
      el.addEventListener('animationend', function(e) {
        if (e.animationName === 'toast-out') { el.remove(); }
      });
    }

    const navItems = [...document.querySelectorAll('.nav-item')];
    const topTabs = [...document.querySelectorAll('.top-tab')];
    const pages = [...document.querySelectorAll('.page')];
    const resultTabs = [...document.querySelectorAll('.result-tab')];
    const resultViews = [...document.querySelectorAll('.result-view')];

    const workflowPhaseHint = document.getElementById('workflowPhaseHint');
    const workflowPercent = document.getElementById('workflowPercent');
    const workflowProgressBar = document.getElementById('workflowProgressBar');
    const workflowThinkingLine = workflowPhaseHint;
    const processEmpty = document.getElementById('processEmpty');
    const processResult = document.getElementById('processResult');
    const stageCards = [...document.querySelectorAll('.stage-card')];
    const workflowHudCard = document.getElementById('workflowHudCard');
    const workflowHudToggleBtn = document.getElementById('workflowHudToggleBtn');
    const uploadPanelBody = document.getElementById('uploadPanelBody');
    const workbench = document.getElementById('workbench');
    const demoResizer = document.getElementById('demoResizer');
    const reviewModal = document.getElementById('reviewModal');
    const closeReviewModal = document.getElementById('closeReviewModal');
    const reviewStayBtn = document.getElementById('reviewStayBtn');
    const reviewConfirmBtn = document.getElementById('reviewConfirmBtn');
    const reviewTableHost = document.getElementById('reviewTableHost');
    const reviewTextarea = document.getElementById('reviewTextarea');
    const reviewSourceNote = document.getElementById('reviewSourceNote');
    const reviewStatusBadge = document.getElementById('reviewStatusBadge');
    const reviewStepLabel = document.getElementById('reviewStepLabel');
    const reviewContinueBtn = document.getElementById('reviewContinueBtn');
    const reviewRerunBtn = document.getElementById('reviewRerunBtn');
    const retrievalLibraryBtn = document.getElementById('retrievalLibraryBtn');
    const featureCacheToggleBtn = document.getElementById('featureCacheToggleBtn');
    const retrievalLibraryModal = document.getElementById('retrievalLibraryModal');
    const closeRetrievalLibraryModalBtn = document.getElementById('closeRetrievalLibraryModal');
    const cancelRetrievalLibraryBtn = document.getElementById('cancelRetrievalLibraryBtn');
    const confirmRetrievalLibraryBtn = document.getElementById('confirmRetrievalLibraryBtn');
    const retrievalLibrarySelect = document.getElementById('retrievalLibrarySelect');
    const retrievalLibraryInfo = document.getElementById('retrievalLibraryInfo');
    const editorShell = document.getElementById('editorShell');
    const editorTextarea = document.getElementById('editorTextarea');
    const editorPreview = document.getElementById('editorPreview');
    const historyRefreshBtn = document.getElementById('historyRefreshBtn');
    const historyCompletedDateInput = document.getElementById('historyCompletedDateInput');
    const historyClearFilterBtn = document.getElementById('historyClearFilterBtn');
    const historyTableBody = document.getElementById('historyTableBody');
    const historyTableMeta = document.getElementById('historyTableMeta');
    const historyRecordCount = document.getElementById('historyRecordCount');
    const historyPageIndicator = document.getElementById('historyPageIndicator');
    const historyTotalValue = document.getElementById('historyTotalValue');
    const historyDoneValue = document.getElementById('historyDoneValue');
    const historyReviewValue = document.getElementById('historyReviewValue');
    const historyStepValue = document.getElementById('historyStepValue');
    const historyPrevBtn = document.getElementById('historyPrevBtn');
    const historyNextBtn = document.getElementById('historyNextBtn');
    const historySnapshotModal = document.getElementById('historySnapshotModal');
    const closeHistorySnapshotModal = document.getElementById('closeHistorySnapshotModal');
    const historySnapshotTitle = document.getElementById('historySnapshotTitle');
    const historySnapshotMeta = document.getElementById('historySnapshotMeta');
    const historySnapshotSource = document.getElementById('historySnapshotSource');
    const historySnapshotImage = document.getElementById('historySnapshotImage');
    const historySnapshotEmpty = document.getElementById('historySnapshotEmpty');
    const historySnapshotCounter = document.getElementById('historySnapshotCounter');
    const historySnapshotZoomLabel = document.getElementById('historySnapshotZoomLabel');
    const historySnapshotPrevBtn = document.getElementById('historySnapshotPrevBtn');
    const historySnapshotNextBtn = document.getElementById('historySnapshotNextBtn');
    const historySnapshotZoomOutBtn = document.getElementById('historySnapshotZoomOutBtn');
    const historySnapshotZoomInBtn = document.getElementById('historySnapshotZoomInBtn');
    const historySnapshotResetBtn = document.getElementById('historySnapshotResetBtn');
    const historyBatchDeleteBtn = document.getElementById('historyBatchDeleteBtn');
    const historySelectAll = document.getElementById('historySelectAll');
    const historySnapshotReview = document.getElementById('historySnapshotReview');
    const historySnapshotProcess = document.getElementById('historySnapshotProcess');
    let taskPreviewImage = document.getElementById('taskPreviewImage');
    let taskPreviewEmpty = document.getElementById('taskPreviewEmpty');
    let taskPreviewCounter = document.getElementById('taskPreviewCounter');
    let taskPreviewZoomLabel = document.getElementById('taskPreviewZoomLabel');
    let taskPreviewFullscreenImage = document.getElementById('taskPreviewFullscreenImage');
    let taskPreviewFullscreenCounter = document.getElementById('taskPreviewFullscreenCounter');
    let taskPreviewFullscreenPrevBtn = document.getElementById('taskPreviewFullscreenPrevBtn');
    let taskPreviewFullscreenNextBtn = document.getElementById('taskPreviewFullscreenNextBtn');
    const taskPreviewPrevBtn = document.getElementById('taskPreviewPrevBtn');
    const taskPreviewNextBtn = document.getElementById('taskPreviewNextBtn');
    const taskPreviewZoomOutBtn = document.getElementById('taskPreviewZoomOutBtn');
    const taskPreviewZoomInBtn = document.getElementById('taskPreviewZoomInBtn');
    const taskPreviewResetBtn = document.getElementById('taskPreviewResetBtn');
    const taskPreviewFullscreenBtn = document.getElementById('taskPreviewFullscreenBtn');

    function setDemoStatusText() {}
    function setDemoHitText() {}
    function setDemoStepText() {}
    function setDemoResultChipText() {}

    function setWorkflowThinkingLine(value) {
      if (workflowThinkingLine) workflowThinkingLine.textContent = String(value || '').trim() || '等待任务启动';
    }

    function sanitizeLiveLogText(value) {
      const text = String(value || '').replace(/^\s*\[(?:[A-Za-z0-9-]+)\]\s*/g, '');
      return text.replace(/^step\s*\d+\s*:\s*/i, '').trim();
    }

    function formatWorkflowThinkingText(tag, text) {
      const clean = sanitizeLiveLogText(text);
      if (!clean) return '等待工艺生成';

      const codeMatch = clean.match(/^(\d{4})/);
      const code = codeMatch ? codeMatch[1] : '';

      if (code) {
        return `工艺路线组合中，正在输出第 ${code} 道工序`;
      }
      if (/视觉分析|图纸|模型|特征/.test(clean)) {
        return `正在分析模型视图特征，准备生成工艺路线：${clean}`;
      }
      if (/专家判断|RAG|检索|候选/.test(clean)) {
        return `工艺路线正在组合与渲染：${clean}`;
      }
      if (/生成完成|保存|完成/.test(clean)) {
        return `工艺路线渲染接近完成：${clean}`;
      }
      if (/review/i.test(tag || '')) {
        return `特征已确认，后端正在继续生成工艺规程，请稍候。`;
      }
      if (/zip|知识库|导入|入库|解析|上传/.test(`${tag || ''} ${clean}`)) {
        if (/上传/.test(clean)) return `正在上传知识库压缩包，准备解析工艺库...`;
        if (/解析/.test(clean)) return `正在解析知识库内容，整理可入库记录...`;
        if (/入库/.test(clean)) return `知识库入库处理中，正在写入并校验数据...`;
        if (/完成/.test(clean)) return `知识库导入完成，正在更新可检索状态...`;
        return `知识库处理进行中：${clean}`;
      }
      return clean;
    }

    function renderWorkflowLiveStream() {}

    function resetWorkflowLiveConsole() {
      backendState.workflowLiveEntries = [];
      setWorkflowThinkingLine('等待任务启动');
    }

    function appendWorkflowLiveEntry(tag, text, tone = 'normal') {
      const cleanText = sanitizeLiveLogText(text);
      if (!cleanText) return;
      backendState.workflowLiveEntries.push({ tag: tag || 'LOG', text: cleanText, tone });
      renderWorkflowLiveStream();
      setWorkflowThinkingLine(formatWorkflowThinkingText(tag, cleanText));
    }

    function setTextIfChanged(node, nextValue) {
      if (!node) return;
      const next = String(nextValue ?? '');
      if (node.textContent !== next) node.textContent = next;
    }

    function setDisabledIfChanged(node, disabled) {
      if (!node) return;
      const next = !!disabled;
      if (node.disabled !== next) node.disabled = next;
    }

    function refreshTaskPreviewFullscreenRefs() {
      taskPreviewFullscreenImage = document.getElementById('taskPreviewFullscreenImage');
      taskPreviewFullscreenCounter = document.getElementById('taskPreviewFullscreenCounter');
      taskPreviewFullscreenPrevBtn = document.getElementById('taskPreviewFullscreenPrevBtn');
      taskPreviewFullscreenNextBtn = document.getElementById('taskPreviewFullscreenNextBtn');
    }

    function refreshTaskPreviewRefs() {
      taskPreviewImage = document.getElementById('taskPreviewImage');
      taskPreviewEmpty = document.getElementById('taskPreviewEmpty');
      taskPreviewCounter = document.getElementById('taskPreviewCounter');
      taskPreviewZoomLabel = document.getElementById('taskPreviewZoomLabel');
    }

    function getOpenExportCardBtn() {
      return document.getElementById('openExportCardBtn');
    }
    const taskDetailTitle = document.getElementById('taskDetailTitle');
    const taskDetailMeta = document.getElementById('taskDetailMeta');
    const taskDetailStatus = document.getElementById('taskDetailStatus');
    const taskFieldStage = document.getElementById('taskFieldStage');
    const taskFieldHit = document.getElementById('taskFieldHit');
    const taskFieldFeature = document.getElementById('taskFieldFeature');
    const taskFieldCount = document.getElementById('taskFieldCount');
    const taskProcessSummaryList = document.getElementById('taskProcessSummaryList');
    const zipTabs = [...document.querySelectorAll('[data-zip-view]')];
    const zipViews = [...document.querySelectorAll('#page-zip .browser-view')];
    const uploadGenerateBtn = document.getElementById('uploadGenerateBtn');
    const resetGenerateBtn = document.getElementById('resetGenerateBtn');
    const zipRunBtn = document.getElementById('zipRunBtn');
    const sampleZipDownloadBtn = document.getElementById('sampleZipDownloadBtn');
    const zipResetBtn = document.getElementById('zipResetBtn');
    const sidebarToggleBtn = document.getElementById('sidebarToggleBtn');
    const zipBatchChip = document.getElementById('zipBatchChip');
    const zipResultChip = document.getElementById('zipResultChip');
    const zipMatchedEmpty = document.getElementById('zipMatchedEmpty');
    const zipMatchedCard = document.getElementById('zipMatchedCard');
    const zipMatchedPager = document.getElementById('zipMatchedPager');
    const zipMatchedPageIndicator = document.getElementById('zipMatchedPageIndicator');
    const zipMatchedPrevBtn = document.getElementById('zipMatchedPrevBtn');
    const zipMatchedNextBtn = document.getElementById('zipMatchedNextBtn');
    const zipLogList = document.getElementById('zipLogList');
    const zipTotalFiles = document.getElementById('zipTotalFiles');
    const zipMatchedCount = document.getElementById('zipMatchedCount');
    const zipUnmatchedCount = document.getElementById('zipUnmatchedCount');
    const zipErrorCount = document.getElementById('zipErrorCount');
    const zipImportStatus = document.getElementById('zipImportStatus');
    const zipUnmatchedPageIndicator = document.getElementById('zipUnmatchedPageIndicator');
    const zipUnmatchedPrevBtn = document.getElementById('zipUnmatchedPrevBtn');
    const zipUnmatchedNextBtn = document.getElementById('zipUnmatchedNextBtn');
    const zipConflictModeBtn = document.getElementById('zipConflictModeBtn');
    const zipLibraryList = document.getElementById('zipLibraryList');
    const zipNewLibraryForm = document.getElementById('zipNewLibraryForm');
    const zipSeedPublicCheckbox = document.getElementById('zipSeedPublicCheckbox');
    const zipLibraryNameInput = document.getElementById('zipLibraryNameInput');
    const zipActiveLibraryChip = document.getElementById('zipActiveLibraryChip');
    const zipPanelLibLabel = document.getElementById('zipPanelLibLabel');
    const dbLockedState = document.getElementById('dbLockedState');
    const dbReadyState = document.getElementById('dbReadyState');
    const goZipFromLockBtn = document.getElementById('goZipFromLockBtn');
    const dbSearchInput = document.getElementById('dbSearchInput');
    const dbTypeSelect = document.getElementById('dbTypeSelect');
    const dbSourceSelect = document.getElementById('dbSourceSelect');
    const dbStatusSelect = document.getElementById('dbStatusSelect');
    const dbPageSizeSelect = document.getElementById('dbPageSizeSelect');
    const dbApplyBtn = document.getElementById('dbApplyBtn');
    const dbResetBtn = document.getElementById('dbResetBtn');
    const dbResetFiltersBtn = document.getElementById('dbResetFiltersBtn');
    const dbRefreshBtn = document.getElementById('dbRefreshBtn');
    const dbPrevBtn = document.getElementById('dbPrevBtn');
    const dbNextBtn = document.getElementById('dbNextBtn');
    const dbRecordList = document.getElementById('dbRecordList');
    const dbListMeta = document.getElementById('dbListMeta');
    const dbRecordCount = document.getElementById('dbRecordCount');
    const dbPageIndicator = document.getElementById('dbPageIndicator');
    const dbPageSummary = document.getElementById('dbPageSummary');
    const dbLibrarySelect = document.getElementById('dbLibrarySelect');
    const dbTotalValue = document.getElementById('dbTotalValue');
    const dbVisibleValue = document.getElementById('dbVisibleValue');
    const dbEditValue = document.getElementById('dbEditValue');
    const dbDetailPrefixChip = document.getElementById('dbDetailPrefixChip');
    const dbDetailSourceChip = document.getElementById('dbDetailSourceChip');
    const dbDetailTypeChip = document.getElementById('dbDetailTypeChip');
    const dbDetailStateChip = document.getElementById('dbDetailStateChip');
    const dbDetailImageSummary = document.getElementById('dbDetailImageSummary');
    const dbOpenImageSnapshotBtn = document.getElementById('dbOpenImageSnapshotBtn');
    const dbPreviewModal = document.getElementById('dbPreviewModal');
    const closeDbPreviewModal = document.getElementById('closeDbPreviewModal');
    const dbPreviewTitle = document.getElementById('dbPreviewTitle');
    const dbPreviewMeta = document.getElementById('dbPreviewMeta');
    const dbPreviewSource = document.getElementById('dbPreviewSource');
    const dbPreviewImage = document.getElementById('dbPreviewImage');
    const dbPreview3DContainer = document.getElementById('dbPreview3DContainer');
    const dbPreviewEmpty = document.getElementById('dbPreviewEmpty');
    const dbPreviewCounter = document.getElementById('dbPreviewCounter');
    const dbPreviewFeature = document.getElementById('dbPreviewFeature');
    const dbPreviewProcess = document.getElementById('dbPreviewProcess');
    const dbPreviewPrevBtn = document.getElementById('dbPreviewPrevBtn');
    const dbPreviewNextBtn = document.getElementById('dbPreviewNextBtn');
    const dbPreviewZoomOutBtn = document.getElementById('dbPreviewZoomOutBtn');
    const dbPreviewZoomInBtn = document.getElementById('dbPreviewZoomInBtn');
    const dbPreviewResetBtn = document.getElementById('dbPreviewResetBtn');
    const dbPreviewZoomLabel = document.getElementById('dbPreviewZoomLabel');
    const dbEditorShell = document.getElementById('dbEditorShell');
    const dbEditorPreview = document.getElementById('dbEditorPreview');
    const dbEditorProductType = document.getElementById('dbEditorProductType');
    const dbEditorContent = document.getElementById('dbEditorContent');
    const dbEditorFeaturePageText = document.getElementById('dbEditorFeaturePageText');
    const dbFeaturePrevBtn = document.getElementById('dbFeaturePrevBtn');
    const dbFeatureNextBtn = document.getElementById('dbFeatureNextBtn');
    const dbFeaturePageIndicator = document.getElementById('dbFeaturePageIndicator');
    const dbFeaturePageMeta = document.getElementById('dbFeaturePageMeta');
    const dbFeaturePageFields = document.getElementById('dbFeaturePageFields');
    const dbEditBtn = document.getElementById('dbEditBtn');
    const dbDeleteBtn = document.getElementById('dbDeleteBtn');
    const dbSaveBtn = document.getElementById('dbSaveBtn');
    const dbCancelBtn = document.getElementById('dbCancelBtn');
    const dbDetailTitle = document.getElementById('dbDetailTitle');
    const dbDetailMeta = document.getElementById('dbDetailMeta');
    const dbDetailStatus = document.getElementById('dbDetailStatus');
    const dbDetailType = document.getElementById('dbDetailType');
    const dbDetailRequirement = document.getElementById('dbDetailRequirement');
    const dbDetailRisk = document.getElementById('dbDetailRisk');
    const dbDeleteModal = document.getElementById('dbDeleteModal');
    const dbDeleteInfo = document.getElementById('dbDeleteInfo');
    const closeDbDeleteModalBtn = document.getElementById('closeDbDeleteModal');
    const cancelDbDeleteBtn = document.getElementById('cancelDbDeleteBtn');
    const confirmDbDeleteBtn = document.getElementById('confirmDbDeleteBtn');
    const dbDeleteLibraryBtn = document.getElementById('dbDeleteLibraryBtn');
    const dbDeleteLibraryModal = document.getElementById('dbDeleteLibraryModal');
    const dbDeleteLibraryInfo = document.getElementById('dbDeleteLibraryInfo');
    const closeDbDeleteLibraryModalBtn = document.getElementById('closeDbDeleteLibraryModal');
    const cancelDbDeleteLibraryBtn = document.getElementById('cancelDbDeleteLibraryBtn');
    const confirmDbDeleteLibraryBtn = document.getElementById('confirmDbDeleteLibraryBtn');
    const viewPublicDbFromLockBtn = document.getElementById('viewPublicDbFromLockBtn');
    const viewMyDbFromLockBtn = document.getElementById('viewMyDbFromLockBtn');
    const dbBrowseBanner = document.getElementById('dbBrowseBanner');
    const dbUnlockHintBtn = document.getElementById('dbUnlockHintBtn');
    const zipImportHud = document.getElementById('zipImportHud');
    const zipImportPhase = document.getElementById('zipImportPhase');
    const zipImportPercent = document.getElementById('zipImportPercent');
    const zipProgressBar = document.getElementById('zipProgressBar');
    const exportModal = document.getElementById('exportModal');
    const exportModalCloseBtn = document.getElementById('exportModalCloseBtn');
    const exportCancelBtn = document.getElementById('exportCancelBtn');
    const exportPdfBtn = document.getElementById('exportPdfBtn');
    const exportExcelBtn = document.getElementById('exportExcelBtn');
    const exportModalImage = document.getElementById('exportModalImage');
    const exportModalImagePlaceholder = document.getElementById('exportModalImagePlaceholder');
    const exportModalInfo = document.getElementById('exportModalInfo');
    const exportModalTable = document.getElementById('exportModalTable');
    const exportModalMeta = document.getElementById('exportModalMeta');
    let libraryReady = false;
    let dbDetailPreviewRequestToken = 0;
    let dbPreviewZoom = 1;
    const historyViewer = make3DViewer();
    const dbViewer = make3DViewer();

    const initialUploadPanelHTML = uploadPanelBody?.innerHTML || '';
    const initialProcessPanelHTML = processResult?.innerHTML || '';
    const initialEditorHTML = editorTextarea?.value || '';
    const SIDEBAR_COLLAPSED_STORAGE_KEY = 'industrial_console_sidebar_collapsed';

    const pageLabels = {
      'page-generate': '工艺生成',
      'page-list': '工艺清单',
      'page-db': '数据库浏览',
      'page-zip': '工艺入库',
    };

    const taskData = {
      spindle: {
        title: '1F16800 主轴',
        meta: '模型编号：1F16800 · 当前版本：v2.3 · 最近更新：2026-04-30 09:28',
        status: '已完成',
        statusClass: 'success',
        stage: '工艺生成已完成，可进入审阅与导出。',
        hit: '命中历史工艺 3 条，主候选为 1F16800。',
        feature: '主轴类、阶梯内孔、R5 过渡、调质处理。',
        count: '共 5 条推荐工序，支持在线编辑。',
      },
      housing: {
        title: 'D125A-181200A003 箱体',
        meta: '模型编号：D125A-181200A003 · 当前版本：v1.7 · 最近更新：2026-04-29 16:12',
        status: '待校审',
        statusClass: 'warn',
        stage: '已完成特征提取，等待人工确认技术要求。',
        hit: '命中箱体类工艺 2 条，建议保留旧版基线。',
        feature: '箱体类、多个安装面、内腔加工、孔系精度要求高。',
        count: '当前生成 7 条工序，待特征审阅后可重新计算。',
      },
      bracket: {
        title: 'GJ-2024-001 支架',
        meta: '模型编号：GJ-2024-001 · 当前版本：v0.9 · 最近更新：2026-04-30 10:41',
        status: '生成中',
        statusClass: 'warn',
        stage: '已进入工艺生成阶段，等待规则整合与路线输出。',
        hit: '命中支架类工艺 1 条，正在补齐孔系加工路线。',
        feature: '支架类、孔位密集、平面加工优先、局部倒角。',
        count: '预计输出 4~6 条工序。',
      },
      flange: {
        title: 'QZ-07-441 法兰盘',
        meta: '模型编号：QZ-07-441 · 当前版本：v0.1 · 最近更新：未开始',
        status: '待上传',
        statusClass: 'danger',
        stage: '尚未接收文件，无法进入解析链路。',
        hit: '无命中记录，待上传后开始检索。',
        feature: '暂无结构化特征。',
        count: '尚未生成工序。',
      },
    };

    const dbRecords = {
      box: {
        title: 'D125A-181200A003',
        meta: '来源：ZIP 入库 · 最近更新：2026-04-30 10:12 · 更新人：工艺工程师',
        status: '待复核',
        statusClass: 'warn',
        type: '箱体类',
        source: 'ZIP 入库',
        processCount: 7,
        summary: '新增热处理要求，工序调整为 7 条。',
        requirement: '箱体内腔需防腐处理，关键孔位复核位置度。',
        risk: '删除后会影响后续同类模型的 RAG 命中结果。',
        tags: ['热处理', '防腐', '孔位复核'],
        content: '0010@料@备料：δ30×250×173=1。\n0020@铣@铣方六面，单边留量0.5。\n0030@钳@划线，钻底孔M10×1.5。\n0040@镗@镗孔Φ40H7，精镗至尺寸。\n0050@铣@铣槽，宽12深8，保证对称度0.05。\n0060@钳@攻丝M10×1.5，去毛刺。\n0070@热@热处理：调质HB240-280，内腔防腐。',
        processList: ['0010@料@备料：δ30×250×173=1。', '0020@铣@铣方六面，单边留量0.5。', '0030@钳@划线，钻底孔M10×1.5。', '0040@镗@镗孔Φ40H7，精镗至尺寸。', '0050@铣@铣槽，宽12深8，保证对称度0.05。', '0060@钳@攻丝M10×1.5，去毛刺。', '0070@热@热处理：调质HB240-280，内腔防腐。'],
      },
      shaft: {
        title: '1F16800',
        meta: '来源：手工修订 · 最近更新：2026-04-29 17:40 · 更新人：系统管理员',
        status: '可用',
        statusClass: 'success',
        type: '轴类',
        source: '手工修订',
        processCount: 5,
        summary: '主轴工艺已稳定，适合作为候选基线复用。',
        requirement: '关键配合段保留调质与磁粉探伤要求。',
        risk: '删除后会降低轴类模型首次命中质量。',
        tags: ['基线', '磁粉探伤', '调质'],
        content: '0010@料@备料：Φ60×355=1，材质40Cr。\n0020@车@粗车外圆，各段留量1.5。\n0030@热@调质HB250-290。\n0040@磨@精磨配合段Φ50g6、Φ40h7至尺寸。\n0050@检@磁粉探伤，检查表面裂纹。',
        processList: ['0010@料@备料：Φ60×355=1，材质40Cr。', '0020@车@粗车外圆，各段留量1.5。', '0030@热@调质HB250-290。', '0040@磨@精磨配合段Φ50g6、Φ40h7至尺寸。', '0050@检@磁粉探伤，检查表面裂纹。'],
      },
      support: {
        title: 'GJ-2024-001',
        meta: '来源：ZIP 入库 · 最近更新：2026-04-30 10:12 · 更新人：工艺工程师',
        status: '草稿',
        statusClass: 'danger',
        type: '支架类',
        source: 'ZIP 入库',
        processCount: 4,
        summary: '孔位密集，当前工艺仍需人工确认夹持方案。',
        requirement: '建议补充钻模定位与孔群精度控制说明。',
        risk: '直接用于分析可能引入错误工艺路线。',
        tags: ['夹持方案', '孔系', '待确认'],
        content: '0010@料@备料：δ10×80×120=1，材质Q235A。\n0020@钳@划线，钻模定位钻底孔。\n0030@铣@铣平面，保证孔群位置度Φ0.2。\n0040@钳@攻丝M8，去毛刺，检查夹持变形。',
        processList: ['0010@料@备料：δ10×80×120=1，材质Q235A。', '0020@钳@划线，钻模定位钻底孔。', '0030@铣@铣平面，保证孔群位置度Φ0.2。', '0040@钳@攻丝M8，去毛刺，检查夹持变形。'],
      },
    };

    const dbOrder = ['box', 'shaft', 'support'];
    const dbState = {
      selectedKey: 'box',
      page: 1,
      pageSize: 3,
      query: '',
      type: '全部',
      source: '全部来源',
      status: '全部状态',
      deleteKey: null,
      removed: new Set(),
    };

    const API_BASE = window.__API_BASE__ || 'http://localhost:5090/api';
    const ZIP_UNLOCK_SESSION_KEY = 'industrial_console_zip_unlocked';
    const ZIP_SCOPE_SESSION_KEY = 'industrial_console_active_scope';
    const RETRIEVAL_SCOPE_SESSION_KEY = 'industrial_console_retrieval_scope';
    const backendState = {
      history: [],
      records: [],
      taskMap: {},
      latestTaskId: '',
      latestResult: null,
      latestZipReport: null,
      zipBrowserState: {
        matchedPage: 1,
        unmatchedPage: 1,
      },
      latestReviewPayload: null,
      currentReviewTaskId: '',
      currentProcessTaskId: '',
      activeLibraryKey: 'public',
      activeLibraryName: '公共工艺库',
      retrievalLibraryKey: 'public',
      retrievalLibraryName: '公共工艺库',
      libraryScopes: [],
      canBrowseDb: false,
      dbBrowseOnly: false,
      selectedTaskKey: 'spindle',
      taskResultsBySlot: {},
      resultRenderedForTask: '',
      lastPreviewUrls: '',
      dbFeatureReport: null,
      zipBusy: false,
      zipConflictMode: 'replace',
      taskBusy: false,
      taskProgress: 0,
      taskPhase: '等待上传文件',
      previewImages: [],
      previewTaskId: '',
      previewIndex: 0,
      previewZoom: 1,
      reviewDirty: false,
      processStreamTaskId: '',
      processStreamText: '',
      processStreamRows: [],
      streamingZoneActive: false,
      twRowQueue: [],
      twLineBuffer: '',
      twIsTyping: false,
      twFieldTimer: null,
      twCurrentTr: null,
      twDoneFlag: false,
      twAllDoneHandled: false,
      workflowLiveEntries: [],
      resultByTaskId: {},
      historyPage: 1,
      historyPageSize: 6,
      historyCompletedDate: '',
      historySelected: new Set(),
      historySnapshot: null,
      taskPollTimer: null,
      reviewEventSource: null,
      initialized: false,
      featureCacheEnabled: false,
    };
    backendState.retrievalLibraryKey = getSessionRetrievalScopeKey() || 'public';
    backendState.retrievalLibraryName = resolveLibraryScopeLabel(backendState.retrievalLibraryKey);
    const taskSlots = ['spindle', 'housing', 'bracket', 'flange'];

    async function apiFetch(path, options = {}) {
      const response = await fetch(`${API_BASE}${path}`, {
        headers: {
          ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
          ...(options.headers || {}),
        },
        ...options,
      });
      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.error || `Request failed: ${response.status}`);
      }
      const contentType = response.headers.get('content-type') || '';
      return contentType.includes('application/json') ? response.json() : response.text();
    }

    function sleep(ms) {
      return new Promise((resolve) => setTimeout(resolve, ms));
    }

    function updateNavigationLockState() {
      navItems.forEach((item) => {
        const pageId = item.dataset.page;
        const disabled = (backendState.zipBusy || backendState.taskBusy) && pageId !== (backendState.zipBusy ? 'page-zip' : 'page-generate');
        item.disabled = disabled;
        item.classList.toggle('disabled', disabled);
      });
      topTabs.forEach((tab) => {
        const pageId = tab.dataset.page;
        const disabled = (backendState.zipBusy || backendState.taskBusy) && pageId !== (backendState.zipBusy ? 'page-zip' : 'page-generate');
        tab.disabled = disabled;
        tab.classList.toggle('disabled', disabled);
      });
    }

    function updateZipConflictModeButton() {
      if (!zipConflictModeBtn) return;
      zipConflictModeBtn.textContent = backendState.zipConflictMode === 'replace'
        ? '⇄ 冲突模式：替换入库'
        : '⇄ 冲突模式：保留旧版';
    }

    function renderZipLibraryList(scopes) {
      if (!zipLibraryList) return;
      const items = Array.isArray(scopes) ? scopes : [];
      const options = items.map((scope) => {
        const meta = scope.scope_type === 'public' ? '公共库' : '私有库';
        const count = scope.record_count != null ? ` · ${scope.record_count}条` : '';
        return `<option value="${escapeHtml(scope.library_key)}">${escapeHtml(scope.library_name || scope.library_key)}（${meta}${count}）</option>`;
      }).join('');
      zipLibraryList.innerHTML = options + `<option value="__new__">＋ 新建工艺库</option>`;
      zipLibraryList.value = items.length > 0 ? items[0].library_key : '__new__';
      updateZipNewLibraryFormVisibility();
      updateZipActiveLibraryChip();
    }

    function updateZipNewLibraryFormVisibility() {
      if (!zipNewLibraryForm) return;
      zipNewLibraryForm.style.display = zipLibraryList?.value === '__new__' ? 'flex' : 'none';
    }

    function updateZipActiveLibraryChip() {
      const val = zipLibraryList?.value;
      let label = '未选择目标库';
      if (val && val !== '__new__') {
        const selectedOpt = zipLibraryList?.options[zipLibraryList.selectedIndex];
        label = selectedOpt?.textContent || val;
      } else if (val === '__new__') {
        const name = (zipLibraryNameInput?.value || '').trim() || '新工艺库';
        label = `${name}（新建）`;
      }
      if (zipActiveLibraryChip) {
        zipActiveLibraryChip.textContent = val ? `当前目标：${label}` : '当前目标：未选择';
      }
      if (zipPanelLibLabel) {
        zipPanelLibLabel.textContent = val ? `目标：${label}` : '未选择目标库';
      }
    }

    async function loadZipLibraryList() {
      if (!zipLibraryList) return;
      try {
        const data = await apiFetch('/library/scopes');
        const scopes = data?.items || [];
        renderZipLibraryList(scopes);
      } catch (_) {
        renderZipLibraryList([]);
      }
    }

    function currentZipLibraryTarget() {
      const val = zipLibraryList?.value;
      if (!val || val === '__new__') {
        const seed = zipSeedPublicCheckbox?.checked !== false;
        const name = (zipLibraryNameInput?.value || '').trim() || '我的工艺库';
        return { mode: seed ? 'private_seed_public' : 'private_empty', name, key: '' };
      }
      return { mode: 'private_empty', name: '', key: val };
    }

    function currentZipLibraryMode() {
      return currentZipLibraryTarget().mode;
    }

    function currentZipLibraryName() {
      return currentZipLibraryTarget().name;
    }

    function updateZipLibraryModeUI() {
      if (zipLibraryNameInput) {
        zipLibraryNameInput.disabled = backendState.zipBusy;
        zipLibraryNameInput.placeholder = '例如：张三-液压项目库';
      }
    }

    function markSessionZipUnlocked(scopeKey) {
      try {
        sessionStorage.setItem(ZIP_UNLOCK_SESSION_KEY, '1');
        if (scopeKey) sessionStorage.setItem(ZIP_SCOPE_SESSION_KEY, scopeKey);
      } catch (error) {
        console.warn('[demo] failed to store zip unlock state:', error);
      }
    }

    function hasSessionZipUnlocked() {
      try {
        return sessionStorage.getItem(ZIP_UNLOCK_SESSION_KEY) === '1';
      } catch (error) {
        return false;
      }
    }

    function getSessionScopeKey() {
      try {
        return sessionStorage.getItem(ZIP_SCOPE_SESSION_KEY) || '';
      } catch (error) {
        return '';
      }
    }

    function getSessionRetrievalScopeKey() {
      try {
        return sessionStorage.getItem(RETRIEVAL_SCOPE_SESSION_KEY) || '';
      } catch (error) {
        return '';
      }
    }

    function setSessionRetrievalScopeKey(scopeKey) {
      try {
        if (scopeKey) {
          sessionStorage.setItem(RETRIEVAL_SCOPE_SESSION_KEY, scopeKey);
        } else {
          sessionStorage.removeItem(RETRIEVAL_SCOPE_SESSION_KEY);
        }
      } catch (error) {
        console.warn('[demo] failed to store retrieval scope:', error);
      }
    }

    function getLibraryScopesWithFallback() {
      return backendState.libraryScopes.length
        ? backendState.libraryScopes
        : [{ library_key: 'public', library_name: '公共工艺库', scope_type: 'public' }];
    }

    function resolveLibraryScopeLabel(libraryKey) {
      const key = String(libraryKey || 'public');
      const scope = getLibraryScopesWithFallback().find((item) => String(item.library_key || '') === key);
      if (scope?.library_name) return scope.library_name;
      return key === 'public' ? '公共工艺库' : key;
    }

    function renderRetrievalLibraryButton() {
      if (!retrievalLibraryBtn) return;
      const key = backendState.retrievalLibraryKey || getSessionRetrievalScopeKey() || 'public';
      const label = resolveLibraryScopeLabel(key);
      retrievalLibraryBtn.textContent = `◉ 检索库：${label}`;
      if (retrievalLibraryInfo) {
        retrievalLibraryInfo.textContent = `${label}｜${key}`;
      }
    }

    function renderRetrievalLibrarySelect() {
      if (!retrievalLibrarySelect) return;
      const scopes = getLibraryScopesWithFallback();
      const selectedKey = backendState.retrievalLibraryKey || getSessionRetrievalScopeKey() || 'public';
      retrievalLibrarySelect.innerHTML = scopes.map((scope) => {
        const suffix = scope.scope_type === 'public' ? '（默认）' : '（可检索）';
        const selected = String(scope.library_key || '') === String(selectedKey) ? ' selected' : '';
        return `<option value="${escapeHtml(scope.library_key || 'public')}"${selected}>${escapeHtml(scope.library_name || scope.library_key || '公共工艺库')}${suffix}</option>`;
      }).join('');
    }

    function setRetrievalLibraryKey(libraryKey, persist = true) {
      const key = libraryKey || 'public';
      backendState.retrievalLibraryKey = key;
      backendState.retrievalLibraryName = resolveLibraryScopeLabel(key);
      if (persist) setSessionRetrievalScopeKey(key);
      renderRetrievalLibrarySelect();
      renderRetrievalLibraryButton();
    }

    function openRetrievalLibraryModal() {
      if (!retrievalLibraryModal) return;
      renderRetrievalLibrarySelect();
      renderRetrievalLibraryButton();
      retrievalLibraryModal.classList.add('open');
      document.body.style.overflow = 'hidden';
    }

    function closeRetrievalLibraryModal() {
      if (!retrievalLibraryModal) return;
      retrievalLibraryModal.classList.remove('open');
      document.body.style.overflow = '';
    }

    function confirmRetrievalLibrarySelection() {
      const key = retrievalLibrarySelect?.value || 'public';
      setRetrievalLibraryKey(key, true);
      closeRetrievalLibraryModal();
    }

    function renderLibraryScopes() {
      const scopes = getLibraryScopesWithFallback();
      if (dbLibrarySelect) {
        dbLibrarySelect.innerHTML = scopes.map((scope) => {
          const suffix = scope.scope_type === 'public' ? '（公共）' : '（我的）';
          const selected = scope.library_key === backendState.activeLibraryKey ? ' selected' : '';
          return `<option value="${escapeHtml(scope.library_key)}"${selected}>${escapeHtml(scope.library_name)}${suffix}</option>`;
        }).join('');
      }
      renderRetrievalLibrarySelect();
      renderRetrievalLibraryButton();
    }

    function renderTaskProcessSummary(key) {
      if (!taskProcessSummaryList) return;
      const result = backendState.taskResultsBySlot[key] || null;
      const rows = result?.process_flow?.data || [];
      if (rows.length) {
        taskProcessSummaryList.innerHTML = rows.slice(0, 6).map((row) => {
          const normalized = normalizeProcessRow(row);
          const display = normalized.code ? `${normalized.code} · ${normalized.content}` : (normalized.content || '待补充');
          return `<div class="demo-list-item"><span>${escapeHtml(display)}</span><span class="status-dot"></span></div>`;
          }).join('');
        return;
      }
      const item = backendState.taskMap[key] || taskData[key] || {};
      taskProcessSummaryList.innerHTML = `<div class="demo-list-item"><span>${escapeHtml(item.stage || '等待后端任务结果')}</span><span class="status-dot"></span></div>`;
    }

    function setWorkflowState(phase, progress = 0, busy = false) {
      backendState.taskPhase = phase || '等待上传文件';
      backendState.taskProgress = Math.max(0, Math.min(100, Number(progress) || 0));
      backendState.taskBusy = !!busy;
      setTextIfChanged(workflowPercent, `${backendState.taskProgress}%`);
      if (workflowProgressBar) {
        const nextWidth = `${backendState.taskProgress}%`;
        if (workflowProgressBar.style.width !== nextWidth) workflowProgressBar.style.width = nextWidth;
      }
      if (workflowHudCard) {
        workflowHudCard.classList.toggle('busy', backendState.taskBusy);
        workflowHudCard.classList.toggle('completed', backendState.taskProgress >= 100 && !backendState.taskBusy);
        const shouldCollapse = backendState.taskProgress >= 100 && !backendState.taskBusy;
        workflowHudCard.classList.toggle('collapsed', shouldCollapse);
        if (workflowHudToggleBtn) workflowHudToggleBtn.textContent = shouldCollapse ? '展开' : '收起';
      }
      if (workflowPhaseHint) {
        const hintMap = [
          [/等待上传/, '等待文件进入解析流程'],
          [/图纸分析|图纸特征/, '2D 图纸正在提取特征，请稍候'],
          [/PRT.*批量|批量分析/, '批量 PRT 模型正在分拣与排队'],
          [/PRT.*分析/, 'PRT 正在解析并生成预览视图'],
          [/视觉|模型|特征/, '模型视图特征正在整理成结构化字段'],
          [/审阅/, '特征已提取，正在等待确认'],
          [/生成/, '等待工艺生成'],
          [/完成|已完成/, '结果已就绪，可继续审阅或导出'],
        ];
        const phaseText = String(backendState.taskPhase || '');
        const matched = hintMap.find(([pattern]) => pattern.test(phaseText));
        const nextHint = matched ? matched[1] : (backendState.taskBusy ? '正在处理当前任务' : '等待工艺生成');
        setTextIfChanged(workflowPhaseHint, nextHint);
        if (!backendState.workflowLiveEntries.length) {
          setWorkflowThinkingLine(nextHint);
        }
      }
      syncButtonRenderStates();
      updateNavigationLockState();
    }

    function syncButtonRenderStates() {
      const busy = !!backendState.taskBusy;
      const primaryButtons = [uploadGenerateBtn, reviewContinueBtn, reviewRerunBtn, getOpenExportCardBtn()];
      primaryButtons.forEach((button) => {
        if (!button) return;
        const shouldAnimate = busy && button !== reviewContinueBtn && button !== reviewRerunBtn;
        button.classList.toggle('is-loading', shouldAnimate);
        if (button === uploadGenerateBtn) {
          setDisabledIfChanged(button, busy);
        }
      });

      if (retrievalLibraryBtn) {
        retrievalLibraryBtn.classList.toggle('is-loading', busy && backendState.taskPhase.includes('检索'));
      }
      if (resetGenerateBtn) {
        resetGenerateBtn.classList.toggle('is-loading', busy && backendState.taskProgress > 0 && backendState.taskProgress < 100);
      }
    }

    function parseProcessCount(result) {
      const processFlow = result?.process_flow || {};
      if (Array.isArray(processFlow.data)) return processFlow.data.length;
      return 0;
    }

    function normalizePreviewImages(result = {}) {
      const urls = result.preview_image_urls || result.previewImages || result.image_urls || [];
      return Array.isArray(urls) ? urls.filter(Boolean) : [];
    }

    function clampPreviewIndex() {
      const max = Math.max(backendState.previewImages.length - 1, 0);
      backendState.previewIndex = Math.max(0, Math.min(max, Number(backendState.previewIndex) || 0));
    }

    function updateTaskPreviewSurface() {
      refreshTaskPreviewRefs();
      refreshTaskPreviewFullscreenRefs();
      const images = backendState.previewImages || [];
      clampPreviewIndex();
      const activeUrl = images[backendState.previewIndex] || '';

      setTextIfChanged(taskPreviewCounter, images.length ? `${backendState.previewIndex + 1} / ${images.length}` : '0 / 0');
      setTextIfChanged(taskPreviewFullscreenCounter, images.length ? `${backendState.previewIndex + 1} / ${images.length}` : '0 / 0');
      setTextIfChanged(taskPreviewZoomLabel, `${Math.round((backendState.previewZoom || 1) * 100)}%`);
      setDisabledIfChanged(taskPreviewPrevBtn, images.length <= 1 || backendState.previewIndex <= 0);
      setDisabledIfChanged(taskPreviewNextBtn, images.length <= 1 || backendState.previewIndex >= images.length - 1);
      setDisabledIfChanged(taskPreviewFullscreenPrevBtn, images.length <= 1 || backendState.previewIndex <= 0);
      setDisabledIfChanged(taskPreviewFullscreenNextBtn, images.length <= 1 || backendState.previewIndex >= images.length - 1);
      setDisabledIfChanged(taskPreviewZoomOutBtn, !images.length);
      setDisabledIfChanged(taskPreviewZoomInBtn, !images.length);
      setDisabledIfChanged(taskPreviewResetBtn, !images.length);
      setDisabledIfChanged(taskPreviewFullscreenBtn, !images.length);

      if (taskPreviewImage) {
        if (activeUrl) {
          if (taskPreviewImage.src !== activeUrl) taskPreviewImage.src = activeUrl;
          taskPreviewImage.style.display = 'block';
          taskPreviewImage.style.transform = `scale(${backendState.previewZoom || 1})`;
        } else {
          taskPreviewImage.removeAttribute('src');
          taskPreviewImage.style.display = 'none';
        }
      }
      if (taskPreviewFullscreenImage) {
        if (activeUrl) {
          if (taskPreviewFullscreenImage.src !== activeUrl) taskPreviewFullscreenImage.src = activeUrl;
          taskPreviewFullscreenImage.style.transform = `scale(${backendState.previewZoom || 1})`;
        } else {
          taskPreviewFullscreenImage.removeAttribute('src');
        }
      }
      if (taskPreviewEmpty) {
        taskPreviewEmpty.style.display = activeUrl ? 'none' : 'flex';
      }
    }

    function ensurePreviewFullscreenHost() {
      let host = document.getElementById('taskPreviewFullscreen');
      if (host) return host;
      host = document.createElement('div');
      host.id = 'taskPreviewFullscreen';
      host.className = 'task-preview-fullscreen';
      host.innerHTML = `
        <div class="task-preview-fullscreen-shell">
          <button class="task-preview-fs-prev" id="taskPreviewFullscreenPrevBtn">&#10094;</button>
          <button class="task-preview-fs-next" id="taskPreviewFullscreenNextBtn">&#10095;</button>
          <button class="task-preview-fs-close" id="taskPreviewFullscreenCloseBtn">✕</button>
          <span class="task-preview-fs-counter" id="taskPreviewFullscreenCounter">0 / 0</span>
          <div class="task-preview-fullscreen-stage">
            <img id="taskPreviewFullscreenImage" class="task-preview-fullscreen-image" alt="模型视图全屏预览" />
          </div>
        </div>
      `;
      document.body.appendChild(host);
      host.addEventListener('click', (event) => {
        if (event.target === host) closePreviewFullscreen();
      });
      const prevBtn = host.querySelector('#taskPreviewFullscreenPrevBtn');
      const nextBtn = host.querySelector('#taskPreviewFullscreenNextBtn');
      const closeBtn = host.querySelector('#taskPreviewFullscreenCloseBtn');
      if (prevBtn) prevBtn.addEventListener('click', () => {
        backendState.previewIndex = Math.max(0, backendState.previewIndex - 1);
        updateTaskPreviewSurface();
      });
      if (nextBtn) nextBtn.addEventListener('click', () => {
        backendState.previewIndex = Math.min(Math.max((backendState.previewImages || []).length - 1, 0), backendState.previewIndex + 1);
        updateTaskPreviewSurface();
      });
      if (closeBtn) closeBtn.addEventListener('click', closePreviewFullscreen);

      // 滚轮缩放
      const stage = host.querySelector('.task-preview-fullscreen-stage');
      if (stage) {
        stage.addEventListener('wheel', (e) => {
          e.preventDefault();
          const delta = e.deltaY < 0 ? 0.15 : -0.15;
          backendState.previewZoom = Math.min(4.0, Math.max(0.3, (backendState.previewZoom || 1) + delta));
          updateTaskPreviewSurface();
        }, { passive: false });
      }

      refreshTaskPreviewFullscreenRefs();
      return host;
    }

    function openPreviewFullscreen() {
      if (!(backendState.previewImages || []).length) return;
      const host = ensurePreviewFullscreenHost();
      updateTaskPreviewSurface();
      host.classList.add('open');
      document.body.style.overflow = 'hidden';
    }

    function closePreviewFullscreen() {
      const host = document.getElementById('taskPreviewFullscreen');
      if (!host) return;
      host.classList.remove('open');
      document.body.style.overflow = '';
    }

    function focusProcessWorkspace() {
      const processTab = document.querySelector('.result-tab[data-result-view="view-process"]');
      const processView = document.getElementById('view-process');
      if (processTab && typeof processTab.scrollIntoView === 'function') {
        processTab.scrollIntoView({ behavior: 'smooth', block: 'center' });
        return;
      }
      if (processView && typeof processView.scrollIntoView === 'function') {
        processView.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    }

    function getTaskResult(key) {
      return backendState.taskResultsBySlot[key] || null;
    }

    function getFeaturePreviewText(result = {}, fallback = '') {
      const text = result?.feature_report_text || result?.review_text || result?.feature_report || result?.raw_review_text || fallback || '';
      return String(text || '').trim() || '暂无特征提取内容。';
    }

    function getHistoryInfoText(result = {}, item = {}) {
      const taskId = result?.task_id || item?.task_id || '-';
      const hitCount = Array.isArray(result?.rag_results?.matches) ? result.rag_results.matches.length : 0;
      const pageCount = Number(result?.png_count || result?.total_pages || 0) || 0;
      return `任务ID：${taskId} · 视图页数：${pageCount} · RAG 命中：${hitCount} 条`;
    }

    function cacheHistoryResult(taskId, result) {
      if (!taskId || !result) return;
      backendState.resultByTaskId[taskId] = result;
    }

    function getHistoryTaskResult(taskId) {
      return backendState.resultByTaskId[taskId] || (backendState.latestResult?.task_id === taskId ? backendState.latestResult : null);
    }

    function normalizeHistoryCard(historyItem = {}, result = {}) {
      const steps = parseProcessCount(result);
      const status = String(result?.status || historyItem.status || (historyItem.progress >= 100 ? 'completed' : 'processing')).trim();
      const statusLabel = status === 'completed' || status === '已完成'
        ? '已完成'
        : (status === 'awaiting_review' ? '待审阅' : (status === 'error' ? '失败' : (historyItem.progress >= 100 ? '已完成' : '处理中')));
      const statusClass = statusLabel === '已完成' ? 'success' : (statusLabel === '失败' ? 'danger' : 'warn');
      return {
        taskId: result?.task_id || historyItem.task_id || '-',
        title: result?.pdf_name || historyItem.pdf_name || historyItem.task_id || '任务',
        meta: `任务：${historyItem.task_id || result?.task_id || '-'} · 最近更新：${historyItem.created_at || result?.created_at || '-'}`,
        status: statusLabel,
        statusClass,
        stage: statusLabel === '已完成'
          ? '历史任务已完成，可查看工艺输出与特征提取。'
          : `历史任务当前状态：${statusLabel}`,
        feature: getFeaturePreviewText(result, historyItem.pdf_name || ''),
        hit: getHistoryInfoText(result, historyItem),
        count: steps ? `已输出 ${steps} 条工序` : '当前暂无可展示的工艺输出。',
        steps,
      };
    }

    function buildHistoryEntries() {
      const items = Array.isArray(backendState.history) ? backendState.history.slice() : [];
      const latestId = backendState.latestResult?.task_id || backendState.latestTaskId || '';
      if (latestId && !items.some((item) => item.task_id === latestId)) {
        items.unshift({
          task_id: latestId,
          pdf_name: backendState.latestResult?.pdf_name || latestId,
          created_at: backendState.latestResult?.created_at || '-',
          status: backendState.latestResult?.status || 'processing',
          progress: backendState.latestResult?.progress || backendState.taskProgress || 0,
        });
      }
      return items.map((item) => {
        const result = getHistoryTaskResult(item.task_id) || (item.task_id === latestId ? backendState.latestResult : null) || {};
        return { item, result, card: normalizeHistoryCard(item, result) };
      });
    }

    function getHistoryDateKey(value) {
      const text = String(value || '').trim();
      if (!text) return '';
      const isoMatch = text.match(/^(\d{4}-\d{2}-\d{2})/);
      if (isoMatch) return isoMatch[1];
      const slashMatch = text.match(/^(\d{4}\/\d{2}\/\d{2})/);
      if (slashMatch) return slashMatch[1].replace(/\//g, '-');
      const date = new Date(text);
      if (!Number.isNaN(date.getTime())) {
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${date.getFullYear()}-${month}-${day}`;
      }
      return text.slice(0, 10);
    }

    function getFilteredHistoryEntries() {
      const entries = buildHistoryEntries();
      const filterDate = String(backendState.historyCompletedDate || '').trim();
      if (!filterDate) return entries;
      return entries.filter(({ item }) => getHistoryDateKey(item.completed_at || item.created_at || '') === filterDate);
    }

    function closeHistorySnapshotModalView() {
      if (historySnapshotModal) historySnapshotModal.classList.remove('open');
      document.body.style.overflow = '';
    }

    function updateHistorySnapshotSurface() {
      const state = backendState.historySnapshot || { images: [], index: 0, zoom: 1 };
      const images = Array.isArray(state.images) ? state.images : [];
      const gltfUrl = state.result?.gltf_url || '';
      const container3D = document.getElementById('historySnapshot3DContainer');

      if (gltfUrl) {
        // PRT task — show 3D viewer
        if (container3D) { container3D.style.display = 'block'; historyViewer.render(gltfUrl, container3D); }
        if (historySnapshotImage) { historySnapshotImage.style.display = 'none'; historySnapshotImage.removeAttribute('src'); }
        if (historySnapshotEmpty) historySnapshotEmpty.style.display = 'none';
        if (historySnapshotCounter) historySnapshotCounter.textContent = '3D 模型';
        if (historySnapshotZoomLabel) historySnapshotZoomLabel.textContent = '拖拽旋转';
        [historySnapshotPrevBtn, historySnapshotNextBtn, historySnapshotZoomInBtn, historySnapshotZoomOutBtn, historySnapshotResetBtn]
          .forEach((btn) => { if (btn) btn.disabled = true; });
        return;
      }

      // No gltf_url — fall back to PNG image display
      historyViewer.dispose();
      if (container3D) container3D.style.display = 'none';
      const activeUrl = images[state.index] || '';
      const zoom = state.zoom || 1;
      if (historySnapshotCounter) historySnapshotCounter.textContent = images.length ? `${state.index + 1} / ${images.length}` : '0 / 0';
      if (historySnapshotZoomLabel) historySnapshotZoomLabel.textContent = `${Math.round(zoom * 100)}%`;
      if (historySnapshotPrevBtn) historySnapshotPrevBtn.disabled = images.length <= 1 || state.index <= 0;
      if (historySnapshotNextBtn) historySnapshotNextBtn.disabled = images.length <= 1 || state.index >= images.length - 1;
      if (historySnapshotZoomOutBtn) historySnapshotZoomOutBtn.disabled = !images.length;
      if (historySnapshotZoomInBtn) historySnapshotZoomInBtn.disabled = !images.length;
      if (historySnapshotResetBtn) historySnapshotResetBtn.disabled = !images.length;
      if (historySnapshotImage) {
        if (activeUrl) {
          historySnapshotImage.src = activeUrl;
          historySnapshotImage.style.display = 'block';
          historySnapshotImage.style.transform = `scale(${zoom})`;
        } else {
          historySnapshotImage.removeAttribute('src');
          historySnapshotImage.style.display = 'none';
        }
      }
      if (historySnapshotEmpty) historySnapshotEmpty.style.display = activeUrl ? 'none' : 'flex';
    }

    function renderHistorySnapshotDetails(card = {}, result = {}) {
      if (historySnapshotTitle) historySnapshotTitle.textContent = card.title || '工艺快照';
      if (historySnapshotMeta) historySnapshotMeta.textContent = card.meta || '点击表格中的快照按钮打开分栏预览。';
      if (historySnapshotSource) {
        historySnapshotSource.textContent = `${card.taskId || '-'} · ${card.status || '-'} · ${result?.png_count || result?.total_pages || 0} 页视图`;
      }
      if (historySnapshotReview) {
        const reviewRows = Array.isArray(result?.review_rows) ? result.review_rows : [];
        const reviewText = reviewRows.length
          ? reviewRows.map((row) => {
            if (row && typeof row === 'object') {
              const label = String(row.label || row.key || '').trim();
              const value = String(row.value || row.content || '').trim();
              return label ? `${label}：${value}` : value;
            }
            return String(row || '').trim();
          }).filter(Boolean).join('\n')
          : getFeaturePreviewText(result, card.feature || '-');
        historySnapshotReview.innerHTML = renderFieldCardStack(reviewText, '暂无特征审阅内容');
      }
      if (historySnapshotProcess) {
        const rows = Array.isArray(result?.process_flow?.data) ? result.process_flow.data : [];
        const text = rows.length
          ? rows.map((row) => {
            const normalized = normalizeProcessRow(row);
            return normalized.code ? `${normalized.code} ${normalized.content}` : normalized.content;
          }).join('\n')
          : '';
        historySnapshotProcess.textContent = text || '暂无工艺规程';
      }
    }

    async function deleteHistoryTask(taskId, buttonEl) {
      if (!taskId) return;
      if (buttonEl) {
        buttonEl.disabled = true;
        buttonEl.textContent = '删除中…';
      }
      try {
        await apiFetch(`/history/${encodeURIComponent(taskId)}`, { method: 'DELETE' });
        backendState.history = (backendState.history || []).filter((item) => item.task_id !== taskId);
        backendState.historySelected.delete(taskId);
        if (backendState.latestTaskId === taskId) backendState.latestTaskId = null;
        renderHistoryPage();
      } catch (error) {
        showToast('删除失败：' + error.message, 'error');
        if (buttonEl) {
          buttonEl.disabled = false;
          buttonEl.textContent = '删除';
        }
      }
    }

    function openHistorySnapshot(taskId) {
      if (!taskId || !historySnapshotModal) return;
      const historyItem = (Array.isArray(backendState.history) ? backendState.history : []).find((item) => item.task_id === taskId) || { task_id: taskId };
      const cachedResult = getHistoryTaskResult(taskId);
      const apply = (result = {}) => {
        const nextResult = result || cachedResult || {};
        cacheHistoryResult(taskId, nextResult);
        const card = normalizeHistoryCard(historyItem, nextResult);
        backendState.historySnapshot = {
          taskId,
          item: historyItem,
          result: nextResult,
          images: normalizePreviewImages(nextResult),
          index: 0,
          zoom: 1,
        };
        renderHistorySnapshotDetails(card, nextResult);
        updateHistorySnapshotSurface();
        historySnapshotModal.classList.add('open');
        document.body.style.overflow = 'hidden';
      };

      if (cachedResult) {
        apply(cachedResult);
        return;
      }

      backendState.historySnapshot = {
        taskId,
        item: historyItem,
        result: {},
        images: [],
        index: 0,
        zoom: 1,
      };
      renderHistorySnapshotDetails(normalizeHistoryCard(historyItem, {}), {});
      updateHistorySnapshotSurface();
      historySnapshotModal.classList.add('open');
      document.body.style.overflow = 'hidden';

      apiFetch(`/result/${encodeURIComponent(taskId)}`)
        .then((result) => apply(result))
        .catch((error) => {
          console.warn('[demo] failed to fetch history snapshot:', error);
        });
    }

    function renderHistoryPage() {
      const entries = getFilteredHistoryEntries();
      const total = entries.length;
      const pageSize = Math.max(1, Number(backendState.historyPageSize) || 6);
      const totalPages = Math.max(1, Math.ceil(Math.max(total, 1) / pageSize));
      backendState.historyPage = Math.min(Math.max(Number(backendState.historyPage) || 1, 1), totalPages);
      const start = (backendState.historyPage - 1) * pageSize;
      const pageItems = entries.slice(start, start + pageSize);
      const historyRenderKey = [
        backendState.historyPage,
        pageSize,
        total,
        backendState.historyCompletedDate,
        entries.map((entry) => `${entry.card.taskId}:${entry.card.status}:${entry.card.count}`).join('|'),
      ].join('::');
      if (backendState.historyRenderKey === historyRenderKey) {
        return;
      }
      backendState.historyRenderKey = historyRenderKey;

      const completed = entries.filter((entry) => entry.card.status === '已完成').length;
      const awaitingReview = entries.filter((entry) => entry.result?.status === 'awaiting_review' || entry.card.status === '待审阅').length;
      const totalSteps = entries.reduce((sum, entry) => sum + (entry.card.steps || 0), 0);
      const filterLabel = backendState.historyCompletedDate ? `完成日期 ${backendState.historyCompletedDate} ` : '';

      setTextIfChanged(historyTotalValue, String(total));
      setTextIfChanged(historyDoneValue, String(completed));
      setTextIfChanged(historyReviewValue, String(awaitingReview));
      setTextIfChanged(historyStepValue, String(totalSteps));
      setTextIfChanged(historyRecordCount, `${total} 条`);
      setTextIfChanged(historyTableMeta, total
        ? `${filterLabel}当前展示第 ${backendState.historyPage} 页，共 ${totalPages} 页，最近任务会优先显示。`
        : (backendState.historyCompletedDate
          ? `未找到完成日期为 ${backendState.historyCompletedDate} 的历史任务。`
          : '暂无历史任务，完成一次工艺生成后会在这里显示。'));
      setTextIfChanged(historyPageIndicator, `第 ${backendState.historyPage} / ${totalPages} 页`);
      setDisabledIfChanged(historyPrevBtn, backendState.historyPage <= 1);
      setDisabledIfChanged(historyNextBtn, backendState.historyPage >= totalPages);

      if (!historyTableBody) return;
      if (!pageItems.length) {
        historyTableBody.innerHTML = '<tr><td colspan="7" class="history-table-empty">暂无历史任务</td></tr>';
        return;
      }

      const selectedSet = backendState.historySelected || new Set();
      historyTableBody.innerHTML = pageItems.map(({ item, result, card }) => {
        const checked = selectedSet.has(card.taskId) ? ' checked' : '';
        return `
        <tr data-history-task-id="${escapeHtml(card.taskId)}">
          <td><input type="checkbox" class="history-row-check" data-select-task-id="${escapeHtml(card.taskId)}"${checked}></td>
          <td class="history-main-cell">
            <div class="history-title">${escapeHtml(card.title)}</div>
            <div class="history-subtitle">${escapeHtml(card.meta)}</div>
          </td>
          <td><span class="status-badge ${card.statusClass}">${escapeHtml(card.status)}</span></td>
          <td>${escapeHtml(String(item.completed_at || result?.completed_at || item.created_at || result?.created_at || '-'))}</td>
          <td>${escapeHtml(card.count)}</td>
          <td><button class="history-snapshot-link" data-history-snapshot="${escapeHtml(card.taskId)}">查看快照</button></td>
          <td><button class="history-delete-btn" data-delete-task-id="${escapeHtml(card.taskId)}" title="删除此记录及本地文件">删除</button></td>
        </tr>
      `}).join('');
      updateHistorySelectAllState();
      updateHistoryBatchDeleteBtn();
    }

    function updateHistorySelectAllState() {
      if (!historySelectAll) return;
      const entries = getFilteredHistoryEntries();
      const pageSize = Math.max(1, Number(backendState.historyPageSize) || 6);
      const start = (backendState.historyPage - 1) * pageSize;
      const pageItems = entries.slice(start, start + pageSize);
      const pageIds = new Set(pageItems.map(({ card }) => card.taskId));
      const selectedOnPage = pageItems.filter(({ card }) => backendState.historySelected.has(card.taskId));
      historySelectAll.checked = pageIds.size > 0 && selectedOnPage.length === pageIds.size;
      historySelectAll.indeterminate = selectedOnPage.length > 0 && selectedOnPage.length < pageIds.size;
    }

    function updateHistoryBatchDeleteBtn() {
      if (!historyBatchDeleteBtn) return;
      const count = backendState.historySelected.size;
      historyBatchDeleteBtn.style.display = count > 0 ? '' : 'none';
      historyBatchDeleteBtn.disabled = count === 0;
      historyBatchDeleteBtn.textContent = count > 0 ? `批量删除 (${count})` : '批量删除';
    }

    function applyHistoryCompletedDateFilter(value = '') {
      backendState.historyCompletedDate = String(value || '').trim();
      backendState.historyPage = 1;
      renderHistoryPage();
    }

    function getZipPhaseLabel(phase = '') {
      const text = String(phase || '').trim();
      if (/上传中/.test(text)) return '上传中';
      if (/解析中/.test(text)) return '解析中';
      if (/入库中/.test(text)) return '入库中';
      if (/已完成/.test(text)) return '已完成';
      if (/等待/.test(text)) return '等待中';
      return text || '处理中';
    }

    function processContentForDisplay(content) {
      if (!content) return '';
      // Insert \n before -2. -3. -4. ... (sub-steps like -1.准备；-2.冲孔)
      content = content.replace(/([；;])\s*(-\d+[.．])/g, '\n$2');
      // Insert \n before 2）3）4）... that follow a ；or ; delimiter
      content = content.replace(/([；;])\s*(\d+[）)])/g, '$1\n$2');
      // Insert \n before N. step markers (1-2 digit number + period) after ；
      // Lookahead (?=[^\d]) prevents matching dimension values like ；88.42
      content = content.replace(/([；;])\s*(\d{1,2}[.．])(?=[^\d])/g, '$1\n$2');
      return content;
    }

    function formatContentHtml(content) {
      // Escape HTML entities first, then convert \n to <br> for innerHTML
      return escapeHtml(processContentForDisplay(content || '')).replace(/\n/g, '<br>');
    }

    function _splitTradeFromContent(content) {
      // Detects embedded trade type: "料@备料...", "数铣@1）...", "外-表@1）..."
      // Suffix format: "工序内容 （工种：料）" — generated by backend _normalize_standard_process_rows
      const mSuffix = content.match(/^(.*?)\s*[（(]工种[：:]\s*([一-龥\-]{1,6})\s*[）)]\s*$/);
      if (mSuffix) return { tradeType: mSuffix[2].trim(), content: mSuffix[1].trim() };
      // Matches 1–6 chars (Chinese, letters, hyphens) that are NOT digits/whitespace/brackets,
      // followed immediately by @ then actual content.
      const m = content.match(/^([^\d\s@（）【】\[\]()]{1,6})@(.+)/s);
      if (m && m[2].trim()) return { tradeType: m[1].trim(), content: m[2].trim() };
      // Handle "料（备料...）", "数铣（1）按图..." format from LLM output
      const m2 = content.match(/^([一-龥\-]{1,6})\s*（([\s\S]+)/);
      if (m2 && m2[2].trim()) {
        let inner = m2[2].trim();
        if (inner.endsWith('）')) inner = inner.slice(0, -1);
        return { tradeType: m2[1].trim(), content: inner };
      }
      return { tradeType: '', content };
    }

    function normalizeProcessRow(row) {
      let code = '', tradeType = '', content = '';

      if (Array.isArray(row)) {
        if (row.length >= 3) {
          code = String(row[0] || '').trim();
          tradeType = String(row[1] || '').trim();
          content = String(row[2] || '').trim();
        } else {
          code = String(row[0] || '').trim();
          content = String(row[1] || '').trim();
        }
      } else if (row && typeof row === 'object') {
        code = String(row.processNo || row.stepNo || row.code || '').trim();
        tradeType = String(row.tradeType || row.trade || row['工种'] || '').trim();
        content = String(row.stepContent || row.content || '').trim();
      } else {
        const text = String(row || '').trim();
        // Three-part format: 0010@工种@内容
        const m3 = text.match(/^(\d{4})@([^@]*)@(.+)$/s);
        if (m3) {
          code = m3[1].trim(); tradeType = m3[2].trim(); content = m3[3].trim();
        } else {
          // Two-part format: 0010@内容 (old records) or delimiter fallback
          const m2 = text.match(/^(\d{4})\s*[@:：\-\|,，;；\s]*\s*(.+)$/s);
          if (m2) { code = m2[1].trim(); content = m2[2].trim(); }
          else return { code: '', tradeType: '', content: text };
        }
      }

      // If tradeType is still empty, check whether content embeds it ("料@备料...", "数铣@1）...")
      if (!tradeType && content) {
        const split = _splitTradeFromContent(content);
        if (split.tradeType) { tradeType = split.tradeType; content = split.content; }
      }

      return { code, tradeType, content };
    }

    function normalizeTaskCard(historyItem = {}, result = {}) {
      const steps = parseProcessCount(result);
      const title = result.pdf_name || historyItem.pdf_name || historyItem.task_id || '任务';
      const meta = `任务：${historyItem.task_id || result.task_id || '-'} · 最近更新：${historyItem.created_at || result.created_at || '-'}`;
      const status = result.process_flow ? '已完成' : (historyItem.progress >= 100 ? '已完成' : (historyItem.status || '处理中'));
      const statusClass = status === '已完成' ? 'success' : 'warn';
      return {
        title,
        meta,
        status,
        statusClass,
        stage: status === '已完成' ? '该历史任务已生成完成，可查看输出与特征提取内容。' : `历史任务当前状态：${status}`,
        hit: getHistoryInfoText(result, historyItem),
        feature: getFeaturePreviewText(result, historyItem.pdf_name || ''),
        count: steps ? `已输出 ${steps} 条工序，可在下方查看历史工艺内容。` : '当前暂无可展示的工艺输出。',
      };
    }

    function summarizeTaskFromHistory(item = {}, slot = 'task') {
      const progress = Number(item.progress || 0);
      const status = progress >= 100 ? '已完成' : (item.status || '处理中');
      const statusClass = status === '已完成' ? 'success' : 'warn';
      return {
        title: item.pdf_name || item.task_id || slot,
        meta: `任务：${item.task_id || '-'} · 最近更新：${item.created_at || '-'}`,
        status,
        statusClass,
        stage: status === '已完成' ? '历史任务已完成，可查看工艺输出与特征提取。' : '历史任务仍在处理中。',
        hit: `任务ID：${item.task_id || '-'} · 后端进度 ${progress}%`,
        feature: item.pdf_name || '等待后端结果。',
        count: '从后端历史结果自动同步。',
      };
    }

    function normalizeLibraryRecord(item = {}) {
      const id = String(item.id);
      const processCount = Number(item.process_count || (Array.isArray(item.process_list) ? item.process_list.length : 0) || 0);
      const processListArr = Array.isArray(item.process_list)
        ? item.process_list.map((row) => String(row || '').trim()).filter(Boolean)
        : [];
      const content = processListArr.length
        ? processListArr.join('\n')
        : String(item.content || item.process_summary || item.context || '').trim();
      const featureReportText = String(item.feature_report_text || item.featureReportText || item.feature_report || '').trim();
      const featureReportJson = item.feature_report_json || item.featureReportJson || {};
      return {
        key: id,
        id: item.id,
        title: item.prefix || `记录 ${id}`,
        meta: `模型编号：${item.prefix || '-'} · 最近更新：${item.created_at || '-'}`,
        status: item.real ? '可用' : '草稿',
        statusClass: item.real ? 'success' : 'warn',
        type: item.product_type || '未分类',
        source: item.real ? '工艺入库' : '手工修订',
        processCount,
        processList: processListArr,
        summary: content,
        content,
        sourceType: item.source_type || '',
        sourceTaskId: item.source_task_id || '',
        keyFeatures: item.key_features || item.keyFeatures || '',
        featureReportText,
        featureReportPath: item.feature_report_path || item.featureReportPath || '',
        featureReportJson: featureReportJson && typeof featureReportJson === 'object' ? featureReportJson : {},
        previewTaskId: item.preview_task_id || item.source_task_id || '',
        previewTotalPages: Number(item.preview_total_pages || 0) || 0,
        previewImageUrls: normalizePreviewUrlList(item.preview_image_urls),
        tags: String(item.key_features || item.keyFeatures || '')
          .split(/[；;,，\n]/)
          .map((v) => v.trim())
          .filter(Boolean)
          .slice(0, 3),
      };
    }

    function normalizeDbFeatureReportPageText(page = {}) {
      return String(page.description || page.text || page.summary || page.content || '').trim();
    }

    function normalizeFeatureLabel(label = '') {
      const cleaned = String(label || '').trim().replace(/^[【\[]|[】\]]$/g, '').replace(/[\s\-—_（）()【】\[\]：:]+$/g, '').replace(/\s+/g, '');
      const map = {
        图纸编号: '模型编号',
        零件号: '模型编号',
        零件图号: '模型编号',
        产品名称: '零件名称',
        部件名称: '零件名称',
        毛坯: '毛坯类型',
        材料: '毛坯类型',
        技术条件: '技术要求',
        加工要求: '技术要求',
        外形: '形态',
        工件形态: '形态',
        类别: '类型',
        规格: '关键尺寸',
        尺寸: '关键尺寸',
        弧段: '弧段与齿形',
        齿形: '弧段与齿形',
        端面: '端面与平面',
        平面: '端面与平面',
        外圆: '外圆与内孔',
        内孔: '外圆与内孔',
        孔: '外圆与内孔',
        螺纹: '螺纹与螺孔',
        螺孔: '螺纹与螺孔',
        倒角要求: '倒角',
        热处理: '热处理与探伤',
        探伤: '热处理与探伤',
        标识: '标识与检验',
        检验: '标识与检验',
        线切: '线切割',
        线割: '线切割',
        精度: '精度与检测特征',
        检测: '精度与检测特征',
        表面处理: '表面处理与镀层特征',
        镀层: '表面处理与镀层特征',
        过渡: '过渡特征',
      };
      if (map[cleaned]) return map[cleaned];
      if (cleaned.startsWith('图号')) return '模型编号';
      if (cleaned.startsWith('零件名称') || cleaned.startsWith('产品名称')) return '零件名称';
      return cleaned;
    }

    const _FEATURE_NOISE_LABELS = new Set(['报告名称', '页数', '图号', '图号保留', '零件名称', '毛坯类型']);
    function _isFeatureNoiseLabel(label) {
      return _FEATURE_NOISE_LABELS.has(label) || /^第\d+页摘要$/.test(label);
    }

    function parseFeatureFieldPairs(text = '') {
      const cleaned = String(text || '').trim().replace(/\ufeff/g, '').replace(/^\[Pasted/i, '');
      if (!cleaned) return [];
      const pairs = [];
      const matches = [...cleaned.matchAll(/【([^】]+)】/g)];
      if (matches.length) {
        const leadingText = cleaned.slice(0, matches[0].index).trim().replace(/^[\s：:\-—\[\]]+|[\s：:\-—\[\]]+$/g, '');
        if (leadingText) pairs.push({ label: '模型编号', value: leadingText });
        matches.forEach((match, index) => {
          const start = match.index + match[0].length;
          const end = index + 1 < matches.length ? matches[index + 1].index : cleaned.length;
          const label = normalizeFeatureLabel(match[1]);
          const value = cleaned.slice(start, end).trim();
          if (label && !_isFeatureNoiseLabel(label)) pairs.push({ label, value });
        });
        return pairs;
      }

      cleaned.split(/\r?\n/).forEach((line) => {
        const current = line.trim();
        if (!current) return;
        const match = current.match(/^【([^】]+)】\s*(.*)$/) || current.match(/^([^:：]{1,32})[：:]\s*(.*)$/);
        if (!match) return;
        const label = normalizeFeatureLabel(match[1]);
        const value = String(match[2] || '').trim();
        if (label && !_isFeatureNoiseLabel(label)) pairs.push({ label, value });
      });

      return pairs;
    }

    function renderFieldCardStack(text = '', emptyText = '暂无内容') {
      const pairs = parseFeatureFieldPairs(text);
      if (!pairs.length) {
        const fallback = String(text || '').trim() || emptyText;
        return `<div class="field-card is-empty"><div class="field-card-label">内容</div><div class="field-card-value">${escapeHtml(fallback)}</div></div>`;
      }
      return pairs.map((pair, index) => `
        <div class="field-card">
          <div class="field-card-head">
            <span class="field-card-index">${String(index + 1).padStart(2, '0')}</span>
            <span class="field-card-label">${escapeHtml(pair.label || '未命名')}</span>
          </div>
          <div class="field-card-value">${escapeHtml(pair.value || '未识别')}</div>
        </div>
      `).join('');
    }

    function normalizeDbFeatureReportPages(item = {}) {
      const report = item.featureReportJson && typeof item.featureReportJson === 'object' ? item.featureReportJson : {};

      // ── PRT 几何链路 ────────────────────────────────────────────────────────
      if (String(item.sourceType || '').toLowerCase() === 'prt') {
        const geoText = String(item.featureReportText || report.report_text || '').trim();
        if (!geoText) return [];
        return [{ page: 1, description: geoText, summary: geoText.slice(0, 200), image_path: '' }];
      }

      // ── PDF / ZIP 图纸链路 ──────────────────────────────────────────────────
      const mergedText = String(report.report_text || item.featureReportText || '').trim();
      const rawPages = Array.isArray(report.pages) ? report.pages : [];

      // ① 优先：rawPages 有实际 【字段】 内容（新入库记录，per-page breakdown）
      if (rawPages.length) {
        const pagesWithContent = rawPages
          .map((page, index) => {
            const description = normalizeDbFeatureReportPageText(page) || '';
            return {
              ...page,
              page: Number(page.page || page._page_number || index + 1) || index + 1,
              description,
              summary: String(page.summary || description || '').trim(),
              image_path: page.image_path || page.source_path || '',
            };
          })
          .filter((p) => p.description);
        if (pagesWithContent.length) return pagesWithContent;
      }

      // ② 回退：把 mergedText（完整结构化报告）整体作为单页展示
      //    不再走 summaryMatches 路径——摘要文本是截断的，【字段】解析会失败
      const fallbackText = mergedText || String(item.keyFeatures || item.summary || item.content || '').trim();
      if (!fallbackText) return [];
      return [{ page: 1, description: fallbackText, summary: fallbackText.slice(0, 200), image_path: '' }];
    }

    function renderDbFeatureReportView(item = {}, options = {}) {
      const key = String(item.key || item.id || '');
      const previous = backendState.dbFeatureReport || {};
      const sameRecord = !!key && previous.key === key;
      const pages = sameRecord && previous.dirty && Array.isArray(previous.pages) && previous.pages.length && !options.forceReload
        ? previous.pages
        : normalizeDbFeatureReportPages(item);
      const hasExplicitIndex = options.index !== undefined && options.index !== null && options.index !== '' && !Number.isNaN(Number(options.index));
      const requestedIndex = hasExplicitIndex ? Number(options.index) : null;
      const index = requestedIndex !== null
        ? Math.min(Math.max(requestedIndex, 0), Math.max(pages.length - 1, 0))
        : (sameRecord
          ? Math.min(Math.max(Number(previous.index) || 0, 0), Math.max(pages.length - 1, 0))
          : 0);
      backendState.dbFeatureReport = {
        key,
        item,
        report: item.featureReportJson && typeof item.featureReportJson === 'object' ? item.featureReportJson : {},
        pages,
        index,
        dirty: sameRecord ? !!previous.dirty : false,
      };

      const currentPage = pages[index] || null;
      const pageLabel = pages.length ? `第 ${index + 1} / ${pages.length} 页` : '暂无分页特征';
      const rawPageText = normalizeDbFeatureReportPageText(currentPage);
      const pageText = rawPageText || '暂无特征内容';
      const pageMeta = currentPage?.summary || currentPage?.image_path || item.featureReportText || item.keyFeatures || '当前页特征可直接编辑';

      if (dbFeaturePageIndicator) dbFeaturePageIndicator.textContent = pageLabel;
      if (dbFeaturePageMeta) dbFeaturePageMeta.textContent = pages.length ? pageMeta : '该记录没有分页特征，保存时会按当前文本生成单页特征报告。';
      if (dbFeaturePrevBtn) dbFeaturePrevBtn.disabled = pages.length <= 1 || index <= 0;
      if (dbFeatureNextBtn) dbFeatureNextBtn.disabled = pages.length <= 1 || index >= pages.length - 1;
      if (dbEditorFeaturePageText && options.syncEditor !== false) dbEditorFeaturePageText.value = rawPageText;
      if (dbFeaturePageFields) dbFeaturePageFields.innerHTML = renderFieldCardStack(rawPageText, '当前页没有结构化字段');
      if (dbPreviewFeature) {
        dbPreviewFeature.innerHTML = renderFieldCardStack(rawPageText, '当前页没有结构化字段');
      }

      refreshDbEditorPreview();
    }

    function syncDbFeatureReportEditor() {
      const state = backendState.dbFeatureReport;
      if (!state || !Array.isArray(state.pages) || !state.pages.length || !dbEditorFeaturePageText) return;
      const currentIndex = Math.min(Math.max(Number(state.index) || 0, 0), state.pages.length - 1);
      const currentPage = state.pages[currentIndex] || {};
      const currentText = String(dbEditorFeaturePageText.value || '').trim();
      const nextPage = {
        ...currentPage,
        page: Number(currentPage.page || currentIndex + 1) || currentIndex + 1,
        description: currentText,
        text: currentText,
        summary: String(currentPage.summary || currentText || '').trim(),
      };
      state.pages[currentIndex] = nextPage;
      state.dirty = true;
      if (dbFeaturePageFields) dbFeaturePageFields.innerHTML = renderFieldCardStack(currentText, '当前页没有结构化字段');
      if (dbPreviewFeature) {
        dbPreviewFeature.innerHTML = renderFieldCardStack(currentText, '当前页没有结构化字段');
      }
      refreshDbEditorPreview();
    }

    function shiftDbFeatureReportPage(delta) {
      const state = backendState.dbFeatureReport;
      if (!state || !Array.isArray(state.pages) || !state.pages.length) return;
      syncDbFeatureReportEditor();
      const nextIndex = Math.min(Math.max((Number(state.index) || 0) + delta, 0), state.pages.length - 1);
      state.index = nextIndex;
      const currentPage = state.pages[nextIndex] || {};
      if (dbEditorFeaturePageText) dbEditorFeaturePageText.value = normalizeDbFeatureReportPageText(currentPage);
      renderDbFeatureReportView({
        ...(state.item || {}),
        featureReportJson: {
          ...(state.report || {}),
          pages: state.pages,
          page_count: state.pages.length,
        },
      }, { index: nextIndex, syncEditor: false });
    }

    function buildDbFeatureReportPayload() {
      const state = backendState.dbFeatureReport;
      if (!state || !Array.isArray(state.pages) || !state.pages.length) return null;
      syncDbFeatureReportEditor();
      const pages = state.pages.map((page, index) => {
        const text = normalizeDbFeatureReportPageText(page);
        return {
          ...page,
          page: Number(page.page || index + 1) || index + 1,
          description: text,
          text,
          summary: String(page.summary || text || '').trim(),
        };
      });
      return {
        ...(state.report || {}),
        pages,
        page_count: pages.length,
        prefix_hint: state.report?.prefix_hint || state.item?.title || '',
        report_text: '',
      };
    }

    function ingestLibraryRecords(items = []) {
      Object.keys(dbRecords).forEach((key) => delete dbRecords[key]);
      dbOrder.splice(0, dbOrder.length, ...items.map((item) => String(item.id)));
      items.forEach((item) => {
        dbRecords[String(item.id)] = normalizeLibraryRecord(item);
      });
      if (dbOrder.length > 0) {
        dbState.selectedKey = dbOrder[0];
      }
    }

    function renderTaskCards() {
      document.querySelectorAll('[data-task]').forEach((button, index) => {
        const slot = taskSlots[index] || button.dataset.task || 'spindle';
        const item = backendState.taskMap[slot] || taskData[slot] || summarizeTaskFromHistory({}, slot);
        button.dataset.task = slot;
        button.innerHTML = `<span>${escapeHtml(item.title)}</span><strong>${escapeHtml(item.status)}</strong>`;
      });
    }

    function buildProcessMarkdown(result = {}) {
      const rows = result?.process_flow?.data || [];
      if (Array.isArray(rows) && rows.length) {
        return rows.map((row) => {
          const normalized = normalizeProcessRow(row);
          return normalized.code
            ? `- ${normalized.code}: ${normalized.content}`
            : `- ${normalized.content}`;
        }).join('\n');
      }
      return editorTextarea?.value || '';
    }

    function resetProcessStreamState(taskId = '') {
      backendState.processStreamTaskId = String(taskId || '');
      backendState.processStreamText = '';
      backendState.processStreamRows = [];
      twResetState();
    }

    // ── Row typing engine ────────────────────────────────────────────────────
    // Drives field-by-field typewriter animation inside the process spec table.
    // State lives in backendState: twRowQueue, twLineBuffer, twIsTyping,
    // twFieldTimer, twCurrentTr.

    function twResetState() {
      if (backendState.twFieldTimer !== null) {
        clearTimeout(backendState.twFieldTimer);
        backendState.twFieldTimer = null;
      }
      backendState.twRowQueue = [];
      backendState.twLineBuffer = '';
      backendState.twIsTyping = false;
      backendState.twCurrentTr = null;
      backendState.twDoneFlag = false;
      backendState.twAllDoneHandled = false;
      backendState.streamingZoneActive = false;
      const list = processResult?.querySelector('#processStepsList');
      if (list) {
        const typingTr = list.querySelector('.tw-typing-tr');
        if (typingTr) typingTr.remove();
        // 清空已渲染行，确保重新生成时不残留旧数据
        const tbody = list.querySelector('tbody');
        if (tbody) tbody.innerHTML = '';
      }
    }

    function showStreamingZone() {
      if (processEmpty) processEmpty.style.display = 'none';
      if (processResult) processResult.style.display = 'block';
      const list = processResult?.querySelector('#processStepsList');
      if (list && !list.querySelector('.step-table-shell')) {
        list.innerHTML = `<div class="step-table-shell"><table class="step-table"><colgroup><col class="col-step-no"/><col class="col-step-trade"/><col/></colgroup><thead><tr><th>工序号</th><th>工种</th><th>工序名称及内容</th></tr></thead><tbody></tbody></table></div>`;
      }
      backendState.streamingZoneActive = true;
    }

    function hideStreamingZone() {
      backendState.streamingZoneActive = false;
      const list = processResult?.querySelector('#processStepsList');
      if (list) {
        const typingTr = list.querySelector('.tw-typing-tr');
        if (typingTr) typingTr.remove();
      }
    }

    function twParseLine(line) {
      const content = line.startsWith('- ') || line.startsWith('* ') ? line.slice(2).trim() : line;
      if (!content || content.startsWith('#') || /^[-=]{3,}$/.test(content)) return null;
      // Three-part format: 0010@工种@内容
      const m3 = content.match(/^(\d{4})@([^@]*)@(.+)$/);
      if (m3) return { code: m3[1].trim(), tradeType: m3[2].trim(), content: m3[3].trim() };
      // Delimiter fallback (streaming LLM outputs plain delimiter format, no 工种)
      const match = content.match(/^(\d{4})\s*[@:：\-\|,，;；\s]*\s*(.+)$/);
      if (!match) return null;
      const rawContent = match[2].trim();
      // Trade may still be embedded in content ("料@备料...", "数铣@1）..."), extract it
      const split = _splitTradeFromContent(rawContent);
      return { code: match[1].trim(), tradeType: split.tradeType, content: split.content || rawContent };
    }

    function twFeedChar(ch) {
      if (ch === '\n') {
        const line = backendState.twLineBuffer.trim();
        backendState.twLineBuffer = '';
        if (line) {
          const row = twParseLine(line);
          if (row) {
            // Dedup: skip rows already rendered in DOM or waiting in queue
            if (row.code) {
              const tbody = processResult?.querySelector('#processStepsList tbody');
              const inDOM = !!tbody?.querySelector(`tr[data-process-row="${CSS.escape(row.code)}"]`);
              const inQueue = backendState.twRowQueue.some(r => r.code === row.code);
              if (inDOM || inQueue) return;
            }
            backendState.twRowQueue.push(row);
            twKick();
          }
        }
      } else {
        backendState.twLineBuffer += ch;
      }
    }

    function twKick() {
      if (backendState.twIsTyping) return;
      if (backendState.twRowQueue.length) {
        twStartNextRow();
      } else if (backendState.twDoneFlag) {
        twOnAllRowsDone();
      }
    }

    function twStartNextRow() {
      const row = backendState.twRowQueue.shift();
      if (!row) { backendState.twIsTyping = false; return; }
      backendState.twIsTyping = true;

      const list = processResult?.querySelector('#processStepsList');
      if (!list) { backendState.twIsTyping = false; return; }
      let tbody = list.querySelector('tbody');
      if (!tbody) {
        list.innerHTML = `<div class="step-table-shell"><table class="step-table"><colgroup><col class="col-step-no"/><col class="col-step-trade"/><col/></colgroup><thead><tr><th>工序号</th><th>工种</th><th>工序名称及内容</th></tr></thead><tbody></tbody></table></div>`;
        tbody = list.querySelector('tbody');
      }

      const tr = document.createElement('tr');
      tr.className = 'tw-typing-tr';
      tr.setAttribute('data-process-row', row.code || '');
      tr.innerHTML = `<td class="step-no"></td><td class="step-trade" data-step-trade></td><td class="step-content-cell"><div class="step-content" data-process-content contenteditable="true" spellcheck="false"></div></td>`;
      tbody.appendChild(tr);
      backendState.twCurrentTr = tr;

      const shell = list.querySelector('.step-table-shell');
      if (shell) shell.scrollTop = shell.scrollHeight;

      const codeTd = tr.querySelector('.step-no');
      const tradeTd = tr.querySelector('[data-step-trade]');
      const contentTd = tr.querySelector('td:last-child');
      const contentEl = tr.querySelector('[data-process-content]');

      twTypeFieldSequence(tr, [
        { el: codeTd,    td: codeTd,    value: row.code,                speed: 'fast' },
        { el: tradeTd,   td: tradeTd,   value: row.tradeType || '',     speed: 'fast' },
        { el: contentEl, td: contentTd, value: row.content,             speed: 'slow' },
      ], 0, row);
    }

    function twTypeFieldSequence(tr, fields, idx, row) {
      if (idx >= fields.length) {
        twFinishRow(tr, row);
        return;
      }
      const { el, td, value, speed } = fields[idx];
      if (td) td.classList.add('tw-cell-active');
      twTypeField(el, value, speed, () => {
        if (td) td.classList.remove('tw-cell-active');
        backendState.twFieldTimer = setTimeout(() => {
          twTypeFieldSequence(tr, fields, idx + 1, row);
        }, 50 + Math.random() * 55);
      });
    }

    function twTypeField(el, text, speed, onDone) {
      if (!el || !text) { onDone(); return; }
      let i = 0;
      function tick() {
        if (i >= text.length) { onDone(); return; }
        const ch = text[i++];
        el.textContent = text.slice(0, i);

        const shell = processResult?.querySelector('.step-table-shell');
        if (shell) shell.scrollTop = shell.scrollHeight;

        let delay;
        if (speed === 'fast') {
          delay = /\d/.test(ch) ? 14 + Math.random() * 14 : 9 + Math.random() * 9;
        } else {
          if (/[，。、；：！？,.!?]/.test(ch)) delay = 55 + Math.random() * 75;
          else if (/[一-鿿]/.test(ch))         delay = 20 + Math.random() * 20;
          else if (/\d/.test(ch))               delay = 16 + Math.random() * 16;
          else                                  delay = 11 + Math.random() * 11;
        }
        backendState.twFieldTimer = setTimeout(tick, delay);
      }
      tick();
    }

    function twFinishRow(tr, row) {
      tr.classList.remove('tw-typing-tr');
      tr.classList.add('row-new', 'tw-row-completing');
      setTimeout(() => tr.classList.remove('tw-row-completing'), 600);

      // Apply line-break formatting to content after typewriter is done
      const contentEl = tr.querySelector('[data-process-content]');
      if (contentEl && contentEl.textContent) {
        const formatted = processContentForDisplay(contentEl.textContent);
        if (formatted !== contentEl.textContent) {
          contentEl.innerHTML = escapeHtml(formatted).replace(/\n/g, '<br>');
        }
      }

      const tbody = tr.parentNode;
      const doneCount = tbody ? Array.from(tbody.querySelectorAll('tr:not(.tw-typing-tr)')).length : 0;
      setWorkflowThinkingLine(`正在输出第 ${row.code} 道工序`);
      setDemoStepText(String(doneCount));

      // Pause between rows; tracked so twDrainAll can cancel if needed
      const pause = 320 + Math.random() * 280;
      backendState.twFieldTimer = setTimeout(() => {
        backendState.twCurrentTr = null;
        backendState.twIsTyping = false;
        twKick();
      }, pause);
    }

    function twDrainAll() {
      if (backendState.twFieldTimer !== null) {
        clearTimeout(backendState.twFieldTimer);
        backendState.twFieldTimer = null;
      }
      backendState.twIsTyping = false;
      backendState.twRowQueue = [];
      backendState.twLineBuffer = '';
      // Remove in-progress typing row (final render will add all rows cleanly)
      const list = processResult?.querySelector('#processStepsList');
      if (list) {
        const typingTr = list.querySelector('.tw-typing-tr');
        if (typingTr) typingTr.remove();
      }
      backendState.twCurrentTr = null;
    }

    function twOnAllRowsDone() {
      if (backendState.twAllDoneHandled) return;
      backendState.twAllDoneHandled = true;

      hideStreamingZone();
      setWorkflowState('工艺生成完成', 100, false);
      setDemoResultChipText('工艺已生成');
      setDemoStatusText('生成完成');
      if (processEmpty) processEmpty.style.display = 'none';
      if (processResult) processResult.style.display = 'block';

      // Append any rows from processStreamText not yet typed — dedup by code
      const list = processResult?.querySelector('#processStepsList');
      const tbody = list?.querySelector('tbody');
      const finalRows = parseStreamingProcessRows(backendState.processStreamText);

      // No parseable rows at all — fetch result from backend as fallback
      if (!finalRows.length) {
        const capturedTaskId = backendState.processStreamTaskId;
        if (capturedTaskId) {
          apiFetch(`/result/${encodeURIComponent(capturedTaskId)}`).then((r) => {
            if (r && r.process_flow) renderProcessFromResult(r);
            else twSyncCompletion();
          }).catch(() => twSyncCompletion());
        }
        return;
      }

      if (tbody && finalRows.length) {
        const renderedCodes = new Set(
          Array.from(tbody.querySelectorAll('tr[data-process-row]'))
            .map(tr => tr.getAttribute('data-process-row'))
            .filter(Boolean)
        );
        const missingRows = finalRows.filter(r => {
          const n = normalizeProcessRow(r);
          return n.code && !renderedCodes.has(n.code);
        });
        const baseCount = tbody.children.length;
        const shell = list.querySelector('.step-table-shell');
        missingRows.forEach((row, i) => {
          setTimeout(() => {
            const n = normalizeProcessRow(row);
            if (tbody.querySelector(`tr[data-process-row="${CSS.escape(n.code)}"]`)) return;
            const tr = document.createElement('tr');
            tr.setAttribute('data-process-row', n.code || '');
            tr.className = 'row-new';
            tr.style.setProperty('--row-idx', String(baseCount + i));
            tr.innerHTML = `<td class="step-no">${escapeHtml(n.code || '----')}</td><td class="step-trade" data-step-trade>${escapeHtml(n.tradeType || '')}</td><td class="step-content-cell"><div class="step-content" data-process-content contenteditable="true" spellcheck="false">${formatContentHtml(n.content)}</div></td>`;
            tbody.appendChild(tr);
            setDemoStepText(String(tbody.children.length));
            if (shell) shell.scrollTop = shell.scrollHeight;
          }, i * 80);
        });
        const syncDelay = missingRows.length * 80 + 350;
        setTimeout(() => twSyncCompletion(), syncDelay);
      } else {
        setTimeout(() => twSyncCompletion(), 200);
      }
    }

    function twSyncCompletion() {
      const rows = parseStreamingProcessRows(backendState.processStreamText);
      if (editorTextarea) {
        editorTextarea.value = rows.map(r => {
          const n = normalizeProcessRow(r);
          return n.code ? `- ${n.code}: ${n.content}` : `- ${n.content}`;
        }).join('\n');
      }
      refreshEditorPreview();
      updateExportCardButtonState();
      setDemoResultChipText('工艺已生成');
      setDemoStatusText('生成完成');
      setWorkflowState('工艺生成完成', 100, false);
      const capturedTaskId = backendState.processStreamTaskId;
      if (capturedTaskId) {
        apiFetch(`/result/${encodeURIComponent(capturedTaskId)}`).then((result) => {
          if (!result) return;
          backendState.latestResult = result;
          cacheHistoryResult(capturedTaskId, result);
          renderReviewFromResult(result, { activate: false });
          renderHistoryPage();
        }).catch(() => {});
      }
    }
    // ─────────────────────────────────────────────────────────────────────────

    function queueProcessStreamChunk(taskId, chunk) {
      if (!chunk || backendState.streamingDone) return;
      const normalizedTaskId = String(taskId || '');
      if (backendState.processStreamTaskId !== normalizedTaskId) {
        resetProcessStreamState(normalizedTaskId);
      }
      if (!backendState.streamingZoneActive) {
        showStreamingZone();
      }
      // Accumulate full text for the complete-handler final render
      backendState.processStreamText += String(chunk);
      // Feed char-by-char to the row typing engine
      for (const ch of String(chunk)) {
        twFeedChar(ch);
      }
    }

    function parseStreamingProcessRows(text = '') {
      const rows = [];
      const seen = new Set();
      String(text || '').split(/\r?\n/).forEach((line) => {
        const current = line.trim();
        if (!current || current.startsWith('#') || current.startsWith('|') || /^[-=]{3,}$/.test(current)) return;
        const content = current.startsWith('- ') || current.startsWith('* ') ? current.slice(2).trim() : current;
        // Three-part: 0010@工种@内容
        const m3 = content.match(/^(\d{4})@([^@]*)@(.+)$/);
        if (m3) {
          const code = m3[1].trim(), trade = m3[2].trim(), value = m3[3].trim();
          const key = `${code}::${value}`;
          if (!seen.has(key)) { seen.add(key); rows.push([code, trade, value]); }
          return;
        }
        // Two-part or delimiter fallback
        const match = content.match(/^(\d{4})\s*[@:：\-\|,，;；\s]*\s*(.+)$/);
        if (!match) return;
        const code = match[1].trim();
        const value = match[2].trim();
        const key = `${code}::${value}`;
        if (seen.has(key)) return;
        seen.add(key);
        rows.push([code, '', value]);
      });
      return rows;
    }

    const PROCESS_PRESET_TRADES = ['划线工','车工','铣工','钻工','镗工','磨工','钳工','热处理','检验','其他'];
    const PROCESS_TRADE_COLOR = { '热处理': 'green', '检验': 'orange' };

    function openProcessRowEdit(tr) {
      if (!tr) return;
      const openRow = tr.closest('table')?.querySelector('tr.process-row-editing');
      if (openRow && openRow !== tr) closeProcessRowEdit(openRow, false);
      tr.classList.add('process-row-editing');
      const trade = tr.dataset.trade || '';
      const content = tr.dataset.content || tr.querySelector('[data-process-content]')?.textContent.trim() || '';
      const code = tr.querySelector('.step-no')?.textContent.trim() || tr.dataset.processRow || '';
      tr.dataset.origTrade = trade;
      tr.dataset.origContent = content;
      const isCustom = trade && !PROCESS_PRESET_TRADES.slice(0, -1).includes(trade);
      const selVal = isCustom ? '其他' : trade;
      const tradeCell = tr.querySelector('td.step-trade');
      const contentCell = tr.querySelector('td.step-content-cell');
      const opCell = tr.querySelector('td.step-op');
      if (tradeCell) {
        tradeCell.innerHTML = `<div class="trade-edit"><select class="process-trade-select">${PROCESS_PRESET_TRADES.map((t) => `<option${t === selVal ? ' selected' : ''}>${escapeHtml(t)}</option>`).join('')}</select><input type="text" class="process-custom-trade" placeholder="输入工种名称" value="${escapeHtml(isCustom ? trade : '')}" style="display:${isCustom ? 'block' : 'none'}"/></div>`;
      }
      if (contentCell) {
        contentCell.innerHTML = `<textarea class="process-content-edit">${escapeHtml(content)}</textarea>`;
      }
      if (opCell) {
        opCell.innerHTML = `<div class="step-edit-actions"><button class="button primary sm" data-process-save="${escapeHtml(code)}">保存</button><button class="button secondary sm" data-process-cancel="${escapeHtml(code)}">取消</button></div>`;
      }
    }

    function closeProcessRowEdit(tr, save) {
      if (!tr) return;
      tr.classList.remove('process-row-editing');
      const tradeSelect = tr.querySelector('.process-trade-select');
      const customInput = tr.querySelector('.process-custom-trade');
      const contentTextarea = tr.querySelector('.process-content-edit');
      const code = tr.querySelector('.step-no')?.textContent.trim() || tr.dataset.processRow || '';
      let trade = tr.dataset.origTrade || '';
      let content = tr.dataset.origContent || '';
      if (save) {
        if (tradeSelect) {
          trade = tradeSelect.value;
          if (trade === '其他' && customInput) trade = customInput.value.trim() || '其他';
        }
        if (contentTextarea) content = contentTextarea.value;
        tr.dataset.trade = trade;
        tr.dataset.content = content;
      }
      const badgeClass = PROCESS_TRADE_COLOR[trade] || 'blue';
      const tradeCell = tr.querySelector('td.step-trade');
      const contentCell = tr.querySelector('td.step-content-cell');
      const opCell = tr.querySelector('td.step-op');
      if (tradeCell) tradeCell.innerHTML = `<span class="trade-badge trade-badge-${badgeClass}">${escapeHtml(trade)}</span>`;
      if (contentCell) {
        const div = document.createElement('div');
        div.className = 'step-content';
        div.setAttribute('data-process-content', '');
        div.contentEditable = 'true';
        div.spellcheck = false;
        div.textContent = content;
        contentCell.innerHTML = '';
        contentCell.appendChild(div);
      }
      if (opCell) opCell.innerHTML = `<button class="step-edit-btn" data-process-edit="${escapeHtml(code)}">编辑</button>`;
      if (save) syncProcessTableToEditor();
    }

    function renderProcessRowsSurface(rows = [], options = {}) {
      const taskId = options.taskId || backendState.currentProcessTaskId || backendState.latestTaskId || '';
      const result = options.result || backendState.latestResult || {};
      const live = !!options.live;
      const markdown = String(options.markdown || '').trim();

      if (taskId) backendState.currentProcessTaskId = taskId;
      if (result && (result.task_id || result.process_flow)) {
        cacheHistoryResult(result.task_id || taskId || backendState.latestTaskId, result);
      }

      if (!Array.isArray(rows) || !rows.length) {
        if (live) {
          if (processEmpty) processEmpty.style.display = 'flex';
          if (processResult) processResult.style.display = 'none';
          setDemoStatusText('工艺生成中');
          setDemoResultChipText('工艺生成中');
          setDemoStepText('0');
          return;
        }
        return;
      }

      if (processEmpty) processEmpty.style.display = 'none';
      if (processResult) processResult.style.display = 'block';
      setDemoStatusText(result.status || (live ? '工艺生成中' : '生成完成'));
      setDemoResultChipText(live ? '工艺生成中' : (result.status === 'completed' ? '工艺已生成' : '处理中'));
      setDemoHitText(String((result.rag_results?.matches || []).length || 0));
      setDemoStepText(String(rows.length));

      const list = processResult?.querySelector('#processStepsList');
      if (list) {
        if (live) {
          // Live DOM is owned by the row typing engine — nothing to do here.
        } else {
          list.innerHTML = `
            <div class="step-table-shell">
              <table class="step-table">
                <colgroup>
                  <col class="col-step-no" />
                  <col class="col-step-trade" />
                  <col />
                  <col class="col-step-op" />
                </colgroup>
                <thead>
                  <tr>
                    <th>工序号</th>
                    <th>工种</th>
                    <th>工序名称及内容</th>
                    <th class="th-op">操作</th>
                  </tr>
                </thead>
                <tbody>
                  ${rows.map((row) => {
                    const normalized = normalizeProcessRow(row);
                    const trade = normalized.tradeType || '';
                    const badgeClass = PROCESS_TRADE_COLOR[trade] || 'blue';
                    return `<tr data-process-row="${escapeHtml(normalized.code || '')}" data-trade="${escapeHtml(trade)}" data-content="${escapeHtml(normalized.content || '')}"><td class="step-no">${escapeHtml(normalized.code || '----')}</td><td class="step-trade"><span class="trade-badge trade-badge-${badgeClass}">${escapeHtml(trade)}</span></td><td class="step-content-cell"><div class="step-content" data-process-content contenteditable="true" spellcheck="false">${formatContentHtml(normalized.content)}</div></td><td class="step-op"><button class="step-edit-btn" data-process-edit="${escapeHtml(normalized.code || '')}">编辑</button></td></tr>`;
                  }).join('')}
                </tbody>
              </table>
            </div>
          `;
        }
      }

      if (editorTextarea) {
        editorTextarea.value = markdown || rows.map((row) => {
          const normalized = normalizeProcessRow(row);
          return normalized.code
            ? `- ${normalized.code}: ${normalized.content}`
            : `- ${normalized.content}`;
        }).join('\n');
      }
      refreshEditorPreview();
      updateExportCardButtonState();

      if (!live) {
        renderHistoryPage();
      }

      if (processResult && rows.length) {
        setTimeout(() => { processResult.scrollTop = processResult.scrollHeight; }, 50);
      }
    }

    function renderProcessFromResult(result = {}) {
      const processFlow = result.process_flow || {};
      const rows = Array.isArray(processFlow.data) ? processFlow.data : [];
      if (!rows.length) {
        if (result.task_id) backendState.currentProcessTaskId = result.task_id;
        cacheHistoryResult(result.task_id || backendState.latestTaskId, result);
        renderUploadedPreviewFromResult(result);
        dispose3DPreview(); setTimeout(() => render3DPreview(result.gltf_url || null, "model3DContainer"), 100);
        if (processEmpty) processEmpty.style.display = 'flex';
        if (processResult) processResult.style.display = 'none';
        setWorkflowState(result.status === 'completed' ? '工艺生成完成' : '工艺生成中', result.status === 'completed' ? 100 : (Number(result.progress) || backendState.taskProgress || 0), false);
        setDemoStatusText(result.status || '生成完成');
        setDemoHitText(String((result.rag_results?.matches || []).length || 0));
        setDemoStepText('0');
        setDemoResultChipText(result.status === 'completed' ? '工艺已生成' : '处理中');
        renderHistoryPage();
        return;
      }
      if (result.task_id) backendState.currentProcessTaskId = result.task_id;
      cacheHistoryResult(result.task_id || backendState.latestTaskId, result);

      setWorkflowState(result.status === 'completed' ? '工艺生成完成' : '工艺生成中', result.status === 'completed' ? 100 : (Number(result.progress) || backendState.taskProgress || 0), false);
      renderUploadedPreviewFromResult(result);
      dispose3DPreview(); setTimeout(() => render3DPreview(result.gltf_url || null, "model3DContainer"), 100);
      renderProcessRowsSurface(rows, { result, markdown: buildProcessMarkdown(result), live: false });
      activateResultView('view-process');
      focusProcessWorkspace();
    }

    function renderUploadedPreviewFromResult(result = {}) {
      const fileName = result.pdf_name || result.file_name || backendState.latestResult?.pdf_name || '后端任务';
      const processCount = parseProcessCount(result);
      const nextPreviewTaskId = String(result.task_id || backendState.latestTaskId || '').trim();
      const isSamePreviewTask = !!nextPreviewTaskId && backendState.previewTaskId === nextPreviewTaskId;
      const existingShell = uploadPanelBody?.querySelector('.task-preview-shell');
      backendState.previewTaskId = nextPreviewTaskId;
      const newPreviewImages = normalizePreviewImages(result);
      if (newPreviewImages.length > 0) {
        backendState.previewImages = newPreviewImages;
      }
      clampPreviewIndex();
      if (uploadPanelBody && (!isSamePreviewTask || !existingShell)) {
        uploadPanelBody.innerHTML = `
        <div class="task-preview-shell">
          <div class="task-preview-head">
            <div>
              <div class="section-label">图纸预览</div>
              <div class="summary-note">${escapeHtml(fileName)}</div>
            </div>
            <div class="task-preview-toolbar">
              <button class="button secondary task-preview-btn" id="taskPreviewPrevBtn">← 上页</button>
              <span class="task-preview-counter" id="taskPreviewCounter">0 / 0</span>
              <button class="button secondary task-preview-btn" id="taskPreviewNextBtn">下页 →</button>
              <button class="button secondary task-preview-btn" id="taskPreviewZoomOutBtn">缩小</button>
              <span class="task-preview-zoom" id="taskPreviewZoomLabel">100%</span>
              <button class="button secondary task-preview-btn" id="taskPreviewZoomInBtn">放大</button>
              <button class="button secondary task-preview-btn" id="taskPreviewResetBtn">重置</button>
              <button class="button secondary task-preview-btn" id="taskPreviewFullscreenBtn">全屏</button>
            </div>
          </div>
          <div class="task-preview-stage">
            <div class="task-preview-empty" id="taskPreviewEmpty">
              <div class="glyph blue">▣</div>
              <div class="dropzone-title" style="font-size:22px; margin:0;">等待图纸解析</div>
              <div class="dropzone-copy" style="font-size:14px; max-width:90%;">图纸页面生成后将自动显示在此处。</div>
            </div>
            <img id="taskPreviewImage" class="task-preview-image" alt="图纸预览" style="display:none;" />
          </div>
        </div>
      `;
      } else {
        const summary = existingShell.querySelector('.summary-note');
        if (summary) summary.textContent = fileName;
      }
      setStageState(3);
      updateTaskPreviewSurface();
    }

    function parseReviewFields(text = '') {
      const fields = [];
      let current = null;
      String(text || '').split(/\r?\n/).forEach((line) => {
        const trimmed = line.trim();
        if (!trimmed) return;
        const match = trimmed.match(/^【([^】]+)】\s*(.*)$/);
        if (match) {
          const label = match[1].trim();
          if (_isFeatureNoiseLabel(label)) { current = null; return; }
          current = { label, value: match[2].trim() };
          fields.push(current);
        } else if (current) {
          current.value = current.value ? current.value + '\n' + trimmed : trimmed;
        }
      });
      if (!fields.length) {
        const raw = String(text || '').trim();
        if (raw) fields.push({ label: '审阅内容', value: raw });
      }
      return fields;
    }

    function currentExportTaskId() {
      return backendState.currentProcessTaskId || backendState.latestResult?.task_id || backendState.currentReviewTaskId || backendState.latestTaskId || '';
    }

    async function downloadExport(format) {
      const taskId = currentExportTaskId();
      if (!taskId) return;
      const rows = readProcessTable();
      const url = `${API_BASE}/export/${encodeURIComponent(taskId)}?format=${format}`;
      try {
        const resp = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ rows }),
        });
        if (!resp.ok) { console.error('Export failed', resp.status); return; }
        const blob = await resp.blob();
        const objUrl = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = objUrl;
        a.download = (format === 'pdf' ? 'ProcessCard' : 'Process') + '_' + taskId.slice(0, 8) + '.' + format;
        document.body.appendChild(a);
        a.click();
        setTimeout(() => { document.body.removeChild(a); URL.revokeObjectURL(objUrl); }, 1000);
      } catch (e) {
        console.error('Export error', e);
      }
    }

    function updateExportCardButtonState() {
      const openExportCardBtn = getOpenExportCardBtn();
      if (!openExportCardBtn) return;
      openExportCardBtn.disabled = !backendState.currentProcessTaskId;
    }

    function fillExportModal(taskId, result) {
      const sourceName = result.source_name || result.pdf_name || taskId;
      const processFlow = result.process_flow || {};
      const rows = Array.isArray(processFlow.data) ? processFlow.data : [];
      let featureText = result.feature_report_text || result.expert_judgment || '';
      // For feature_report_text format, keep only the 4 info fields
      if (result.feature_report_text) {
        featureText = filterInfoFields(featureText);
      }

      exportModalMeta.textContent = '任务ID：' + taskId + '  |  文件：' + sourceName;

      // Info block
      let infoHtml = '';
      if (sourceName) infoHtml += '<div><span class="label">文件名称</span> <span class="value">' + escapeHtml(sourceName) + '</span></div>';
      if (taskId) infoHtml += '<div><span class="label">任务ID</span> <span class="value">' + escapeHtml(taskId) + '</span></div>';
      if (featureText) {
        infoHtml += '<div style="margin-top:6px;font-size:12px;line-height:1.6;white-space:pre-wrap;">' + escapeHtml(featureText) + '</div>';
      }
      exportModalInfo.innerHTML = infoHtml || '暂无信息';

      // Use API-provided preview URL (covers both PDF pages/ and PRT creo_views/)
      const preferredUrl = result.image_url
        || (result.preview_image_urls && result.preview_image_urls.length > 0 ? result.preview_image_urls[0] : '');
      let imageUrl;
      if (preferredUrl) {
        imageUrl = API_BASE.replace(/\/api$/, '') + preferredUrl;
      } else {
        imageUrl = API_BASE + '/result/' + encodeURIComponent(taskId) + '/asset/pages/page_1.png';
      }
      exportModalImage.src = imageUrl;
      exportModalImage.style.display = 'block';
      exportModalImagePlaceholder.style.display = 'none';
      exportModalImage.onerror = function() {
        exportModalImage.style.display = 'none';
        exportModalImagePlaceholder.style.display = 'block';
        exportModalImagePlaceholder.textContent = '未找到预览图';
      };

      // Process table
      renderExportTable(rows);
    }

    function fillExportModalFallback(taskId) {
      exportModalMeta.textContent = '任务ID：' + taskId;
      exportModalInfo.innerHTML = '<div><span class="label">任务ID</span> <span class="value">' + escapeHtml(taskId) + '</span></div>';
      exportModalImage.style.display = 'none';
      exportModalImagePlaceholder.style.display = 'block';
      exportModalImagePlaceholder.textContent = '无法加载图片';
      renderExportTable([]);
    }

    function renderExportTable(rows) {
      const tbody = exportModalTable.querySelector('tbody');
      if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="3" class="empty-row">暂无工艺数据</td></tr>';
        return;
      }
      tbody.innerHTML = rows.map(function(r) {
        const code = Array.isArray(r) ? String(r[0] || '').trim() : '';
        const trade = Array.isArray(r) ? String(r[1] || '').trim() : '';
        const content = Array.isArray(r) ? String(r[2] || '').trim() : String(r || '');
        return '<tr>' +
          '<td class="step-code">' + escapeHtml(code) + '</td>' +
          '<td class="step-trade">' + escapeHtml(trade) + '</td>' +
          '<td class="step-content">' + escapeHtml(content) + '</td>' +
        '</tr>';
      }).join('');
    }

    function closeExportModal() {
      if (!exportModal) return;
      exportModal.classList.remove('open');
      document.body.style.overflow = '';
      exportModalImage.removeAttribute('src');
    }

    function openExportEngineeringCard() {
      const taskId = currentExportTaskId();
      if (!taskId) {
        if (reviewStatusBadge) {
          reviewStatusBadge.textContent = '暂无可导出任务';
          reviewStatusBadge.className = 'status-badge danger';
        }
        return;
      }
      // Snapshot current DOM rows now (sync) so user edits are captured
      const domRows = readProcessTable().map(function(r) {
        return [r.code, r.tradeType || '', r.content];
      });

      exportModalMeta.textContent = '加载任务 ' + taskId + ' 数据...';
      exportModalImage.style.display = 'none';
      exportModalImagePlaceholder.style.display = 'block';
      exportModalImagePlaceholder.textContent = '加载中...';
      exportModalInfo.innerHTML = '加载中...';
      exportModalTable.querySelector('tbody').innerHTML = '<tr><td colspan="3" class="empty-row">加载中...</td></tr>';
      document.body.style.overflow = 'hidden';
      exportModal.classList.add('open');

      apiFetch('/result/' + encodeURIComponent(taskId)).then(function(result) {
        if (!result) { fillExportModalFallback(taskId); return; }
        // Prefer live DOM rows over stored result so edits are always reflected
        if (domRows.length) {
          result = Object.assign({}, result, {
            process_flow: Object.assign({}, result.process_flow || {}, { data: domRows }),
          });
        }
        fillExportModal(taskId, result);
        cacheHistoryResult(taskId, result);
      }).catch(function() {
        fillExportModalFallback(taskId);
      });
    }

    function readReviewTable() {
      if (!reviewTableHost) return [];
      const rows = [...reviewTableHost.querySelectorAll('tbody tr')];
      const hasSections = rows.some(function(r) { return r.hasAttribute('data-review-section'); });

      if (hasSections) {
        return readReviewTableSections(rows);
      }

      return rows.map(function(row) {
        const index = Number(row.getAttribute('data-review-index') || '0');
        const labelEl = row.querySelector('[data-review-label]');
        const valueEl = row.querySelector('[data-review-value]');
        const label = (labelEl && labelEl.textContent || '').trim();
        const value = (valueEl && 'value' in valueEl ? valueEl.value : valueEl && valueEl.textContent || '').trim();
        return { index: index, label: label, value: value };
      }).filter(function(field) { return field.label || field.value; });
    }

    function serializeReviewFields(fields, sections) {
      // If sections are provided, output v5 section-delimited format
      if (sections && sections.length) {
        return serializeReviewSections(sections);
      }
      return (fields || [])
        .map(function(field) { return '【' + (field.label || '未命名') + '】' + (field.value || ''); })
        .join('\n');
    }

    function readReviewTableSections(rows) {
      // Reconstruct sections from DOM rows with data-review-section attr
      var sections = [];
      var sectionMap = {};
      rows.forEach(function(row) {
        var sectionIdx = row.getAttribute('data-review-section');
        if (!sectionIdx) return;
        var key = String(sectionIdx);
        if (!sectionMap[key]) {
          sectionMap[key] = { title: '', fields: [], subSections: [], uncertainItems: [] };
        }
        var labelEl = row.querySelector('[data-review-label]');
        var valueEl = row.querySelector('[data-review-value]');
        var label = (labelEl && labelEl.textContent || '').trim();
        var value = (valueEl && 'value' in valueEl ? valueEl.value : valueEl && valueEl.textContent || '').trim();
        if (!label && !value) return;
        sectionMap[key].fields.push({ label: label, value: value });
      });
      // Read section titles from separator rows
      rows.forEach(function(row) {
        var sectionIdx = row.getAttribute('data-section-idx');
        if (sectionIdx !== null && sectionIdx !== undefined) {
          var key = String(sectionIdx);
          if (sectionMap[key]) {
            sectionMap[key].title = (row.textContent || '').trim();
          }
        }
      });
      // Preserve section order
      var seen = {};
      rows.forEach(function(row) {
        var sectionIdx = row.getAttribute('data-review-section');
        if (!sectionIdx) return;
        var key = String(sectionIdx);
        if (!seen[key]) {
          seen[key] = true;
          sections.push(sectionMap[key]);
        }
      });
      return sections;
    }

    function serializeReviewSections(sections) {
      var lines = [];
      sections.forEach(function(section, si) {
        if (section.title) {
          lines.push('━━━ ' + section.title + ' ━━━');
        }
        (section.fields || []).forEach(function(f) {
          lines.push('【' + (f.label || '') + '】' + (f.value || ''));
        });
      });
      return lines.join('\n');
    }

    function readProcessTable() {
      const list = processResult?.querySelector('#processStepsList');
      if (!list) return [];
      return [...list.querySelectorAll('[data-process-row]')].map((row) => {
        const code = String(row.getAttribute('data-process-row') || row.querySelector('.step-no')?.textContent || '').trim();
        const tradeType = String(row.dataset.trade || row.querySelector('[data-step-trade]')?.textContent || '').trim();
        const contentEl = row.querySelector('[data-process-content]');
        const rawHtml = contentEl ? contentEl.innerHTML : '';
        const content = String(
          rawHtml
            ? rawHtml.replace(/<br\s*\/?>/gi, '\n').replace(/<[^>]+>/g, '')
            : row.dataset.content || ''
        ).trim();
        return { code, tradeType, content };
      }).filter((row) => row.code || row.content);
    }

    function syncProcessTableToEditor() {
      const rows = readProcessTable();
      if (!rows.length) return;
      const markdown = rows.map((row) => (row.code ? `- ${row.code}: ${row.content}` : `- ${row.content}`)).join('\n');
      if (editorTextarea) editorTextarea.value = markdown;
      refreshEditorPreview();
      updateExportCardButtonState();
      if (backendState.latestResult?.process_flow) {
        backendState.latestResult = {
          ...backendState.latestResult,
          process_flow: {
            ...(backendState.latestResult.process_flow || {}),
            data: rows.map((row) => [row.code, row.tradeType || '', row.content]),
          },
        };
      }
    }

    function syncReviewTextarea() {
      const fields = readReviewTable();
      const reviewText = serializeReviewFields(fields);
      backendState.reviewDirty = true;
      if (reviewTextarea) {
        reviewTextarea.value = reviewText;
      }
      backendState.latestReviewPayload = {
        ...(backendState.latestReviewPayload || {}),
        content: reviewText,
        fields,
      };
      if (reviewStatusBadge && fields.length) {
        reviewStatusBadge.textContent = `已加载 ${fields.length} 项特征`;
        reviewStatusBadge.className = 'status-badge success';
      }
    }

    function renderReviewTable(payload = {}, options = {}) {
      backendState.currentReviewTaskId = payload.task_id || backendState.currentReviewTaskId || backendState.latestTaskId || '';
      const content = payload.content || payload.review_text || payload.raw_content || backendState.latestResult?.review_text || '';
      const fields = parseReviewFields(content);
      backendState.latestReviewPayload = {
        ...payload,
        content,
        fields,
      };

      if (reviewTableHost) {
        reviewTableHost.innerHTML = `
          <table class="step-table review-table">
            <colgroup>
              <col class="col-step-no" />
              <col />
            </colgroup>
            <thead>
              <tr>
                <th>字段</th>
                <th>内容</th>
              </tr>
            </thead>
            <tbody>
              ${fields.map((field, index) => `
                <tr data-review-row="${index}">
                  <td class="step-no" data-review-label>${escapeHtml(field.label)}</td>
                  <td><div class="step-content review-content" data-review-value contenteditable="true" spellcheck="false">${escapeHtml(field.value)}</div></td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        `;
      }

      if (reviewTextarea) {
        reviewTextarea.value = serializeReviewFields(fields);
      }
      if (reviewSourceNote) {
        reviewSourceNote.textContent = payload.message || `已收到 ${fields.length} 项特征，内容可编辑，字段名固定。`;
      }
      backendState.reviewDirty = false;
      if (reviewContinueBtn) reviewContinueBtn.disabled = false;
      if (reviewRerunBtn) reviewRerunBtn.disabled = false;
      if (options.activate !== false) {
        activateResultView('view-review');
      }
    }

    function renderReviewFromResult(result = {}, options = {}) {
      cacheHistoryResult(result.task_id || backendState.latestTaskId, result);
      renderReviewTable({
        task_id: result.task_id || backendState.latestTaskId || '',
        title: '后端工艺结果',
        content: result.review_text || result.feature_report || '',
        raw_content: result.raw_review_text || '',
        message: result.status === 'completed' ? '后端工艺已完成，可继续查看或编辑特征。' : '已从后端加载审阅结果。',
      }, { activate: options.activate });
      if (options.activate !== false) {
        activateResultView('view-review');
      }
      renderHistoryPage();
    }

    function setReviewFeedback(message, tone = 'warn', stepMessage = '') {
      if (reviewSourceNote) {
        reviewSourceNote.textContent = stepMessage || message;
      }
    }

    async function fetchReviewTaskSnapshot(taskId) {
      if (!taskId) return null;
      try {
        return await apiFetch(`/result/${encodeURIComponent(taskId)}`);
      } catch (error) {
        console.warn('[demo] failed to fetch review task snapshot:', error);
        return null;
      }
    }

    async function submitReview(action) {
      const taskId = backendState.latestReviewPayload?.task_id || backendState.currentReviewTaskId || backendState.latestTaskId;
      activateResultView('view-process');
      focusProcessWorkspace();
      backendState.streamingDone = false;
      resetProcessStreamState(taskId);
      if (!taskId) {
        setReviewFeedback('暂无可继续的任务', 'danger');
        return;
      }
      // Set early so SSE review_required events don't switch the tab back while awaiting
      backendState.reviewSubmittedForTaskId = taskId;

      const fields = readReviewTable();
      const reviewText = serializeReviewFields(fields).trim() || (backendState.latestReviewPayload?.content || '').trim();
      if (!reviewText) {
        setReviewFeedback('审阅内容为空', 'danger');
        return;
      }

      const taskSnapshot = await fetchReviewTaskSnapshot(taskId);
      const currentStatus = String(taskSnapshot?.status || '').trim();
      if (action !== 'rerun' && currentStatus && currentStatus !== 'awaiting_review') {
        const detail = currentStatus === 'completed'
          ? '该任务已经完成工艺生成，请不要再提交旧审阅。'
          : `该任务当前状态为 ${currentStatus}，不是等待审阅状态。`;
        setReviewFeedback('任务不在待审阅状态', 'danger', detail);
        return;
      }
      if (action === 'rerun' && currentStatus && !['completed', 'error', 'processing', 'awaiting_review'].includes(currentStatus)) {
        setReviewFeedback('任务当前不可重新生成', 'danger', `后端状态为 ${currentStatus}，暂时不能执行重新生成。`);
        return;
      }

      if (reviewContinueBtn) reviewContinueBtn.disabled = true;
      if (reviewRerunBtn) reviewRerunBtn.disabled = true;

      setReviewFeedback(
        action === 'rerun' ? '正在重新生成' : '已提交，等待继续',
        'warn',
        action === 'rerun'
          ? '后端正在使用修改后的特征重新生成工艺。'
          : '后端正在继续生成工艺，请稍候。'
      );
      setDemoStatusText(action === 'rerun' ? '重新生成中' : '待继续生成');
      setDemoResultChipText(action === 'rerun' ? '重新生成中' : '特征已确认');

      setWorkflowState(action === 'rerun' ? '重新生成中' : '等待后端继续生成', action === 'rerun' ? 65 : 55, true);
      updateExportCardButtonState();
      if (processEmpty) {
        processEmpty.style.display = 'flex';
        const title = processEmpty.querySelector('.dropzone-title');
        const copy = processEmpty.querySelector('.dropzone-copy');
        if (title) title.textContent = '工艺正在生成';
        if (copy) copy.textContent = action === 'rerun'
          ? '已提交修改后的特征，后端正在重新生成工艺规程。'
          : '特征已确认，后端正在继续生成工艺规程，请稍候。';
      }
      if (processResult) processResult.style.display = 'none';

      try {
        await apiFetch(`/review/${encodeURIComponent(taskId)}`, {
          method: 'POST',
          body: JSON.stringify({ review_text: reviewText, action, library_key: backendState.retrievalLibraryKey || 'public' }),
        });

        backendState.currentReviewTaskId = taskId;
        backendState.latestReviewPayload = {
          ...(backendState.latestReviewPayload || {}),
          task_id: taskId,
          content: reviewText,
          fields,
        };
        backendState.reviewDirty = false;
        backendState.reviewRenderedForTask = '';

        followTaskProgress(taskId);
      } catch (error) {
        console.error(error);
        if (reviewContinueBtn) reviewContinueBtn.disabled = false;
        if (reviewRerunBtn) reviewRerunBtn.disabled = false;
        setWorkflowState('等待审阅', 50, false);
        activateResultView('view-review');
        if (processEmpty) processEmpty.style.display = 'none';
        if (processResult) processResult.style.display = 'none';
        setReviewFeedback('审阅提交失败', 'danger', error.message || '后端拒绝了本次审阅提交。');
      }
    }

    function disconnectTaskEvents() {
      if (backendState.reviewEventSource) {
        backendState.reviewEventSource.close();
        backendState.reviewEventSource = null;
      }
    }

    function connectTaskEvents(taskId) {
      if (!taskId || typeof EventSource === 'undefined') return;
      disconnectTaskEvents();
      const source = new EventSource(`${API_BASE}/events/${encodeURIComponent(taskId)}`);
      backendState.reviewEventSource = source;

      source.addEventListener('review_required', (event) => {
        try {
          const payload = JSON.parse(event.data || '{}');
          backendState.latestTaskId = taskId;
          backendState.currentReviewTaskId = taskId;
          // Always update latestReviewPayload so submitReview has the right task_id,
          // but skip re-rendering the table if user already confirmed this review.
          if (!backendState.reviewSubmittedForTaskId || backendState.reviewSubmittedForTaskId !== taskId) {
            backendState.latestReviewPayload = payload;
          }
          backendState.reviewRenderedForTask = taskId;
          cacheHistoryResult(taskId, payload);
          setWorkflowState('等待特征审阅', 50, false);
          setDemoStatusText('等待审阅');
          setDemoResultChipText('特征待确认');
          appendWorkflowLiveEntry('REVIEW', payload.message || '特征已提取，等待确认', 'step');
          // 左侧面板：建立 3D 容器，有 glTF 则渲染真实模型，无则占位方块
          renderUploadedPreviewFromResult({ task_id: taskId, pdf_name: payload.title || taskId });
          dispose3DPreview();
          setTimeout(() => render3DPreview(payload.gltf_url || null, "model3DContainer"), 150);
          // Don't overwrite user edits if they've already submitted this review
          if (backendState.reviewSubmittedForTaskId !== taskId) {
            renderReviewTable(payload);
          }
          renderHistoryPage();
        } catch (error) {
          console.warn('[demo] review_required parse failed:', error);
        }
      });

      source.addEventListener('step_start', (event) => {
        try {
          const payload = JSON.parse(event.data || '{}');
          appendWorkflowLiveEntry(`STEP ${String(payload.step || '').padStart(2, '0')}`, `${payload.name || '步骤'} · ${payload.message || '开始'}`, 'step');
        } catch (error) {
          console.warn('[demo] step_start parse failed:', error);
        }
      });

      source.addEventListener('step_complete', (event) => {
        try {
          const payload = JSON.parse(event.data || '{}');
          appendWorkflowLiveEntry(`STEP ${String(payload.step || '').padStart(2, '0')}`, `${payload.name || '步骤'} · ${payload.result || '完成'}`, 'step');
        } catch (error) {
          console.warn('[demo] step_complete parse failed:', error);
        }
      });

      source.addEventListener('image_ready', (event) => {
        try {
          const payload = JSON.parse(event.data || '{}');
          appendWorkflowLiveEntry(`PAGE ${payload.page || 0}/${payload.total || 0}`, payload.message || '页面已生成', 'step');
          const url = payload.url ? (API_BASE.replace('/api', '') + payload.url) : '';
          if (url && !backendState.previewImages.includes(url)) {
            backendState.previewImages.push(url);
            updateTaskPreviewSurface();
          }
        } catch (error) {
          console.warn('[demo] image_ready parse failed:', error);
        }
      });

      source.addEventListener('log', () => {});

      source.addEventListener('process_stream', (event) => {
        try {
          const payload = JSON.parse(event.data || '{}');
          const chunk = String(payload.chunk || '');
          queueProcessStreamChunk(taskId, chunk);
        } catch (error) {
          console.warn('[demo] process_stream parse failed:', error);
        }
      });

      source.addEventListener('complete', () => {
        // Stop task poll — SSE stream is ending
        if (backendState.taskPollTimer) {
          clearInterval(backendState.taskPollTimer);
          backendState.taskPollTimer = null;
        }
        backendState.taskPollSession = null;

        const wasStreaming = !backendState.streamingDone;
        backendState.streamingDone = true;
        disconnectTaskEvents();

        if (!wasStreaming) {
          // Duplicate complete event — ensure final state
          if (!backendState.twAllDoneHandled) twOnAllRowsDone();
          return;
        }

        // Signal done to the typing engine.
        // If the queue is already drained, finalize now.
        // Otherwise twKick() → twOnAllRowsDone() naturally after the last row.
        backendState.twDoneFlag = true;
        if (!backendState.twIsTyping && !backendState.twRowQueue.length) {
          twOnAllRowsDone();
        }
        // If processStreamText has no parseable rows at all, fall back to a result fetch
        // (this fires before twOnAllRowsDone because twDoneFlag is set but queue is empty)
      });

      source.addEventListener('error', (event) => {
        try {
          const payload = JSON.parse(event.data || '{}');
          setWorkflowState('任务失败', backendState.taskProgress || 0, false);
          setDemoStatusText('任务失败');
          setDemoResultChipText('处理出错');
          setWorkflowThinkingLine(payload.message || '未知错误');
          appendWorkflowLiveEntry('ERROR', payload.message || '任务异常', 'error');
          if (backendState.taskPollTimer) {
            clearInterval(backendState.taskPollTimer);
            backendState.taskPollTimer = null;
          }
          backendState.taskPollSession = null;
        } catch (e) {
          // native EventSource connection error — browser will reconnect
        }
      });
    }

    async function loadBackendHistory() {
      const data = await apiFetch('/history');
      backendState.history = Array.isArray(data.history) ? data.history : [];
      backendState.resultByTaskId = {};
      const slots = taskSlots.slice(0);
      const hydrated = await Promise.all(backendState.history.slice(0, slots.length).map(async (item, index) => {
        const slot = slots[index];
        if (!item?.task_id) return { slot, item: summarizeTaskFromHistory(item, slot) };
        try {
          const result = await apiFetch(`/result/${encodeURIComponent(item.task_id)}`);
          if (result && result.process_flow) {
            return { slot, item: normalizeTaskCard(item, result), result, task_id: item.task_id };
          }
          return { slot, item: summarizeTaskFromHistory({ ...item, ...result }, slot), result, task_id: item.task_id };
        } catch (error) {
          return { slot, item: summarizeTaskFromHistory(item, slot), task_id: item.task_id };
        }
      }));

      slots.forEach((slot) => {
        backendState.taskMap[slot] = taskData[slot];
      });
      hydrated.forEach(({ slot, item, result, task_id }) => {
        if (!slot) return;
        backendState.taskMap[slot] = item;
        taskData[slot] = item;
        if (result) {
          backendState.taskResultsBySlot[slot] = result;
          cacheHistoryResult(task_id, result);
        }
        if (task_id) {
          backendState.latestTaskId = task_id;
          if (result) backendState.latestResult = result;
        }
      });
      renderTaskCards();
      renderTaskProcessSummary(backendState.selectedTaskKey);
      refreshCadPanel();
      updateZipConflictModeButton();
      updateNavigationLockState();
      renderHistoryPage();
    }

    async function loadBackendLibrary(libraryKey = backendState.activeLibraryKey || getSessionScopeKey() || 'public') {
      const encodedKey = encodeURIComponent(libraryKey || 'public');
      const status = await apiFetch(`/library/status?library_key=${encodedKey}`);
      libraryReady = !!status.ready;
      backendState.canBrowseDb = !!status.can_browse;
      backendState.libraryScopes = Array.isArray(status.scopes) ? status.scopes : backendState.libraryScopes;
      if (status.active_scope?.library_key) {
        backendState.activeLibraryKey = status.active_scope.library_key;
        backendState.activeLibraryName = status.active_scope.library_name || status.active_scope.library_key;
      }
      renderLibraryScopes();
      const records = await apiFetch(`/library/records?page=1&page_size=50&library_key=${encodeURIComponent(backendState.activeLibraryKey || 'public')}`);
      ingestLibraryRecords(records.items || []);
      if (Array.isArray(records.product_types) && records.product_types.length) {
        const currentType = dbTypeSelect.value || '全部';
        const uniqueTypes = [...new Set(records.product_types.filter(Boolean))];
        dbTypeSelect.innerHTML = ['全部', ...uniqueTypes].map((item) => `<option${item === currentType ? ' selected' : ''}>${escapeHtml(item)}</option>`).join('');
        if (!uniqueTypes.includes(currentType) && currentType !== '全部') {
          dbTypeSelect.value = '全部';
        }
      }
      refreshLibraryGate();
      renderDbList();
      applyDbRecord(dbState.selectedKey || dbOrder[0] || 'box');
      refreshCadPanel();
    }

    async function bootstrapBackend() {
      if (backendState.initialized) return;
      backendState.initialized = true;
      try {
        const sessionScope = getSessionScopeKey();
        if (sessionScope) backendState.activeLibraryKey = sessionScope;
        await Promise.all([loadBackendHistory().catch(() => null), loadBackendLibrary().catch(() => null)]);
        renderTaskCards();
        setWorkflowState('等待上传文件', 0, false);
        setDemoStatusText('已接入后端');
        refreshCadPanel();
        updateZipConflictModeButton();
        updateNavigationLockState();
      } catch (error) {
        console.warn('[demo] backend bootstrap failed:', error);
      }
    }

    function createHiddenFileInput(accept, multiple = false) {
      return new Promise((resolve) => {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = accept;
        input.multiple = multiple;
        input.style.display = 'none';
        document.body.appendChild(input);
        input.addEventListener('change', () => {
          const files = [...input.files];
          input.remove();
          resolve(files);
        }, { once: true });
        input.click();
      });
    }

    function downloadSampleZip() {
      const link = document.createElement('a');
      link.href = '/api/kb/sample_zip';
      link.download = 'sample_process_library.zip';
      link.rel = 'noopener';
      document.body.appendChild(link);
      link.click();
      link.remove();
    }

    function getZipBrowserState() {
      if (!backendState.zipBrowserState) {
        backendState.zipBrowserState = { matchedPage: 1, unmatchedPage: 1 };
      }
      return backendState.zipBrowserState;
    }

    function clampZipPage(page, totalPages) {
      return Math.min(Math.max(Number(page) || 1, 1), Math.max(Number(totalPages) || 1, 1));
    }

    function updateZipPager(buttonPrev, buttonNext, indicator, page, totalPages) {
      const safeTotal = Math.max(Number(totalPages) || 1, 1);
      const safePage = clampZipPage(page, safeTotal);
      if (indicator) indicator.textContent = `当前页：第 ${safePage} / ${safeTotal} 页`;
      setDisabledIfChanged(buttonPrev, safePage <= 1);
      setDisabledIfChanged(buttonNext, safePage >= safeTotal);
      return safePage;
    }

    function shiftZipBrowserPage(view, delta) {
      const report = backendState.latestZipReport || {};
      const zipBrowserState = getZipBrowserState();
      const matchedPairs = Array.isArray(report.matched_pairs) ? report.matched_pairs : [];
      const unmatchedPrts = Array.isArray(report.unmatched_pdfs) ? report.unmatched_pdfs : [];
      const unmatchedPdfs2 = Array.isArray(report.unmatched_xlsx) ? report.unmatched_xlsx : [];
      const matchedTotalPages = Math.max(1, Math.ceil(Math.max(matchedPairs.length, 1) / 1));
      const unmatchedTotalPages = Math.max(1, Math.max(
        Math.ceil(Math.max(unmatchedPrts.length, 1) / 6),
        Math.ceil(Math.max(unmatchedPdfs2.length, 1) / 6),
      ));
      if (view === 'matched') {
        zipBrowserState.matchedPage = clampZipPage((zipBrowserState.matchedPage || 1) + delta, matchedTotalPages);
      } else if (view === 'unmatched') {
        zipBrowserState.unmatchedPage = clampZipPage((zipBrowserState.unmatchedPage || 1) + delta, unmatchedTotalPages);
      }
      renderZipReport(report);
    }

    async function uploadToBackend(files) {
      if (!files.length) return null;
      const isZip = files.length === 1 && /\.zip$/i.test(files[0].name);
      if (isZip) {
        const form = new FormData();
        form.append('zip_file', files[0]);
        form.append('conflict_mode', backendState.zipConflictMode);
        const zipTarget = currentZipLibraryTarget();
        form.append('library_mode', zipTarget.mode);
        form.append('library_name', zipTarget.name);
        if (zipTarget.key) form.append('library_key', zipTarget.key);
        backendState.zipBusy = true;
        updateNavigationLockState();
        updateZipConflictModeButton();
        updateZipLibraryModeUI();
        try {
          setZipImportState('知识库上传中', `正在上传并解析 ${files[0].name}。含 PRT 模型时，几何分析需要较长时间，请耐心等待...`);
          const report = await apiFetch('/kb/import_zip', { method: 'POST', body: form });
          if (report.target_library?.library_key) {
            backendState.activeLibraryKey = report.target_library.library_key;
            backendState.activeLibraryName = report.target_library.library_name || report.target_library.library_key;
            markSessionZipUnlocked(report.target_library.library_key);
            loadZipLibraryList();
          }
          const hasPrt = (report.summary?.prt_count || 0) > 0;
          setZipImportState('知识库解析中', `已解析 ${hasPrt ? `PRT×${report.summary.prt_count} + ` : ''}${report.zip_name || files[0].name}，正在整理匹配关系...`);
          await sleep(600);
          renderZipReport(report);
          setZipImportState('知识库入库中', `批次 ${report.batch_id || '-'} 已匹配 ${report.summary?.matched_pairs || 0} 组，正在写入目标库...`);
          await sleep(800);
          setZipImportState('知识库已完成', `批次 ${report.batch_id || '-'} 已完成，共 ${report.summary?.matched_pairs || 0} 组匹配${report.summary?.error_count ? `，${report.summary.error_count} 项错误` : ''}。`);
          await loadBackendLibrary(backendState.activeLibraryKey);
          return report;
        } finally {
          backendState.zipBusy = false;
          updateNavigationLockState();
          updateZipConflictModeButton();
        }
      }

      resetGenerateWorkspace();
      resetWorkflowLiveConsole();
      const form = new FormData();
      const prtFiles = files.filter((file) => /\.prt(\.\d+)?$/i.test(file.name));
      const drawingFiles = files.filter((file) => /\.(pdf|png|jpg|jpeg|dxf|dwg)$/i.test(file.name));

      // 2D drawing (PDF / PNG / JPG) — single file, dedicated endpoint
      if (drawingFiles.length > 0) {
        form.append('file', drawingFiles[0]);
        form.append('library_key', backendState.retrievalLibraryKey || 'public');
        form.append('use_cache', backendState.featureCacheEnabled ? '1' : '0');
        setWorkflowState('图纸分析准备中', 10, true);
        const result = await apiFetch('/upload_drawing', { method: 'POST', body: form });
        if (result.task_id) backendState.currentProcessTaskId = result.task_id;
        setWorkflowState('图纸特征提取中', 20, true);
        followTaskProgress(result.task_id);
        return result;
      }

      if (files.length > 1 || prtFiles.length > 1) {
        prtFiles.forEach((file) => form.append('files', file));
        form.append('library_key', backendState.retrievalLibraryKey || 'public');
        setWorkflowState('PRT 批量分析准备中', 10, true);
        const result = await apiFetch('/batch_upload', { method: 'POST', body: form });
        const batchId = result.batch_task_id || result.task_id || result.batchTaskId;
        if (batchId) backendState.currentProcessTaskId = batchId;
        setWorkflowState('PRT 批量分析中', 24, true);
        followTaskProgress(batchId);
        return result;
      }

      form.append('file', files[0]);
      form.append('library_key', backendState.retrievalLibraryKey || 'public');
      setWorkflowState('PRT 分析准备中', 10, true);
      const result = await apiFetch('/upload', { method: 'POST', body: form });
      if (result.task_id) backendState.currentProcessTaskId = result.task_id;
      setWorkflowState('PRT 分析中', 20, true);
      followTaskProgress(result.task_id);
      return result;
    }

    function renderZipReport(report = {}) {
      const summary = report.summary || {};
      const zipBrowserState = getZipBrowserState();
      if ((backendState.latestZipReport?.batch_id || '') !== (report.batch_id || '')) {
        zipBrowserState.matchedPage = 1;
        zipBrowserState.unmatchedPage = 1;
      }
      backendState.latestZipReport = report;
      if (report.target_library?.library_key) {
        backendState.activeLibraryKey = report.target_library.library_key;
        backendState.activeLibraryName = report.target_library.library_name || report.target_library.library_key;
      }
      const matchedCount = report.summary?.matched_pairs || 0;
      zipBatchChip.textContent = report.batch_id ? `批次 ${report.batch_id.slice(-6)}` : '等待批次';
      zipResultChip.textContent = report.batch_id ? `已入库 ${matchedCount} 组` : '未开始';
      if (zipActiveLibraryChip) {
        zipActiveLibraryChip.textContent = `当前目标：${backendState.activeLibraryName || '未选择'}`;
      }
      if (zipPanelLibLabel) {
        zipPanelLibLabel.textContent = backendState.activeLibraryName ? `目标：${backendState.activeLibraryName}` : '未选择目标库';
      }
      if (report.batch_id && zipImportHud) {
        zipImportHud.classList.add('success');
        zipImportHud.classList.remove('busy', 'error');
      }
      zipTotalFiles.textContent = String(summary.total_files || 0);
      zipMatchedCount.textContent = String(summary.matched_pairs || 0);
      zipUnmatchedCount.textContent = String((report.unmatched_pdfs || []).length + (report.unmatched_xlsx || []).length);
      zipErrorCount.textContent = String(summary.error_count || 0);
      const matchedPairs = Array.isArray(report.matched_pairs) ? report.matched_pairs : [];
      const unmatchedPrts = Array.isArray(report.unmatched_pdfs) ? report.unmatched_pdfs : [];
      const unmatchedPdfs = Array.isArray(report.unmatched_xlsx) ? report.unmatched_xlsx : [];
      const errors = Array.isArray(report.errors) ? report.errors : [];
      const matchedPageSize = 1;
      const unmatchedPageSize = 6;
      const matchedTotalPages = Math.max(1, Math.ceil(Math.max(matchedPairs.length, 1) / matchedPageSize));
      const unmatchedTotalPages = Math.max(1, Math.max(
        Math.ceil(Math.max(unmatchedPrts.length, 1) / unmatchedPageSize),
        Math.ceil(Math.max(unmatchedPdfs.length, 1) / unmatchedPageSize),
      ));
      zipBrowserState.matchedPage = clampZipPage(zipBrowserState.matchedPage, matchedTotalPages);
      zipBrowserState.unmatchedPage = clampZipPage(zipBrowserState.unmatchedPage, unmatchedTotalPages);

      const dropzoneTitle = document.querySelector('#zipDropzone .dropzone-title');
      const dropzoneCopy = document.querySelector('#zipDropzone .dropzone-copy');
      if (dropzoneTitle) {
        dropzoneTitle.textContent = report.batch_id ? '知识库已入库' : '等待上传知识库压缩包';
      }
      if (dropzoneCopy) {
        dropzoneCopy.textContent = report.batch_id
          ? `批次 ${report.batch_id} 已完成导入，已写入 ${backendState.activeLibraryName || '目标库'}。这里展示的是知识库结果，不是模型分析结果。`
          : '上传 ZIP 后会自动导入知识库内容；要分析 PRT 模型，请到“工艺生成”页上传 PRT。';
      }

      const steps = [...document.querySelectorAll('#zipWorkbench .batch-step')];
      const stepMeta = [
        [`文件解压`, `总文件 ${summary.total_files || 0} 个`],
        [`模型编号提取`, `PRT ${summary.prt_count || 0} / PDF ${summary.pdf_count || 0}`],
        [`PRT 匹配`, `匹配 ${summary.matched_pairs || 0} 组`],
        [`报告生成`, `错误 ${summary.error_count || 0} 项`],
      ];
      steps.forEach((step, index) => {
        const titleEl = step.querySelector('strong');
        const descEl = step.querySelector('span');
        const hasProgress = !!report.batch_id;
        step.classList.toggle('active', hasProgress);
        step.classList.toggle('done', hasProgress && index < 3);
        if (titleEl) titleEl.textContent = stepMeta[index][0];
        if (descEl) descEl.textContent = report.batch_id ? stepMeta[index][1] : descEl.textContent;
      });

      updateZipPager(zipMatchedPrevBtn, zipMatchedNextBtn, zipMatchedPageIndicator, zipBrowserState.matchedPage, matchedTotalPages);
      updateZipPager(zipUnmatchedPrevBtn, zipUnmatchedNextBtn, zipUnmatchedPageIndicator, zipBrowserState.unmatchedPage, unmatchedTotalPages);

      zipMatchedEmpty.style.display = matchedPairs.length ? 'none' : 'flex';
      zipMatchedCard.style.display = matchedPairs.length ? 'block' : 'none';
      if (matchedPairs.length) {
        const matchedStart = (zipBrowserState.matchedPage - 1) * matchedPageSize;
        const matchedPageItems = matchedPairs.slice(matchedStart, matchedStart + matchedPageSize);
        zipMatchedCard.innerHTML = matchedPageItems.map((pair) => {
          const draft = pair.draft || {};
          const prtNames = Array.isArray(pair.prt_names) ? pair.prt_names.join(' · ') : (Array.isArray(pair.pdf_names) ? pair.pdf_names.join(' · ') : '');
          const pdfSrcNames = Array.isArray(pair.xlsx_names) ? pair.xlsx_names.join(' · ') : '';
          const processCount = Array.isArray(draft.process_list) ? draft.process_list.length : (draft.process_summary ? draft.process_summary.split('；').filter(Boolean).length : 0);
          return `
            <div class="match-card" style="margin-bottom:14px;">
              <div class="match-head">
                <div>
                  <div class="match-title">${escapeHtml(pair.prefix || '未命名模型')}</div>
                <div class="match-sub">PRT：${escapeHtml(prtNames || '无')} · PDF：${escapeHtml(pdfSrcNames || '无')}</div>
                </div>
                <span class="status-badge ${pair.status === 'skipped' ? 'warn' : 'success'}">${escapeHtml(pair.status || 'imported')}</span>
              </div>
              <div class="match-columns">
                <div class="match-pane">
                  <h4>已有记录</h4>
                  <div class="summary-note">${escapeHtml(pair.existing?.process_summary || pair.existing?.context || '未检测到历史记录')}</div>
                </div>
                <div class="match-pane">
                  <h4>本次导入</h4>
                  <div class="summary-note">${escapeHtml(draft.process_summary || draft.context || '未生成工艺摘要')}</div>
                </div>
              </div>
              <div class="match-meta-row">
                <span class="chip">工序 ${escapeHtml(String(processCount || 0))} 条</span>
                <span class="chip">视图页数 ${escapeHtml(String(draft.pdf_page_count || 0))}</span>
                <span class="chip">冲突模式：${escapeHtml(pair.conflict_mode || report.conflict_mode || 'replace')}</span>
                <span class="chip">目标库：${escapeHtml(report.target_library?.library_name || backendState.activeLibraryName || '公共工艺库')}</span>
              </div>
            </div>
          `;
        }).join('');
      } else {
        zipMatchedCard.innerHTML = '';
      }

      const unmatchedPrtPane = document.querySelector('#zip-unmatched .match-pane:nth-child(1) .pill-stack');
      const unmatchedPdfPane = document.querySelector('#zip-unmatched .match-pane:nth-child(2) .pill-stack');
      const unmatchedStart = (zipBrowserState.unmatchedPage - 1) * unmatchedPageSize;
      const unmatchedPrtItems = unmatchedPrts.slice(unmatchedStart, unmatchedStart + unmatchedPageSize);
      const unmatchedPdfItems = unmatchedPdfs.slice(unmatchedStart, unmatchedStart + unmatchedPageSize);
      if (unmatchedPrtPane) {
        unmatchedPrtPane.innerHTML = unmatchedPrtItems.length
          ? unmatchedPrtItems.map((item) => `<span class="chip">${escapeHtml(item)}</span>`).join('')
          : '<span class="chip">暂无</span>';
      }
      if (unmatchedPdfPane) {
        unmatchedPdfPane.innerHTML = unmatchedPdfItems.length
          ? unmatchedPdfItems.map((item) => `<span class="chip">${escapeHtml(item)}</span>`).join('')
          : '<span class="chip">暂无</span>';
      }

      const logLines = [
        `接收到 ZIP 批次 ${report.zip_name || '工艺包.zip'}。`,
        `PRT ${summary.prt_count || 0} 个，PDF ${summary.pdf_count || 0} 个。`,
        `已匹配 ${summary.matched_pairs || 0} 组，导入 ${summary.imported_count || 0} 条。`,
        `未匹配 PRT ${unmatchedPrts.length} 项，未匹配 PDF ${unmatchedPdfs.length} 项。`,
        ...errors.slice(0, 3).map((err) => `错误：${err.prefix || err.pdf_name || err.prt_name || '批次项'} - ${err.error || err.message || '解析失败'}`),
      ];
      const logBase = new Date();
      zipLogList.innerHTML = logLines.map((text, index) => {
        const t = new Date(logBase.getTime() + index * 800);
        const ts = `${String(t.getHours()).padStart(2,'0')}:${String(t.getMinutes()).padStart(2,'0')}:${String(t.getSeconds()).padStart(2,'0')}`;
        return `<div class="log-line"><span class="log-time">${ts}</span><span>${escapeHtml(text)}</span></div>`;
      }).join('');
      activateZipView('zip-matched');
    }

    function setZipImportState(phase, detail) {
      const phaseStr = String(phase || '');
      const busyPhase = /上传中|解析中|入库中/.test(phaseStr);
      const successPhase = /已完成/.test(phaseStr);
      const errorPhase = /失败|错误/.test(phaseStr);
      const thinkingText = getZipPhaseLabel(phase);
      setTextIfChanged(zipImportStatus, detail || phase || '等待工艺入库');
      setTextIfChanged(zipImportPhase, thinkingText);
      const progress = /上传中/.test(phaseStr) ? 18 : (/解析中/.test(phaseStr) ? 48 : (/入库中/.test(phaseStr) ? 78 : (successPhase ? 100 : 0)));
      setTextIfChanged(zipImportPercent, `${Math.max(0, Math.min(100, progress))}%`);
      if (zipProgressBar) {
        const nextWidth = `${Math.max(0, Math.min(100, progress))}%`;
        if (zipProgressBar.style.width !== nextWidth) zipProgressBar.style.width = nextWidth;
      }
      if (zipImportHud) {
        zipImportHud.classList.toggle('busy', busyPhase);
        zipImportHud.classList.toggle('success', successPhase);
        zipImportHud.classList.toggle('error', errorPhase);
        zipImportHud.classList.toggle('completed', successPhase);
      }
      const chipText = busyPhase ? (
        /上传中/.test(phaseStr) ? '上传中' : /解析中/.test(phaseStr) ? '解析中' : '入库中'
      ) : successPhase ? '入库完成' : errorPhase ? '入库失败' : (phase || '等待批次');
      setTextIfChanged(zipBatchChip, chipText);
      setTextIfChanged(zipResultChip, busyPhase ? '处理中' : successPhase ? '已入库' : errorPhase ? '失败' : phase && phase !== '等待批次' ? '处理中' : '未开始');
      const uploadBtn = zipRunBtn;
      const resetBtn = zipResetBtn;
      const conflictBtn = zipConflictModeBtn;
      setDisabledIfChanged(uploadBtn, busyPhase);
      setDisabledIfChanged(resetBtn, busyPhase);
      setDisabledIfChanged(conflictBtn, busyPhase);
    }

    async function followTaskProgress(taskId) {
      if (!taskId) return;
      if (backendState.taskPollTimer) {
        clearInterval(backendState.taskPollTimer);
        backendState.taskPollTimer = null;
      }
      const pollSession = Symbol('taskPollSession');
      backendState.taskPollSession = pollSession;
      let pollGeneration = 0;
      connectTaskEvents(taskId);
      const poll = async () => {
        if (backendState.taskPollSession !== pollSession) return;
        const generation = ++pollGeneration;
        try {
          const result = await apiFetch(`/result/${encodeURIComponent(taskId)}`);
          if (backendState.taskPollSession !== pollSession || generation !== pollGeneration) return;
          if (result?.gltf_url && result.gltf_url !== backendState.lastPreviewUrls) {
            backendState.lastPreviewUrls = result.gltf_url;
            dispose3DPreview(); setTimeout(() => render3DPreview(result.gltf_url, "model3DContainer"), 100);
          }
          if (result && result.process_flow) {
            backendState.latestTaskId = taskId;
            backendState.latestResult = result;
            backendState.taskResultsBySlot.spindle = result;
            cacheHistoryResult(taskId, result);
            backendState.taskMap.spindle = normalizeTaskCard({ task_id: taskId, pdf_name: result.pdf_name, created_at: result.created_at }, result);
            taskData.spindle = backendState.taskMap.spindle;
            setWorkflowState('工艺生成完成', 100, false);
            renderTaskCards();
            // Stop streaming before full render so replayed process_stream events don't overwrite it
            backendState.streamingDone = true;
            twDrainAll();
            renderProcessFromResult(result);
            renderReviewFromResult(result, { activate: false });
            applyTaskDetail('spindle');
            setDemoStatusText('生成完成');
            setDemoResultChipText('工艺已生成');
            disconnectTaskEvents();
            if (backendState.taskPollTimer) {
              clearInterval(backendState.taskPollTimer);
              backendState.taskPollTimer = null;
            }
            backendState.taskPollSession = null;
            renderHistoryPage();
            return;
          }
          const nextProgress = Math.max(Number(result.progress || 0), backendState.taskProgress || 0);
          if (result.status === 'error') {
            setWorkflowState('任务失败', nextProgress, false);
            setDemoStatusText('任务失败');
            setDemoResultChipText('处理出错');
            setWorkflowThinkingLine((result.error || result.message || '未知错误'));
            disconnectTaskEvents();
            if (backendState.taskPollTimer) {
              clearInterval(backendState.taskPollTimer);
              backendState.taskPollTimer = null;
            }
            backendState.taskPollSession = null;
            return;
          }
          const phase = result.status === 'processing'
            ? '工艺生成中'
            : (result.status === 'awaiting_review' ? '等待审阅' : '处理中');
          setWorkflowState(phase, nextProgress, result.status !== 'awaiting_review');
          setDemoStatusText(result.status || '处理中');
          if (result.status === 'awaiting_review') {
            backendState.latestResult = {
              ...(backendState.latestResult || {}),
              ...result,
              task_id: taskId,
            };
            cacheHistoryResult(taskId, backendState.latestResult);
            const reviewAlreadySubmitted = backendState.reviewSubmittedForTaskId === taskId;
            if (!reviewAlreadySubmitted && !backendState.reviewDirty && !backendState.reviewRenderedForTask
                && (result.review_text || result.feature_report || result.raw_review_text)) {
              backendState.reviewRenderedForTask = taskId;
              renderReviewTable({
                task_id: taskId,
                title: '待审阅特征',
                content: result.review_text || result.feature_report || '',
                raw_content: result.raw_review_text || '',
                failures: result.vision_failures || [],
                message: '任务正在等待特征确认。',
              });
            } else if (!reviewAlreadySubmitted && !backendState.reviewDirty && backendState.latestReviewPayload?.content) {
              renderReviewTable({ ...backendState.latestReviewPayload, task_id: taskId });
            }
            renderHistoryPage();
          }
        } catch (error) {
          if (backendState.taskPollSession !== pollSession || generation !== pollGeneration) return;
          console.warn('[demo] poll retry:', error.message || error);
        }
      };
      await poll();
      backendState.taskPollTimer = setInterval(poll, 2500);
    }

    function activatePage(pageId) {
      if (backendState.zipBusy && pageId !== 'page-zip') return;
      if (backendState.taskBusy && pageId !== 'page-generate') return;
      navItems.forEach(item => item.classList.toggle('active', item.dataset.page === pageId));
      topTabs.forEach(tab => tab.classList.toggle('active', tab.dataset.page === pageId));
      pages.forEach(page => page.classList.toggle('active', page.id === pageId));
      if (pageId === 'page-list') renderHistoryPage();
    }

    async function checkStartupToken() {
      const STORAGE_KEY = '__prt_startup_token__';
      try {
        const res = await fetch(`${window.__API_BASE__ || '/api'}/startup_token`);
        if (!res.ok) return;
        const { token } = await res.json();
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored !== token) {
          localStorage.setItem(STORAGE_KEY, token);
          if (stored !== null) {
            // Only reset when a previous token existed — skip very first page load
            resetGenerateWorkspace();
          }
        }
      } catch (_) {
        // Backend not reachable — skip reset
      }
    }

    function resetGenerateWorkspace() {
      backendState.currentReviewTaskId = '';
      backendState.currentProcessTaskId = '';
      backendState.latestReviewPayload = null;
      backendState.latestResult = null;
      backendState.latestTaskId = '';
      backendState.previewImages = [];
      backendState.previewTaskId = '';
      backendState.previewIndex = 0;
      backendState.previewZoom = 1;
      backendState.reviewDirty = false;
      resetProcessStreamState('');
      hideStreamingZone();
      resetWorkflowLiveConsole();
      backendState.reviewRenderedForTask = '';
      backendState.renderedPreviewTaskId = '';
      backendState.lastPreviewUrls = '';
      backendState.resultRenderedForTask = '';
      backendState.reviewSubmittedForTaskId = '';
      backendState.streamingDone = false;
      backendState.pollFailCount = 0;
      dispose3DPreview();
      backendState.taskBusy = false;
      backendState.taskProgress = 0;
      backendState.taskPhase = '等待上传文件';
      resetProcessStreamState('');
      disconnectTaskEvents();
      if (backendState.taskPollTimer) {
        clearInterval(backendState.taskPollTimer);
        backendState.taskPollTimer = null;
      }

      setWorkflowState('等待上传文件', 0, false);
      if (workflowHudCard) workflowHudCard.classList.remove('collapsed');
      if (workflowHudToggleBtn) workflowHudToggleBtn.textContent = '收起';
      setDemoStatusText('待上传');
      setDemoHitText('0');
      setDemoStepText('0');
      setDemoResultChipText('未开始');
      if (reviewContinueBtn) reviewContinueBtn.disabled = false;
      if (reviewRerunBtn) reviewRerunBtn.disabled = false;

      if (uploadPanelBody) uploadPanelBody.innerHTML = initialUploadPanelHTML;
      if (processResult) processResult.innerHTML = initialProcessPanelHTML;
      if (processEmpty) processEmpty.style.display = 'flex';
      if (processResult) processResult.style.display = 'none';

      if (reviewTableHost) reviewTableHost.innerHTML = '';
      if (reviewStatusBadge) {
        reviewStatusBadge.textContent = '未开始';
        reviewStatusBadge.className = 'status-badge warn';
      }
      if (reviewStepLabel) reviewStepLabel.textContent = '收到 review_required 后会在此显示可编辑表格。';
      if (reviewSourceNote) reviewSourceNote.textContent = '等待后端推送审阅结果。';

      if (editorTextarea) editorTextarea.value = initialEditorHTML;
      if (editorPreview) editorPreview.textContent = initialEditorHTML;
      if (editorShell) editorShell.classList.remove('active');

      updateExportCardButtonState();
    }

    function activateResultView(viewId) {
      resultTabs.forEach(tab => tab.classList.toggle('active', tab.dataset.resultView === viewId));
      resultViews.forEach(view => view.classList.toggle('active', view.id === viewId));
    }

    function activateZipView(viewId) {
      zipTabs.forEach(tab => tab.classList.toggle('active', tab.dataset.zipView === viewId));
      zipViews.forEach(view => view.classList.toggle('active', view.id === viewId));
    }

    function applySidebarCollapsedState(collapsed, persist = true) {
      const next = !!collapsed;
      document.body.classList.toggle('sidebar-collapsed', next);
      if (sidebarToggleBtn) {
        sidebarToggleBtn.textContent = next ? '展开侧栏' : '折叠侧栏';
        sidebarToggleBtn.setAttribute('aria-expanded', String(!next));
      }
      if (persist) {
        try {
          localStorage.setItem(SIDEBAR_COLLAPSED_STORAGE_KEY, next ? '1' : '0');
        } catch (error) {
          console.warn('[demo] failed to store sidebar state:', error);
        }
      }
    }

    applySidebarCollapsedState((() => {
      try {
        return localStorage.getItem(SIDEBAR_COLLAPSED_STORAGE_KEY) === '1';
      } catch (error) {
        return false;
      }
    })(), false);

    function openModal() {
      reviewModal.classList.add('open');
    }

    function closeModal() {
      reviewModal.classList.remove('open');
    }

    function refreshEditorPreview() {
      if (editorPreview && editorTextarea) editorPreview.textContent = editorTextarea.value;
    }

    function toggleEditor() {
      if (!editorShell) return;
      const active = editorShell.classList.toggle('active');
      if (active) refreshEditorPreview();
    }

    function escapeHtml(value) {
      return String(value ?? '').replace(/[&<>"]/g, (ch) => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;'
      }[ch]));
    }

    function filterInfoFields(text) {
      var keepFields = ['零件名称', '形态', '类型', '技术要求'];
      // Split by 【 delimiter, keeping the delimiter with its section
      var sections = String(text || '').split(/(?=【)/);
      var kept = [];
      for (var i = 0; i < sections.length; i++) {
        var s = sections[i].trim();
        if (!s) continue;
        for (var j = 0; j < keepFields.length; j++) {
          if (s.indexOf('【' + keepFields[j] + '】') === 0) {
            kept.push(s);
            break;
          }
        }
      }
      return kept.join('\n');
    }

    function normalizePreviewUrlList(value) {
      if (Array.isArray(value)) {
        return value.map((item) => String(item || '').trim()).filter(Boolean);
      }
      if (typeof value === 'string') {
        const text = value.trim();
        if (!text) return [];
        try {
          const parsed = JSON.parse(text);
          if (Array.isArray(parsed)) {
            return parsed.map((item) => String(item || '').trim()).filter(Boolean);
          }
        } catch (error) {
          // fall through to line splitting
        }
        return text.split(/[\n,]/).map((item) => item.trim()).filter(Boolean);
      }
      return [];
    }

    function renderDbPreviewSurface(item = {}, images = [], index = 0, statusText = '', gltfUrl = '') {
      const list = Array.isArray(images) ? images.filter(Boolean) : [];
      const safeIndex = list.length ? Math.min(Math.max(Number(index) || 0, 0), list.length - 1) : 0;
      const label = statusText || (list.length ? `${safeIndex + 1} / ${list.length}` : '暂无可用图片');

      if (dbPreviewModal) dbPreviewModal.dataset.previewLoaded = (list.length || gltfUrl) ? '1' : '0';
      if (dbPreviewMeta) dbPreviewMeta.textContent = label;
      if (dbPreviewSource) dbPreviewSource.textContent = item.title ? `${item.title} · ${item.sourceType || item.source || '记录快照'}` : label;

      if (gltfUrl) {
        if (dbPreviewCounter) dbPreviewCounter.textContent = '3D 模型';
        if (dbPreviewZoomLabel) dbPreviewZoomLabel.textContent = '拖拽旋转';
        [dbPreviewPrevBtn, dbPreviewNextBtn, dbPreviewZoomOutBtn, dbPreviewZoomInBtn, dbPreviewResetBtn]
          .forEach((btn) => { if (btn) btn.disabled = true; });
        if (dbPreview3DContainer) { dbPreview3DContainer.style.display = 'block'; dbViewer.render(gltfUrl, dbPreview3DContainer); }
        if (dbPreviewImage) { dbPreviewImage.style.display = 'none'; dbPreviewImage.removeAttribute('src'); }
        if (dbPreviewEmpty) dbPreviewEmpty.style.display = 'none';
      } else {
        dbViewer.dispose();
        if (dbPreview3DContainer) dbPreview3DContainer.style.display = 'none';
        if (dbPreviewCounter) dbPreviewCounter.textContent = list.length ? `${safeIndex + 1} / ${list.length}` : '0 / 0';
        if (dbPreviewZoomLabel) dbPreviewZoomLabel.textContent = `${Math.round(dbPreviewZoom * 100)}%`;
        if (dbPreviewPrevBtn) dbPreviewPrevBtn.disabled = list.length <= 1 || safeIndex <= 0;
        if (dbPreviewNextBtn) dbPreviewNextBtn.disabled = list.length <= 1 || safeIndex >= list.length - 1;
        if (dbPreviewZoomOutBtn) dbPreviewZoomOutBtn.disabled = !list.length;
        if (dbPreviewZoomInBtn) dbPreviewZoomInBtn.disabled = !list.length;
        if (dbPreviewResetBtn) dbPreviewResetBtn.disabled = !list.length;
        if (dbPreviewImage) {
          if (list.length) {
            dbPreviewImage.src = list[safeIndex];
            dbPreviewImage.style.display = 'block';
            dbPreviewImage.style.transform = `scale(${dbPreviewZoom})`;
          } else {
            dbPreviewImage.removeAttribute('src');
            dbPreviewImage.style.display = 'none';
          }
        }
        if (dbPreviewEmpty) {
          dbPreviewEmpty.style.display = list.length ? 'none' : 'flex';
        }
      }

      backendState.dbDetailPreview = {
        key: item.key || item.id || '',
        images: list,
        index: safeIndex,
        gltfUrl,
      };
    }

    function formatDbSnapshotText(item = {}) {
      const raw = String(item.content || item.processSummary || item.summary || item.context || '').trim();
      if (!raw) return '-';
      if (raw.includes('\n')) return raw;
      const list = Array.isArray(item.processList) ? item.processList.map((row) => String(row || '').trim()).filter(Boolean) : [];
      if (list.length) return list.join('\n');
      return raw;
    }

    function formatDbFeatureText(item = {}) {
      const raw = String(item.featureReportText || item.keyFeatures || item.key_features || item.context || item.summary || '').trim();
      if (!raw) return '-';
      return raw.includes('\n') ? raw : raw.replace(/【/g, '\n【').trim();
    }

    function formatDbProcessText(item = {}) {
      // Returns structured HTML table with 工序号|工种|工序内容 columns.
      const processArr = item.process_list || item.processList;
      let rows = Array.isArray(processArr)
        ? processArr.map((row) => String(row || '').trim()).filter(Boolean)
        : [];
      if (!rows.length) {
        // Try content, processSummary, then summary as last resort
        const raw = String(item.content || item.processSummary || item.summary || '').trim();
        if (!raw) return '-';
        rows = raw.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
      }
      if (!rows.length) return '-';

      // Build structured table from process rows (parses 0010@工种@内容)
      const tbody = rows.map((row) => {
        const normalized = normalizeProcessRow(row);
        if (!normalized.code && !normalized.content) return '';
        return `<tr data-process-row="${escapeHtml(normalized.code || '')}">
          <td class="step-no">${escapeHtml(normalized.code || '----')}</td>
          <td class="step-trade" data-step-trade>${escapeHtml(normalized.tradeType || '')}</td>
          <td class="step-content-cell"><div class="step-content">${formatContentHtml(normalized.content)}</div></td>
        </tr>`;
      }).filter(Boolean).join('');

      if (!tbody) return escapeHtml(String(item.content || item.processSummary || '').trim());

      return `<div class="step-table-shell">
        <table class="step-table">
          <colgroup><col class="col-step-no"/><col class="col-step-trade"/><col/></colgroup>
          <thead><tr><th>工序号</th><th>工种</th><th>工序名称及内容</th></tr></thead>
          <tbody>${tbody}</tbody>
        </table>
      </div>`;
    }

    async function loadDbRecordPreview(item = {}) {
      const inlineImages = normalizePreviewUrlList(item.previewImageUrls || item.preview_image_urls);
      const previewTaskId = String(item.previewTaskId || item.preview_task_id || item.sourceTaskId || item.source_task_id || '').trim();
      const isPrt = String(item.sourceType || '').toLowerCase() === 'prt';

      // PRT records: always try to fetch gltf_url first; fall back to inline images if unavailable
      if (isPrt && previewTaskId) {
        const token = ++dbDetailPreviewRequestToken;
        renderDbPreviewSurface(item, [], 0, '正在加载 3D 模型...');
        try {
          const result = await apiFetch(`/result/${encodeURIComponent(previewTaskId)}`);
          if (token !== dbDetailPreviewRequestToken) return;
          const gltfUrl = String(result?.gltf_url || result?.gltfUrl || '').trim();
          const fetchedImages = normalizePreviewUrlList(result?.previewImageUrls || result?.preview_image_urls);
          if (gltfUrl) {
            renderDbPreviewSurface(item, fetchedImages.length ? fetchedImages : inlineImages, 0, '3D 模型预览', gltfUrl);
          } else if (fetchedImages.length) {
            renderDbPreviewSurface(item, fetchedImages, 0, `${fetchedImages.length} 张图片`);
          } else if (inlineImages.length) {
            renderDbPreviewSurface(item, inlineImages, 0, `${inlineImages.length} 张图片`);
          } else {
            renderDbPreviewSurface(item, [], 0, '暂无可显示的模型或图片');
          }
        } catch {
          if (token !== dbDetailPreviewRequestToken) return;
          if (inlineImages.length) {
            renderDbPreviewSurface(item, inlineImages, 0, `${inlineImages.length} 张图片`);
          } else {
            renderDbPreviewSurface(item, [], 0, '模型加载失败');
          }
        }
        return;
      }

      // Non-PRT: inline images take priority (original behavior)
      if (inlineImages.length) {
        renderDbPreviewSurface(item, inlineImages, 0, `${inlineImages.length} 张图片`);
        return;
      }

      if (!previewTaskId) {
        renderDbPreviewSurface(item, [], 0, '当前记录没有保存图片来源');
        return;
      }

      const token = ++dbDetailPreviewRequestToken;
      renderDbPreviewSurface(item, [], 0, `正在加载 ${previewTaskId} 的图片...`);
      try {
        const result = await apiFetch(`/result/${encodeURIComponent(previewTaskId)}`);
        if (token !== dbDetailPreviewRequestToken) return;
        const gltfUrl = String(result?.gltf_url || result?.gltfUrl || '').trim();
        const nextImages = normalizePreviewUrlList(result?.previewImageUrls || result?.preview_image_urls);
        if (gltfUrl) {
          renderDbPreviewSurface(item, nextImages, 0, '3D 模型预览', gltfUrl);
        } else if (nextImages.length) {
          renderDbPreviewSurface(item, nextImages, 0, `${nextImages.length} 张图片`);
        } else {
          renderDbPreviewSurface(item, [], 0, '未找到可显示的图片');
        }
      } catch (error) {
        if (token !== dbDetailPreviewRequestToken) return;
        renderDbPreviewSurface(item, [], 0, '图片加载失败');
        console.warn('[demo] failed to load db record preview:', error);
      }
    }


    function openDbPreviewModal() {
      if (!dbPreviewModal) return;
      dbPreviewModal.classList.add('open');
      document.body.style.overflow = 'hidden';
    }

    function closeDbPreviewModalView() {
      if (!dbPreviewModal) return;
      dbPreviewModal.classList.remove('open');
      document.body.style.overflow = '';
      dbViewer.dispose();
      if (dbPreview3DContainer) dbPreview3DContainer.style.display = 'none';
    }

    function updateDbPreviewTitle(item = {}, images = []) {
      if (dbPreviewTitle) dbPreviewTitle.textContent = `${item.title || '库记录快照'}`;
      if (dbPreviewMeta) {
        const count = Array.isArray(images) ? images.length : 0;
        const source = item.previewTaskId || item.sourceTaskId ? `来源任务：${item.previewTaskId || item.sourceTaskId}` : '无来源任务';
        dbPreviewMeta.textContent = count ? `${source} · ${count} 张图片` : `${source} · 暂无可用图片`;
      }
    }

    function openDbPreviewFromCurrent() {
      const preview = backendState.dbDetailPreview || { images: [], index: 0, key: '' };
      const item = dbRecords[preview.key] || dbRecords[dbState.selectedKey] || {};
      const storedGltfUrl = String(preview.gltfUrl || '').trim();
      const statusText = storedGltfUrl
        ? '3D 模型预览'
        : (preview.images?.length ? `${(preview.index || 0) + 1} / ${preview.images.length}` : '暂无可用图片');
      updateDbPreviewTitle(item, preview.images || []);
      renderDbPreviewSurface(item, preview.images || [], preview.index || 0, statusText, storedGltfUrl);
      openDbPreviewModal();
    }

    function highlightText(text, term) {
      const source = escapeHtml(text);
      const query = String(term || '').trim();
      if (!query) return source;
      const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      return source.replace(new RegExp(`(${escaped})`, 'gi'), '<mark class="search-hit">$1</mark>');
    }

    function getDbVisibleRecords() {
      const query = dbState.query.trim().toLowerCase();
      return dbOrder
        .map((key) => ({ key, ...dbRecords[key] }))
        .filter((item) => !dbState.removed.has(item.key))
        .filter((item) => {
          const haystack = [
            item.title,
            item.meta,
            item.type,
            item.source,
            item.status,
            item.summary,
            ...(item.tags || []),
          ].join(' ').toLowerCase();
          if (query && !haystack.includes(query)) return false;
          if (dbState.type !== '全部' && item.type !== dbState.type) return false;
          if (dbState.source !== '全部来源' && item.source !== dbState.source) return false;
          if (dbState.status !== '全部状态' && item.status !== dbState.status) return false;
          return true;
        });
    }

    function updateDbSummary(visible, totalPages) {
      const browseOnly = !!backendState.dbBrowseOnly && !(!!backendState.canBrowseDb && hasSessionZipUnlocked());
      setTextIfChanged(dbTotalValue, String(dbOrder.length - dbState.removed.size));
      setTextIfChanged(dbVisibleValue, String(visible.length));
      setTextIfChanged(dbEditValue, browseOnly ? '只读' : (dbEditorShell.classList.contains('active') ? '编辑中' : '启用'));
      setTextIfChanged(dbPageSummary, `${backendState.activeLibraryName || '当前工艺库'} · ${visible.length} 条记录`);
      setTextIfChanged(dbRecordCount, `${visible.length} / ${dbOrder.length}`);
      setTextIfChanged(dbListMeta, visible.length ? `当前显示 ${backendState.activeLibraryName || '当前工艺库'} 的 ${visible.length} 条记录` : '没有符合条件的后端记录');
      setTextIfChanged(dbPageIndicator, `第 ${dbState.page} / ${totalPages} 页`);
      if (dbPageSizeSelect && dbPageSizeSelect.value !== String(dbState.pageSize)) dbPageSizeSelect.value = String(dbState.pageSize);
      updateDbDeleteState();
      updateDbDeleteLibraryState();
    }

    function renderDbDetail(item) {
      if (!item) return;
      const browseOnly = !!backendState.dbBrowseOnly && !(!!backendState.canBrowseDb && hasSessionZipUnlocked());
      const nextPreviewKey = String(item.key || item.id || '');
      const previousPreviewKey = String(backendState.dbDetailPreview?.key || '');
      const isSamePreview = !!nextPreviewKey && previousPreviewKey === nextPreviewKey;
      if (!isSamePreview) {
        dbDetailPreviewRequestToken += 1;
        dbPreviewZoom = 1;
      }
      dbDetailTitle.textContent = item.title;
      const imageHint = item.previewImageUrls?.length || item.previewTaskId ? ' · 含图片快照' : '';
      dbDetailMeta.textContent = `${item.meta} · 所属库：${backendState.activeLibraryName || '公共工艺库'}${imageHint}`;
      dbDetailStatus.textContent = item.status;
      dbDetailStatus.className = `status-badge ${item.statusClass}`;
      if (dbDetailTypeChip) dbDetailTypeChip.textContent = item.type;
      dbDetailPrefixChip.textContent = item.title;
      dbDetailSourceChip.textContent = item.sourceType || item.source;
      dbDetailStateChip.textContent = item.status;
      if (dbEditorProductType) dbEditorProductType.value = item.type || '';
      if (dbEditorContent) dbEditorContent.value = item.content || item.processSummary || item.summary || '';
      renderDbFeatureReportView(item);
      if (dbEditorPreview) {
        const currentPage = backendState.dbFeatureReport?.pages?.[backendState.dbFeatureReport?.index || 0] || null;
        dbEditorPreview.textContent = [
          `产品类型：${item.type || '-'}`,
          `工艺内容：${item.content || item.processSummary || item.summary || '-'}`,
          `特征页：${currentPage ? `第 ${(backendState.dbFeatureReport?.index || 0) + 1} 页` : '无分页特征'}`,
        ].join('\n');
      }
      dbEditBtn.textContent = browseOnly ? '只读浏览' : '编辑记录';
      dbSaveBtn.style.display = 'none';
      dbCancelBtn.style.display = 'none';
      dbEditorShell.classList.remove('active');
      dbEditValue.textContent = browseOnly ? '只读' : '启用';
      if (dbDetailImageSummary) {
        dbDetailImageSummary.textContent = item.previewImageUrls?.length
          ? `已保存 ${item.previewImageUrls.length} 张图片，点击查看快照。`
          : (item.previewTaskId
            ? `已保存来源任务 ${item.previewTaskId}，点击查看快照。`
            : '暂无可用图片');
      }
      if (dbOpenImageSnapshotBtn) {
        dbOpenImageSnapshotBtn.textContent = '查看快照';
      }
      if (dbPreviewFeature) {
        dbPreviewFeature.style.whiteSpace = 'pre-wrap';
        dbPreviewFeature.style.wordBreak = 'break-word';
      }
      if (dbPreviewProcess) {
        const processHTML = formatDbProcessText(item);
        dbPreviewProcess.innerHTML = processHTML;
        if (processHTML.startsWith('<div class="step-table-shell"')) {
          // Override .history-scroll-field > span constraints so the
          // step-table-shell manages its own scroll / max-height.
          dbPreviewProcess.style.display = 'block';
          dbPreviewProcess.style.flex = '1 1 auto';
          dbPreviewProcess.style.minHeight = '0';
          dbPreviewProcess.style.overflow = 'visible';
          dbPreviewProcess.style.whiteSpace = 'normal';
          dbPreviewProcess.style.wordBreak = 'normal';
          // Parent .history-scroll-field has overflow:hidden – let table
          // shell scroll independently.
          if (dbPreviewProcess.parentElement) {
            dbPreviewProcess.parentElement.style.overflow = 'visible';
          }
        } else {
          dbPreviewProcess.style.display = '';
          dbPreviewProcess.style.flex = '';
          dbPreviewProcess.style.minHeight = '';
          dbPreviewProcess.style.overflow = '';
          dbPreviewProcess.style.whiteSpace = '';
          dbPreviewProcess.style.wordBreak = '';
          if (dbPreviewProcess.parentElement) {
            dbPreviewProcess.parentElement.style.overflow = '';
          }
        }
      }
      renderDbPreviewSurface(item, isSamePreview ? (backendState.dbDetailPreview?.images || []) : [], isSamePreview ? (backendState.dbDetailPreview?.index || 0) : 0, item.previewImageUrls?.length ? '正在准备图片预览' : '暂无可用图片');
      loadDbRecordPreview(item).catch(() => null);
      updateDbDeleteState();
      updateDbDeleteLibraryState();
    }

    function selectDbRecord(key) {
      const item = dbRecords[key];
      if (!item || dbState.removed.has(key)) return;
      dbState.selectedKey = key;
      renderDbDetail(item);
      renderDbList();
    }

    function renderDbList() {
      const visible = getDbVisibleRecords();
      const totalPages = Math.max(1, Math.ceil(Math.max(visible.length, 1) / Math.max(dbState.pageSize, 1)));
      dbState.page = Math.min(Math.max(dbState.page, 1), totalPages);
      const start = (dbState.page - 1) * dbState.pageSize;
      const pageItems = visible.slice(start, start + dbState.pageSize);
      const dbRenderKey = [
        backendState.activeLibraryKey || 'public',
        dbState.page,
        dbState.pageSize,
        dbState.query,
        dbState.type,
        dbState.source,
        dbState.status,
        dbState.selectedKey,
        visible.length,
        pageItems.map((item) => `${item.key}:${item.status}:${item.processCount}:${item.title}`).join('|'),
      ].join('::');
      if (backendState.dbRenderKey === dbRenderKey) {
        updateDbSummary(visible, totalPages);
        return;
      }
      backendState.dbRenderKey = dbRenderKey;

      if (!pageItems.length) {
        dbRecordList.innerHTML = '<div class="result-empty" style="min-height:240px;"><div class="glyph blue">⟁</div><div class="dropzone-title" style="font-size:24px; margin:0;">暂无符合条件的记录</div><div class="dropzone-copy" style="font-size:15px; max-width:86%;">调整筛选条件后可重新查看后端数据库内容。</div></div>';
        dbListMeta.textContent = '没有符合条件的后端记录';
        dbRecordCount.textContent = `0 / ${dbOrder.length}`;
        dbPageIndicator.textContent = `第 1 / 1 页`;
        dbPrevBtn.disabled = true;
        dbNextBtn.disabled = true;
        dbDetailTitle.textContent = '暂无记录';
        dbDetailMeta.textContent = `当前库“${backendState.activeLibraryName || '公共工艺库'}”暂无可显示数据`;
        dbDetailStatus.textContent = '空';
        dbDetailStatus.className = 'status-badge warn';
        if (dbDetailTypeChip) dbDetailTypeChip.textContent = '-';
        dbDetailPrefixChip.textContent = '-';
        dbDetailSourceChip.textContent = backendState.activeLibraryName || '公共工艺库';
        dbDetailStateChip.textContent = '-';
        if (dbDetailImageSummary) dbDetailImageSummary.textContent = '暂无可用图片';
        if (dbOpenImageSnapshotBtn) dbOpenImageSnapshotBtn.disabled = false;
        updateDbSummary(visible, 1);
        return;
      }

      if (!pageItems.some((item) => item.key === dbState.selectedKey)) {
        dbState.selectedKey = pageItems[0].key;
      }

      dbRecordList.innerHTML = pageItems.map((item) => `
        <button class="record-row ${item.key === dbState.selectedKey ? 'active' : ''}" data-db-record="${item.key}">
          <div style="display:flex; justify-content:space-between; gap:12px; align-items:flex-start;">
            <strong>${highlightText(item.title, dbState.query)}</strong>
            <span class="status-badge ${item.statusClass}">${escapeHtml(item.status)}</span>
          </div>
          <span>${escapeHtml(item.type)} · ${escapeHtml(item.source)} · 工序 ${item.processCount} 条</span>
          <div class="record-row-tags">
            ${(item.tags || []).map((tag) => `<span class="record-tag">${escapeHtml(tag)}</span>`).join('')}
          </div>
        </button>
      `).join('');

      dbPrevBtn.disabled = dbState.page <= 1;
      dbNextBtn.disabled = dbState.page >= totalPages;
      updateDbSummary(visible, totalPages);
      renderDbDetail(dbRecords[dbState.selectedKey]);
    }

    function applyDbRecord(key) {
      selectDbRecord(key);
    }

    function refreshDbEditorPreview() {
      if (!dbEditorPreview) return;
      const featureState = backendState.dbFeatureReport || {};
      const currentPage = Array.isArray(featureState.pages) ? featureState.pages[featureState.index || 0] : null;
      dbEditorPreview.textContent = [
        `产品类型：${dbEditorProductType?.value || '-'}`,
        `工艺内容：${dbEditorContent?.value || '-'}`,
        `特征页：${currentPage ? `第 ${(featureState.index || 0) + 1} 页 / 共 ${featureState.pages.length} 页` : '无分页特征'}`,
      ].join('\n');
    }

    function toggleDbEditor(force) {
      if (backendState.dbBrowseOnly && !(!!backendState.canBrowseDb && hasSessionZipUnlocked())) return;
      const next = typeof force === 'boolean' ? force : !dbEditorShell.classList.contains('active');
      dbEditorShell.classList.toggle('active', next);
      dbSaveBtn.style.display = next ? 'inline-flex' : 'none';
      dbCancelBtn.style.display = next ? 'inline-flex' : 'none';
      dbEditBtn.textContent = next ? '收起编辑' : '编辑记录';
      dbEditValue.textContent = next ? '编辑中' : '启用';
      if (next) refreshDbEditorPreview();
    }

    function openDbDeleteModal() {
      if (isPublicLibraryActive()) return;
      const item = dbRecords[dbState.selectedKey];
      if (!item) return;
      dbState.deleteKey = dbState.selectedKey;
      dbDeleteInfo.textContent = `${item.title}｜${item.type}｜${item.source}`;
      dbDeleteModal.classList.add('open');
    }

    function openDbDeleteLibraryModal() {
      if (isPublicLibraryActive()) return;
      if (!dbDeleteLibraryModal) return;
      const label = backendState.activeLibraryName || backendState.activeLibraryKey || '当前数据库';
      if (dbDeleteLibraryInfo) {
        dbDeleteLibraryInfo.textContent = `${label}｜${backendState.activeLibraryKey || 'public'}`;
      }
      dbDeleteLibraryModal.classList.add('open');
    }

    function closeDbDeleteModal() {
      dbState.deleteKey = null;
      dbDeleteModal.classList.remove('open');
    }

    function closeDbDeleteLibraryModal() {
      if (dbDeleteLibraryModal) dbDeleteLibraryModal.classList.remove('open');
    }

    function confirmDbDelete() {
      const key = dbState.deleteKey;
      if (!key) return;
      const current = dbRecords[key];
      if (isPublicLibraryActive()) {
        closeDbDeleteModal();
        showToast('公共工艺库只读，不能删除废表。', 'warn');
        return;
      }
      if (current?.id) {
        apiFetch(`/library/records/${current.id}?library_key=${encodeURIComponent(backendState.activeLibraryKey || 'public')}`, { method: 'DELETE' })
          .then(() => loadBackendLibrary(backendState.activeLibraryKey))
          .catch((error) => {
            console.error(error);
            showToast(error.message || '删除失败', 'error');
          })
          .finally(closeDbDeleteModal);
        return;
      }

      dbState.removed.add(key);
      closeDbDeleteModal();
      const visible = getDbVisibleRecords();
      const next = visible[0];
      if (next) {
        dbState.selectedKey = next.key;
        renderDbDetail(next);
      } else {
        dbDetailTitle.textContent = '暂无记录';
        dbDetailMeta.textContent = '当前筛选条件下没有可显示的数据';
        dbDetailStatus.textContent = '空';
        dbDetailStatus.className = 'status-badge warn';
        if (dbDetailTypeChip) dbDetailTypeChip.textContent = '-';
        dbDetailPrefixChip.textContent = '-';
        dbDetailSourceChip.textContent = '-';
        dbDetailStateChip.textContent = '-';
      }
      renderDbList();
    }

    async function confirmDbDeleteLibrary() {
      if (isPublicLibraryActive()) {
        closeDbDeleteLibraryModal();
        showToast('公共工艺库只读，不能删除当前数据库。', 'warn');
        return;
      }

      const libraryKey = backendState.activeLibraryKey || 'public';
      try {
        await apiFetch(`/library/scopes/${encodeURIComponent(libraryKey)}`, { method: 'DELETE' });
        closeDbDeleteLibraryModal();
        await loadBackendLibrary(libraryKey);
        renderDbList();
      } catch (error) {
        console.error(error);
        showToast(error.message || '删除当前数据库失败', 'error');
      }
    }

    function resetDbFilters() {
      dbState.query = '';
      dbState.type = '全部';
      dbState.source = '全部来源';
      dbState.status = '全部状态';
      dbState.page = 1;
      dbSearchInput.value = '';
      dbTypeSelect.value = '全部';
      dbSourceSelect.value = '全部来源';
      dbStatusSelect.value = '全部状态';
      renderDbList();
    }

    function syncDbPageSize() {
      dbState.pageSize = Number(dbPageSizeSelect.value) || 3;
      dbState.page = 1;
      renderDbList();
    }

    function isPublicLibraryActive() {
      return String(backendState.activeLibraryKey || 'public') === 'public';
    }

    function updateDbDeleteState() {
      if (!dbDeleteBtn) return;
      const disableDelete = isPublicLibraryActive();
      dbDeleteBtn.disabled = disableDelete;
      dbDeleteBtn.textContent = disableDelete ? '公共库只读' : '删除废表';
    }

    function updateDbDeleteLibraryState() {
      if (!dbDeleteLibraryBtn) return;
      const disableDelete = isPublicLibraryActive();
      dbDeleteLibraryBtn.disabled = disableDelete;
      dbDeleteLibraryBtn.textContent = disableDelete ? '公共库只读' : '删除当前数据库';
    }

    function setDbBrowseOnlyMode(enabled) {
      backendState.dbBrowseOnly = !!enabled;
      refreshLibraryGate();
    }

    function preferredMyLibraryKey() {
      const scoped = (Array.isArray(backendState.libraryScopes) ? backendState.libraryScopes : [])
        .find((scope) => scope?.library_key && scope.scope_type !== 'public');
      if (scoped?.library_key) return scoped.library_key;
      const sessionScope = getSessionScopeKey();
      if (sessionScope && sessionScope !== 'public') return sessionScope;
      if (backendState.activeLibraryKey && backendState.activeLibraryKey !== 'public') return backendState.activeLibraryKey;
      return 'public';
    }

    async function openDbLibraryFromLock(libraryKey) {
      const key = libraryKey || 'public';
      setDbBrowseOnlyMode(true);
      backendState.activeLibraryKey = key;
      try {
        await loadBackendLibrary(key);
        activatePage('page-db');
        renderDbList();
      } catch (error) {
        console.warn('[demo] failed to open db browser:', error);
      }
    }

    function refreshLibraryGate() {
      const unlocked = !!backendState.canBrowseDb && hasSessionZipUnlocked();
      const browseOnly = !!backendState.dbBrowseOnly && !unlocked;
      const visible = unlocked || browseOnly;
      dbLockedState.style.display = visible ? 'none' : 'flex';
      dbReadyState.style.display = visible ? 'block' : 'none';
      if (dbBrowseBanner) dbBrowseBanner.style.display = browseOnly ? 'flex' : 'none';
      [dbEditBtn, dbSaveBtn, dbCancelBtn].forEach((button) => {
        if (button) button.disabled = browseOnly;
      });
      updateDbDeleteState();
      updateDbDeleteLibraryState();
      if (dbEditBtn) dbEditBtn.textContent = browseOnly ? '只读浏览' : '编辑记录';
      if (dbEditValue) dbEditValue.textContent = browseOnly ? '只读' : (dbEditorShell.classList.contains('active') ? '编辑中' : '启用');
      if (visible) renderDbList();
    }

    function refreshNoticePanel() {
      return;
    }

    function refreshCadPanel() {
      return;
    }

    function applyTaskDetail(key) {
      backendState.selectedTaskKey = key;
      const item = backendState.taskMap[key] || taskData[key];
      if (!item) return;
      const result = getTaskResult(key);
      if (!taskDetailTitle || !taskDetailMeta || !taskDetailStatus || !taskFieldStage || !taskFieldHit || !taskFieldFeature || !taskFieldCount || !taskProcessSummaryList) {
        return;
      }
      taskDetailTitle.textContent = item.title;
      taskDetailMeta.textContent = item.meta;
      taskDetailStatus.textContent = item.status;
      taskDetailStatus.className = `status-badge ${item.statusClass}`;
      taskFieldStage.textContent = item.stage;
      taskFieldHit.textContent = result ? getHistoryInfoText(result, item) : item.hit;
      taskFieldFeature.textContent = result ? getFeaturePreviewText(result, item.feature) : item.feature;
      taskFieldCount.textContent = result && parseProcessCount(result)
        ? `已输出 ${parseProcessCount(result)} 条工序，下方可查看历史工艺内容。`
        : item.count;
      renderTaskProcessSummary(key);
    }

    navItems.forEach(item => item.addEventListener('click', () => activatePage(item.dataset.page)));
    topTabs.forEach(tab => tab.addEventListener('click', () => activatePage(tab.dataset.page)));
    resultTabs.forEach(tab => tab.addEventListener('click', () => activateResultView(tab.dataset.resultView)));
    zipTabs.forEach(tab => tab.addEventListener('click', () => activateZipView(tab.dataset.zipView)));
    if (reviewTableHost) {
      reviewTableHost.addEventListener('input', syncReviewTextarea);
      reviewTableHost.addEventListener('blur', syncReviewTextarea, true);
    }

    function setStageState(activeIndex) {
      stageCards.forEach((card, index) => card.classList.toggle('active', index === activeIndex));
    }


function runGenerateFlow() {
      createHiddenFileInput('.prt,.prt.1,.prt.2,.prt.3,.prt.4,.prt.5,.prt.6,.prt.7,.prt.8,.prt.9,.pdf,.png,.jpg,.jpeg,.dxf,.dwg', true)
        .then((files) => uploadToBackend(files).catch((error) => {
          console.error(error);
          setDemoStatusText('上传失败');
          setWorkflowState('等待上传文件', 0, false);
        }));
    }

    function resetGenerateFlow() {
      location.reload();
    }

    function runZipFlow() {
      createHiddenFileInput('.zip', false)
        .then((files) => uploadToBackend(files).catch((error) => {
          console.error(error);
          zipBatchChip.textContent = '入库失败';
          backendState.zipBusy = false;
          updateNavigationLockState();
          updateZipConflictModeButton();
        }));
    }

    function resetZipFlow() {
      setZipImportState('等待批次', '等待上传工艺包');
      renderZipReport(backendState.latestZipReport || {});
      bootstrapBackend().catch(() => null);
    }

    function tickClock() {
      const now = new Date();
      const pad = (n) => String(n).padStart(2, '0');
    }

if (uploadGenerateBtn) uploadGenerateBtn.addEventListener('click', runGenerateFlow);
    if (resetGenerateBtn) resetGenerateBtn.addEventListener('click', resetGenerateFlow);
    if (featureCacheToggleBtn) featureCacheToggleBtn.addEventListener('click', () => {
      backendState.featureCacheEnabled = !backendState.featureCacheEnabled;
      const on = backendState.featureCacheEnabled;
      featureCacheToggleBtn.textContent = `⚡ 特征缓存：${on ? '开' : '关'}`;
      featureCacheToggleBtn.classList.toggle('is-active', on);
    });
    zipRunBtn.addEventListener('click', runZipFlow);

    // Detect backend restart and clear stale visual state
    checkStartupToken();
    loadZipLibraryList();

    if (sampleZipDownloadBtn) sampleZipDownloadBtn.addEventListener('click', downloadSampleZip);
    zipResetBtn.addEventListener('click', resetZipFlow);
    if (zipLibraryList) {
      zipLibraryList.addEventListener('change', () => {
        updateZipNewLibraryFormVisibility();
        updateZipActiveLibraryChip();
      });
    }
    if (zipLibraryNameInput) {
      zipLibraryNameInput.addEventListener('input', updateZipLibraryModeUI);
      zipLibraryNameInput.addEventListener('input', updateZipActiveLibraryChip);
    }
    if (zipConflictModeBtn) {
      zipConflictModeBtn.addEventListener('click', () => {
        if (backendState.zipBusy) return;
        backendState.zipConflictMode = backendState.zipConflictMode === 'replace' ? 'keep' : 'replace';
        updateZipConflictModeButton();
        setZipImportState('等待批次', backendState.zipConflictMode === 'replace' ? '当前冲突模式：替换入库' : '当前冲突模式：保留旧版', 0);
      });
    }
    if (zipMatchedPrevBtn) zipMatchedPrevBtn.addEventListener('click', () => shiftZipBrowserPage('matched', -1));
    if (zipMatchedNextBtn) zipMatchedNextBtn.addEventListener('click', () => shiftZipBrowserPage('matched', 1));
    if (zipUnmatchedPrevBtn) zipUnmatchedPrevBtn.addEventListener('click', () => shiftZipBrowserPage('unmatched', -1));
    if (zipUnmatchedNextBtn) zipUnmatchedNextBtn.addEventListener('click', () => shiftZipBrowserPage('unmatched', 1));
    goZipFromLockBtn.addEventListener('click', () => activatePage('page-zip'));
    if (viewPublicDbFromLockBtn) {
      viewPublicDbFromLockBtn.addEventListener('click', () => openDbLibraryFromLock('public'));
    }
    if (viewMyDbFromLockBtn) {
      viewMyDbFromLockBtn.addEventListener('click', () => openDbLibraryFromLock(preferredMyLibraryKey()));
    }
    if (dbUnlockHintBtn) {
      dbUnlockHintBtn.addEventListener('click', () => activatePage('page-zip'));
    }
    if (dbDeleteLibraryBtn) {
      dbDeleteLibraryBtn.addEventListener('click', openDbDeleteLibraryModal);
    }
    if (dbOpenImageSnapshotBtn) {
      dbOpenImageSnapshotBtn.addEventListener('click', openDbPreviewFromCurrent);
    }
    if (closeDbPreviewModal) {
      closeDbPreviewModal.onclick = closeDbPreviewModalView;
      closeDbPreviewModal.addEventListener('click', closeDbPreviewModalView);
    }
    if (dbPreviewModal) {
      dbPreviewModal.addEventListener('click', (event) => {
        if (event.target === dbPreviewModal) closeDbPreviewModalView();
      });
      dbPreviewModal.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') closeDbPreviewModalView();
      });
    }
    document.addEventListener('click', (event) => {
      if (event.target instanceof Element && event.target.closest('#closeDbPreviewModal')) {
        closeDbPreviewModalView();
      }
    });
    if (dbPreviewPrevBtn) {
      dbPreviewPrevBtn.addEventListener('click', () => {
        const preview = backendState.dbDetailPreview;
        if (!preview || !preview.images || preview.index <= 0) return;
        preview.index -= 1;
        const item = dbRecords[preview.key] || dbRecords[dbState.selectedKey] || {};
        renderDbPreviewSurface(item, preview.images, preview.index, '', preview.gltfUrl || '');
      });
    }
    if (dbPreviewNextBtn) {
      dbPreviewNextBtn.addEventListener('click', () => {
        const preview = backendState.dbDetailPreview;
        if (!preview || !preview.images || preview.index >= preview.images.length - 1) return;
        preview.index += 1;
        const item = dbRecords[preview.key] || dbRecords[dbState.selectedKey] || {};
        renderDbPreviewSurface(item, preview.images, preview.index, '', preview.gltfUrl || '');
      });
    }
    if (dbPreviewZoomOutBtn) {
      dbPreviewZoomOutBtn.addEventListener('click', () => {
        const preview = backendState.dbDetailPreview;
        if (!preview || !preview.images || !preview.images.length) return;
        dbPreviewZoom = Math.max(0.5, Math.round((dbPreviewZoom - 0.1) * 10) / 10);
        const item = dbRecords[preview.key] || dbRecords[dbState.selectedKey] || {};
        renderDbPreviewSurface(item, preview.images, preview.index, '', preview.gltfUrl || '');
      });
    }
    if (dbPreviewZoomInBtn) {
      dbPreviewZoomInBtn.addEventListener('click', () => {
        const preview = backendState.dbDetailPreview;
        if (!preview || !preview.images || !preview.images.length) return;
        dbPreviewZoom = Math.min(2, Math.round((dbPreviewZoom + 0.1) * 10) / 10);
        const item = dbRecords[preview.key] || dbRecords[dbState.selectedKey] || {};
        renderDbPreviewSurface(item, preview.images, preview.index, '', preview.gltfUrl || '');
      });
    }
    if (dbPreviewResetBtn) {
      dbPreviewResetBtn.addEventListener('click', () => {
        const preview = backendState.dbDetailPreview;
        if (!preview || !preview.images || !preview.images.length) return;
        dbPreviewZoom = 1;
        const item = dbRecords[preview.key] || dbRecords[dbState.selectedKey] || {};
        renderDbPreviewSurface(item, preview.images, preview.index, '', preview.gltfUrl || '');
      });
    }
    closeReviewModal.addEventListener('click', closeModal);
    reviewStayBtn.addEventListener('click', closeModal);
    reviewConfirmBtn.addEventListener('click', () => {
      closeModal();
      submitReview('continue').catch((error) => console.error(error));
    });
    if (reviewContinueBtn) {
      reviewContinueBtn.addEventListener('click', () => submitReview('continue').catch((error) => console.error(error)));
    }
    if (reviewRerunBtn) {
      reviewRerunBtn.addEventListener('click', () => submitReview('rerun').catch((error) => console.error(error)));
    }
    if (retrievalLibraryBtn) {
      retrievalLibraryBtn.addEventListener('click', openRetrievalLibraryModal);
    }
    if (closeRetrievalLibraryModalBtn) closeRetrievalLibraryModalBtn.addEventListener('click', closeRetrievalLibraryModal);
    if (cancelRetrievalLibraryBtn) cancelRetrievalLibraryBtn.addEventListener('click', closeRetrievalLibraryModal);
    if (confirmRetrievalLibraryBtn) confirmRetrievalLibraryBtn.addEventListener('click', confirmRetrievalLibrarySelection);
    if (retrievalLibrarySelect) {
      retrievalLibrarySelect.addEventListener('change', () => {
        backendState.retrievalLibraryKey = retrievalLibrarySelect.value || 'public';
        backendState.retrievalLibraryName = resolveLibraryScopeLabel(backendState.retrievalLibraryKey);
        renderRetrievalLibraryButton();
      });
    }
    if (retrievalLibraryModal) {
      retrievalLibraryModal.addEventListener('click', (event) => {
        if (event.target === retrievalLibraryModal) closeRetrievalLibraryModal();
      });
    }
    if (processResult) {
      processResult.addEventListener('click', (event) => {
        const el = event.target instanceof Element ? event.target : null;
        if (!el) return;
        if (el.closest('#openExportCardBtn')) { openExportEngineeringCard(); return; }
        // 编辑按钮
        const editBtn = el.closest('[data-process-edit]');
        if (editBtn) { openProcessRowEdit(editBtn.closest('tr')); return; }
        // 保存按钮
        const saveBtn = el.closest('[data-process-save]');
        if (saveBtn) { closeProcessRowEdit(saveBtn.closest('tr'), true); return; }
        // 取消按钮
        const cancelBtn = el.closest('[data-process-cancel]');
        if (cancelBtn) { closeProcessRowEdit(cancelBtn.closest('tr'), false); return; }
        // Clicking anywhere in a content cell (including padding) focuses the editable div
        const contentCell = el.closest('.step-content-cell');
        if (contentCell && !el.closest('[data-process-content]') && !el.closest('.process-content-edit')) {
          const editable = contentCell.querySelector('[data-process-content]');
          if (editable) {
            editable.focus();
            const range = document.createRange();
            range.selectNodeContents(editable);
            range.collapse(false);
            const sel = window.getSelection();
            if (sel) { sel.removeAllRanges(); sel.addRange(range); }
          }
        }
      });
      processResult.addEventListener('change', (event) => {
        const target = event.target instanceof Element ? event.target : null;
        if (!target) return;
        const sel = target.closest('.process-trade-select');
        if (sel) {
          const inp = sel.closest('.trade-edit')?.querySelector('.process-custom-trade');
          if (inp) {
            inp.style.display = sel.value === '其他' ? 'block' : 'none';
            if (sel.value === '其他') inp.focus();
          }
        }
      });
      processResult.addEventListener('input', (event) => {
        const target = event.target instanceof Element ? event.target : null;
        if (target && target.closest('[data-process-content]')) syncProcessTableToEditor();
      });
    }
    // ── Export modal event listeners ──
    if (exportModalCloseBtn) exportModalCloseBtn.addEventListener('click', closeExportModal);
    if (exportCancelBtn) exportCancelBtn.addEventListener('click', closeExportModal);
    if (exportModal) exportModal.addEventListener('click', function(e) { if (e.target === exportModal) closeExportModal(); });
    if (exportPdfBtn) exportPdfBtn.addEventListener('click', function() { downloadExport('pdf'); });
    if (exportExcelBtn) exportExcelBtn.addEventListener('click', function() { downloadExport('xlsx'); });
    if (uploadPanelBody) {
      uploadPanelBody.addEventListener('click', (event) => {
        const previewImage = event.target instanceof Element ? event.target.closest('#taskPreviewImage') : null;
        if (previewImage) {
          openPreviewFullscreen();
          return;
        }
        const button = event.target instanceof Element ? event.target.closest('.task-preview-btn') : null;
        if (!button) return;
        if (button.id === 'taskPreviewPrevBtn') {
          backendState.previewIndex = Math.max(0, backendState.previewIndex - 1);
        }
        if (button.id === 'taskPreviewNextBtn') {
          backendState.previewIndex = Math.min(Math.max((backendState.previewImages || []).length - 1, 0), backendState.previewIndex + 1);
        }
        if (button.id === 'taskPreviewZoomInBtn') {
          backendState.previewZoom = Math.min(2.4, (backendState.previewZoom || 1) + 0.2);
        }
        if (button.id === 'taskPreviewZoomOutBtn') {
          backendState.previewZoom = Math.max(0.6, (backendState.previewZoom || 1) - 0.2);
        }
        if (button.id === 'taskPreviewResetBtn') {
          backendState.previewZoom = 1;
          backendState.previewIndex = 0;
        }
        if (button.id === 'taskPreviewFullscreenBtn') {
          openPreviewFullscreen();
        }
        updateTaskPreviewSurface();
      });
    }
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') closeHistorySnapshotModalView();
      if (event.key === 'Escape') closePreviewFullscreen();
      if (event.key === 'Escape') closeRetrievalLibraryModal();
      if (event.key === 'Escape') closeExportModal();
    });
    if (workflowHudToggleBtn) {
      workflowHudToggleBtn.addEventListener('click', () => {
        if (!workflowHudCard) return;
        const collapsed = workflowHudCard.classList.toggle('collapsed');
        workflowHudToggleBtn.textContent = collapsed ? '展开' : '收起';
      });
    }
    if (editorTextarea) editorTextarea.addEventListener('input', refreshEditorPreview);
    if (dbEditorFeaturePageText) dbEditorFeaturePageText.addEventListener('input', syncDbFeatureReportEditor);
    dbEditBtn.addEventListener('click', () => toggleDbEditor());
    dbCancelBtn.addEventListener('click', () => {
      const current = dbRecords[dbState.selectedKey];
      backendState.dbFeatureReport = null;
      if (current) renderDbDetail(current);
      toggleDbEditor(false);
    });
    if (dbFeaturePrevBtn) dbFeaturePrevBtn.addEventListener('click', () => shiftDbFeatureReportPage(-1));
    if (dbFeatureNextBtn) dbFeatureNextBtn.addEventListener('click', () => shiftDbFeatureReportPage(1));
    dbSaveBtn.addEventListener('click', async () => {
      const current = dbRecords[dbState.selectedKey];
      if (current?.id) {
        const productType = String(dbEditorProductType?.value || '').trim();
        const content = String(dbEditorContent?.value || '').trim();
        const featureReportJson = buildDbFeatureReportPayload();
        const processLines = content
          ? content.split(/\r?\n/).map((line) => line.trim()).filter(Boolean)
          : [];
        try {
          await apiFetch(`/library/records/${current.id}?library_key=${encodeURIComponent(backendState.activeLibraryKey || 'public')}`, { method: 'PUT', body: JSON.stringify({
            library_key: backendState.activeLibraryKey || 'public',
            prefix: current.title,
            product_type: productType || current.type,
            process_summary: current.summary,
            context: content || current.content || current.summary,
            tech_requirement: current.requirement || current.techRequirement || current.tech_requirement || '',
            process_list: processLines.length ? processLines : (current.process_list || []),
            content: content || processLines.join('\n'),
            feature_report_json: featureReportJson || current.featureReportJson || {},
            feature_report_text: featureReportJson ? '' : (current.featureReportText || ''),
            feature_report_path: current.featureReportPath || '',
          }) });
          await loadBackendLibrary(backendState.activeLibraryKey);
        } catch (error) {
          console.error(error);
          showToast(error.message || '保存失败', 'error');
        }
        toggleDbEditor(false);
        return;
      }

      if (current) {
        const next = { ...current };
        if (dbEditorProductType) next.type = dbEditorProductType.value.trim() || next.type;
        if (dbEditorContent) next.content = dbEditorContent.value.trim() || next.content;
        dbRecords[dbState.selectedKey] = next;
        renderDbDetail(next);
        renderDbList();
      }
      toggleDbEditor(false);
    });
    dbDeleteBtn.addEventListener('click', openDbDeleteModal);
    if (dbDeleteLibraryBtn) dbDeleteLibraryBtn.addEventListener('click', openDbDeleteLibraryModal);
    closeDbDeleteModalBtn.addEventListener('click', closeDbDeleteModal);
    cancelDbDeleteBtn.addEventListener('click', closeDbDeleteModal);
    confirmDbDeleteBtn.addEventListener('click', confirmDbDelete);
    dbDeleteModal.addEventListener('click', (event) => {
      if (event.target === dbDeleteModal) closeDbDeleteModal();
    });
    if (closeDbDeleteLibraryModalBtn) closeDbDeleteLibraryModalBtn.addEventListener('click', closeDbDeleteLibraryModal);
    if (cancelDbDeleteLibraryBtn) cancelDbDeleteLibraryBtn.addEventListener('click', closeDbDeleteLibraryModal);
    if (confirmDbDeleteLibraryBtn) confirmDbDeleteLibraryBtn.addEventListener('click', () => confirmDbDeleteLibrary().catch((error) => console.error(error)));
    if (dbDeleteLibraryModal) {
      dbDeleteLibraryModal.addEventListener('click', (event) => {
        if (event.target === dbDeleteLibraryModal) closeDbDeleteLibraryModal();
      });
    }
    if (historyRefreshBtn) {
      historyRefreshBtn.addEventListener('click', () => {
        loadBackendHistory().catch(() => renderHistoryPage());
      });
    }
    if (historyCompletedDateInput) {
      historyCompletedDateInput.value = backendState.historyCompletedDate;
      historyCompletedDateInput.addEventListener('change', () => {
        applyHistoryCompletedDateFilter(historyCompletedDateInput.value);
      });
    }
    if (historyClearFilterBtn) {
      historyClearFilterBtn.addEventListener('click', () => {
        if (historyCompletedDateInput) historyCompletedDateInput.value = '';
        applyHistoryCompletedDateFilter('');
      });
    }
    if (historyPrevBtn) {
      historyPrevBtn.addEventListener('click', () => {
        backendState.historyPage = Math.max(1, backendState.historyPage - 1);
        renderHistoryPage();
      });
    }
    if (historyNextBtn) {
      historyNextBtn.addEventListener('click', () => {
        backendState.historyPage += 1;
        renderHistoryPage();
      });
    }
    dbApplyBtn.addEventListener('click', () => {
      dbState.query = dbSearchInput.value.trim();
      dbState.type = dbTypeSelect.value;
      dbState.source = dbSourceSelect.value;
      dbState.status = dbStatusSelect.value;
      dbState.page = 1;
      renderDbList();
    });
    dbResetBtn.addEventListener('click', resetDbFilters);
    dbResetFiltersBtn.addEventListener('click', resetDbFilters);
    dbRefreshBtn.addEventListener('click', renderDbList);
    dbPageSizeSelect.addEventListener('change', syncDbPageSize);
    if (dbLibrarySelect) {
      dbLibrarySelect.addEventListener('change', async () => {
        backendState.activeLibraryKey = dbLibrarySelect.value || 'public';
        await loadBackendLibrary(backendState.activeLibraryKey);
      });
    }
    dbSearchInput.addEventListener('input', () => {
      dbState.query = dbSearchInput.value.trim();
      dbState.page = 1;
      renderDbList();
    });
    [dbTypeSelect, dbSourceSelect, dbStatusSelect].forEach((select) => {
      select.addEventListener('change', () => {
        dbState.type = dbTypeSelect.value;
        dbState.source = dbSourceSelect.value;
        dbState.status = dbStatusSelect.value;
        dbState.page = 1;
        renderDbList();
      });
    });
    dbPrevBtn.addEventListener('click', () => {
      dbState.page = Math.max(1, dbState.page - 1);
      renderDbList();
    });
    dbNextBtn.addEventListener('click', () => {
      dbState.page += 1;
      renderDbList();
    });
    dbRecordList.addEventListener('click', (event) => {
      const button = event.target.closest('[data-db-record]');
      if (!button) return;
      selectDbRecord(button.dataset.dbRecord);
    });
    if (historyTableBody) {
      historyTableBody.addEventListener('click', (event) => {
        const snapshotBtn = event.target.closest('[data-history-snapshot]');
        if (snapshotBtn) {
          openHistorySnapshot(snapshotBtn.dataset.historySnapshot);
          return;
        }
        const deleteBtn = event.target.closest('[data-delete-task-id]');
        if (deleteBtn) {
          const taskId = deleteBtn.dataset.deleteTaskId;
          if (confirm(`确认删除此历史记录？\n\n任务ID: ${taskId}\n删除后本地文件将一并清除，此操作不可恢复。`)) {
            deleteHistoryTask(taskId, deleteBtn);
          }
          return;
        }
        const rowCheck = event.target.closest('[data-select-task-id]');
        if (rowCheck) {
          const taskId = rowCheck.dataset.selectTaskId;
          if (rowCheck.checked) {
            backendState.historySelected.add(taskId);
          } else {
            backendState.historySelected.delete(taskId);
          }
          updateHistorySelectAllState();
          updateHistoryBatchDeleteBtn();
        }
      });
      if (historySelectAll) {
        historySelectAll.addEventListener('change', () => {
          const entries = getFilteredHistoryEntries();
          const pageSize = Math.max(1, Number(backendState.historyPageSize) || 6);
          const start = (backendState.historyPage - 1) * pageSize;
          const pageItems = entries.slice(start, start + pageSize);
          if (historySelectAll.checked) {
            pageItems.forEach(({ card }) => backendState.historySelected.add(card.taskId));
          } else {
            pageItems.forEach(({ card }) => backendState.historySelected.delete(card.taskId));
          }
          renderHistoryPage();
          updateHistoryBatchDeleteBtn();
        });
      }
      if (historyBatchDeleteBtn) {
        historyBatchDeleteBtn.addEventListener('click', async () => {
          const ids = Array.from(backendState.historySelected);
          if (!ids.length) return;
          if (!confirm(`确认删除选中的 ${ids.length} 条历史记录？\n\n删除后本地文件将一并清除，此操作不可恢复。`)) return;
          historyBatchDeleteBtn.disabled = true;
          historyBatchDeleteBtn.textContent = '删除中…';
          let failCount = 0;
          for (const taskId of ids) {
            try {
              await apiFetch(`/history/${encodeURIComponent(taskId)}`, { method: 'DELETE' });
              backendState.history = (backendState.history || []).filter((item) => item.task_id !== taskId);
              backendState.historySelected.delete(taskId);
            } catch (e) {
              failCount++;
              console.warn(`[demo] delete failed for ${taskId}:`, e);
            }
          }
          if (failCount) showToast((ids.length - failCount) + ' 条已删除，' + failCount + ' 条失败。', 'warn');
          updateHistoryBatchDeleteBtn();
          updateHistorySelectAllState();
          renderHistoryPage();
        });
      }
    }
    if (historySnapshotModal) {
      historySnapshotModal.addEventListener('click', (event) => {
        if (event.target === historySnapshotModal) closeHistorySnapshotModalView();
      });
    }
    if (closeHistorySnapshotModal) closeHistorySnapshotModal.addEventListener('click', closeHistorySnapshotModalView);
    if (historySnapshotPrevBtn) {
      historySnapshotPrevBtn.addEventListener('click', () => {
        const state = backendState.historySnapshot;
        if (!state) return;
        state.index = Math.max(0, state.index - 1);
        updateHistorySnapshotSurface();
      });
    }
    if (historySnapshotNextBtn) {
      historySnapshotNextBtn.addEventListener('click', () => {
        const state = backendState.historySnapshot;
        if (!state) return;
        state.index = Math.min(Math.max((state.images || []).length - 1, 0), state.index + 1);
        updateHistorySnapshotSurface();
      });
    }
    if (historySnapshotZoomInBtn) {
      historySnapshotZoomInBtn.addEventListener('click', () => {
        const state = backendState.historySnapshot;
        if (!state) return;
        state.zoom = Math.min(2.4, (state.zoom || 1) + 0.2);
        updateHistorySnapshotSurface();
      });
    }
    if (historySnapshotZoomOutBtn) {
      historySnapshotZoomOutBtn.addEventListener('click', () => {
        const state = backendState.historySnapshot;
        if (!state) return;
        state.zoom = Math.max(0.6, (state.zoom || 1) - 0.2);
        updateHistorySnapshotSurface();
      });
    }
    if (historySnapshotResetBtn) {
      historySnapshotResetBtn.addEventListener('click', () => {
        const state = backendState.historySnapshot;
        if (!state) return;
        state.zoom = 1;
        state.index = 0;
        updateHistorySnapshotSurface();
      });
    }
    if (sidebarToggleBtn) {
      sidebarToggleBtn.addEventListener('click', () => {
        applySidebarCollapsedState(!document.body.classList.contains('sidebar-collapsed'));
      });
    }
    document.querySelectorAll('[data-task]').forEach((button) => {
      button.addEventListener('click', () => applyTaskDetail(button.dataset.task));
    });

    refreshEditorPreview();
    applyTaskDetail('spindle');
    applyDbRecord('box');
    renderTaskCards();
    renderLibraryScopes();
    updateZipLibraryModeUI();
    renderHistoryPage();
    dbSearchInput.value = dbState.query;
    dbTypeSelect.value = dbState.type;
    dbSourceSelect.value = dbState.source;
    dbStatusSelect.value = dbState.status;
    dbPageSizeSelect.value = String(dbState.pageSize);
    renderDbList();
    refreshLibraryGate();
    bootstrapBackend().catch(() => null);
    tickClock();
    setInterval(tickClock, 1000);

    let resizing = false;
    demoResizer.addEventListener('mousedown', (event) => {
      event.preventDefault();
      resizing = true;
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
    });

    window.addEventListener('mousemove', (event) => {
      if (!resizing) return;
      const rect = workbench.getBoundingClientRect();
      const left = Math.min(Math.max(event.clientX - rect.left, 320), rect.width - 440);
      workbench.style.gridTemplateColumns = `${left}px 14px minmax(420px, 1fr)`;
    });

    window.addEventListener('mouseup', () => {
      resizing = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    });

    // ============ 3D Model Preview (inline in upload panel) ============
    let preview3DScene = null, preview3DCamera = null, preview3DRenderer = null, preview3DAnimId = null;

    // Shared factory: creates an independent 3D viewer instance (for modals)
    function make3DViewer() {
      let _scene = null, _camera = null, _renderer = null, _animId = null;
      function _setup3DScene(container, gltfUrl) {
        if (typeof THREE === 'undefined') { setTimeout(() => _setup3DScene(container, gltfUrl), 200); return; }
        container.innerHTML = '';
        const w = container.clientWidth || 480;
        const h = container.clientHeight || 380;
        _scene = new THREE.Scene();
        _scene.background = new THREE.Color(0xdce2ec);
        _camera = new THREE.PerspectiveCamera(45, w / h, 0.1, 1000);
        _camera.position.set(4, 3, 5);
        _camera.lookAt(0, 0, 0);
        _renderer = new THREE.WebGLRenderer({ antialias: true });
        _renderer.setSize(w, h);
        _renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        _renderer.domElement.style.display = 'block';
        container.appendChild(_renderer.domElement);
        _scene.add(new THREE.AmbientLight(0xffffff, 3.5));
        const d1 = new THREE.DirectionalLight(0xffffff, 2.5); d1.position.set(5, 10, 7); _scene.add(d1);
        const d2 = new THREE.DirectionalLight(0x88aacc, 1.2); d2.position.set(-5, -2, -3); _scene.add(d2);
        _scene.add(new THREE.GridHelper(8, 16, 0x9aa5b8, 0xb8c2d0));
        if (gltfUrl && typeof THREE.GLTFLoader !== 'undefined') {
          new THREE.GLTFLoader().load(gltfUrl, (gltf) => {
            if (!_scene) return;
            _scene.add(gltf.scene);
            const box = new THREE.Box3().setFromObject(gltf.scene);
            const center = box.getCenter(new THREE.Vector3());
            const size = box.getSize(new THREE.Vector3());
            const maxDim = Math.max(size.x, size.y, size.z);
            if (maxDim > 0.001) {
              const scale = 4 / maxDim;
              gltf.scene.scale.setScalar(scale);
              gltf.scene.position.set(-center.x * scale, -center.y * scale, -center.z * scale);
            }
          }, undefined, () => addFallbackBox(_scene));
        } else { addFallbackBox(_scene); }
        let dragging = false, prevX = 0, prevY = 0, rotX = 0.3, rotY = 0.5, dist = 6;
        container.onmousedown = (e) => { dragging = true; prevX = e.clientX; prevY = e.clientY; container.style.cursor = 'grabbing'; };
        window.addEventListener('mouseup', () => { dragging = false; if (container.isConnected) container.style.cursor = 'grab'; });
        window.addEventListener('mousemove', (e) => {
          if (!dragging) return;
          rotY += (e.clientX - prevX) * 0.005; rotX += (e.clientY - prevY) * 0.005;
          rotX = Math.max(-1.4, Math.min(1.4, rotX)); prevX = e.clientX; prevY = e.clientY;
        });
        container.addEventListener('wheel', (e) => { e.preventDefault(); dist = Math.max(2, Math.min(15, dist + e.deltaY * 0.01)); }, { passive: false });
        const s = _scene, r = _renderer, c = _camera;
        (function tick() { _animId = requestAnimationFrame(tick); const x = dist*Math.sin(rotY)*Math.cos(rotX), y = dist*Math.sin(rotX), z = dist*Math.cos(rotY)*Math.cos(rotX); c.position.set(x,y,z); c.lookAt(0,0,0); r.render(s,c); })();
      }
      return {
        render(gltfUrl, container) { this.dispose(); if (container) _setup3DScene(container, gltfUrl); },
        dispose() { if (_animId) { cancelAnimationFrame(_animId); _animId = null; } if (_renderer) { _renderer.dispose(); _renderer = null; } _scene = null; _camera = null; },
      };
    }
    function render3DPreview(gltfUrl, containerId) {
      if (typeof THREE === 'undefined') { setTimeout(() => render3DPreview(gltfUrl, containerId), 200); return; }
      const container = document.getElementById(containerId);
      if (!container) return;

      container.innerHTML = "";
      container.style.cursor = "grab";

      const w = container.clientWidth || 600;
      const h = Math.max(container.clientHeight || 0, 420);

      const scene = new THREE.Scene();
      scene.background = new THREE.Color(0xdce2ec);
      preview3DScene = scene;

      const camera = new THREE.PerspectiveCamera(45, w / h, 0.1, 1000);
      camera.position.set(4, 3, 5);
      camera.lookAt(0, 0, 0);
      preview3DCamera = camera;

      const renderer = new THREE.WebGLRenderer({ antialias: true });
      renderer.setSize(w, h);
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      renderer.domElement.style.display = "block";
      container.appendChild(renderer.domElement);
      preview3DRenderer = renderer;

      scene.add(new THREE.AmbientLight(0xffffff, 3.5));
      const d1 = new THREE.DirectionalLight(0xffffff, 2.5);
      d1.position.set(5, 10, 7);
      scene.add(d1);
      const d2 = new THREE.DirectionalLight(0x88aacc, 1.2);
      d2.position.set(-5, -2, -3);
      scene.add(d2);

      scene.add(new THREE.GridHelper(8, 16, 0x9aa5b8, 0xb8c2d0));

      if (gltfUrl) {
        loadModelIntoScene(gltfUrl, scene);
      } else {
        addFallbackBox(scene);
      }

      // Orbit: drag to rotate, scroll to zoom
      let dragging = false, prevX = 0, prevY = 0, rotX = 0.3, rotY = 0.5, dist = 6;
      container.onmousedown = (e) => { dragging = true; prevX = e.clientX; prevY = e.clientY; container.style.cursor = "grabbing"; };
      window.addEventListener("mouseup", () => { dragging = false; container.style.cursor = "grab"; });
      window.addEventListener("mousemove", (e) => {
        if (!dragging) return;
        rotY += (e.clientX - prevX) * 0.005;
        rotX += (e.clientY - prevY) * 0.005;
        rotX = Math.max(-1.4, Math.min(1.4, rotX));
        prevX = e.clientX; prevY = e.clientY;
      });
      container.addEventListener("wheel", (e) => {
        e.preventDefault();
        dist = Math.max(2, Math.min(15, dist + e.deltaY * 0.01));
      }, { passive: false });

      function animate() {
        preview3DAnimId = requestAnimationFrame(animate);
        const x = dist * Math.sin(rotY) * Math.cos(rotX);
        const y = dist * Math.sin(rotX);
        const z = dist * Math.cos(rotY) * Math.cos(rotX);
        camera.position.set(x, y, z);
        camera.lookAt(0, 0, 0);
        renderer.render(scene, camera);
      }
      animate();
      console.log("[3D] Preview viewer initialized, gltf:", gltfUrl || "fallback");
    }

    function loadModelIntoScene(url, scene) {
      if (typeof THREE.GLTFLoader !== "undefined") {
        new THREE.GLTFLoader().load(url, (gltf) => {
          scene.add(gltf.scene);
          const box = new THREE.Box3().setFromObject(gltf.scene);
          const center = box.getCenter(new THREE.Vector3());
          const size = box.getSize(new THREE.Vector3());
          const maxDim = Math.max(size.x, size.y, size.z);
          if (maxDim > 0.001) {
            const scale = 4 / maxDim;
            gltf.scene.scale.setScalar(scale);
            // Center model at world origin after scaling
            gltf.scene.position.set(
              -center.x * scale,
              -center.y * scale,
              -center.z * scale
            );
          }
          console.log("[3D] glTF loaded:", url, "maxDim:", maxDim.toFixed(3));
        }, undefined, () => {
          console.warn("[3D] glTF load failed, fallback box");
          addFallbackBox(scene);
        });
      } else {
        addFallbackBox(scene);
      }
    }

    function addFallbackBox(scene) {
      const geo = new THREE.BoxGeometry(2, 2, 2);
      const mat = new THREE.MeshPhongMaterial({ color: 0x4488cc, specular: 0x111122, shininess: 30 });
      const mesh = new THREE.Mesh(geo, mat);
      mesh.position.y = 1;
      scene.add(mesh);
    }

    function dispose3DPreview() {
      if (preview3DAnimId) { cancelAnimationFrame(preview3DAnimId); preview3DAnimId = null; }
      if (preview3DRenderer) { preview3DRenderer.dispose(); preview3DRenderer = null; }
      preview3DScene = null; preview3DCamera = null;
    }

/* ===================================
   ENHANCEMENT PATCH — micro-interactions
   =================================== */

(function() {
  'use strict';

  // ── 1. Dropzone drag-over visual feedback ──
  document.querySelectorAll('.dropzone').forEach(function(zone) {
    zone.addEventListener('dragover', function(e) {
      e.preventDefault();
      zone.classList.add('dragover');
    });
    zone.addEventListener('dragleave', function(e) {
      if (!zone.contains(e.relatedTarget)) {
        zone.classList.remove('dragover');
      }
    });
    zone.addEventListener('drop', function() {
      zone.classList.remove('dragover');
    });
  });

  // ── 2. Button ripple effect ──
  document.addEventListener('click', function(e) {
    var btn = e.target.closest('.button');
    if (!btn) return;
    var existing = btn.querySelector('.btn-ripple');
    if (existing) existing.remove();

    var rect = btn.getBoundingClientRect();
    var ripple = document.createElement('span');
    var size = Math.max(rect.width, rect.height) * 1.8;
    ripple.className = 'btn-ripple';
    ripple.style.cssText = [
      'position:absolute',
      'pointer-events:none',
      'border-radius:50%',
      'background:rgba(255,255,255,0.35)',
      'width:' + size + 'px',
      'height:' + size + 'px',
      'left:' + (e.clientX - rect.left - size / 2) + 'px',
      'top:' + (e.clientY - rect.top - size / 2) + 'px',
      'transform:scale(0)',
      'transition:transform 0.45s ease, opacity 0.45s ease',
      'z-index:10'
    ].join(';');
    btn.appendChild(ripple);
    requestAnimationFrame(function() {
      ripple.style.transform = 'scale(1)';
      ripple.style.opacity = '0';
    });
    setTimeout(function() { ripple.remove(); }, 500);
  });

  // ── 3. Log line stagger on append ──
  var originalAppendChild = Element.prototype.appendChild;
  function hookLogList(listEl) {
    if (!listEl || listEl._hookedLog) return;
    listEl._hookedLog = true;
    var obs = new MutationObserver(function(mutations) {
      mutations.forEach(function(m) {
        m.addedNodes.forEach(function(node) {
          if (node.nodeType === 1 && node.classList.contains('log-line')) {
            node.style.animationDelay = '0ms';
            node.style.animationDuration = '0.22s';
          }
        });
      });
    });
    obs.observe(listEl, { childList: true });
  }

  var logLists = document.querySelectorAll('.log-list');
  logLists.forEach(hookLogList);

  // ── 4. Summary card count flash on value change ──
  var summaryValues = document.querySelectorAll('.summary-card strong, .db-stat-value');
  summaryValues.forEach(function(el) {
    var lastVal = el.textContent;
    var obs = new MutationObserver(function() {
      if (el.textContent !== lastVal) {
        lastVal = el.textContent;
        el.style.animation = 'none';
        requestAnimationFrame(function() {
          el.style.animation = 'count-up-flash 0.5s ease';
        });
      }
    });
    obs.observe(el, { childList: true, characterData: true, subtree: true });
  });

  // ── 5. Nav item tooltip when collapsed ──
  var navItems = document.querySelectorAll('.nav-item');
  navItems.forEach(function(item) {
    var title = item.querySelector('.nav-title');
    if (!title) return;
    item.setAttribute('title', title.textContent);
  });

  // ── 6. Batch step highlight on progress ──
  function updateBatchSteps(percent) {
    var steps = document.querySelectorAll('.batch-step');
    var count = steps.length;
    var activeIdx = Math.min(Math.floor((percent / 100) * count), count - 1);
    steps.forEach(function(s, i) {
      s.classList.toggle('active', i === activeIdx);
    });
  }

  // Hook into workflowProgressBar width changes
  var progressBar = document.getElementById('workflowProgressBar');
  if (progressBar) {
    var progObs = new MutationObserver(function() {
      var w = parseFloat(progressBar.style.width) || 0;
      updateBatchSteps(w);
    });
    progObs.observe(progressBar, { attributes: true, attributeFilter: ['style'] });
  }

  // ── 7. Smooth page switching with fade ──
  var pageButtons = document.querySelectorAll('.nav-item[data-page]');
  pageButtons.forEach(function(btn) {
    btn.addEventListener('click', function() {
      var pages = document.querySelectorAll('.page');
      pages.forEach(function(p) {
        if (p.classList.contains('active')) {
          p.style.opacity = '0';
          p.style.transition = 'opacity 0.14s ease';
          setTimeout(function() {
            p.style.opacity = '';
            p.style.transition = '';
          }, 140);
        }
      });
    });
  });

  // ── 8. Result tab change animation ──
  var resultTabsAll = document.querySelectorAll('.result-tab');
  resultTabsAll.forEach(function(tab) {
    tab.addEventListener('click', function() {
      var targetId = tab.dataset.resultView || tab.dataset.zipView;
      if (!targetId) return;
      var view = document.getElementById(targetId);
      if (view) {
        view.style.animation = 'none';
        requestAnimationFrame(function() {
          view.style.animation = 'page-enter 0.22s cubic-bezier(0.16, 1, 0.3, 1) both';
        });
      }
    });
  });

  // ── 9. Focus ring enhancement for keyboard users ──
  var usingKeyboard = false;
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Tab') usingKeyboard = true;
  });
  document.addEventListener('mousedown', function() {
    usingKeyboard = false;
  });

  // ── 10. Sidebar collapse button label toggle ──
  var collapseBtn = document.getElementById('sidebarToggleBtn');
  if (collapseBtn) {
    var observer = new MutationObserver(function() {
      var isCollapsed = document.body.classList.contains('sidebar-collapsed');
      collapseBtn.textContent = isCollapsed ? '展开侧栏' : '折叠侧栏';
    });
    observer.observe(document.body, { attributes: true, attributeFilter: ['class'] });
  }

})();

