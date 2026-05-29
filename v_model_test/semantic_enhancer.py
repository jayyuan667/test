# -*- coding: utf-8 -*-
"""
语义增强模块 - Qwen3-VL-8B
给定 EasyOCR+RuleEngine 的确定性提取结果，调用 Qwen3-VL-8B
补充形态(type)、材料牌号(material-grade)、特殊工艺(special-process) 等字段
"""

import base64
import json
import re
import sys

import requests


# ----------------------------------------------------------------------
# vLLM 服务配置
# ----------------------------------------------------------------------
VLLM_HOST = "http://192.168.2.24"
VLLM_PORT = 8001  # Qwen3-VL-8B
VLLM_URL = f"{VLLM_HOST}:{VLLM_PORT}"

TIMEOUT = 120


# ----------------------------------------------------------------------
# 提示词
# ----------------------------------------------------------------------
SEMANTIC_ENHANCE_PROMPT = """你是一个工程图纸语义分析专家。请直接从图纸图像中读取所有可见信息，补充已有提取结果的不足。

请逐字段读取图像并返回JSON，每个字段都要读取，不要遗漏：

1. **drawing_no**: 图号（如 1F17810、D125A-181200A003）
2. **process_type**: 加工类型（如"轴加工"、"盘类加工"）
3. **part_name**: 零件名称（标题栏中的零件名称）
4. **material_form**: 毛坯类型（如锻件、铸件、棒料；无则填"无"）
5. **morphology**: 形态（如"轴类"、"盘类"、"法兰类"）
6. **part_type**: 类型/功能类别（如"滑动导向件"、"密封件"）
7. **roughness**: 粗糙度要求（如 Ra1.6、Ra3.2，多个用分号分隔）
8. **heat_treatment**: 热处理（如调质HRC28-32、渗碳等）
9. **flaw_detection**: 探伤要求（如超声波探伤、磁粉探伤）
10. **special_process**: 特殊工艺（如发蓝、镀铬、焊接）
11. **surface_treatment**: 表面处理/镀层（如发蓝、磷化）
12. **chamfer**: 倒角（如 1×45°、C1.5、2×45°）
13. **end_face**: 端面特征（如基准面、打印标识面）
14. **tolerance**: 形位公差（如同轴度0.05、垂直度0.02）
15. **linear_tolerance**: 线性公差（如 ±0.035）
16. **material_grade**: 材料牌号（45钢、Q235、HT200等，无法推断填"未标注"）

请仔细读取图纸图像中的所有文字和标注，结合已有信息，填入每个字段。
若某字段在图纸中完全不存在，填"无"，不要留空。

请以JSON格式返回（只返回JSON，不要其他内容）：
{{
  "drawing_no": "图号",
  "process_type": "加工类型",
  "part_name": "零件名称",
  "material_form": "毛坯类型",
  "morphology": "形态",
  "part_type": "类型",
  "roughness": "粗糙度",
  "heat_treatment": "热处理",
  "flaw_detection": "探伤",
  "special_process": "特殊工艺",
  "surface_treatment": "表面处理",
  "chamfer": "倒角",
  "end_face": "端面特征",
  "tolerance": "形位公差",
  "linear_tolerance": "线性公差",
  "material_grade": "材料牌号"
}}
"""


def encode_image_to_base64(image_path: str) -> str:
    """将图片转为 base64 字符串"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def enhance(image_path: str, rule_result: dict) -> dict:
    """
    调用 Qwen3-VL-8B 进行语义增强

    Args:
        image_path: 图纸图片路径
        rule_result: DrawingRuleEngine.extract_all() 的结果

    Returns:
        dict: 包含 morphology, material_grade, special_process
    """
    # 提示词已自含所有要求，不再需要 format
    prompt = SEMANTIC_ENHANCE_PROMPT

    # 构建 messages
    image_b64 = encode_image_to_base64(image_path)

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                {"type": "text", "text": prompt},
            ],
        }
    ]

    payload = {
        "model": "/home/caojiayuan/model/Qwen3_8B_V",
        "messages": messages,
        "max_tokens": 2048,
        "temperature": 0.1,
    }

    raw = ""
    try:
        resp = requests.post(f"{VLLM_URL}/v1/chat/completions", json=payload, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        raw = data["choices"][0]["message"]["content"]

        # 提 JSON
        match = re.search(r"\{[^}]+\}", raw, re.DOTALL)
        if match:
            json_str = match.group()
            result = json.loads(json_str)
        else:
            result = {
                "drawing_no": "识别失败",
                "process_type": "无",
                "morphology": raw,
                "material_grade": "未标注",
                "special_process": "无",
            }

        return result

    except Exception as e:
        print(f"  [语义增强失败] {e}")
        print(f"  [DEBUG] raw response: {raw[:500] if raw else 'no response'}")
        return {
            "morphology": "识别失败",
            "material_grade": "未标注",
            "special_process": "无",
        }


if __name__ == "__main__":
    # 快速测试
    if len(sys.argv) < 2:
        print("用法: python semantic_enhancer.py <图片路径>")
        sys.exit(1)

    image_path = sys.argv[1]

    # 模拟 rule_result（实际从 test_pipeline 获取）
    demo_rule = {
        "零件名称": "液压缸端盖",
        "技术要求": ["未注倒角2×45°", "锐边倒钝", "表面涂防锈漆"],
        "热处理": "调质HRC28-32",
        "螺纹与螺孔": ["M16"],
        "粗糙度": ["Ra1.6", "Ra3.2"],
    }

    print(">>> Qwen3-VL-8B 语义增强测试")
    result = enhance(image_path, demo_rule)
    for k, v in result.items():
        print(f"  {k}: {v}")
