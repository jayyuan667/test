# -*- coding: utf-8 -*-
"""Expert judgment step using LLM — structured compression layer."""

import json
import os
from typing import List, Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field


class ExpertJudgmentOutput(BaseModel):
    """结构化专家判断输出，作为 ProcessGenerator 的唯一上下文来源。"""
    part_number: str = Field(default="未知", description="图号")
    part_type: str = Field(default="未知", description="零件类型")
    material: str = Field(default="未知", description="材料")
    dimensions: str = Field(default="未知", description="外形尺寸")
    surface_treatment: str = Field(default="无", description="表面处理")
    tolerances: str = Field(default="未知", description="公差等级")
    heat_treatment: str = Field(default="无", description="热处理要求")
    special_requirements: str = Field(default="无", description="特殊要求")
    confidence: float = Field(default=0.5, description="提取完整性置信度 0.0–1.0")


_SYSTEM_PROMPT = """你是资深机械工艺工程师。根据输入的图纸特征描述，提取结构化摘要。

输出格式（严格 JSON，不输出任何其他内容）：
{
  "part_number": "图号，无则填'未知'",
  "part_type": "零件功能类型，如'板类-安装板'或'轴套类-配合件'",
  "material": "材料牌号，如'6061铝合金'或'45钢'，无则填'未知'",
  "dimensions": "外形尺寸，如'388×358×13'或'Ø63×16'，无则填'未知'",
  "surface_treatment": "表面处理工艺，如'阳极氧化'，无则填'无'",
  "tolerances": "关键公差等级或未注公差标准，无则填'未知'",
  "heat_treatment": "热处理要求，如'调质HRC40-45'，无则填'无'",
  "special_requirements": "其他特殊工艺要求，无则填'无'",
  "confidence": 0.85
}

要求：
- 每个字段必须输出，无法判断的字符串字段填'未知'，confidence 填 0.5，不允许省略任何字段
- confidence 为你对本次提取完整性的自评（0.0 最低，1.0 最高）
- 只输出 JSON，不输出任何 Markdown 标记或其他文字""".strip()

# 保留旧提示词，供 analyze_single() 向后兼容
_LEGACY_SYSTEM_PROMPT = (
    "You are an industrial expert. "
    "Please output a compact Markdown format analysis report in Chinese."
)


class ExpertJudge:
    """Performs expert judgment on drawing analysis results using LLM."""

    def __init__(self):
        self.client = ChatOpenAI(
            api_key=os.getenv("LLM_API_KEY"),
            base_url=os.getenv("LLM_BASE_URL"),
            model=os.getenv("LLM_MODEL"),
            temperature=0.3,
            timeout=300,
        )

    def analyze(self, descriptions: List[Dict[str, Any]]) -> ExpertJudgmentOutput:
        """分析图纸描述，返回结构化专家判断。

        Args:
            descriptions: Vision analysis 结果列表，每项含 'description' 字段

        Returns:
            ExpertJudgmentOutput 结构化对象（含 confidence）
        """
        descriptions_text = "\n\n".join(
            f"第{i + 1}页：{r['description']}" for i, r in enumerate(descriptions)
        )

        response = self.client.invoke([
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=f"图纸特征描述如下：\n\n{descriptions_text}"),
        ])

        raw = response.content.strip()
        # 去除模型可能添加的 markdown 代码块标记
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        try:
            data = json.loads(raw)
            # confidence 需为 float
            if "confidence" in data:
                data["confidence"] = float(data["confidence"])
            return ExpertJudgmentOutput(**data)
        except Exception as e:
            # 解析失败时返回低置信度的默认对象，不阻断主流程
            import logging
            logging.getLogger(__name__).warning(
                "[ExpertJudge] JSON 解析失败，使用默认输出: %s | raw=%s", e, raw[:200]
            )
            return ExpertJudgmentOutput(confidence=0.3)

    @staticmethod
    def to_str(output: ExpertJudgmentOutput) -> str:
        """将结构化输出序列化为【字段】值格式，供 ProcessGenerator 消费。"""
        return (
            f"【零件类型】{output.part_type}\n"
            f"【图号】{output.part_number}\n"
            f"【材料】{output.material}\n"
            f"【外形尺寸】{output.dimensions}\n"
            f"【表面处理】{output.surface_treatment}\n"
            f"【公差等级】{output.tolerances}\n"
            f"【热处理要求】{output.heat_treatment}\n"
            f"【特殊要求】{output.special_requirements}\n"
            f"【综合置信度】{output.confidence:.2f}"
        )

    def analyze_single(self, description: str, page_num: int = 1) -> str:
        """单页分析，保留向后兼容接口（batch.py 使用）。"""
        response = self.client.invoke([
            SystemMessage(content=_LEGACY_SYSTEM_PROMPT),
            HumanMessage(content=f"第{page_num}页：\n{description}"),
        ])
        return response.content
