# -*- coding: utf-8 -*-
"""7 类工程特征标签 — 统一定义源。

annotation_renderer.py / annotations.py / yolo_detector.py 均从此 import。
"""

# 按工程语义分组排序（孔类 0-3，加工特征 4-6）
YOLO_CLASSES = [
    "code_hole",       # 0  编码孔/基准孔
    "through_hole",    # 1  通孔
    "blind_hole",      # 2  盲孔
    "threaded_hole",   # 3  螺纹孔
    "chamfer",         # 4  倒角
    "counterbore",     # 5  沉头孔
    "countersink",     # 6  锥口孔
]

LABEL_TO_ID = {name: i for i, name in enumerate(YOLO_CLASSES)}
ID_TO_LABEL = {i: name for name, i in LABEL_TO_ID.items()}

LABEL_TO_ZH = {
    "code_hole":     "编码孔",
    "through_hole":  "通孔",
    "blind_hole":    "盲孔",
    "threaded_hole": "螺纹孔",
    "chamfer":       "倒角",
    "counterbore":   "沉头孔",
    "countersink":   "锥口孔",
}

# RGB colors — 与前端 annotate.ts BUILT_IN_LABELS 色板一致
LABEL_TO_RGB = {
    "code_hole":     (59,  130, 246),   # #3b82f6 blue
    "through_hole":  (34,  197, 94),    # #22c55e green
    "blind_hole":    (239, 68,  68),    # #ef4444 red
    "threaded_hole": (99,  102, 241),   # #6366f1 indigo
    "chamfer":       (245, 158, 11),    # #f59e0b amber
    "counterbore":   (249, 115, 22),    # #f97316 orange
    "countersink":   (139, 92,  246),   # #8b5cf6 violet
}

# 虚线边框类（螺纹孔用虚线区分于直孔）
LABEL_DASHED = {"threaded_hole"}
