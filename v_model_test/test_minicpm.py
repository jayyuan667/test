# -*- coding: utf-8 -*-
"""测试 MiniCPM-V-4_5 视觉模型 - 4图测试"""

import base64
import os
import sys
from io import BytesIO
from PIL import Image
from openai import OpenAI

API_BASE = "http://192.168.2.24:8002/v1"
API_KEY = "EMPTY"
MODEL = "/home/caojiayuan/model/MinCPM-V-4_5"

VISION_SYSTEM_PROMPT = (
    "你是机械工程图纸解析专家。请读取图纸中的实际标注值。\n\n"
    "【格式要求】严格按以下格式输出，每行一个字段，【】后面直接跟内容：\n\n"
    "【图号】\n"
    "【零件名称】\n"
    "【技术要求】\n"
    "【形态】\n"
    "【类型】\n"
    "【螺纹与螺孔】\n"
    "【热处理与探伤】\n"
    "【精度与检测特征】\n"
    "【表面处理与镀层特征】\n"
    "【其他特征】\n\n"
    "【规则】只写图纸上明确有的数据；不编造不猜测；如果某项图纸无标注则写'无'。不要输出关键尺寸。"
)


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


def analyze_single(client: OpenAI, image_path: str, page_num: int) -> str:
    image_bytes = resize_image(image_path, max_pixels=2048)
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")

    messages = [
        {"role": "system", "content": VISION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
                {"type": "text", "text": "请仅输出图纸上明确标注的信息，不要输出关键尺寸。"},
            ],
        },
    ]

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_tokens=512,
        temperature=0.0,
        timeout=300,
    )
    return response.choices[0].message.content


def main():
    test_dir = r"D:\Work_project\back_up\Artificial_agent\v_model_test"
    image_files = ["cat_asleep.png", "cat_awake.png", "chair.png", "flower.png"]

    client = OpenAI(api_key=API_KEY, base_url=API_BASE)

    print("=" * 60)
    print(f"API: {API_BASE}")
    print(f"Model: {MODEL}")
    print("=" * 60)

    for i, fname in enumerate(image_files, 1):
        fpath = os.path.join(test_dir, fname)
        if not os.path.exists(fpath):
            print(f"[跳过] 不存在: {fpath}")
            continue

        print(f"\n>>> [{i}/4] 分析: {fname}")
        try:
            result = analyze_single(client, fpath, i)
            print(f"--- 结果 ---\n{result}")
        except Exception as e:
            print(f"[错误] {e}")

        if i < 4:
            print()

    print("\n" + "=" * 60)
    print("全部完成")


if __name__ == "__main__":
    main()
