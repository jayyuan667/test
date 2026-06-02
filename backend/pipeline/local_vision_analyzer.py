# -*- coding: utf-8 -*-
"""
本地视觉分析器 - 使用 EasyOCR + 规则引擎 + Qwen3-VL-8B
作为 VisionAnalyzer 的本地离线替代方案
"""

import os
import sys
from typing import List, Dict, Any
from datetime import datetime

# 确保 v_model_test 路径在 sys.path 中（相对于 backend 目录）
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_V_MODEL_DIR = os.path.join(_BACKEND_DIR, "..", "v_model_test")
if _V_MODEL_DIR not in sys.path:
    sys.path.insert(0, _V_MODEL_DIR)

from ppstructure_extractor import extract_with_ppstructure
from rule_engine import DrawingRuleEngine
from semantic_enhancer import enhance as semantic_enhance
from format_output import format_output


# 本地 vLLM 服务地址（服务器）
_LOCAL_VLLM_HOST = "http://192.168.2.24"
_LOCAL_VLLM_PORT = 8001
_LOCAL_VLLM_URL = f"{_LOCAL_VLLM_HOST}:{_LOCAL_VLLM_PORT}"

# 全局 v_model_test 路径（部署时需同步到服务器）
V_MODEL_TEST_DIR = _V_MODEL_DIR


def _format_rule_result(rule_result: dict, sem_result: dict) -> str:
    """
    将规则引擎 + 语义增强的结果格式化为与 Doubao 输出兼容的 description 字符串
    这样 expert_judge 和 process_gen 保持兼容
    """
    lines = []

    drawing_no = rule_result.get("图号", "")
    # 图号 - 优先 RuleEngine，否则用 Qwen 提取
    drawing_no = rule_result.get("图号", "") or sem_result.get("drawing_no", "")
    if drawing_no:
        lines.append(f"【图号】{drawing_no}")

    # 加工类型 - Qwen 补充
    process_type = sem_result.get("process_type", "")
    if process_type:
        lines.append(f"【加工类型】{process_type}")

    # 零件名称 - 优先 RuleEngine，否则用 Qwen 补充
    part_name = rule_result.get("零件名称", "") or sem_result.get("part_name", "")
    if part_name:
        lines.append(f"【零件名称】{part_name}")

    # 毛坯类型 - Qwen 补充
    material_form = sem_result.get("material_form", "")
    if material_form:
        lines.append(f"【毛坯类型】{material_form}")

    # 技术要求
    tech_reqs = rule_result.get("技术要求", [])
    if tech_reqs:
        lines.append("【技术要求】" + "；".join(tech_reqs))

    # 形态
    morphology = sem_result.get("morphology", "")
    if morphology:
        lines.append(f"【形态】{morphology}")

    # 类型
    part_type = sem_result.get("part_type", "")
    if part_type:
        lines.append(f"【类型】{part_type}")

    # 关键尺寸
    dimensions = rule_result.get("尺寸", [])
    if dimensions:
        lines.append("【关键尺寸】" + "；".join(dimensions[:20]))

    # 螺纹与螺孔
    threads = rule_result.get("螺纹与螺孔", [])
    if threads:
        lines.append("【螺纹与螺孔】" + "；".join(threads))

    # 倒角 - 合并 RuleEngine 和 Qwen 结果
    chamfers = rule_result.get("倒角", [])
    qchamfer = sem_result.get("chamfer", "")
    if qchamfer and qchamfer not in chamfers:
        chamfers.append(qchamfer)
    if chamfers:
        lines.append("【倒角】" + "；".join(chamfers))

    # 圆角
    radii = rule_result.get("圆角", [])
    if radii:
        lines.append("【圆角】" + "；".join(radii))

    # 热处理 - 合并
    heat = rule_result.get("热处理", "") or sem_result.get("heat_treatment", "")
    if heat:
        lines.append(f"【热处理与探伤】{heat}")

    # 探伤 - Qwen 补充
    flaw = rule_result.get("探伤", "") or sem_result.get("flaw_detection", "")
    if flaw:
        lines.append(f"【探伤】{flaw}")

    # 粗糙度 - 合并 RuleEngine 和 Qwen
    roughness = rule_result.get("粗糙度", [])
    qrough = sem_result.get("roughness", "")
    if qrough:
        for r in qrough.split("；"):
            if r not in roughness:
                roughness.append(r)
    if roughness:
        lines.append("【标识与检验】" + "；".join(roughness))

    # 形位公差 - Qwen 补充
    tolerance = sem_result.get("tolerance", "")
    linear_tol = sem_result.get("linear_tolerance", "")
    if tolerance or linear_tol:
        tol_parts = []
        if tolerance:
            tol_parts.append(tolerance)
        if linear_tol:
            tol_parts.append(linear_tol)
        lines.append("【精度与检测特征】" + "；".join(tol_parts))

    # 端面特征 - Qwen 补充
    end_face = sem_result.get("end_face", "")
    if end_face:
        lines.append(f"【端面与平面】{end_face}")

    # 材料牌号
    material_grade = sem_result.get("material_grade", "")
    if material_grade and material_grade != "未标注":
        lines.append(f"【材料牌号】{material_grade}")

    # 特殊工艺
    special_process = sem_result.get("special_process", "")
    if special_process and special_process != "无":
        lines.append(f"【特殊工艺】{special_process}")

    # 表面处理 - Qwen 补充
    surface = sem_result.get("surface_treatment", "")
    if surface and surface != "无":
        lines.append(f"【表面处理与镀层特征】{surface}")

    return "\n".join(lines)


