"""生成二维工艺系统介绍 PPT"""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
import os

# ── 常量 ──
DOC_DIR = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = DOC_DIR  # 截图都在 docs/ 下

# 品牌色
C_PRIMARY   = RGBColor(0x1A, 0x56, 0xDB)  # 蓝色
C_ACCENT    = RGBColor(0xFF, 0x65, 0x28)  # 橙色
C_BG_DARK   = RGBColor(0x0F, 0x17, 0x2A)  # 深蓝背景
C_BG_WHITE  = RGBColor(0xFF, 0xFF, 0xFF)
C_TEXT_W     = RGBColor(0xFF, 0xFF, 0xFF)
C_TEXT_L     = RGBColor(0xCC, 0xD5, 0xE0)
C_TEXT_D     = RGBColor(0x1E, 0x29, 0x3B)
C_TEXT_G     = RGBColor(0x64, 0x74, 0x8B)
C_GREEN     = RGBColor(0x10, 0xB9, 0x81)
C_YELLOW    = RGBColor(0xF5, 0x9E, 0x0B)
C_RED       = RGBColor(0xEF, 0x44, 0x44)
C_PURPLE    = RGBColor(0x63, 0x66, 0xF1)
C_CARD_BG   = RGBColor(0x1E, 0x29, 0x3B)
C_CARD_BG2  = RGBColor(0xF1, 0xF5, 0xF9)

prs = Presentation()
prs.slide_width  = Inches(13.333)
prs.slide_height = Inches(7.5)
SW = prs.slide_width
SH = prs.slide_height


# ════════════════════════════════════════
# 工具函数
# ════════════════════════════════════════

def add_bg(slide, color):
    """设置幻灯片背景色"""
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color

def add_shape(slide, left, top, width, height, fill_color=None, line_color=None, line_width=None, shape_type=MSO_SHAPE.RECTANGLE):
    """添加形状"""
    shape = slide.shapes.add_shape(shape_type, left, top, width, height)
    shape.line.fill.background()
    if fill_color:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill_color
    else:
        shape.fill.background()
    if line_color:
        shape.line.color.rgb = line_color
        shape.line.width = line_width or Pt(1)
    return shape

def add_text(slide, left, top, width, height, text, font_size=18, color=C_TEXT_D, bold=False, alignment=PP_ALIGN.LEFT, font_name="Microsoft YaHei"):
    """添加文本框"""
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(font_size)
    p.font.color.rgb = color
    p.font.bold = bold
    p.font.name = font_name
    p.alignment = alignment
    return txBox

def add_multiline(slide, left, top, width, height, lines, font_size=16, color=C_TEXT_D, line_spacing=1.5, bullet=False):
    """添加多行文本框"""
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    for i, line in enumerate(lines):
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.text = line
        p.font.size = Pt(font_size)
        p.font.color.rgb = color
        p.font.name = "Microsoft YaHei"
        p.space_after = Pt(font_size * (line_spacing - 1))
        if bullet:
            p.level = 0
    return txBox

def add_card(slide, left, top, width, height, title, body, title_color=C_PRIMARY, bg_color=C_CARD_BG2):
    """添加卡片（白底圆角风格）"""
    shape = add_shape(slide, left, top, width, height, fill_color=bg_color)
    # 标题
    add_text(slide, left + Inches(0.2), top + Inches(0.15), width - Inches(0.4), Inches(0.4),
             title, font_size=16, color=title_color, bold=True)
    # 内容
    if isinstance(body, list):
        add_multiline(slide, left + Inches(0.2), top + Inches(0.55), width - Inches(0.4), height - Inches(0.7),
                      body, font_size=13, color=C_TEXT_G, line_spacing=1.4)
    else:
        add_text(slide, left + Inches(0.2), top + Inches(0.55), width - Inches(0.4), height - Inches(0.7),
                 body, font_size=13, color=C_TEXT_G)
    return shape

def add_section_header(slide, text, subtitle=""):
    """添加页面顶部标题栏"""
    # 蓝色顶条
    add_shape(slide, 0, 0, SW, Inches(0.06), fill_color=C_PRIMARY)
    # 标题
    add_text(slide, Inches(0.8), Inches(0.4), Inches(10), Inches(0.6),
             text, font_size=32, color=C_TEXT_D, bold=True)
    if subtitle:
        add_text(slide, Inches(0.8), Inches(0.95), Inches(10), Inches(0.4),
                 subtitle, font_size=16, color=C_TEXT_G)
    # 分隔线
    add_shape(slide, Inches(0.8), Inches(1.35), Inches(11.7), Inches(0.02), fill_color=RGBColor(0xE2, 0xE8, 0xF0))


