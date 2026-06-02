# -*- coding: utf-8 -*-
"""Expert judgment step using LLM."""

import os
from typing import List, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage


# Expert judgment prompt template
EXPERT_JUDGMENT_PROMPT = """Based on the following drawing analysis results:

{descriptions}

Please output in compact Markdown format:

## 专家判断报告

- 文档类型: [type]
- 行业: [industry]
- 核心技术: [technology]
- 主要材料: [material]
- 关键工艺: [processes]

## 关键信息

- 核心部件: [components]
- 核心尺寸: [dimensions]
- 制造标准: [standards]

## 详细参数

- [参数1]: [值] - [描述]
- [参数2]: [值] - [描述]

精简输出，不要多余的空行。"""


class ExpertJudge:
    """Performs expert judgment on drawing analysis results using LLM."""

    def __init__(self):
        """Initialize LLM client from environment variables."""
        self.client = ChatOpenAI(
            api_key=os.getenv("LLM_API_KEY"),
            base_url=os.getenv("LLM_BASE_URL"),
            model=os.getenv("LLM_MODEL"),
            temperature=0.3,
            timeout=300,  # 5 minutes for local vLLM
        )

    def analyze(self, descriptions: List[Dict[str, Any]]) -> str:
        """Analyze drawing descriptions and produce expert judgment.

        Args:
            descriptions: List of vision analysis results with 'description' field

        Returns:
            Expert judgment report in Markdown format
        """
        descriptions_text = "\n\n".join(
            [f"Page {i + 1}: {r['description']}" for i, r in enumerate(descriptions)]
        )

        prompt = EXPERT_JUDGMENT_PROMPT.format(descriptions=descriptions_text)

        response = self.client.invoke(
            [
                SystemMessage(
                    content="You are an industrial expert. Please output a compact Markdown format analysis report in Chinese."
                ),
                HumanMessage(content=prompt),
            ]
        )

        return response.content

    def analyze_single(self, description: str, page_num: int = 1) -> str:
        """Analyze a single page description.

        Args:
            description: Vision analysis description text
            page_num: Page number for reference

        Returns:
            Expert judgment report
        """
        response = self.client.invoke(
            [
                SystemMessage(
                    content="You are an industrial expert. Please output a compact Markdown format analysis report in Chinese."
                ),
                HumanMessage(
                    content=f"Page {page_num}:\n{description}\n\n{EXPERT_JUDGMENT_PROMPT.format(descriptions='')}"
                ),
            ]
        )

        return response.content
