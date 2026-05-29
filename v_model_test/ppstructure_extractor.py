# -*- coding: utf-8 -*-
"""OCR + 布局分析 - 本地调试版"""

from PIL import Image
from typing import Dict, List
import os


def extract_with_ppstructure(image_path: str) -> Dict:
    """
    使用 EasyOCR 提取图纸文字（本地调试优先方案）
    """
    try:
        import easyocr
        reader = easyocr.Reader(['ch_sim', 'en'], verbose=False)
        result = reader.readtext(image_path)

        blocks = []
        full_text_parts = []

        for item in result:
            bbox, text, confidence = item
            if isinstance(text, str):
                text = text.strip()
            else:
                continue
            if not text or confidence < 0.15:  # 降低阈值，不丢弃弱检测
                continue
            blocks.append({'bbox': bbox, 'text': text, 'type': 'text'})
            full_text_parts.append(text)

        full_text = '\n'.join(full_text_parts)
        return {'full_text': full_text, 'blocks': blocks, 'tables': []}

    except Exception as e:
        print(f"    EasyOCR 失败: {e}")
        return {'full_text': '', 'blocks': [], 'tables': []}


def extract_drawing_info(image_path: str) -> Dict:
    """
    别名 - 兼容旧调用
    """
    return extract_with_ppstructure(image_path)
