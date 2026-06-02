# -*- coding: utf-8 -*-
"""
本地测试入口 - PP-StructureV3 + 规则引擎 + Qwen3-VL-8B
本地调试流程，在本地跑通后上传服务器
"""

import sys
import os

# 添加父目录路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ppstructure_extractor import extract_with_ppstructure, extract_drawing_info
from rule_engine import DrawingRuleEngine
from semantic_enhancer import enhance as semantic_enhance
from format_output import format_output


def main():
    if len(sys.argv) < 2:
        print("用法: python test_pipeline.py <图纸图片路径>")
        print("示例: python test_pipeline.py ./test_page.png")
        sys.exit(1)

    image_path = sys.argv[1]
    if not os.path.exists(image_path):
        print(f"[错误] 文件不存在: {image_path}")
        sys.exit(1)

    print("=" * 70)
    print("工程图纸提取 Pipeline - 本地测试")
    print("=" * 70)

    # ========== Step 1: PP-StructureV3 OCR ==========
    print("\n>>> Step 1: PP-StructureV3 OCR + 布局分析")
    print("-" * 50)

    try:
        ocr_result = extract_with_ppstructure(image_path)
        print(f"  文字块数量: {len(ocr_result['blocks'])}")
        print(f"  表格数量: {len(ocr_result['tables'])}")
        print(f"  完整文字长度: {len(ocr_result['full_text'])} 字符")
    except ImportError as e:
        print(f"  [跳过] PP-StructureV3 未安装: {e}")
        print("  使用备用简单 OCR...")
        ocr_result = extract_drawing_info_fallback(image_path)

    # 保存 OCR 结果
    ocr_txt = image_path + '.ocr.txt'
    with open(ocr_txt, 'w', encoding='utf-8') as f:
        f.write(ocr_result.get('full_text', ''))
    print(f"  OCR 文字已保存: {ocr_txt}")

    # ========== Step 2: 规则引擎提取 ==========
    print("\n>>> Step 2: 规则引擎确定性提取")
    print("-" * 50)

    engine = DrawingRuleEngine()
    rule_result = engine.extract_all(ocr_result.get('full_text', ''), ocr_result.get('blocks', []))

    for key, value in rule_result.items():
        if value:
            if isinstance(value, list):
                print(f"  {key}: {value[:10]}{' ...' if len(value) > 10 else ''}")
            else:
                print(f"  {key}: {value}")

    # ========== Step 3: Qwen3-VL-8B 语义增强 ==========
    print("\n>>> Step 3: Qwen3-VL-8B 语义增强")
    print("-" * 50)

    try:
        sem_result = semantic_enhance(image_path, rule_result)
        for key, value in sem_result.items():
            print(f"  {key}: {value}")
    except Exception as e:
        print(f"  [跳过] 语义增强不可用: {e}")
        sem_result = {"morphology": "未识别", "material_grade": "未标注", "special_process": "无"}

    # 打印最终结果汇总
    print("\n>>> 最终提取结果汇总")
    print("=" * 70)

    final = {
        '图号': rule_result.get('图号', ''),
        '零件名称': rule_result.get('零件名称', ''),
        '技术要求': rule_result.get('技术要求', []),
        '形态': sem_result.get('morphology', ''),
        '材料牌号': sem_result.get('material_grade', ''),
        '特殊工艺': sem_result.get('special_process', ''),
        '关键尺寸': rule_result.get('尺寸', [])[:20],
        '螺纹与螺孔': rule_result.get('螺纹与螺孔', []),
        '热处理与探伤': [],
        '精度与检测特征': rule_result.get('粗糙度', []),
        '表面处理与镀层特征': '',
        '其他特征': [],
    }

    if rule_result.get('热处理'):
        final['热处理与探伤'].append(rule_result['热处理'])
    if rule_result.get('探伤'):
        final['热处理与探伤'].append(rule_result['探伤'])

    if rule_result.get('倒角'):
        final['其他特征'].append('倒角: ' + ', '.join(rule_result['倒角']))
    if rule_result.get('圆角'):
        final['其他特征'].append('圆角: ' + ', '.join(rule_result['圆角']))

    # ========== Step 4: Qwen-VL 格式化输出（传图像） ==========
    print("\n>>> Step 4: Qwen3-VL-8B 格式化输出（按 Doubao 标准提示词）")
    print("-" * 50)

    try:
        formatted = format_output(rule_result, sem_result)
        print(formatted)
    except Exception as e:
        print(f"  [跳过] 格式化不可用: {e}")
        for key, value in final.items():
            if value:
                if isinstance(value, list):
                    if value:
                        print(f"  {key}:")
                        for v in value[:10]:
                            print(f"    - {v}")
                else:
                    print(f"  {key}: {value}")

    print("\n" + "=" * 70)
    print("本地测试完成！Rule Engine 部分已验证。")
    print("Qwen3-VL-8B 语义增强需在服务器上测试。")


def extract_drawing_info_fallback(image_path: str) -> dict:
    """
    PP-StructureV3 不可用时的备用 OCR
    使用 PIL 简单读取 + 规则匹配
    """
    try:
        from PIL import Image
        import pytesseract

        img = Image.open(image_path)
        text = pytesseract.image_to_string(img, lang='chi_sim')
        return {'full_text': text, 'blocks': [], 'tables': []}
    except ImportError:
        return {'full_text': '', 'blocks': [], 'tables': []}


if __name__ == "__main__":
    main()