def safe_img(name):
    """安全获取图片路径"""
    p = os.path.join(IMG_DIR, name)
    return p if os.path.exists(p) else None


# ════════════════════════════════════════
# P1 — 封面
# ════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
add_bg(slide, C_BG_DARK)

# 左侧装饰条
add_shape(slide, Inches(0.8), Inches(1.5), Inches(0.06), Inches(4.5), fill_color=C_PRIMARY)

# 主标题
add_text(slide, Inches(1.3), Inches(2.0), Inches(8), Inches(1.0),
         "二维工艺系统", font_size=48, color=C_TEXT_W, bold=True)

# 副标题
add_text(slide, Inches(1.3), Inches(3.1), Inches(9), Inches(0.6),
         "基于 2D 工艺图纸的 AI 智能工艺规程生成系统", font_size=22, color=C_TEXT_L)

# 分隔线
add_shape(slide, Inches(1.3), Inches(3.9), Inches(3), Inches(0.03), fill_color=C_ACCENT)

# 底部信息
add_text(slide, Inches(1.3), Inches(4.3), Inches(6), Inches(0.4),
         "2026 年 6 月", font_size=16, color=C_TEXT_G)

# 右侧装饰方块
add_shape(slide, Inches(10), Inches(1.5), Inches(2.5), Inches(2.5), fill_color=C_PRIMARY)
add_shape(slide, Inches(10.3), Inches(1.8), Inches(2.5), Inches(2.5),
          fill_color=None, line_color=C_ACCENT, line_width=Pt(2))

# 技术标签
tags = ["VLM 视觉提取", "RAG 检索增强", "SSE 流式输出", "SVG 标注"]
for i, tag in enumerate(tags):
    x = Inches(1.3 + i * 2.5)
    y = Inches(5.3)
    s = add_shape(slide, x, y, Inches(2.2), Inches(0.45), fill_color=C_CARD_BG)
    add_text(slide, x, y + Inches(0.05), Inches(2.2), Inches(0.35),
             tag, font_size=13, color=C_TEXT_L, alignment=PP_ALIGN.CENTER)


# ════════════════════════════════════════
# P2 — 项目背景
# ════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, C_BG_WHITE)
add_section_header(slide, "项目背景", "行业痛点与系统定位")

# 左侧：行业痛点
add_text(slide, Inches(0.8), Inches(1.6), Inches(5.5), Inches(0.5),
         "行业痛点", font_size=22, color=C_RED, bold=True)

pains = [
    ("效率低", "传统工艺规程编写依赖人工经验，单件耗时 1-2 小时"),
    ("易遗漏", "2D 图纸特征提取纯靠手工，尺寸公差、粗糙度等易漏项"),
    ("难复用", "工艺知识分散在个人经验和 Excel 表格中，难以传承"),
    ("重复劳动", "同类零件重复编写工艺规程，浪费大量工时"),
]
for i, (title, desc) in enumerate(pains):
    y = Inches(2.2 + i * 1.1)
    # 红色圆点
    add_shape(slide, Inches(1.0), y + Inches(0.08), Inches(0.18), Inches(0.18),
              fill_color=C_RED, shape_type=MSO_SHAPE.OVAL)
    add_text(slide, Inches(1.35), y, Inches(1.2), Inches(0.35),
             title, font_size=16, color=C_TEXT_D, bold=True)
    add_text(slide, Inches(1.35), y + Inches(0.35), Inches(5), Inches(0.5),
             desc, font_size=14, color=C_TEXT_G)

# 右侧：系统定位
add_shape(slide, Inches(7.2), Inches(1.6), Inches(5.3), Inches(5.2), fill_color=RGBColor(0xEF, 0xF6, 0xFF))
add_text(slide, Inches(7.5), Inches(1.8), Inches(4.8), Inches(0.5),
         "系统定位", font_size=22, color=C_PRIMARY, bold=True)

add_text(slide, Inches(7.5), Inches(2.5), Inches(4.8), Inches(0.8),
         "用 AI 替代重复劳动，让工艺工程师聚焦核心判断",
         font_size=16, color=C_TEXT_D, bold=True)

