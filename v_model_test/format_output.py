# -*- coding: utf-8 -*-
"""
最终格式化模块 - 纯文本模型（Step 3 已看完图，Step 4 只做格式整理）
将 Step 3 提取的丰富字段映射到 Doubao 的 19 字段标准格式
"""

import requests


VLLM_HOST = "http://192.168.2.24"
VLLM_PORT = 8001
VLLM_URL = f"{VLLM_HOST}:{VLLM_PORT}"
TIMEOUT = 120


FORMAT_PROMPT = """你是一个工程图纸格式整理专家。请将以下提取结果整理成标准格式输出：

【格式要求】
- 只输出【】字段，每行一个字段
- 同一字段多条内容用分号分隔
- 字段不存在填"无"
- 不要编造，不要重复，不要输出解释

请整理输出以下19个字段：
【图号】
【零件名称】
【毛坯类型】
【技术要求】
【形态】
【类型】
【关键尺寸】
【弧段与齿形】
【端面与平面】
【外圆与内孔】
【螺纹与螺孔】
【倒角】
【热处理与探伤】
【标识与检验】
【线切割】
【精度与检测特征】
【表面处理与镀层特征】
【过渡特征】
【其他特征】
"""


def _map_field(value, max_items=30) -> str:
    """把源值映射为字符串，空则返回'无'"""
    if not value:
        return "无"
    if isinstance(value, list):
        items = [str(v).strip() for v in value if str(v).strip()]
        if not items:
            return "无"
        seen = set()
        unique = []
        for v in items:
            if v not in seen:
                seen.add(v)
                unique.append(v)
        result = "；".join(unique[:max_items])
        return result if result else "无"
    return str(value).strip() if str(value).strip() else "无"


def build_extracted_text(rule_result: dict, sem_result: dict) -> str:
    """把所有已有提取结果整理成纯文本"""
    parts = []

    dn = rule_result.get("图号", "") or sem_result.get("drawing_no", "")
    parts.append(f"图号: {_map_field(dn)}")

    pn = rule_result.get("零件名称", "") or sem_result.get("part_name", "")
    parts.append(f"零件名称: {_map_field(pn)}")

    mf = sem_result.get("material_form", "")
    parts.append(f"毛坯类型: {_map_field(mf)}")

    tech = rule_result.get("技术要求", [])
    parts.append(f"技术要求: {_map_field(tech)}")

    morph = sem_result.get("morphology", "")
    parts.append(f"形态: {_map_field(morph)}")

    pt = sem_result.get("part_type", "")
    parts.append(f"类型: {_map_field(pt)}")

    dims = rule_result.get("尺寸", [])
    parts.append(f"关键尺寸: {_map_field(dims)}")

    parts.append("弧段与齿形: 无")

    ef = sem_result.get("end_face", "")
    parts.append(f"端面与平面: {_map_field(ef)}")

    parts.append("外圆与内孔: 无")

    threads = rule_result.get("螺纹与螺孔", [])
    parts.append(f"螺纹与螺孔: {_map_field(threads)}")

    chamfers = list(rule_result.get("倒角", []))
    qch = sem_result.get("chamfer", "")
    if qch and qch not in chamfers:
        chamfers.append(qch)
    parts.append(f"倒角: {_map_field(chamfers)}")

    heat = rule_result.get("热处理", "") or sem_result.get("heat_treatment", "")
    flaw = rule_result.get("探伤", "") or sem_result.get("flaw_detection", "")
    hp = [h for h in [heat, flaw] if h]
    parts.append(f"热处理与探伤: {_map_field(hp)}")

    rough = list(rule_result.get("粗糙度", []))
    qrough = sem_result.get("roughness", "")
    if qrough and qrough not in rough:
        rough.append(qrough)
    parts.append(f"标识与检验: {_map_field(rough)}")

    parts.append("线切割: 无")

    tols = list(rule_result.get("公差", []))
    qtol = sem_result.get("tolerance", "")
    qlin = sem_result.get("linear_tolerance", "")
    for v in [qtol, qlin]:
        if v and v not in tols:
            tols.append(v)
    parts.append(f"精度与检测特征: {_map_field(tols)}")

    surf = sem_result.get("surface_treatment", "") or sem_result.get("material_grade", "")
    parts.append(f"表面处理与镀层特征: {_map_field(surf)}")

    radii = rule_result.get("圆角", [])
    parts.append(f"过渡特征: {_map_field(radii)}")

    other = list(rule_result.get("数量/均布", []))
    sp = sem_result.get("special_process", "")
    if sp and sp not in ("无", ""):
        other.append(sp)
    parts.append(f"其他特征: {_map_field(other)}")

    return "\n".join(parts)


