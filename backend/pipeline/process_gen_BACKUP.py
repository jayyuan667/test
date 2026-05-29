# -*- coding: utf-8 -*-
"""Process generation step using RAG and LLM."""

import os
import re
import time
from typing import List, Dict, Any, Optional, Tuple
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage


class ProcessGenerator:
    """Generates manufacturing process specifications using RAG and LLM."""

    def __init__(self):
        """Initialize process generator with RAG and LLM."""
        self.llm_client = ChatOpenAI(
            api_key=os.getenv("LLM_API_KEY"),
            base_url=os.getenv("LLM_BASE_URL"),
            model=os.getenv("LLM_MODEL"),
            temperature=0.3,
            timeout=300,  # 5 minutes for local vLLM
        )

        # Try to import RAG functions (use relative import within backend package)
        try:
            from ..vector_map_rag import query_by_fused_text, query_by_prefix

            self.rag_available = True
            self.query_by_fused_text = query_by_fused_text
            self.query_by_prefix = query_by_prefix
        except ImportError:
            self.rag_available = False
            print("Warning: RAG engine not available")

    def _extract_prefix_from_text(self, text: str) -> Optional[str]:
        """Extract drawing number prefix from text."""
        patterns = [
            r"【图号】\s*([1-9][A-Z]\d{4,6})",
            r"(?:^|[^\w])([1-9][A-Z]\d{4,6})(?:[A-Z]|$|[^\w])",
        ]
        for p in patterns:
            found = re.findall(p, text or "", re.IGNORECASE)
            if found:
                return found[0].upper()
        return None

    def _fuse_descriptions(self, descriptions: List[Dict[str, Any]]) -> str:
        """Fuse multiple page descriptions into a single feature set.

        Args:
            descriptions: List of vision analysis results

        Returns:
            Fused description text with 【】 field prefixes
        """
        feature_pattern = r"【([^】]+)】([^\n【]*)"

        all_features = {}
        for i, r in enumerate(descriptions):
            features = re.findall(feature_pattern, r.get("description", ""))
            for field_name, field_value in features:
                if field_name not in all_features:
                    all_features[field_name] = []
                if field_value.strip():
                    all_features[field_name].append(field_value.strip())

        fused_parts = []
        for field_name, values in sorted(all_features.items()):
            if values:
                unique_values = list(dict.fromkeys(values))
                fused_parts.append(f"【{field_name}】" + "；".join(unique_values))

        fused_description = "\n".join(fused_parts)
        if not fused_description:
            fused_description = "\n".join(
                [r.get("description", "") for r in descriptions]
            )

        return fused_description

    def _parse_markdown_process(self, raw_text: str) -> List[List[str]]:
        """Parse Markdown list format process steps.

        Args:
            raw_text: Raw text containing markdown process list

        Returns:
            List of [tag, content] pairs
        """
        import re
        process_data = []
        for line in raw_text.strip().split("\n"):
            line = line.strip()
            if line.startswith("- ") or line.startswith("* "):
                content = line[2:].strip()
                # 兼容多种分隔符：: @ ：(中文冒号)
                # 匹配如：0010: 车外圆 或 0010@车外圆 或 0010：车外圆
                match = re.match(r"^(\d{4})\s*[:：@]\s*(.+)$", content)
                if match:
                    tag = match.group(1)
                    proc_content = match.group(2).strip()
                    process_data.append([tag, proc_content])
        return process_data

    def _normalize_standard_process_rows(self, rows: List[Any]) -> List[List[str]]:
        """Normalize stored DB process rows into [tag, content] pairs.

        Stored `vectors_v2.content` rows are often plain strings like:
        - 0010@工序内容
        - 0010: 工序内容
        - 0010 工序内容
        """
        normalized = []
        for row in rows or []:
            if isinstance(row, (list, tuple)) and len(row) >= 2:
                normalized.append([str(row[0]).strip(), str(row[1]).strip()])
                continue

            text = str(row or "").strip()
            if not text:
                continue

            match = re.match(r"^(\d{4})\s*[@:：\-\|,，;；\s]*\s*(.+)$", text)
            if match:
                normalized.append([match.group(1).strip(), match.group(2).strip()])
            else:
                normalized.append(["", text])
        return normalized

    def generate(
        self,
        descriptions: List[Dict[str, Any]],
        expert_judgment: str,
        prefix_hint: Optional[str] = None,
        log_callback=None,
        stream_callback=None,
        library_key: Optional[str] = None,
    ) -> Tuple[str, List[List[str]], Optional[Dict[str, Any]]:
        """Generate process specifications.

        Args:
            descriptions: Vision analysis results
            expert_judgment: Expert judgment report
            prefix_hint: Optional drawing number prefix hint
            log_callback: Optional callback function for logging
            stream_callback: Optional streaming callback
            library_key: Optional library key for RAG scope (default: public)
        """
        fused_description = self._fuse_descriptions(descriptions)

        rag_results = None
        rag_context = ""
        use_rag_only = False
        process_flow_raw = ""

        # Try RAG lookup
        if self.rag_available:
            try:
                # Always try to extract REAL drawing number from Vision output first
                # (Vision output is more reliable than filename)
                extracted_from_vision = None
                for r in descriptions:
                    extracted = self._extract_prefix_from_text(r.get("description", ""))
                    if extracted:
                        extracted_from_vision = extracted
                        break

                # Use Vision-extracted number if available, otherwise use filename hint
                effective_prefix = extracted_from_vision or prefix_hint
                print(
                    f"[RAG] prefix_hint={prefix_hint}, extracted_from_vision={extracted_from_vision}, effective_prefix={effective_prefix}"
                )

                rag_results = self.query_by_fused_text(
                    fused_description,
                    top_k=3,
                    min_similarity=0.25,
                    prefix_hint=effective_prefix,
                    log_callback=log_callback,
                    library_key=library_key,
                )

                # Check for exact prefix match first (use effective prefix)
                if effective_prefix:
                    exact_result = self.query_by_prefix(effective_prefix, top_k=1, library_key=library_key)
                    if exact_result and exact_result.get("matches"):
                        use_rag_only = True
                        process_list = exact_result["matches"][0].get(
                            "process_list", []
                        )
                        normalized_rows = self._normalize_standard_process_rows(process_list)
                        process_flow_raw = "\n".join(
                            [f"- {tag}: {content}" if tag else f"- {content}" for tag, content in normalized_rows]
                        )
                        if log_callback:
                            log_callback("📌 命中精确图号，开始逐步输出工艺...")
                        if stream_callback:
                            for tag, content in normalized_rows:
                                stream_callback(f"- {tag}: {content}\n" if tag else f"- {content}\n")
                                time.sleep(0.03)

                if not use_rag_only and rag_results and rag_results.get("matches"):
                    rag_context = rag_results.get("rag_context", "")

            except Exception as e:
                print(f"RAG error: {e}")
                rag_results = None

        # Generate using LLM if not using RAG directly
        if not use_rag_only:
            if rag_context:
                prompt = self._build_llm_prompt(
                    fused_description, expert_judgment, rag_context, rag_results
                )
            else:
                prompt = self._build_fallback_prompt(fused_description, expert_judgment)

            if log_callback:
                log_callback("🧠 开始流式生成工艺规程...")
            process_flow_raw = self._stream_llm_response(
                prompt,
                log_callback=log_callback,
                stream_callback=stream_callback,
            )

            # Extract process section if present
            if "## 生成的工艺规程" in process_flow_raw:
                parts = process_flow_raw.split("## 生成的工艺规程")
                if len(parts) > 1:
                    process_flow_raw = parts[-1].strip()

        # Parse the markdown
        if use_rag_only:
            process_data = self._normalize_standard_process_rows(
                exact_result["matches"][0].get("process_list", []) if exact_result and exact_result.get("matches") else []
            )
        else:
            process_data = self._parse_markdown_process(process_flow_raw)

        return process_flow_raw, process_data, rag_results

    def _stream_llm_response(self, prompt: str, log_callback=None, stream_callback=None) -> str:
        """Stream LLM response chunk by chunk and collect final text."""
        messages = [
            SystemMessage(content="输出简单Markdown格式，逐步流式输出，不要一次性整段返回。"),
            HumanMessage(content=prompt),
        ]

        try:
            chunks = []
            buffered_for_log = ""
            for chunk in self.llm_client.stream(messages):
                delta = getattr(chunk, "content", "") or ""
                if not delta:
                    continue
                chunks.append(delta)
                if stream_callback:
                    stream_callback(delta)

                buffered_for_log += delta
                if log_callback and (len(buffered_for_log) >= 80 or "\n" in delta):
                    log_callback(buffered_for_log)
                    buffered_for_log = ""
                    time.sleep(0.01)

            if buffered_for_log and log_callback:
                log_callback(buffered_for_log)

            final_text = "".join(chunks)
            if final_text.strip():
                return final_text
        except Exception as e:
            print(f"[ProcessGenerator] streaming failed, fallback to invoke: {e}")

        # Fallback: non-streaming invoke
        response = self.llm_client.invoke(messages)
        final_text = response.content or ""

        if log_callback and final_text:
            # Simulate gradual output if the provider doesn't stream
            step = max(5, len(final_text) // 40)
            for i in range(0, len(final_text), step):
                log_callback(final_text[i:i + step])
                time.sleep(0.01)

        if stream_callback and final_text:
            step = max(5, len(final_text) // 40)
            for i in range(0, len(final_text), step):
                stream_callback(final_text[i:i + step])
                time.sleep(0.01)

        return final_text

    def _build_llm_prompt(
        self,
        fused_description: str,
        expert_judgment: str,
        rag_context: str,
        rag_results: Optional[Dict[str, Any]],
    ) -> str:
        """Build LLM prompt with RAG context."""
        candidates_info = ""
        if rag_results and rag_results.get("matches"):
            for i, m in enumerate(rag_results["matches"][:3], 1):
                candidates_info += f"候选{i}: {m.get('drawing_id')} (相似度:{m.get('similarity'):.3f}, 类型:{m.get('match_type')})\n"

        prompt = f"""你是一名资深工艺工程师。现在有3个参考工艺候选，请先进行对比分析，再选择最合适的一个进行增删改。

## 候选工艺概览:
{candidates_info}

## 候选工艺详情:
{rag_context}

## 专家分析结果（关键选型依据）:
{expert_judgment}

## 图纸视觉描述:
{fused_description[:800]}

## 输出格式:
```markdown
## 候选选择
选择: [图号]
理由: [根据专家分析中的哪些特征选择该候选]

## 生成的工艺规程
- 0010: 工序内容
...
```"""
        return prompt

    def _build_fallback_prompt(
        self, fused_description: str, expert_judgment: str
    ) -> str:
        """Build LLM prompt without RAG context."""
        return f"""你是一名工艺工程师。根据图纸分析结果生成工艺规程。

## 专家分析结果:
{expert_judgment}

## 图纸视觉描述:
{fused_description[:500]}

## 输出要求：
1. 只输出标签编码和工序内容
2. 使用Markdown格式：- 0010: 工序内容"""