flow_items = [
    ("输入", "2D 工艺图纸（PDF/PNG/JPG）\n或 3D 模型（PRT）"),
    ("输出", "结构化工艺规程\n（工序号、工种、工序内容）"),
    ("核心", "VLM 视觉特征提取\n+ RAG 知识库检索增强生成"),
]
for i, (label, desc) in enumerate(flow_items):
    y = Inches(3.3 + i * 1.2)
    add_shape(slide, Inches(7.5), y, Inches(0.9), Inches(0.4), fill_color=C_PRIMARY)
    add_text(slide, Inches(7.5), y + Inches(0.02), Inches(0.9), Inches(0.35),
             label, font_size=13, color=C_TEXT_W, alignment=PP_ALIGN.CENTER)
    add_text(slide, Inches(8.6), y, Inches(3.8), Inches(0.9),
             desc, font_size=13, color=C_TEXT_D)


# ════════════════════════════════════════
# P3 — 系统概述
# ════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, C_BG_WHITE)
add_section_header(slide, "系统概述", "核心业务流程与系统价值")

# 流程图
flow_steps = ["上传图纸\n/模型", "AI 特征\n提取", "人工审阅\n确认", "工艺规程\n生成", "导出\n/入库"]
arrow_x = Inches(0.8)
for i, step in enumerate(flow_steps):
    x = Inches(0.8 + i * 2.5)
    y = Inches(1.8)
    # 圆角矩形
    color = C_ACCENT if i == 2 else C_PRIMARY
    s = add_shape(slide, x, y, Inches(2.0), Inches(1.2), fill_color=color,
                  shape_type=MSO_SHAPE.ROUNDED_RECTANGLE)
    add_text(slide, x, y + Inches(0.25), Inches(2.0), Inches(0.7),
             step, font_size=16, color=C_TEXT_W, alignment=PP_ALIGN.CENTER, bold=True)
    # 箭头
    if i < len(flow_steps) - 1:
        add_text(slide, x + Inches(2.0), y + Inches(0.3), Inches(0.5), Inches(0.5),
                 "→", font_size=28, color=C_TEXT_G, alignment=PP_ALIGN.CENTER)

# 对比表格
add_text(slide, Inches(0.8), Inches(3.5), Inches(6), Inches(0.5),
         "系统价值对比", font_size=22, color=C_TEXT_D, bold=True)

table_data = [
    ["维度", "传统方式", "智能系统"],
    ["特征提取", "人工逐项标注，30-60min", "AI 自动提取，2-5min"],
    ["工艺编写", "参考手册手写，1-2h", "RAG+LLM 生成，5-10min"],
    ["知识复用", "依赖个人经验", "知识库统一管理"],
    ["质量一致性", "因人而异", "标准化模板+AI辅助"],
]
table = slide.shapes.add_table(len(table_data), 3,
                                Inches(0.8), Inches(4.0),
                                Inches(11.7), Inches(2.8)).table
table.columns[0].width = Inches(2.0)
table.columns[1].width = Inches(4.85)
table.columns[2].width = Inches(4.85)

for r, row in enumerate(table_data):
    for c, cell_text in enumerate(row):
        cell = table.cell(r, c)
        cell.text = cell_text
        p = cell.text_frame.paragraphs[0]
        p.font.size = Pt(14)
        p.font.name = "Microsoft YaHei"
        if r == 0:
            p.font.bold = True
            p.font.color.rgb = C_TEXT_W
            cell.fill.solid()
            cell.fill.fore_color.rgb = C_PRIMARY
        else:
            p.font.color.rgb = C_TEXT_D
            if c == 2:
                p.font.color.rgb = C_GREEN
                p.font.bold = True
        p.alignment = PP_ALIGN.CENTER


# ════════════════════════════════════════
# P4 — 技术架构
# ════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, C_BG_WHITE)
add_section_header(slide, "技术架构", "技术栈与架构特点")

# 左侧技术栈表格
tech_data = [
    ["层次", "技术"],
    ["页面结构", "HTML5 + CSS3 + 原生 JavaScript"],
    ["3D 预览", "Three.js + GLTFLoader"],
    ["标注工具", "自研 SVG BoundingBox 标注模块"],
    ["PDF 导出", "Vue 3 + jsPDF + OPPOSans 中文字体"],
    ["后端通信", "Fetch API + SSE 长连接"],
    ["后端服务", "Python Flask + SQLite"],
    ["AI 能力", "VLM 视觉语言模型 + RAG 检索增强"],
]
table = slide.shapes.add_table(len(tech_data), 2,
                                Inches(0.8), Inches(1.6),
                                Inches(6.5), Inches(4.5)).table
table.columns[0].width = Inches(1.8)
table.columns[1].width = Inches(4.7)