class LocalVisionAnalyzer:
    """
    本地离线视觉分析器
    流程: EasyOCR(OCR) -> DrawingRuleEngine(确定性提取) -> Qwen3-VL-8B(语义增强)
    """

    def __init__(self):
        print("[LocalVision] 初始化本地视觉分析器")
        print(f"[LocalVision] vLLM: {_LOCAL_VLLM_URL}")
        self.rule_engine = DrawingRuleEngine()
        print("[LocalVision] RuleEngine 初始化完成")

    def analyze_image(self, image_path: str) -> Dict[str, Any]:
        """分析单张图片

        Args:
            image_path: PNG 图片路径

        Returns:
            兼容 VisionAnalyzer 接口的字典: {image_path, description, timestamp}
        """
        print(f"[LocalVision] 分析图片: {image_path}")

        try:
            # Step 1: EasyOCR OCR
            ocr_result = extract_with_ppstructure(image_path)
            full_text = ocr_result.get("full_text", "")
            print(f"[LocalVision] OCR 完成，文字长度: {len(full_text)}")

            # Step 2: 规则引擎确定性提取
            rule_result = self.rule_engine.extract_all(full_text, ocr_result.get("blocks", []))
            print(f"[LocalVision] RuleEngine 完成，图号: {rule_result.get('图号', '未找到')}")

            # Step 3: Qwen3-VL-8B 语义增强
            sem_result = semantic_enhance(image_path, rule_result)
            print(f"[LocalVision] 语义增强完成，形态: {sem_result.get('morphology', '无')}")

            # Step 4: Qwen3-8B 纯文本格式化输出（19字段 Doubao 格式）
            description = format_output(rule_result, sem_result)

            return {
                "image_path": image_path,
                "description": description,
                "timestamp": datetime.now().isoformat(),
                "ok": True,
            }

        except Exception as e:
            print(f"[LocalVision] ERROR: {e}")
            import traceback
            traceback.print_exc()
            return {
                "image_path": image_path,
                "description": "",
                "timestamp": datetime.now().isoformat(),
                "ok": False,
                "error": str(e),
            }

    def analyze_images(self, image_paths: List[str], progress_callback=None) -> List[Dict[str, Any]]:
        """分析多张图片

        Args:
            image_paths: PNG 图片路径列表
            progress_callback: 进度回调(image_path, message)

        Returns:
            分析结果列表
        """
        print(f"[LocalVision] 开始分析 {len(image_paths)} 张图片")
        results = []
        for i, image_path in enumerate(image_paths):
            msg = f"正在分析第 {i+1}/{len(image_paths)} 页..."
            print(f"[LocalVision] {msg}")
            if progress_callback:
                progress_callback(image_path, msg)

            result = self.analyze_image(image_path)
            results.append(result)

            if progress_callback:
                desc = result.get("description", "")
                if result.get("error"):
                    desc = f"[ERROR] {result['error']}"
                progress_callback(image_path, f"第 {i+1}/{len(image_paths)} 页分析完成:\n{desc}")

        print(f"[LocalVision] 所有图片分析完成，共 {len(results)} 页")
        return results
