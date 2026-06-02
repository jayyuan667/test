# -*- coding: utf-8 -*-
"""测试 Kimi-VL-A3B (no think) - 工程图纸测试"""

import base64
import os
import sys
from io import BytesIO
from PIL import Image
from openai import OpenAI

API_BASE = "http://192.168.2.24:8003/v1"
API_KEY = "EMPTY"
MODEL = "/home/caojiayuan/model/kimi_no_think"

VISION_SYSTEM_PROMPT = """你是一名专业的机械工程图纸解析专家。请仔细读取图纸中的实际标注值，仅输出图纸上明确有的信息，严禁凭空编造。

【重要规则】
1. 只能填写图纸上实际存在的数值，如图纸上未标注则填"无"
2. 禁止自行推断或补充任何图纸上未明确标注的数据
3. 图号、尺寸、技术要求等所有信息必须来自图纸原文，不得自行命名
4. 如无法确定某个特征是否存在，该字段填"无"
5.【】后面直接接信息

【输出格式】

【图号】（仅填图纸标题栏中的实际图号）
【零件名称】（仅填图纸标题栏中的实际零件名）
【技术要求】（仅填图纸上原文标注的技术要求）
【形态】（一句话描述图纸上能看到的实际结构）
【类型】（根据图纸判断零件功能类别）
【关键尺寸】（仅填图纸上标注的尺寸，包括总长、直径等，带公差）
【螺纹与螺孔】（仅填图纸上标注的螺纹规格）
【热处理与探伤】（仅填图纸上标注的热处理或探伤要求）
【精度与检测特征】（仅填图纸上标注的形位公差）
【表面处理与镀层特征】（仅填图纸上标注的表面处理要求）
【其他特征】（仅填图纸上标注的其他信息）"""


def resize_image(image_path: str, max_pixels: int = 2048) -> bytes:
    img = Image.open(image_path)
    w, h = img.size
    print(f"[图片] {image_path} 原始尺寸: {w}x{h}")
    max_dim = max(w, h)
    if max_dim > max_pixels:
        ratio = max_pixels / max_dim
        new_w = int(w * ratio)
        new_h = int(h * ratio)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        print(f"[图片] 已缩小至: {new_w}x{new_h}")
    buf = BytesIO()
    img.save(buf, format="PNG", optimize=False)
    return buf.getvalue()


def analyze_single(client: OpenAI, image_path: str) -> str:
    image_bytes = resize_image(image_path, max_pixels=2048)
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")

    messages = [
        {"role": "system", "content": VISION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
                {"type": "text", "text": "请严格按照上述格式要求，填写图纸上的实际数据，不要编造。"},
            ],
        },
    ]

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_tokens=8192,
        temperature=0.0,
        timeout=600,
    )
    return response.choices[0].message.content


def main():
    if len(sys.argv) < 2:
        print("用法: python test_kimi_drawing.py <图片路径>")
        sys.exit(1)

    image_path = sys.argv[1]
    if not os.path.exists(image_path):
        print(f"[错误] 文件不存在: {image_path}")
        sys.exit(1)

    client = OpenAI(api_key=API_KEY, base_url=API_BASE)

    print("=" * 60)
    print(f"API: {API_BASE}")
    print(f"Model: {MODEL}")
    print("=" * 60)

    try:
        result = analyze_single(client, image_path)
        print("\n=== 提取结果 ===")
        print(result)
    except Exception as e:
        print(f"[错误] {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