for r, row in enumerate(tech_data):
    for c, cell_text in enumerate(row):
        cell = table.cell(r, c)
        cell.text = cell_text
        p = cell.text_frame.paragraphs[0]
        p.font.size = Pt(13)
        p.font.name = "Microsoft YaHei"
        if r == 0:
            p.font.bold = True
            p.font.color.rgb = C_TEXT_W
            cell.fill.solid()
            cell.fill.fore_color.rgb = C_PRIMARY
        else:
            p.font.color.rgb = C_TEXT_D

# 右侧架构特点
add_text(slide, Inches(8), Inches(1.6), Inches(4.5), Inches(0.5),
         "架构特点", font_size=22, color=C_PRIMARY, bold=True)

features = [
    ("单页应用", "侧栏导航 + 页面切换，无刷新跳转"),
    ("流式通信", "SSE 长连接实时推送进度和工艺输出"),
    ("打字机动画", "逐行逐字符输出工艺规程，模拟真人编写"),
    ("多库隔离", "公共库（只读）+ 用户私有库（可编辑）"),
    ("特征缓存", "按文件 hash 缓存，重复上传秒级响应"),
    ("零构建依赖", "全量原生开发，无需 Node/Webpack"),
]
for i, (title, desc) in enumerate(features):
    y = Inches(2.2 + i * 0.85)
    add_shape(slide, Inches(8), y, Inches(0.12), Inches(0.12),
              fill_color=C_ACCENT, shape_type=MSO_SHAPE.OVAL)
    add_text(slide, Inches(8.3), y - Inches(0.05), Inches(1.5), Inches(0.3),
             title, font_size=15, color=C_TEXT_D, bold=True)
    add_text(slide, Inches(8.3), y + Inches(0.25), Inches(4.2), Inches(0.5),
             desc, font_size=13, color=C_TEXT_G)


# ════════════════════════════════════════
# P5 — 功能总览
# ════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, C_BG_WHITE)
add_section_header(slide, "功能总览", "四大核心模块与辅助功能")

# 四大模块卡片
modules = [
    ("工艺入库", C_PRIMARY, "ZIP 工艺包批量导入知识库\n支持新建库/选择已有库\n替换/保留旧版冲突模式\n实时进度 + 匹配结果"),
    ("工艺生成", C_ACCENT, "上传图纸 AI 自动提取特征\nYOLO 自动检测标注\nRAG 检索 + LLM 生成工艺\n打字机动画逐行输出"),
    ("历史记录", C_GREEN, "浏览所有历史生成任务\n统计概览（总数/完成/工序）\n快照回看 + 3D 预览\n批量管理 + 分页筛选"),
    ("数据库浏览", C_PURPLE, "浏览编辑知识库记录\n多库隔离（公共/私有）\n三栏布局（筛选/列表/详情）\n支持记录编辑和删除"),
]
for i, (title, color, desc) in enumerate(modules):
    x = Inches(0.8 + i * 3.1)
    y = Inches(1.6)
    w = Inches(2.8)
    h = Inches(3.5)
    add_shape(slide, x, y, w, h, fill_color=C_CARD_BG2)
    # 顶部色条
    add_shape(slide, x, y, w, Inches(0.06), fill_color=color)
    add_text(slide, x + Inches(0.2), y + Inches(0.25), w - Inches(0.4), Inches(0.4),
             title, font_size=20, color=color, bold=True)
    add_text(slide, x + Inches(0.2), y + Inches(0.8), w - Inches(0.4), h - Inches(1.0),
             desc, font_size=14, color=C_TEXT_G)

# 辅助功能
add_text(slide, Inches(0.8), Inches(5.5), Inches(3), Inches(0.4),
         "辅助功能", font_size=18, color=C_TEXT_D, bold=True)
aux = ["SVG 矢量标注工具（YOLO + 人工）", "3D 模型预览（Three.js GLTF）",
       "PDF 工艺卡片导出（jsPDF）", "特征缓存机制（重复上传加速）"]