def format_output(rule_result: dict, sem_result: dict) -> str:
    """纯文本模型做格式整理（Step3 已提取完所有字段，这里只整理格式）"""
    extracted_text = build_extracted_text(rule_result, sem_result)

    messages = [
        {"role": "system", "content": FORMAT_PROMPT},
        {
            "role": "user",
            "content": f"请将以下提取结果整理成标准格式输出（每行一个字段，只用【】标记，不要解释）：\n\n{extracted_text}",
        },
    ]

    payload = {
        "model": "/home/caojiayuan/model/Qwen3_8B_V",
        "messages": messages,
        "max_tokens": 1024,
        "temperature": 0.05,
    }

    try:
        resp = requests.post(f"{VLLM_URL}/v1/chat/completions", json=payload, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        raw = data["choices"][0]["message"]["content"]
        return raw.strip()
    except Exception as e:
        print(f"  [Step4 格式化失败] {e}")
        return _fallback_format(rule_result, sem_result)


def _fallback_format(rule_result: dict, sem_result: dict) -> str:
    """直接拼接"""
    lines = []
    dn = rule_result.get("图号", "") or sem_result.get("drawing_no", "")
    pn = rule_result.get("零件名称", "") or sem_result.get("part_name", "")
    morph = sem_result.get("morphology", "")
    tech = rule_result.get("技术要求", [])
    dims = rule_result.get("尺寸", [])[:20]
    threads = rule_result.get("螺纹与螺孔", [])
    chamfers = list(rule_result.get("倒角", []))
    qch = sem_result.get("chamfer", "")
    if qch and qch not in chamfers:
        chamfers.append(qch)
    heat = rule_result.get("热处理", "") or sem_result.get("heat_treatment", "")
    flaw = rule_result.get("探伤", "") or sem_result.get("flaw_detection", "")
    rough = list(rule_result.get("粗糙度", []))
    qrough = sem_result.get("roughness", "")
    if qrough and qrough not in rough:
        rough.append(qrough)
    tols = list(rule_result.get("公差", []))
    qtol = sem_result.get("tolerance", "")
    if qtol and qtol not in tols:
        tols.append(qtol)
    radii = rule_result.get("圆角", [])
    other = list(rule_result.get("数量/均布", []))
    sp = sem_result.get("special_process", "")
    if sp and sp not in ("无", ""):
        other.append(sp)
    mf = sem_result.get("material_form", "")
    surf = sem_result.get("surface_treatment", "")
    pt = sem_result.get("part_type", "")
    ef = sem_result.get("end_face", "")

    lines.append(f"【图号】{dn or '无'}")
    lines.append(f"【零件名称】{pn or '无'}")
    lines.append(f"【毛坯类型】{mf or '无'}")
    lines.append(f"【技术要求】{'；'.join(tech) if tech else '无'}")
    lines.append(f"【形态】{morph or '无'}")
    lines.append(f"【类型】{pt or '无'}")
    lines.append(f"【关键尺寸】{'；'.join(dims) if dims else '无'}")
    lines.append("【弧段与齿形】无")
    lines.append(f"【端面与平面】{ef or '无'}")
    lines.append("【外圆与内孔】无")
    lines.append(f"【螺纹与螺孔】{'；'.join(threads) if threads else '无'}")
    lines.append(f"【倒角】{'；'.join(chamfers) if chamfers else '无'}")
    hp = [h for h in [heat, flaw] if h]
    lines.append(f"【热处理与探伤】{'；'.join(hp) if hp else '无'}")
    lines.append(f"【标识与检验】{'；'.join(rough) if rough else '无'}")
    lines.append("【线切割】无")
    lines.append(f"【精度与检测特征】{'；'.join(tols) if tols else '无'}")
    lines.append(f"【表面处理与镀层特征】{surf or '无'}")
    lines.append(f"【过渡特征】{'；'.join(radii) if radii else '无'}")
    lines.append(f"【其他特征】{'；'.join(other) if other else '无'}")
    return "\n".join(lines)


if __name__ == "__main__":
    print("Usage: from format_output import format_output")
    print("  format_output(rule_result, sem_result)")
