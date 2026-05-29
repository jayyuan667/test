# -*- coding: utf-8 -*-
import sys; sys.stdout.reconfigure(encoding="utf-8")
"""Vision analysis step using multi-modal vision model."""

import os
import base64
from typing import List, Dict, Any
from datetime import datetime
from openai import OpenAI

from ..config import validate_vision_config


# System prompt for mechanical engineering drawing analysis
VISION_SYSTEM_PROMPT = """你是一名专业的机械工程图纸解析专家。请对输入的工程图纸进行详细特征提取，并按以下严格格式要求紧密输出：

【格式约束】
1. 图号仅保留文件代号（如D125A-181200A003），严禁包含版本、比例、密级、文件名前缀（如(AB)）等任何其他信息
2. 各特征大类之间不要使用横杠(---)或任何分隔符，直接连续输出
3. 同一大类下的多条内容必须用分号(；)分隔，严禁使用换行或序号
4. 所有数值必须保留图纸原标注的公差、符号和单位
5. 如某特征在图纸中不存在，该字段填写"无"
6. 【】后面直接接信息

【提取字段及规则】

【图号】
仅填写文件代号（示例：D125A-181200A003）

【零件名称】
填写图纸标题栏中的零件名称

【毛坯类型】
填写毛坯类型（如锻件、铸件、棒料等）；如无明确标注填"无"

【技术要求】
原文提取所有技术要求条目；多条用分号分隔

【形态】
一句话概括零件整体几何形态（如：双端螺纹中段多阶梯光杆轴类零件；长方体板状结构）

【类型】
零件功能类别（如：紧固件-双头螺柱；密封件-汽封圈；滑动导向件-滑块）

【关键尺寸】
提取所有关键尺寸（总长、直径、长度、孔径、深度、角度等）；带公差的尺寸保留公差；多条用分号分隔

【弧段与齿形】
提取圆弧分度、齿形参数、滚花参数、齿距、模数等；多条用分号分隔

【端面与平面】
描述各端面特征、基准面、打印标识面、配合面等；多条用分号分隔

【外圆与内孔】
提取外圆直径及公差、内孔直径及公差、表面粗糙度；多条用分号分隔

【螺纹与螺孔】
提取螺纹规格（如M27×2-6H、5 1/2"-8UN-2A）、螺纹长度、旋向、精度等级；多条用分号分隔

【倒角】
提取所有倒角尺寸（如1×45°、C1.5、0.8×45°）；多条用分号分隔

【热处理与探伤】
提取硬度要求（如HB293-321、HRC43-48）、热处理工艺、无损检测要求（如超声波探伤2级、磁粉探伤）；多条用分号分隔

【标识与检验】
提取打印标识要求、检验标准、粗糙度要求；多条用分号分隔

【线切割】
填写线切割工艺要求或"无"

【精度与检测特征】
提取形位公差（如同轴度、垂直度、跳动）、线性公差；保留公差值和基准符号；多条用分号分隔

【表面处理与镀层特征】
提取表面处理（如发蓝、磷化）、镀层要求；如无填"无"

【过渡特征】
提取所有圆弧过渡（如R3.15、R0.5）、锥面过渡、退刀槽；多条用分号分隔

【其他特征】
提取弧段数量（如6段60°弧段）、特殊工艺要求、材料可追溯要求、工作温度等；多条用分号分隔"""


class VisionAnalyzer:
    """Analyzes PDF pages using vision model to extract drawing features."""

    @staticmethod
    def _normalize_base_url(base_url: str | None) -> str | None:
        if not base_url:
            return None
        value = base_url.strip()
        if not value:
            return None
        if not value.startswith(("http://", "https://")):
            value = f"https://{value}"
        return value.rstrip("/")

    def __init__(self):
        """Initialize vision analyzer with API credentials from environment."""
        config_error = validate_vision_config("doubao")
        if config_error:
            raise ValueError(config_error)

        self.api_key = os.getenv("VISION_API_KEY")
        self.base_url = self._normalize_base_url(os.getenv("VISION_API_BASE"))
        model_param = os.getenv("VISION_MODEL_ID", "")
        self.model = model_param.replace("model_id=", "").strip()
        requested_max_tokens = int(os.getenv("VISION_MAX_TOKENS", "4096"))
        self.max_tokens = min(requested_max_tokens, 4096)

        print(f"[Vision] API配置: base_url={self.base_url}, model={self.model}")

        if not self.api_key:
            print("[Vision] WARNING: VISION_API_KEY is not set!")
        if not self.base_url:
            print("[Vision] WARNING: VISION_API_BASE is not set!")
        if not self.model:
            print("[Vision] WARNING: VISION_MODEL_ID is not set!")

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def analyze_image(self, image_path: str) -> Dict[str, Any]:
        """Analyze a single image and extract features.

        Args:
            image_path: Path to the PNG image file

        Returns:
            Dictionary with image_path, description, and timestamp
        """
        print(f"[Vision] 开始分析图片: {image_path}")

        try:
            with open(image_path, "rb") as f:
                image_base64 = base64.b64encode(f.read()).decode("utf-8")

            messages = [
                {"role": "system", "content": VISION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_base64}"
                            },
                        },
                        {
                            "type": "text",
                            "text": "请严格按照上述格式要求详细分析这张工程图纸，提取所有特征信息，确保每个字段都填写完整。",
                        },
                    ],
                },
            ]

            print("[Vision] 发送API请求...")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                timeout=600,
            )
            print("[Vision] API响应接收完成")

            description = response.choices[0].message.content
            print(f"[Vision] 分析完成: {image_path}")

            return {
                "image_path": image_path,
                "description": description,
                "timestamp": datetime.now().isoformat(),
                "ok": True,
            }

        except Exception as e:
            print(f"[Vision] ERROR分析图片失败 {image_path}: {e}")
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
        """Analyze multiple images.

        Args:
            image_paths: List of paths to PNG image files
            progress_callback: Optional callback function(image_path, result) called after each image

        Returns:
            List of analysis results
        """
        print(f"[Vision] 开始分析 {len(image_paths)} 张图片")
        results = []
        for i, image_path in enumerate(image_paths):
            print(f"[Vision] 分析进度: {i+1}/{len(image_paths)}")

            # 分析前发送进度
            if progress_callback:
                progress_callback(image_path, f"正在分析第 {i+1}/{len(image_paths)} 页...")

            result = self.analyze_image(image_path)
            results.append(result)

            # 分析完成后发送完整结果（不截断）
            if progress_callback:
                desc = result.get("description", "")
                if result.get("error"):
                    desc = f"[ERROR] {result['error']}"
                progress_callback(image_path, f"第 {i+1} 页分析完成:\n{desc}")

        print("[Vision] 所有图片分析完成")
        return results