for i, a in enumerate(aux):
    x = Inches(0.8 + (i % 2) * 6)
    y = Inches(6.0 + (i // 2) * 0.45)
    add_text(slide, x, y, Inches(5.5), Inches(0.4),
             f"•  {a}", font_size=14, color=C_TEXT_G)


# ════════════════════════════════════════
# P6 — 工艺入库
# ════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, C_BG_WHITE)
add_section_header(slide, "工艺入库", "ZIP 工艺包批量导入知识库")

# 左侧说明
add_text(slide, Inches(0.8), Inches(1.6), Inches(5), Inches(0.5),
         "核心特性", font_size=20, color=C_PRIMARY, bold=True)

features = [
    "入库目标：支持选择已有库或新建私有工艺库",
    "冲突模式：替换入库 / 保留旧版",
    "实时进度：空闲 → 上传中 → 解析中 → 入库中 → 完成",
    "结果展示：已匹配记录、未匹配项、批次日志三个 Tab",
]
for i, f in enumerate(features):
    y = Inches(2.2 + i * 0.55)
    add_text(slide, Inches(1.0), y, Inches(5.5), Inches(0.5),
             f"•  {f}", font_size=14, color=C_TEXT_D)

# 流程
add_text(slide, Inches(0.8), Inches(4.5), Inches(5), Inches(0.5),
         "入库流程", font_size=20, color=C_PRIMARY, bold=True)

steps = ["选择 ZIP 文件", "选择目标库\n冲突模式", "系统解析\n匹配内容", "逐条入库", "显示匹配\n结果日志"]
for i, step in enumerate(steps):
    x = Inches(0.8 + i * 2.3)
    y = Inches(5.2)
    color = C_GREEN if i == 4 else C_PRIMARY
    add_shape(slide, x, y, Inches(1.8), Inches(0.9), fill_color=color,
              shape_type=MSO_SHAPE.ROUNDED_RECTANGLE)
    add_text(slide, x, y + Inches(0.15), Inches(1.8), Inches(0.6),
             step, font_size=13, color=C_TEXT_W, alignment=PP_ALIGN.CENTER)
    if i < 4:
        add_text(slide, x + Inches(1.8), y + Inches(0.2), Inches(0.5), Inches(0.5),
                 "→", font_size=22, color=C_TEXT_G, alignment=PP_ALIGN.CENTER)

# 右侧截图
img = safe_img("screenshot-zip-redesigned.png")
if img:
    slide.shapes.add_picture(img, Inches(7), Inches(1.6), width=Inches(5.5))


# ════════════════════════════════════════
# P7 — 工艺生成
# ════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, C_BG_WHITE)
add_section_header(slide, "工艺生成", "上传图纸 → AI 提取 → 生成工艺规程")

# 完整流程
add_text(slide, Inches(0.8), Inches(1.6), Inches(10), Inches(0.5),
         "完整流程", font_size=20, color=C_PRIMARY, bold=True)

gen_steps = [
    ("① 上传图纸", "PDF/PNG/JPG"),
    ("② AI 提取", "VLM 视觉分析"),
    ("③ YOLO 检测", "自动标注特征"),
    ("④ 人工审阅", "确认/修改特征"),
    ("⑤ 工艺生成", "RAG+LLM"),
    ("⑥ 流式输出", "打字机动画"),
]
for i, (title, desc) in enumerate(gen_steps):
    x = Inches(0.8 + i * 2.05)
    y = Inches(2.2)
    color = C_ACCENT if i in [1, 4] else C_PRIMARY
    add_shape(slide, x, y, Inches(1.8), Inches(0.9), fill_color=color,
              shape_type=MSO_SHAPE.ROUNDED_RECTANGLE)
    add_text(slide, x, y + Inches(0.1), Inches(1.8), Inches(0.4),
             title, font_size=13, color=C_TEXT_W, alignment=PP_ALIGN.CENTER, bold=True)
    add_text(slide, x, y + Inches(0.5), Inches(1.8), Inches(0.35),
             desc, font_size=11, color=RGBColor(0xBF, 0xDB, 0xFE), alignment=PP_ALIGN.CENTER)
    if i < 5:
        add_text(slide, x + Inches(1.8), y + Inches(0.2), Inches(0.3), Inches(0.5),
                 "→", font_size=20, color=C_TEXT_G, alignment=PP_ALIGN.CENTER)

# 界面布局说明
add_text(slide, Inches(0.8), Inches(3.5), Inches(5.5), Inches(0.5),
         "界面布局", font_size=20, color=C_PRIMARY, bold=True)
layout_desc = [
    "左侧：图纸预览（支持多页翻页、缩放、全屏）",
    "右侧：特征审阅 Tab + 工艺规程 Tab",
    "顶部：统一进度条 + 阶段提示（呼吸灯动画）",
    "底部：工具栏（上传/选择知识库/特征缓存/重置）",
]
for i, d in enumerate(layout_desc):
    add_text(slide, Inches(1.0), Inches(4.1 + i * 0.45), Inches(5.5), Inches(0.4),
             f"•  {d}", font_size=14, color=C_TEXT_D)

# 右侧截图
img = safe_img("screenshot-generate.png")
if img:
    slide.shapes.add_picture(img, Inches(6.8), Inches(3.3), width=Inches(6))


# ════════════════════════════════════════
# P8 — 标注工具
# ════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, C_BG_WHITE)
add_section_header(slide, "标注工具", "YOLO 自动检测 + 人工精修标注")

# 左侧说明
add_text(slide, Inches(0.8), Inches(1.6), Inches(5.5), Inches(0.5),
         "核心能力", font_size=20, color=C_PRIMARY, bold=True)

ann_features = [
    ("YOLO 自动检测", "AI 自动识别倒角、螺纹孔、圆孔等特征"),
    ("人工标注", "鼠标拖拽绘制矩形框，右键删除"),
    ("标签系统", "内建 3 类标签 + 自定义标签（持久化）"),
    ("多页支持", "PDF 多页独立标注，切换自动保存"),
    ("缩放适配", "Ctrl+滚轮缩放，适应视口/100%"),
    ("双向联动", "画布点击↔列表点击，自动滚动定位"),
    ("自动保存", "1s 防抖 + sendBeacon 页面关闭兜底"),
    ("导出", "标注数据导出为 ZIP"),
]
for i, (title, desc) in enumerate(ann_features):
    y = Inches(2.2 + i * 0.6)
    add_text(slide, Inches(1.0), y, Inches(1.8), Inches(0.35),
             f"•  {title}", font_size=14, color=C_PRIMARY, bold=True)
    add_text(slide, Inches(2.8), y, Inches(3.5), Inches(0.35),
             desc, font_size=13, color=C_TEXT_G)

# 标签类型表格
add_text(slide, Inches(0.8), Inches(5.2), Inches(3), Inches(0.4),
         "标签类型", font_size=18, color=C_PRIMARY, bold=True)
tag_data = [
    ["标签", "颜色", "键名"],
    ["倒角", "#f59e0b", "chamfer"],
    ["螺纹孔", "#6366f1", "threaded_hole"],
    ["圆孔", "#10b981", "circle_hole"],
    ["自定义", "循环色池", "用户自定义"],
]
table = slide.shapes.add_table(5, 3, Inches(0.8), Inches(5.6),
                                Inches(5), Inches(1.5)).table
table.columns[0].width = Inches(1.2)
table.columns[1].width = Inches(1.8)
table.columns[2].width = Inches(2.0)
for r, row in enumerate(tag_data):
    for c, val in enumerate(row):
        cell = table.cell(r, c)
        cell.text = val
        p = cell.text_frame.paragraphs[0]
        p.font.size = Pt(12)
        p.font.name = "Microsoft YaHei"
        if r == 0:
            p.font.bold = True
            p.font.color.rgb = C_TEXT_W
            cell.fill.solid()
            cell.fill.fore_color.rgb = C_PRIMARY
        else:
            p.font.color.rgb = C_TEXT_D
        p.alignment = PP_ALIGN.CENTER


# ════════════════════════════════════════
# P9 — 历史记录
# ════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, C_BG_WHITE)
add_section_header(slide, "历史记录", "浏览所有历史工艺生成任务")

# 左侧说明
add_text(slide, Inches(0.8), Inches(1.6), Inches(5), Inches(0.5),
         "核心特性", font_size=20, color=C_PRIMARY, bold=True)

hist_features = [
    "统计概览：总任务数、已完成数、待审阅数、总工序数",
    "任务列表：任务名、状态、完成时间、工序数",
    "快照回看：分栏预览（左图右文），支持图片缩放/翻页",
    "3D 预览：PRT 模型的三维视图（Three.js GLTF）",
    "批量管理：多选删除、按日期筛选、分页浏览",
]
for i, f in enumerate(hist_features):
    y = Inches(2.2 + i * 0.55)
    add_text(slide, Inches(1.0), y, Inches(5.5), Inches(0.5),
             f"•  {f}", font_size=14, color=C_TEXT_D)

# 状态表
add_text(slide, Inches(0.8), Inches(5.0), Inches(3), Inches(0.4),
         "任务状态体系", font_size=18, color=C_PRIMARY, bold=True)
status_data = [
    ["状态", "含义"],
    ["排队中", "等待处理"],
    ["图纸分析中", "AI 正在提取特征"],
    ["特征审阅中", "等待人工确认"],
    ["工艺生成中", "RAG+LLM 生成工艺"],
    ["已完成", "工艺规程已生成"],
    ["失败", "处理异常"],
]
table = slide.shapes.add_table(len(status_data), 2, Inches(0.8), Inches(5.4),
                                Inches(5.5), Inches(1.8)).table
table.columns[0].width = Inches(2.0)
table.columns[1].width = Inches(3.5)
for r, row in enumerate(status_data):
    for c, val in enumerate(row):
        cell = table.cell(r, c)
        cell.text = val
        p = cell.text_frame.paragraphs[0]
        p.font.size = Pt(12)
        p.font.name = "Microsoft YaHei"
        if r == 0:
            p.font.bold = True
            p.font.color.rgb = C_TEXT_W
            cell.fill.solid()
            cell.fill.fore_color.rgb = C_PRIMARY
        else:
            p.font.color.rgb = C_TEXT_D
        p.alignment = PP_ALIGN.CENTER

# 右侧截图
img = safe_img("screenshot-history-fixed.png")
if img:
    slide.shapes.add_picture(img, Inches(6.8), Inches(1.6), width=Inches(6))


# ════════════════════════════════════════
# P10 — 数据库浏览
# ════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, C_BG_WHITE)
add_section_header(slide, "数据库浏览", "知识库管理与工艺记录编辑")

# 左侧说明
add_text(slide, Inches(0.8), Inches(1.6), Inches(5), Inches(0.5),
         "核心特性", font_size=20, color=C_PRIMARY, bold=True)

db_features = [
    "访问控制：默认锁定，需先完成一次 ZIP 入库解锁",
    "多库架构：公共工艺库（只读）+ 用户私有库（可编辑）",
    "三栏布局：左侧筛选、中间记录列表、右侧详情",
    "筛选维度：关键词、产品类型、来源、状态",
    "详情编辑：记录元数据、模型快照、工艺内容、特征报告",
    "操作：编辑记录、删除废表、删除整个用户库",
]
for i, f in enumerate(db_features):
    y = Inches(2.2 + i * 0.55)
    add_text(slide, Inches(1.0), y, Inches(5.5), Inches(0.5),
             f"•  {f}", font_size=14, color=C_TEXT_D)

# 库类型对比
add_text(slide, Inches(0.8), Inches(5.6), Inches(3), Inches(0.4),
         "知识库隔离", font_size=18, color=C_PRIMARY, bold=True)
lib_data = [
    ["库类型", "权限", "用途"],
    ["公共工艺库", "只读", "全局共享基线"],
    ["用户私有库", "读写", "个人工艺积累"],
]
table = slide.shapes.add_table(3, 3, Inches(0.8), Inches(6.0),
                                Inches(5.5), Inches(1.0)).table
for r, row in enumerate(lib_data):
    for c, val in enumerate(row):
        cell = table.cell(r, c)
        cell.text = val
        p = cell.text_frame.paragraphs[0]
        p.font.size = Pt(13)
        p.font.name = "Microsoft YaHei"
        if r == 0:
            p.font.bold = True
            p.font.color.rgb = C_TEXT_W
            cell.fill.solid()
            cell.fill.fore_color.rgb = C_PRIMARY
        else:
            p.font.color.rgb = C_TEXT_D
        p.alignment = PP_ALIGN.CENTER

# 右侧截图
img = safe_img("screenshot-db-unlocked.png")
if img:
    slide.shapes.add_picture(img, Inches(6.8), Inches(1.6), width=Inches(6))


# ════════════════════════════════════════
# P11 — AI 核心能力
# ════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, C_BG_WHITE)
add_section_header(slide, "AI 核心能力", "VLM 视觉提取 + RAG 检索增强生成")

# 左：VLM
add_shape(slide, Inches(0.8), Inches(1.6), Inches(5.5), Inches(5.3), fill_color=C_CARD_BG2)
add_text(slide, Inches(1.1), Inches(1.8), Inches(5), Inches(0.5),
         "VLM 视觉特征提取", font_size=22, color=C_PRIMARY, bold=True)
add_text(slide, Inches(1.1), Inches(2.4), Inches(5), Inches(0.4),
         "输入：2D 工艺图纸（PDF/PNG/JPG）", font_size=15, color=C_TEXT_D)
add_text(slide, Inches(1.1), Inches(2.8), Inches(5), Inches(0.4),
         "输出：结构化特征报告", font_size=15, color=C_TEXT_D, bold=True)

vlm_items = ["尺寸公差", "表面粗糙度", "形位公差", "材料信息", "加工要求", "热处理要求"]
for i, item in enumerate(vlm_items):
    x = Inches(1.3 + (i % 2) * 2.5)
    y = Inches(3.4 + (i // 2) * 0.5)
    add_shape(slide, x, y, Inches(0.12), Inches(0.12), fill_color=C_GREEN, shape_type=MSO_SHAPE.OVAL)
    add_text(slide, x + Inches(0.25), y - Inches(0.05), Inches(2), Inches(0.35),
             item, font_size=14, color=C_TEXT_D)

# 特征缓存
add_text(slide, Inches(1.1), Inches(5.2), Inches(5), Inches(0.4),
         "特征缓存机制", font_size=18, color=C_ACCENT, bold=True)
add_text(slide, Inches(1.1), Inches(5.6), Inches(5), Inches(0.8),
         "按文件 hash 判断是否为同一份图纸，开启后跳过 VLM 特征提取，\n直接返回上次结果，加速重复上传场景。",
         font_size=13, color=C_TEXT_G)

# 右：RAG
add_shape(slide, Inches(7), Inches(1.6), Inches(5.5), Inches(5.3), fill_color=C_CARD_BG2)
add_text(slide, Inches(7.3), Inches(1.8), Inches(5), Inches(0.5),
         "RAG 检索增强生成", font_size=22, color=C_ACCENT, bold=True)

rag_steps = [
    ("① 知识库检索", "在工艺知识库中检索相似工艺记录"),
    ("② 特征融合", "结合 AI 特征报告和检索结果"),
    ("③ LLM 生成", "大语言模型生成结构化工艺规程"),
    ("④ 流式输出", "SSE 推送 + 打字机逐行输出"),
]
for i, (title, desc) in enumerate(rag_steps):
    y = Inches(2.5 + i * 1.0)
    add_shape(slide, Inches(7.3), y, Inches(0.06), Inches(0.6), fill_color=C_ACCENT)
    add_text(slide, Inches(7.6), y, Inches(4.5), Inches(0.35),
             title, font_size=16, color=C_TEXT_D, bold=True)
    add_text(slide, Inches(7.6), y + Inches(0.35), Inches(4.5), Inches(0.4),
             desc, font_size=13, color=C_TEXT_G)

# 输出格式
add_text(slide, Inches(7.3), Inches(6.2), Inches(5), Inches(0.4),
         "输出格式：工序号 @ 工种 @ 工序内容", font_size=14, color=C_TEXT_D, bold=True)


# ════════════════════════════════════════
# P12 — 感谢
# ════════════════════════════════════════
slide = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide, C_BG_DARK)

# 顶部装饰线
add_shape(slide, Inches(5.67), Inches(1.5), Inches(2.0), Inches(0.04), fill_color=C_PRIMARY)

# 主标题
add_text(slide, Inches(0.8), Inches(2.2), Inches(11.7), Inches(1.0),
         "感谢聆听", font_size=52, color=C_TEXT_W, bold=True, alignment=PP_ALIGN.CENTER)

# 副标题
add_text(slide, Inches(0.8), Inches(3.3), Inches(11.7), Inches(0.6),
         "THANK YOU", font_size=28, color=C_PRIMARY, alignment=PP_ALIGN.CENTER,
         font_name="Cascadia Code")

# 分隔线
add_shape(slide, Inches(5.67), Inches(4.2), Inches(2.0), Inches(0.03), fill_color=C_ACCENT)

# 系统名称
add_text(slide, Inches(0.8), Inches(4.6), Inches(11.7), Inches(0.5),
         "二维工艺系统", font_size=20, color=C_TEXT_L, alignment=PP_ALIGN.CENTER)

# 底部标签
tags = ["VLM 视觉提取", "RAG 检索增强", "SSE 流式输出", "SVG 标注工具"]
for i, tag in enumerate(tags):
    x = Inches(2.5 + i * 2.2)
    y = Inches(5.6)
    add_shape(slide, x, y, Inches(1.9), Inches(0.4), fill_color=C_CARD_BG,
              shape_type=MSO_SHAPE.ROUNDED_RECTANGLE)
    add_text(slide, x, y + Inches(0.04), Inches(1.9), Inches(0.32),
             tag, font_size=12, color=C_TEXT_L, alignment=PP_ALIGN.CENTER)

# 底部装饰线
add_shape(slide, Inches(5.67), Inches(6.5), Inches(2.0), Inches(0.04), fill_color=C_PRIMARY)


# ════════════════════════════════════════
# 保存
# ════════════════════════════════════════
out_path = os.path.join(DOC_DIR, "2d-process-system.pptx")
prs.save(out_path)
print(f"PPT 已生成: {out_path}")
