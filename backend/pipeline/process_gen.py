# -*- coding: utf-8 -*-
"""Process generation step using RAG and LLM."""

import os
import re
import time
import logging
from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)


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

        # Try to import RAG functions with package/script fallbacks.
        try:
            from ..vector_map_rag import query_by_fused_text, query_by_prefix, query_by_vector_similarity
        except ImportError:
            try:
                from backend.vector_map_rag import query_by_fused_text, query_by_prefix, query_by_vector_similarity
            except ImportError:
                from vector_map_rag import query_by_fused_text, query_by_prefix, query_by_vector_similarity

        self.rag_available = True
        self.query_by_fused_text = query_by_fused_text
        self.query_by_prefix = query_by_prefix
        self.query_by_vector_similarity = query_by_vector_similarity

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

    def _normalize_prefix_hint(self, prefix_hint: Optional[str]) -> Optional[str]:
        if not prefix_hint:
            return None
        stem = os.path.splitext(os.path.basename(str(prefix_hint).strip()))[0].strip()
        return stem.upper() or None

    def _replace_placeholder_tokens(self, text: str) -> str:
        if not text:
            return ""
        cleaned = str(text).replace("ENDD$$", " ")
        cleaned = re.sub(r'(^|；|;|\n)-(\d)', r'\1\2', cleaned)
        return cleaned

    def _fuse_descriptions(self, descriptions: List[Dict[str, Any]]) -> str:
        """Fuse multiple page descriptions into a single feature set.

        Args:
            descriptions: List of vision analysis results

        Returns:
            Fused description text with 【】 field prefixes
        """
        # 单页无需合并，直接返回原文（保留用户审阅修改的全部内容）
        if len(descriptions) == 1:
            return self._replace_placeholder_tokens(descriptions[0].get("description", ""))

        feature_pattern = r"【([^】]+)】([^\n【]*)"

        all_features = {}
        for i, r in enumerate(descriptions):
            features = re.findall(feature_pattern, self._replace_placeholder_tokens(r.get("description", "")))
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
                [self._replace_placeholder_tokens(r.get("description", "")) for r in descriptions]
            )

        return fused_description

    def _parse_markdown_process(self, raw_text: str) -> List[List[str]]:
        """Parse Markdown list format process steps.

        Handles two output formats:
        - New: `- 0010: 工序内容 （工种：料）`
        - Old (legacy bug): `- 0010: 料（工序内容）`

        Returns:
            List of [tag, content] or [tag, trade_type, content] pairs
        """
        import re
        process_data = []
        for line in self._replace_placeholder_tokens(raw_text).strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            content = line[2:].strip() if line.startswith(("- ", "* ")) else line
            match = re.match(r"^(\d{4})\s*[:：@\-\|,，;；\s]*\s*(.+)$", content)
            if match:
                tag = match.group(1)
                proc_content = match.group(2).strip()
                if proc_content:
                    trade_type = ""
                    # ── 新格式：工序内容 （工种：料）──
                    trade_suffix_m = re.search(
                        r'\s*[（(]工种[：:]\s*([一-鿿\-]{1,6})\s*[）)]\s*$', proc_content
                    )
                    if trade_suffix_m:
                        trade_type = trade_suffix_m.group(1)
                        proc_content = proc_content[:trade_suffix_m.start()].strip()
                    else:
                        # ── 旧格式（bug产生的）：料（备料...）──
                        trade_m = re.match(r'^([一-鿿\-]{1,6})\s*[（(]([\s\S]+)', proc_content)
                        if trade_m:
                            trade_type = trade_m.group(1)
                            inner = trade_m.group(2)
                            if inner.endswith('）') or inner.endswith(')'):
                                inner = inner[:-1]
                            proc_content = inner.strip()

                    if trade_type:
                        process_data.append([tag, trade_type, proc_content.strip()])
                    else:
                        process_data.append([tag, proc_content])
        return process_data

    def _normalize_standard_process_rows(self, rows: List[Any]) -> List[List[str]]:
        """Normalize stored DB process rows into [tag, content] pairs.

        Handles three stored formats:
        - Two-segment:  0010@工序内容  →  [0010, 工序内容]
        - Three-segment: 0010@工种@工序内容  →  [0010, 工序内容 （工种：工种）]
        - Plain text:   0010: 工序内容  →  [0010, 工序内容]
        """
        normalized = []
        for row in rows or []:
            if isinstance(row, (list, tuple)) and len(row) >= 2:
                normalized.append([
                    self._replace_placeholder_tokens(str(row[0]).strip()),
                    self._replace_placeholder_tokens(str(row[1]).strip()),
                ])
                continue

            text = self._replace_placeholder_tokens(str(row or "")).strip()
            if not text:
                continue

            # ── 检测三段式格式：0010@工种@工序内容 ──
            parts = [p.strip() for p in text.split("@") if p.strip()]
            trade = ""
            content_body = ""
            if len(parts) >= 3:
                p1, p2 = parts[1], parts[2]
                if (len(p1) <= 6
                        and re.match(r'^[一-鿿\-]+$', p1)
                        and not re.match(r'^(?:工种|设备|工时|备注)[：:]', p2)
                        and len(p2) > len(p1)):
                    trade = p1
                    content_body = p2
                    if len(parts) > 3:
                        content_body += " " + " ".join(parts[3:])

            if trade and content_body:
                normalized.append([parts[0], f"{content_body} （工种：{trade}）"])
            else:
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
        geo_data: Optional[dict] = None,
        force_llm: bool = False,
    ) -> tuple[str, list[list[str]], dict | None]:
        """Generate process specifications with constraint-aware assembly."""
        fused_description = self._replace_placeholder_tokens(self._fuse_descriptions(descriptions))
        expert_judgment = self._replace_placeholder_tokens(expert_judgment)

        # ── Step 1: Extract constraints from review/feature text ──
        constraints = self._extract_process_constraints(fused_description, geo_data=geo_data)

        rag_results, rag_context, use_rag_only, exact_result = self._run_rag_lookup(
            fused_description, descriptions, prefix_hint, log_callback, library_key
        )

        # ── Step 2: 图号精确匹配 + 高相似度 → 直接返回蓝本工艺原文 ──
        if use_rag_only and not force_llm:
            if log_callback:
                log_callback("🔍 图号精确匹配且高相似度，直接采用蓝本工艺，跳过 LLM 和后校验...")
            process_list = (
                exact_result["matches"][0].get("process_list", [])
                if exact_result and exact_result.get("matches") else []
            )
            norm_rows = self._normalize_standard_process_rows(process_list)
            # Ensure all rows have （工种：xx） suffix — infer from content if absent
            _TRADE_KEYWORDS = [
                ("料", ["备料", "下料", "毛坯"]),
                ("热", ["退火", "时效", "正火", "淬火", "回火", "调质"]),
                ("铣", ["铣方", "铣外形", "数铣"]),
                ("车", ["车削", "车端面", "粗车", "精车"]),
                ("钻", ["钻孔", "钻"]),
                ("攻", ["攻丝", "攻螺纹", "攻"]),
                ("钳", ["去毛刺", "清洗", "试装", "钳"]),
                ("镀覆", ["镀覆", "外协镀", "AL/Ct", "Ocd"]),
                ("表处", ["阳极化", "电镀", "喷漆", "氧化", "镀"]),
                ("刻字", ["刻字"]),
                ("检", ["检验", "标识", "入库", "检"]),
            ]
            _rows_with_trade = []
            for tag, content in norm_rows:
                if "工种：" not in content:
                    for trade, keywords in _TRADE_KEYWORDS:
                        if any(kw in content for kw in keywords):
                            content = f"{content} （工种：{trade}）"
                            break
                _rows_with_trade.append(f"- {tag}: {content}" if tag else f"- {content}")
            proc_raw = "\n".join(_rows_with_trade)
            # ⚠️ 蓝本精确匹配 → 直接输出，不进行后校验（避免拆分改动）
            if stream_callback and proc_raw:
                lines = proc_raw.split("\n")
                for line in lines:
                    chunk = line + "\n"
                    stream_callback(chunk)
                    if log_callback:
                        log_callback(chunk)
                    time.sleep(0.06)  # 每行 60ms，10道工序约 0.6s，前端打字机可见
            return proc_raw, self._parse_markdown_process(proc_raw), rag_results

        if not rag_context:
            rag_context, rag_results = self._nearest_neighbor_fallback(
                fused_description, rag_results, library_key, log_callback
            )

        # ── Step 3: Determine blueprint usage mode ──
        exact_match = False
        vec_sim = 0.0
        if exact_result and exact_result.get("matches"):
            matched = exact_result["matches"][0]
            vec_sim = self._get_vector_sim_for_drawing(matched["drawing_id"], rag_results)
            exact_match = True
        use_blueprint = self._should_use_blueprint_as_base(exact_match, vec_sim)

        # ── Step 4: Extract allowed fragments (only when low similarity) ──
        allowed_fragments = {}
        if not use_blueprint and rag_context:
            allowed_fragments = self._extract_allowed_feature_fragments(rag_context, constraints)
            if log_callback and any(allowed_fragments.values()):
                frag_info = "；".join(f"{k}={v}" for k, v in allowed_fragments.items() if v)
                log_callback(f"📎 低相似度模式下，从历史候选提取允许补充字段: {frag_info}")

        # ── Step 5: Build controlled prompt ──
        prompt = (
            self._build_controlled_prompt(
                fused_description, expert_judgment, rag_context, rag_results,
                constraints, use_blueprint, allowed_fragments
            )
            if rag_context
            else self._build_fallback_prompt(fused_description, expert_judgment, constraints)
        )

        if log_callback:
            log_callback("🧠 开始流式生成工艺规程...")
        process_flow_raw = self._stream_llm_response(
            prompt, log_callback=log_callback, stream_callback=stream_callback
        )
        process_flow_raw = self._extract_process_section(process_flow_raw)

        # ── Step 6: Post-check ──
        process_flow_raw = self._post_check_process(process_flow_raw, constraints)

        return process_flow_raw, self._parse_markdown_process(process_flow_raw), rag_results

    # ── RAG helpers ──────────────────────────────────────────────────────────

    def _extract_drawing_prefix(self, descriptions: List[Dict[str, Any]], prefix_hint: Optional[str]) -> Optional[str]:
        """从视觉描述中提取图号，优先于文件名。"""
        for r in descriptions:
            extracted = self._extract_prefix_from_text(r.get("description", ""))
            if extracted:
                return extracted
        return self._normalize_prefix_hint(prefix_hint)

    def _get_vector_sim_for_drawing(self, drawing_id: str, rag_results: Optional[Dict]) -> float:
        """从 rag_results 查找某图号的实际余弦相似度。"""
        if not rag_results or not rag_results.get("matches"):
            return 0.0
        target = drawing_id.upper()
        for m in rag_results["matches"]:
            if m.get("drawing_id", "").upper() == target:
                return m.get("vector_similarity", m.get("similarity", 0.0))
        return 0.0

    def _check_exact_prefix(
        self,
        effective_prefix: Optional[str],
        rag_results: Optional[Dict],
        library_key: Optional[str],
        log_callback,
        prefetched_result: Optional[Dict] = None,
    ) -> tuple[bool, str, Optional[Dict]]:
        """精确图号命中判断。返回 (use_rag_only, prefix_context, exact_result)。"""
        if not effective_prefix:
            return False, "", None

        exact_result = (
            prefetched_result
            if prefetched_result is not None
            else self.query_by_prefix(effective_prefix, top_k=1, library_key=library_key)
        )
        if not exact_result or not exact_result.get("matches"):
            return False, "", None

        matched = exact_result["matches"][0]
        vec_sim = self._get_vector_sim_for_drawing(matched["drawing_id"], rag_results)

        if vec_sim >= 0.75:
            if log_callback:
                log_callback(
                    f"📎 图号精确匹配 + 余弦相似度 {vec_sim:.1%} ≥ 75%，直接采用蓝本工艺（跳过LLM）..."
                )
            return True, "", exact_result

        # 相似度不足 → 构建蓝本候选上下文交给 LLM
        rows = self._normalize_standard_process_rows(matched.get("process_list", []))
        proc_str = "\n".join(
            [f"- {tag}: {content}" if tag else f"- {content}" for tag, content in rows]
        )
        prefix_context = (
            f"## 精确匹配工艺候选 ({matched['drawing_id']}, 共{len(rows)}道工序)\n"
            + proc_str + "\n\n"
        )
        if log_callback:
            log_callback(
                f"📌 命中精确图号（余弦相似度 {vec_sim:.1%} < 70%），提交给LLM进行增删改..."
            )
        return False, prefix_context, exact_result

    def _run_rag_lookup(
        self,
        fused_description: str,
        descriptions: List[Dict[str, Any]],
        prefix_hint: Optional[str],
        log_callback,
        library_key: Optional[str],
    ) -> tuple[Optional[Dict], str, bool, Optional[Dict]]:
        """执行完整 RAG 检索。返回 (rag_results, rag_context, use_rag_only, exact_result)。

        query_by_fused_text 与 query_by_prefix 并发执行，节省串行等待时间。
        """
        if not self.rag_available:
            return None, "", False, None

        try:
            from concurrent.futures import ThreadPoolExecutor

            effective_prefix = self._extract_drawing_prefix(descriptions, prefix_hint)
            logger.info("[RAG] prefix_hint=%s, effective_prefix=%s", prefix_hint, effective_prefix)

            # 并发：向量相似度查询 + 图号精确查询（两者相互独立）
            with ThreadPoolExecutor(max_workers=2) as executor:
                fused_future = executor.submit(
                    self.query_by_fused_text,
                    fused_description,
                    top_k=5,
                    min_similarity=0.20,
                    prefix_hint=effective_prefix,
                    log_callback=log_callback,
                    library_key=library_key,
                )
                prefix_future = (
                    executor.submit(
                        self.query_by_prefix,
                        effective_prefix,
                        top_k=1,
                        library_key=library_key,
                    )
                    if effective_prefix
                    else None
                )
                rag_results = fused_future.result()
                prefetched_prefix = prefix_future.result() if prefix_future else None

            # 非公共库匹配度不足时，补充公共库检索
            if library_key and library_key != "public" and rag_results:
                best_sim = rag_results["matches"][0].get("similarity", 0) if rag_results.get("matches") else 0
                if best_sim < 0.25:
                    public_results = self.query_by_fused_text(
                        fused_description,
                        top_k=5,
                        min_similarity=0.20,
                        prefix_hint=effective_prefix,
                        log_callback=log_callback,
                        library_key="public",
                    )
                    if public_results and public_results.get("matches"):
                        existing_ids = {m.get("drawing_id") for m in rag_results.get("matches", [])}
                        for pm in public_results["matches"]:
                            if pm.get("drawing_id") not in existing_ids:
                                rag_results["matches"].append(pm)
                                existing_ids.add(pm.get("drawing_id"))
                        if log_callback:
                            log_callback("🔍 私有库匹配度不足（<0.3），已补充公共工艺库检索结果")

            use_rag_only, prefix_context, exact_result = self._check_exact_prefix(
                effective_prefix, rag_results, library_key, log_callback,
                prefetched_result=prefetched_prefix,
            )

            merged_rag = self._replace_placeholder_tokens(
                rag_results.get("rag_context", "") if rag_results else ""
            )
            rag_context = (prefix_context + merged_rag) if prefix_context else merged_rag
            rag_context = self._replace_placeholder_tokens(rag_context)

            return rag_results, rag_context, use_rag_only, exact_result

        except Exception as e:
            logger.error("RAG error: %s", e)
            return None, "", False, None

    def _search_with_public_fallback(
        self,
        fused_description: str,
        top_k: int,
        min_similarity: float,
        library_key: Optional[str],
        prefix_hint: Optional[str] = None,
        log_callback=None,
    ):
        """搜索指定库，若结果不足则自动回退公共库补充。"""
        results = self.query_by_vector_similarity(
            fused_description, top_k=top_k, min_similarity=min_similarity,
            prefix_hint=prefix_hint, library_key=library_key,
        ) if self.rag_available else []

        # 非公共库且结果不足时，追加公共库结果
        if library_key and library_key != "public" and self.rag_available:
            best_sim = results[0].get("similarity", 0) if results else 0
            if best_sim < 0.3:
                public_results = self.query_by_vector_similarity(
                    fused_description, top_k=top_k, min_similarity=min_similarity,
                    prefix_hint=prefix_hint, library_key="public",
                )
                existing_ids = {r.get("drawing_id") for r in results}
                for pr in public_results:
                    if pr.get("drawing_id") not in existing_ids:
                        results.append(pr)
                        existing_ids.add(pr.get("drawing_id"))
                if log_callback and any(
                    pr.get("drawing_id") not in {r.get("drawing_id") for r in results[:-len(public_results)]}
                    for pr in public_results
                ):
                    log_callback("🔍 私有库匹配度不足，已补充公共工艺库检索结果")

        return results

    def _nearest_neighbor_fallback(
        self,
        fused_description: str,
        rag_results: Optional[Dict],
        library_key: Optional[str],
        log_callback,
    ) -> tuple[str, Optional[Dict]]:
        """知识库无匹配时取最近邻蓝本，私有库无结果则回退公共库。"""
        if not self.rag_available:
            return "", rag_results
        try:
            nearest = self.query_by_vector_similarity(
                fused_description, top_k=1, min_similarity=0.0, library_key=library_key
            )
            # 私有库无匹配时回退公共库
            if not nearest and library_key and library_key != "public":
                if log_callback:
                    log_callback("🔍 私有工艺库无匹配，回退公共工艺库检索...")
                nearest = self.query_by_vector_similarity(
                    fused_description, top_k=1, min_similarity=0.0, library_key="public"
                )
            if not nearest:
                return "", rag_results

            best = nearest[0]
            rows = self._normalize_standard_process_rows(best.get("process_list", []))
            proc_str = "\n".join(
                [f"- {tag}: {content}" if tag else f"- {content}" for tag, content in rows]
            )
            rag_context = (
                f"## 最近邻参考蓝本 ({best['drawing_id']}, "
                f"相似度 {best.get('similarity', 0):.1%}, 共{len(rows)}道工序)\n"
                f"⚠️ 当前零件不在知识库中，以下工艺仅供参考，需根据实际几何参数增删改。\n"
                + proc_str + "\n\n"
            )
            if rag_results is None:
                rag_results = {"matches": [best]}
            if log_callback:
                log_callback(
                    f"🔍 知识库无可用工艺蓝本（图号已入库但无工艺数据，或未入库），"
                    f"取最近邻 {best['drawing_id']} "
                    f"（相似度 {best.get('similarity', 0):.1%}）作为参考蓝本..."
                )
            return rag_context, rag_results

        except Exception as e:
            logger.warning("[ProcessGenerator] nearest-neighbor fallback error: %s", e)
            return "", rag_results

    @staticmethod
    def _extract_process_section(raw_text: str) -> str:
        """从 LLM 输出中裁剪出工艺规程段落。"""
        if "## 生成的工艺规程" not in raw_text:
            return raw_text
        parts = raw_text.split("## 生成的工艺规程")
        return parts[-1].strip() if len(parts) > 1 else raw_text

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
                # Avoid flushing mid-（工种：xxx） pattern — only flush when
                # the marker is complete (closing ） present) or on newline.
                _trade_ok = True
                _trade_open = re.search(r'[（(]工种(?:[：:]\s*[一-鿿\-\w]*)?$', buffered_for_log)
                _trade_closed = re.search(r'[（(]工种[：:]\s*[一-鿿\-\w]+\s*[）)]', buffered_for_log)
                if _trade_open and not _trade_closed:
                    _trade_ok = False
                if log_callback and (len(buffered_for_log) >= 80 or "\n" in delta) and _trade_ok:
                    log_callback(buffered_for_log)
                    buffered_for_log = ""
                    time.sleep(0.01)

            if buffered_for_log and log_callback:
                log_callback(buffered_for_log)

            final_text = "".join(chunks)
            if final_text.strip():
                return final_text
        except Exception as e:
            logger.warning("[ProcessGenerator] streaming failed, fallback to invoke: %s", e)

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
            # 按行切分，每行间隔 50ms，保证前端打字机有足够时间响应
            for line in final_text.split("\n"):
                stream_callback(line + "\n")
                time.sleep(0.05)

        return final_text

    @staticmethod
    def _parse_structural_dims(text: str):
        """Extract (thickness_mm, area_mm2) from feature description.

        Supports:
          - ≠T×L×W  (备料 notation)
          - 厚: T  +  长: L 宽: W  (field notation)
        Returns (None, None) when not enough information is found.
        """
        thickness = length = width = None

        # ≠T×L×W pattern
        m = re.search(
            r'[≠δ]\s*(\d+(?:\.\d+)?)\s*[×xX×]\s*(\d+(?:\.\d+)?)\s*[×xX×]\s*(\d+(?:\.\d+)?)',
            text,
        )
        if m:
            thickness = float(m.group(1))
            d2, d3 = float(m.group(2)), float(m.group(3))
            length, width = max(d2, d3), min(d2, d3)

        if thickness is None:
            m = re.search(r'厚(?:度)?\s*[:：]\s*(\d+(?:\.\d+)?)', text)
            if m:
                thickness = float(m.group(1))

        if length is None:
            ml = re.search(r'长\s*[:：]\s*(\d+(?:\.\d+)?)', text)
            mw = re.search(r'宽\s*[:：]\s*(\d+(?:\.\d+)?)', text)
            if ml and mw:
                length = float(ml.group(1))
                width = float(mw.group(1))

        area = length * width if (length is not None and width is not None) else None
        return thickness, area

    @staticmethod
    def _extract_key_geo_fields(feature_text: str) -> str:
        """Extract key geometry fields from feature text for prompt injection."""
        target_fields = {"尺寸", "形状分类", "孔特征", "体积", "总面积"}
        found = {}
        for m in re.finditer(r'【([^】]+)】([^\n【]*)', feature_text):
            name, val = m.group(1).strip(), m.group(2).strip()
            if name in target_fields and val:
                found[name] = val
        if not found:
            return ""
        parts = []
        for key in ["尺寸", "形状分类", "孔特征", "体积", "总面积"]:
            if key in found:
                parts.append(f"{key}: {found[key]}")
        return " | ".join(parts)

    # ── Constraint Assembly ─────────────────────────────────────────────────

    def _extract_process_constraints(self, feature_text: str, geo_data=None) -> dict:
        """从审阅特征文本中提取结构化约束。

        解析【】字段，分为硬约束（不可被历史覆盖）和软特征（低相似度可受控补充）。

        Returns:
            {
                "hard_constraints": {
                    "blank_size": "...",   # 毛坯尺寸
                    "outer_size": "...",   # 外形尺寸
                    "key_dims": "..."      # 关键尺寸
                },
                "soft_features": {
                    "roughness": "...",         # 粗糙度
                    "chamfer": "...",           # 倒角
                    "fillet": "...",            # 圆角/过渡特征
                    "surface_treatment": "...", # 表面处理
                    "holes_threads": "..."      # 孔/螺纹规格
                }
            }
        """
        fields = {}
        for m in re.finditer(r'【([^】]+)】([^\n【]*)', feature_text):
            fields[m.group(1).strip()] = m.group(2).strip()

        hard = {"blank_size": "", "outer_size": "", "key_dims": "", "part_count": 1, "material_form": "",
                "heat_treatment": "", "surface_treatment": "",
                "is_cavity_part": False, "is_aluminum_alloy": False, "is_large_part": False,
                "cavity_depth_hint": ""}
        soft = {"roughness": "", "chamfer": "", "fillet": "", "surface_treatment": "", "holes_threads": ""}

        # ── 硬约束 ──
        hard["material_form"] = self._extract_material_form(feature_text)
        hard["heat_treatment"] = fields.get("热处理与探伤", "")
        hard["surface_treatment"] = fields.get("表面处理与镀层特征", "")
        hard["key_dims"] = fields.get("关键尺寸", "")

        # 外形尺寸：优先【外形尺寸】/【主要外形尺寸】，其次【关键尺寸】
        outer = fields.get("外形尺寸", "") or fields.get("主要外形尺寸", "") or ""
        if not outer or outer == "无":
            outer = fields.get("关键尺寸", "")
        hard["outer_size"] = outer if outer and outer != "无" else ""

        # 毛坯尺寸：从所有字段中搜索 δ/δ/板材/毛坯 等模式
        blank_candidates = []
        for name, val in fields.items():
            if val and re.search(r'[δδ﹩$]\s*\d+', val):
                blank_candidates.append(val)
            if val and re.search(r'(?:毛坯|板材|棒材|型材)', val):
                blank_candidates.append(val)
        hard["blank_size"] = "；".join(dict.fromkeys(blank_candidates)) if blank_candidates else ""

        # ── 软特征 ──
        tech_req = fields.get("技术要求", "")
        quantity_sources = [
            tech_req,
            fields.get("其他特征", ""),
        ]
        for src in quantity_sources:
            if not src:
                continue
            m = re.search(r'(?:^|[；;。\.\n,，])\s*数量\s*[:：]?\s*(\d+)(?=$|[；;。\.\n,，])', src)
            if m:
                hard["part_count"] = int(m.group(1))
                break
        soft["roughness"] = self._extract_roughness(tech_req) if tech_req else ""
        soft["chamfer"] = fields.get("倒角", "")
        fillet_val = fields.get("过渡特征", "")
        soft["fillet"] = fillet_val if fillet_val and fillet_val != "无" else ""
        soft["surface_treatment"] = self._extract_surface_treatment(tech_req) if tech_req else ""

        # 孔/螺纹：合并【螺纹与螺孔】和【外圆与内孔】中的孔信息
        holes_parts = []
        thread_val = fields.get("螺纹与螺孔", "")
        if thread_val and thread_val != "无":
            holes_parts.append(thread_val)
        bore_val = fields.get("外圆与内孔", "")
        if bore_val and bore_val != "无":
            inner_parts = [p for p in re.split(r'[；;]', bore_val) if re.search(r'孔|内', p)]
            holes_parts.extend(inner_parts)
        soft["holes_threads"] = "；".join(dict.fromkeys(holes_parts)) if holes_parts else ""

        # ── 几何硬约束 ──
        hard["geo_blank_spec"] = ""
        hard["geo_hole_count"] = 0
        hard["geo_bore_range"] = ""

        part_count = hard.get("part_count", 1) or 1

        # ① 优先：Creo zhushi.txt 原始尺寸（最精确，按 D1+10/D2+10/floor(D3/10)*10+10 规则）
        blank = self._derive_blank_from_creo_zhushi(fields, part_count, geo_data)
        skip_ceil = bool(blank)

        # ② 次选：Creo 显式外形尺寸标注 (外形尺寸：a=169,b=244,c=36 等)
        if not blank:
            blank = self._derive_blank_from_creo_fields(fields, part_count)

        # ③ 次次选：STEP 几何推导 + Creo 标注值校准
        if not blank and geo_data and "error" not in geo_data:
            try:
                from .geometry_analyzer import derive_blank_spec
            except ImportError:
                try:
                    from backend.pipeline.geometry_analyzer import derive_blank_spec
                except ImportError:
                    from pipeline.geometry_analyzer import derive_blank_spec

            blank = derive_blank_spec(geo_data)
            if blank:
                blank = self._calibrate_blank_with_creo(blank, fields)

        if blank:
            blank = re.sub(r'=\d+$', f'={part_count}', blank)
            if not skip_ceil:
                blank = self._ceil_blank_dims(blank)
            hard["geo_blank_spec"] = blank

            # material_form 强制修正：若 Creo 推导的毛坯规格含 ≠/δ 符号，无视 VLM 结果
            if re.search(r'[≠δ]\s*\d+', blank):
                hard["material_form"] = "板料"

        # 孔信息始终来自几何分析（Creo 没有等效数据）
        if geo_data and "error" not in geo_data:
            hole_info = geo_data.get("hole_info", {})
            if hole_info:
                count = hole_info.get("count", 0)
                min_d = hole_info.get("min_diameter", 0)
                max_d = hole_info.get("max_diameter", 0)
                if count:
                    hard["geo_hole_count"] = count
                if min_d and max_d:
                    hard["geo_bore_range"] = f"{min_d}~{max_d}mm"

        # ── 吊面/翻面约束（硬约束：有吊面必须生成翻面工序）──
        flip_face_val = fields.get("吊面/翻面特征", "") or ""
        if flip_face_val in ("无", "无。", ""):
            flip_face_val = ""
        # 兜底：从【其他特征】文本中检测翻面/吊面关键词
        if not flip_face_val:
            _other = fields.get("其他特征", "") or ""
            if re.search(r'吊面|翻面|背面加工|反面特征', _other):
                flip_face_val = f"存在（来自其他特征：{_other[:60]}）"
        # 从技术要求中检测
        if not flip_face_val:
            for _note in (fields.get("技术要求", "") or "").split("；"):
                if re.search(r'翻面|吊面|反面|背面', _note):
                    flip_face_val = f"存在（来自技术要求：{_note.strip()[:60]}）"
                    break
        hard["flip_face"] = flip_face_val

        # ── 腔体件 / 铝合金 / 大尺寸检测 ──
        _shape_val  = (fields.get("形态", "") or "") + (fields.get("类型", "") or "")
        _other_val  = fields.get("其他特征", "") or ""
        _tech_val   = fields.get("技术要求", "") or ""
        _all_text   = feature_text  # 全文兜底
        _cavity_kw  = ["腔体", "内腔", "腔室", "深腔", "型腔", "腔内", "空腔"]
        hard["is_cavity_part"] = any(kw in _all_text for kw in _cavity_kw)

        _al_pattern = r'铝合金|铝板|Al\b|5A\d+|6061|6063|7075|2A\d+|LY\d+|LD\d+|LC\d+'
        hard["is_aluminum_alloy"] = bool(re.search(_al_pattern, _all_text, re.I))

        _outer_nums = [float(n) for n in re.findall(r'\d+(?:\.\d+)?', hard.get("outer_size", "") or "")
                       if float(n) >= 10]
        hard["is_large_part"] = bool(_outer_nums and max(_outer_nums) >= 500)

        # 腔体深度粗估：从关键尺寸中找最小值作为可能的腔体深度参考
        if hard["is_cavity_part"]:
            _key_nums = [float(n) for n in re.findall(r'\d+(?:\.\d+)?', hard.get("key_dims", "") or "")
                         if 5 <= float(n) <= 100]
            if _key_nums:
                hard["cavity_depth_hint"] = f"关键尺寸中含可能的腔深参考值：{min(_key_nums):.0f}~{max(_key_nums):.0f}mm"

        # ── 特征字段（传递给 post-check 用于一致性对比）──
        feature_fields = {}
        for _k in ("螺纹孔", "通孔", "沉孔沉槽", "特殊孔",
                    "刻字", "尺寸公差", "形位公差", "螺纹与螺孔",
                    "外圆与内孔", "技术要求", "表面粗糙度"):
            _v = fields.get(_k, "")
            if _v and _v != "无":
                feature_fields[_k] = _v

        return {"hard_constraints": hard, "soft_features": soft, "feature_fields": feature_fields}

    @staticmethod
    def _extract_roughness(text: str) -> str:
        """从技术要求文本中提取粗糙度信息。"""
        patterns = [
            r'Ra\s*\d+\.?\d*',
            r'Rz\s*\d+\.?\d*',
            r'粗糙度[：:]\s*\S+',
            r'表面粗糙度[：:]\s*\S+',
        ]
        found = []
        for p in patterns:
            for m in re.finditer(p, text):
                found.append(m.group(0))
        return "；".join(dict.fromkeys(found)) if found else ""

    @staticmethod
    def _extract_surface_treatment(text: str) -> str:
        """从技术要求文本中提取表面处理信息。"""
        patterns = [
            r'(?:阳极化|氧化|镀[^；;。]*|涂覆|喷涂|发蓝|磷化|钝化|电泳|喷丸|喷砂)(?:[^。；;]*)?',
        ]
        found = []
        for p in patterns:
            for m in re.finditer(p, text):
                found.append(m.group(0).strip())
        return "；".join(dict.fromkeys(found)) if found else ""

    @staticmethod
    def _extract_material_form(feature_text: str) -> str:
        """从特征报告提取【物料形态】字段；无该字段或为"其他"时降级推断。"""
        declared = ""
        m = re.search(r'【物料形态】([^\n【]*)', feature_text)
        if m:
            declared = m.group(1).strip()
        # 有明确非"其他"值时直接返回
        if declared and declared not in ("无", "其他"):
            return declared

        # 降级推断1：≠ 符号
        if re.search(r'[≠δ]\s*\d+', feature_text):
            return "板料"
        # 降级推断2：外形尺寸几何比例 — 最小维度 < 最大维度的 30% 视为薄板
        outer_m = re.search(r'【外形尺寸】([^\n【]*)', feature_text)
        if outer_m:
            nums = re.findall(r'\d+(?:\.\d+)?', outer_m.group(1))
            if len(nums) >= 3:
                vals = sorted([float(n) for n in nums[:3]])
                # vals[0]=最小, vals[2]=最大
                if vals[2] > 0 and vals[0] / vals[2] < 0.30:
                    return "板料"
        # 降级推断3：圆棒格式
        if re.search(r'φ\s*\d+\s*[×x]\s*\d', feature_text):
            return "棒料（圆）"
        return declared or ""

    @staticmethod
    def _infer_blueprint_material_form(rag_context: str) -> str:
        """从蓝本工艺文本推断物料形态（用于不匹配检测）。"""
        if not rag_context:
            return ""
        if re.search(r'[≠δ]\s*\d+|铣四边', rag_context):
            return "板料"
        if re.search(r'φ\s*\d+\s*[×x]\s*\d', rag_context):
            return "棒料（圆）"
        if re.search(r'铣六面', rag_context):
            # 铣六面通常对应方棒或块体
            return "棒料（方）"
        return ""

    @staticmethod
    def _derive_blank_from_creo_fields(fields: dict, part_count: int = 1) -> str:
        """从 Creo 显式外形标注推导毛坯规格。

        仅解析 Creo CAD 坐标系的 a/b/c 标注格式：
        - 外形尺寸：a=169,b=244,c=36
        - 主要外形尺寸：a=169,b=244,c=36

        规则：三个值中最小值→厚度(向上取整)，其余两项各+5→长宽(向上取整)。
        不处理 VLM 语义描述的 长/宽/高（取决于截图视角，不可靠）。
        如果 fields 中无匹配的显式外形标注，返回空字符串。
        """
        import math

        # 收集候选文本
        parts = []
        for field_name in ("外形尺寸", "主要外形尺寸", "关键尺寸", "尺寸"):
            val = fields.get(field_name, "")
            if val and val != "无":
                parts.append(val)
        if not parts:
            return ""
        combined = "；".join(parts)

        # 模式1: a=169,b=244,c=36（大小写，有无空格）
        a_vals = re.findall(r"\b[aA]\s*=\s*(\d+(?:\.\d+)?)", combined)
        b_vals = re.findall(r"\b[bB]\s*=\s*(\d+(?:\.\d+)?)", combined)
        c_vals = re.findall(r"\b[cC]\s*=\s*(\d+(?:\.\d+)?)", combined)

        if a_vals and b_vals and c_vals:
            dims = [float(a_vals[0]), float(b_vals[0]), float(c_vals[0])]
            dims.sort()
            thickness = math.ceil(dims[0])
            length = math.ceil(dims[2] + 5)
            width = math.ceil(dims[1] + 5)
            return f"δ{thickness}×{length}×{width}={part_count}"

        return ""

    @staticmethod
    def _derive_blank_from_creo_zhushi(
        fields: dict, part_count: int = 1, geo_data=None
    ) -> str:
        """从特征字段按制造余量规则推导板类毛坯规格。

        规则：
          D1（最大）→ D1 + 10，保留个位
          D2（次大）→ D2 + 10，保留个位
          D3（厚度/最小）→ floor(D3/10)×10 + 10（取当前整十档再加10）

        维度识别优先级：
          ① 综合尺寸 推断:T×L×H（OCC+VLM 联合推断，含图纸修正，最准）
          ② OCC 主外形摘要「长×宽×高」（无 VLM 修正时的回退）
          ③ OCC bounding box 锚定 Creo 原始标注值
          ④ 取 top-2 大值 + 全局最小值兜底
        """
        import math

        def _blank_from_lwh(L: float, W: float, H: float) -> str:
            """Apply blank rules to three known body dimensions."""
            dims = sorted([L, W, H])          # [min, mid, max]
            D3, D2, D1 = dims[0], dims[1], dims[2]
            D3_b = math.floor(D3 / 10) * 10 + 10  # 取当前整十档再加10
            # 厚度向上取整：若加值(D3_b - D3) < 6.0，多上一档(+5)
            _gap = D3_b - D3
            if _gap > 0 and _gap < 6.0:
                D3_b += 5
            D1_b = D1 + 10
            D2_b = D2 + 10
            def _f(v): return str(int(v)) if v == int(v) else str(round(v, 1))
            return f"δ{_f(D3_b)}×{_f(D1_b)}×{_f(D2_b)}={part_count}"

        # ── ① 优先：综合尺寸 推断:T×L×H（OCC+VLM 联合推断，含 VLM 图纸修正，最准）──
        _combined = fields.get("综合尺寸", "")
        if _combined:
            _pm = re.search(r'推断:T([\d.]+)×L([\d.]+)×H([\d.]+)', _combined)
            if _pm:
                T_inf = float(_pm.group(1))
                L_inf = float(_pm.group(2))
                H_inf = float(_pm.group(3))
                if T_inf > 0 and L_inf > 0 and H_inf > 0:
                    # Blank T must accommodate the full OCC bounding box (not just the
                    # VLM-corrected plate face). Use max(T_inf, OCC_T) so stock fits all
                    # depth features (e.g. T_inf=18.7, OCC_T=24.5 → D3=24.5 → δ30).
                    D3_for_blank = T_inf
                    # Primary: parse OCC dims from "几何:长X×宽Y×高Z" in _combined
                    # (always present alongside 推断, works without FreeCAD/geo_data)
                    _geo_m = re.search(r'几何[：:]长([\d.]+)×宽([\d.]+)×高([\d.]+)', _combined)
                    if _geo_m:
                        occ_vals = sorted([float(_geo_m.group(1)), float(_geo_m.group(2)), float(_geo_m.group(3))])
                        D3_for_blank = max(T_inf, occ_vals[0])
                    elif geo_data and "error" not in geo_data:
                        occ_d = geo_data.get("dimensions", {})
                        occ_vals = sorted(
                            [v for v in [occ_d.get("x", 0), occ_d.get("y", 0), occ_d.get("z", 0)] if v > 0]
                        )
                        if occ_vals:
                            D3_for_blank = max(T_inf, occ_vals[0])  # occ_vals[0] = OCC_T (smallest)
                    return _blank_from_lwh(D3_for_blank, L_inf, H_inf)

        # ── ② 次选：「长×宽×高」OCC 主外形摘要（无 VLM 修正时的回退）──
        # VLM 在【关键尺寸】末尾附加 "长 240.0mm × 宽 163.0mm × 高 24.5mm"
        for _fk in ("关键尺寸", "主要外形尺寸", "外形尺寸"):
            _fv = fields.get(_fk, "")
            if not _fv:
                continue
            _m = re.search(
                r'长\s*([\d.]+)\s*mm\s*[×x]\s*宽\s*([\d.]+)\s*mm\s*[×x]\s*高\s*([\d.]+)\s*mm',
                _fv,
            )
            if _m:
                L, W, H = float(_m.group(1)), float(_m.group(2)), float(_m.group(3))
                if L > 0 and W > 0 and H > 0:
                    return _blank_from_lwh(L, W, H)

        creo_raw = fields.get("Creo原始尺寸", "")
        if not creo_raw or creo_raw == "无":
            return ""

        nums = sorted(
            {float(n) for n in re.findall(r"\d+(?:\.\d+)?", creo_raw) if float(n) > 5},
            reverse=True,
        )
        if len(nums) < 2:
            return ""

        def _pick_occ_anchored(nums, geo_data):
            """Use OCC bounding box (x/y/z) to identify the best-matching 3 zhushi dims.

            OCC tends to overestimate because its bounding box includes protrusions.
            For each axis, prefer the smallest zhushi value within [OCC*0.85, OCC] —
            that candidate is more likely the true body dimension (e.g. 163 preferred
            over 176 when OCC=176 and 163 is also annotated on the drawing).
            Falls back to nearest-match when no candidate falls in the tolerance band.
            """
            if not geo_data or "error" in geo_data:
                return None
            d = geo_data.get("dimensions", {})
            occ_vals = [d.get("x", 0), d.get("y", 0), d.get("z", 0)]
            occ_sorted = sorted([v for v in occ_vals if v > 0], reverse=True)
            if len(occ_sorted) < 3:
                return None
            remaining = list(nums)
            picked = []
            for occ_d in occ_sorted:
                if not remaining:
                    break
                in_range = [x for x in remaining if occ_d * 0.85 <= x <= occ_d]
                chosen = min(in_range) if in_range else min(remaining, key=lambda x: abs(x - occ_d))
                picked.append(chosen)
                remaining.remove(chosen)
            return sorted(picked, reverse=True) if len(picked) == 3 else None

        dims = _pick_occ_anchored(nums, geo_data)

        if dims is None:
            # Fallback: top-2 large (>50mm, main outer dims) + global minimum (thickness)
            large = [n for n in nums if n > 50]
            if len(large) >= 2:
                dims = sorted([large[0], large[1], nums[-1]], reverse=True)
            elif len(nums) >= 3:
                dims = [nums[0], nums[1], nums[-1]]
            else:
                return ""

        D1, D2, D3 = dims[0], dims[1], dims[2]
        D1_b = D1 + 10
        D2_b = D2 + 10
        D3_b = math.floor(D3 / 10) * 10 + 10  # 取当前整十档再加10
        _gap = D3_b - D3
        if _gap > 0 and _gap < 6.0:
            D3_b += 5

        def _f(v):
            return str(int(v)) if v == int(v) else str(round(v, 1))

        if geo_data and not geo_data.get("error"):
            shape = geo_data.get("shape_class", "")
            faces = geo_data.get("faces", [])
            radii = [
                f.get("params", {}).get("radius", 0)
                for f in faces
                if f.get("type_name") == "Cylinder"
            ]
            max_r = max(radii, default=0)
            if shape == "轴类" and max_r > 0:
                D_cyl = math.ceil((max_r * 2 + 10) / 10) * 10
                return f"φ{_f(D_cyl)}×{_f(D1_b)}={part_count}"
            if shape == "盘类" and max_r > 0:
                D_cyl = math.ceil((max_r * 2 + 10) / 10) * 10
                D3_b_disk = math.ceil((D3 + 10) / 5) * 5
                return f"φ{_f(D_cyl)}×{_f(D3_b_disk)}={part_count}"

        return f"δ{_f(D3_b)}×{_f(D1_b)}×{_f(D2_b)}={part_count}"

    @staticmethod
    def _ceil_blank_dims(blank_spec: str) -> str:
        """对 blank spec 中所有尺寸值向上取整到十位（个位变 0，十位进一）。

        制造惯例：毛坯余量以 10mm 为单位向上取整。
        δ16.2×233×161.4=5 → δ20×240×170=5
        φ79.5×318.7=1 → φ80×320=1
        """
        import math

        if not blank_spec:
            return blank_spec

        body = re.sub(r"=\d+$", "", blank_spec)
        dims = re.findall(r"(\d+(?:\.\d+)?)", body)
        if not dims:
            return blank_spec

        result = blank_spec
        for dim_str in dims:
            v = float(dim_str)
            ceiled = math.ceil(v / 10) * 10
            if ceiled != v:
                ceiled_str = str(ceiled)
                result = result.replace(dim_str, ceiled_str, 1)

        return result

    @staticmethod
    def _calibrate_blank_with_creo(blank_spec: str, fields: dict) -> str:
        """用 Creo TXT 标注尺寸校准 STEP 推导的毛坯规格。

        对 blank_spec 中每个维度（δ16.2×233×161.4），
        在 Creo 标注尺寸中找到容差 <1% 的值时，用 Creo 值替换。
        Creo 标注来自 fields 中的关键尺寸/主要外形尺寸/特征尺寸。
        """
        if not blank_spec or not fields:
            return blank_spec

        # 收集 Creo 候选值：优先含"×"或"mm"的尺寸字段
        creo_candidates = []
        for field_name in ("关键尺寸", "主要外形尺寸", "特征尺寸", "尺寸"):
            val = fields.get(field_name, "")
            if val and val != "无":
                nums = re.findall(r"(\d+(?:\.\d+)?)", val)
                for n in nums:
                    try:
                        f = float(n)
                        if f > 2.0 and f < 10000:
                            creo_candidates.append(f)
                    except ValueError:
                        pass

        # 也拉取所有字段中含×尺寸模式的值
        for _name, val in fields.items():
            if val and val != "无" and re.search(r"\d+\s*[×xX\*]\s*\d+", val):
                nums = re.findall(r"(\d+(?:\.\d+)?)", val)
                for n in nums:
                    try:
                        f = float(n)
                        if f > 2.0 and f < 10000:
                            creo_candidates.append(f)
                    except ValueError:
                        pass

        if not creo_candidates:
            return blank_spec

        creo_candidates = sorted(set(creo_candidates))

        # 解析 blank spec 里的维度值（去掉前缀符号和 =数量 后缀）
        body = re.sub(r"=\d+$", "", blank_spec)
        raw_dims = re.findall(r"(\d+(?:\.\d+)?)", body)
        if not raw_dims:
            return blank_spec

        result = blank_spec
        for dim_str in raw_dims:
            dim_val = float(dim_str)
            best_match = None
            best_diff = float("inf")
            for candidate in creo_candidates:
                if dim_val > 0 and abs(candidate - dim_val) / dim_val < 0.01:
                    diff = abs(candidate - dim_val)
                    if diff < best_diff:
                        best_diff = diff
                        best_match = candidate
            if best_match is not None and abs(best_match - dim_val) > 0.001:
                # 保持原始的小数位精度
                if "." in dim_str:
                    creo_str = f"{best_match:.3f}".rstrip("0").rstrip(".")
                else:
                    creo_str = str(int(best_match)) if best_match == int(best_match) else str(best_match)
                result = result.replace(dim_str, creo_str, 1)

        return result

    @staticmethod
    def _should_use_blueprint_as_base(exact_match: bool, similarity: float) -> bool:
        """判断蓝本是否可作为主流程框架。

        规则：
        - 精确图号匹配 + 相似度 >= 0.70 → 蓝本可作为主框架
        - 其他情况 → 蓝本仅做流程参考，不得覆盖当前事实
        """
        if not exact_match:
            return False
        return similarity >= 0.70

    @staticmethod
    def _extract_allowed_feature_fragments(rag_context: str, review_constraints: dict) -> dict:
        """从历史候选中提取允许补充的局部特征。

        仅当低相似度（图号不匹配或<80%）时调用。
        只返回当前审阅特征未明确给出的受控字段。

        Returns:
            {"roughness": "Ra3.2", "chamfer": "锐边倒钝", "fillet": "R0.5",
             "surface_treatment": "导电阳极化", "holes_threads": "M3 深6"}
        """
        soft = review_constraints.get("soft_features", {}) if review_constraints else {}
        allowed = {"roughness": "", "chamfer": "", "fillet": "", "surface_treatment": "", "holes_threads": ""}

        if not rag_context:
            return allowed

        # 对于每个受控字段，检查当前特征是否已给出明确值
        # 若未给出，从 RAG context 中提取

        # 粗糙度
        if not soft.get("roughness"):
            ra_match = re.search(r'Ra\s*\d+\.?\d*', rag_context, re.IGNORECASE)
            if ra_match:
                allowed["roughness"] = ra_match.group(0)

        # 倒角
        if not soft.get("chamfer") or soft["chamfer"] == "无":
            cham_matches = re.findall(r'(?:倒角|C\d+|锐边倒钝|去毛刺)', rag_context)
            if cham_matches:
                allowed["chamfer"] = "；".join(dict.fromkeys(cham_matches))[:100]

        # 圆角
        if not soft.get("fillet") or soft["fillet"] == "无":
            fillet_matches = re.findall(r'R\d+\.?\d*', rag_context)
            if fillet_matches:
                allowed["fillet"] = "；".join(dict.fromkeys(fillet_matches))[:100]

        # 表面处理
        if not soft.get("surface_treatment"):
            st_matches = re.findall(r'(?:阳极化|氧化|镀[^；;。]*|涂覆|喷涂|发蓝|磷化|钝化|电泳|喷丸|喷砂)', rag_context)
            if st_matches:
                allowed["surface_treatment"] = "；".join(dict.fromkeys(st_matches))[:100]

        # 孔/螺纹
        if not soft.get("holes_threads"):
            ht_matches = re.findall(r'M\d+\s*(?:深\s*\d+)?', rag_context)
            hole_matches = re.findall(r'(?:孔\s*|孔径)\s*\d+\.?\d*', rag_context)
            all_matches = ht_matches + hole_matches
            if all_matches:
                allowed["holes_threads"] = "；".join(dict.fromkeys(all_matches))[:150]

        return allowed

    # ── Post-check ──────────────────────────────────────────────────────────

    @staticmethod
    def _extract_lwh_mm(text: str) -> tuple[float, float, float] | None:
        """Extract 长/宽/厚 in mm from key_dims text. Returns (length, width, thickness) or None."""
        if not text:
            return None
        nums = re.findall(r'(\d+(?:\.\d+)?)', str(text))
        if len(nums) < 3:
            return None
        vals = [float(n) for n in nums[:3]]
        thickness = min(vals)
        large = sorted([v for v in vals if v != thickness], reverse=True)
        if len(large) >= 2:
            return (large[0], large[1], thickness)
        return None

    @staticmethod
    def _build_mill_blank_instruction(
        feature_text: str,
        authoritative_blank: str,
        rag_context: str = "",
    ) -> str:
        """Build 备料/铣方/铣外形 dimension instruction.

        备料 → 使用现有 authoritative_blank
        铣方 → 备料三个方向各 -5mm，始终带 ±0.1 公差；
               厚度减后 <20 则取备料原厚度（不减）
        铣外形 → 取 推断:T×L×H 中的 T/L/W；L/W 追加蓝本轮廓公差 ±tol（T 不追加）
        """
        if not authoritative_blank:
            return ""

        fields = {}
        for m in re.finditer(r'【([^】]+)】([^\n【]*)', feature_text):
            fields[m.group(1).strip()] = m.group(2).strip()

        _f = ProcessGenerator._fmt_dim

        # ── 解析备料规格，得到 T_b/L_b/W_b ──
        body = re.sub(r'=\d+$', '', authoritative_blank)
        blank_nums = sorted(
            [float(n) for n in re.findall(r'\d+(?:\.\d+)?', body)],
            reverse=True,
        )
        if len(blank_nums) >= 3:
            L_b, W_b, T_b = blank_nums[0], blank_nums[1], blank_nums[2]
            T_mill_raw = T_b - 5
            T_mill = T_b if T_mill_raw < 20 else T_mill_raw  # 厚度 <20 时不减
            L_mill = L_b - 5
            W_mill = W_b - 5

            # 铣方始终带 ±0.1 公差
            def _dim(v: float) -> str:
                return f"{_f(v)}±0.1"

            mill_target = f"{_dim(T_mill)}×{_dim(L_mill)}×{_dim(W_mill)}"
        else:
            mill_target = "（备料规格解析失败，以审阅特征为准）"

        # ── 铣外形尺寸：来自 综合尺寸 推断:T×L×H ──
        outline_target = ""
        _combined = fields.get("综合尺寸", "")
        _pm = re.search(r'推断:T([\d.]+)×L([\d.]+)×H([\d.]+)', _combined) if _combined else None
        if _pm:
            T_out = float(_pm.group(1))
            L_out = float(_pm.group(2))
            W_out = float(_pm.group(3))
            # 轮廓外形公差来自蓝本 rag_context
            outline_tol = None
            if rag_context:
                _tm = re.search(
                    r'(?:最大轮廓外形尺寸公差|外形尺寸公差)\s*按\s*[±±]\s*([\d.]+)',
                    rag_context,
                )
                if _tm:
                    outline_tol = float(_tm.group(1))
            if outline_tol is not None:
                outline_target = (
                    f"{_f(T_out)}×{_f(L_out)}±{_f(outline_tol)}×{_f(W_out)}±{_f(outline_tol)}"
                )
            else:
                outline_target = f"{_f(T_out)}×{_f(L_out)}×{_f(W_out)}"

        outline_section = (
            f"\n- 铣外形目标尺寸：{outline_target}"
            "\n- 铣外形 = 推断T/L/H 原值；L/W 按蓝本轮廓公差加 ±tol 标注，T 不加"
        ) if outline_target else ""

        return f"""
## 备料/铣方尺寸规则
- 0010 备料毛坯规格：{authoritative_blank}（Creo规则：大面+10mm、厚度取当前整十档+10）
- 铣方目标尺寸：{mill_target}
- 铣方 = 备料各 -5mm，始终带 ±0.1 公差；厚度 <20 则不减
- 若蓝本备料/铣方尺寸与此不一致，必须替换为当前计算值{outline_section}
"""

    @staticmethod
    def _merge_same_prefix_subitems(text: str) -> str:
        """Merge consecutive numbered sub-items sharing the same 按X， prefix.

        Rules:
        - Consecutive run of 2+ items with the same 按X，prefix → merged into one item
        - A different prefix (or no prefix) breaks the run; each run is independent
        - Single-item runs are never merged
        - Non-numbered lines pass through unchanged
        - The merged block is renumbered from 1）
        """
        lines = text.split('\n')
        item_re = re.compile(r'^(\s*)\d+[）)]\s*(.+)$')

        def get_prefix(content: str) -> str:
            m = re.match(r'^(按[^，]*[，])', content)
            return m.group(1) if m else ''

        result_lines: list = []
        buffer: list = []  # list of (indent, content)

        def flush() -> list:
            if not buffer:
                return []
            prefixes = [get_prefix(c) for _, c in buffer]
            merged: list = []
            i = 0
            while i < len(buffer):
                _, content = buffer[i]
                prefix = prefixes[i]
                j = i + 1
                while j < len(buffer) and prefixes[j] == prefix and prefix:
                    j += 1
                if j - i >= 2:
                    ops = [buffer[k][1][len(prefix):].rstrip('；;') for k in range(i, j)]
                    merged.append(f"{prefix}{'；'.join(ops)}；")
                else:
                    merged.append(content)
                i = j
            indent = buffer[0][0]
            return [f"{indent}{idx}）{item}" for idx, item in enumerate(merged, 1)]

        for line in lines:
            m = item_re.match(line)
            if m:
                buffer.append((m.group(1), m.group(2)))
            else:
                result_lines.extend(flush())
                buffer = []
                result_lines.append(line)

        result_lines.extend(flush())
        return '\n'.join(result_lines)

    @staticmethod
    def _restore_inspection_numbering(text: str) -> str:
        """Restore 1）2）numbering in inspection step when LLM merges them on one line.

        Matches: 目视检查...；检验，标识，入库 (same line, no existing 1）)
        Result:  1）目视检查...；\\n2）检验，标识，入库
        Preserves step prefix on split lines so trade suffix stays attached.
        """
        return re.sub(
            r'^(.*?)(?:1）)?(目视检查[^；\n]*[；;])\s*(检验，标识，入库[^\n]*)',
            r'\g<1>1）\g<2>\n\g<1>2）\g<3>',
            text,
            flags=re.MULTILINE,
        )

    @staticmethod
    def _fmt_dim(v: float) -> str:
        return str(int(v)) if v % 1 == 0 else str(round(v, 1))

    @staticmethod
    def _extract_dim_pattern(text: str) -> str:
        """提取尺寸模式如 30×380×376.5，用于冲突比较。"""
        m = re.search(r'(?:[δδ])?\s*\d+(?:\.\d+)?\s*[×xX\*]\s*\d+(?:\.\d+)?(?:\s*[×xX\*]\s*\d+(?:\.\d+)?)?', text)
        return m.group(0).strip() if m else ""

    def _post_check_process(self, process_raw: str, constraints: dict) -> str:
        """对生成的工艺进行约束校验和几何数据覆盖。

        四类校验：
          ① 备料规格 (0010行): geo_blank_spec > blank_size
          ② 孔数量: 用 geo_hole_count 覆盖 N×φ/M 模式中的 N
          ③ 孔径范围: 超出 geo_bore_range ±1mm 时追加 ⚠ 标记
          ④ 检验末步：恢复 1）2）条目序号
          ⑤ 连续相同前缀子条目合并
        """
        if not process_raw or not constraints:
            return process_raw

        hard = constraints.get("hard_constraints", {})

        # ── ① 备料规格 ──
        geo_blank = hard.get("geo_blank_spec", "")
        legacy_blank = hard.get("blank_size", "")
        authoritative_blank = geo_blank or legacy_blank
        part_count = hard.get("part_count", 1) or 1
        if authoritative_blank:
            authoritative_blank = re.sub(r'=\d+$', f'={part_count}', authoritative_blank)

        if authoritative_blank:
            def _fix_blank_line(match):
                tag = match.group(1)
                action = match.group(2)
                rest = match.group(3).strip()
                current_dim = self._extract_dim_pattern(authoritative_blank)
                output_dim = self._extract_dim_pattern(rest)

                # Extract and preserve （工种：xx） suffix from original line
                _trade_suf = re.search(r'\s*[（(]工种[：:][^）)]*[）)]\s*$', rest)
                _ts = _trade_suf.group(0) if _trade_suf else ''

                if not current_dim:
                    return match.group(0)
                if not rest:
                    return f"- {tag}: {action} {authoritative_blank}{_ts}"
                if "按毛坯尺寸备料" in rest:
                    return f"- {tag}: {action} {authoritative_blank}{_ts}"
                if "毛坯尺寸" in rest and not output_dim:
                    return f"- {tag}: {action} {authoritative_blank}{_ts}"
                if output_dim and output_dim != current_dim:
                    return f"- {tag}: {action} {authoritative_blank}{_ts}"
                current_qty = re.search(r'=(\d+)$', authoritative_blank)
                output_qty = re.search(r'=(\d+)', rest)
                if output_dim and output_dim == current_dim and current_qty and output_qty:
                    if output_qty.group(1) != current_qty.group(1):
                        fixed_rest = re.sub(r'=\d+', f'={current_qty.group(1)}', rest, count=1)
                        return f"- {tag}: {action} {fixed_rest}"
                return match.group(0)

            blank_pat = re.compile(
                r'^(?:-\s*)?(\d{4})\s*[:：@\-\|,，;；\s]*(备料|下料|毛坯)(.*?)$',
                re.MULTILINE,
            )
            process_raw = blank_pat.sub(_fix_blank_line, process_raw)

        # ── ① bis: 掏铣外形 → 三段式备料尺寸兜底校验 ──
        # 仅当生成结果含"掏铣外形"且备料尺寸明显偏小时修正；不插入铣四边（交由提示词控制）
        # 几何守卫：小边 ≥ 150mm 且 长厚比 ≥ 20（与提示词触发条件一致）
        # 对于小边 < 150mm 的细长板（如 Y2 293×51.3×10），即使 LLM 写了"掏铣外形"也不套三段式
        if "掏铣外形" in process_raw:
            _outer_val = hard.get("outer_size", "")
            if _outer_val and _outer_val != "无":
                _onums = re.findall(r'\d+(?:\.\d+)?', _outer_val)
                _ovals = sorted([float(n) for n in _onums if float(n) >= 5], reverse=True)
                if len(_ovals) >= 2:
                    _L = _ovals[0]
                    _W = _ovals[1]
                    _T = int(_ovals[2]) if len(_ovals) >= 3 else None
                    # 薄板夹持框判定：小边 ≥ 150mm 且 长厚比 ≥ 20（与提示词触发条件一致）
                    # 细长板/厚板即使 LLM 写"掏铣外形"也只是工步描述，无需三段式备料
                    _needs_frame = _W >= 150 and _T is not None and _T > 0 and _L / _T >= 20
                    if not _needs_frame and _T is not None:
                        # 兜底：LLM 违规生成了三段式备料，改回简单余量
                        _sl = int(_L + 5) if _L <= 100 else int(_L + 7)
                        _sw = int(_W + 5) if _W <= 100 else int(_W + 7)
                        _min3 = int(_L + 15 * 2)  # 最小三段式尺寸下限（frame=15最小）
                        _bm2 = re.search(
                            r'^((?:-\s*)?\d{4}\s*[:：@\-\|,，;；\s]*'
                            r'(?:[^\n]*?(?:备料|下料|毛坯)[^\n]*|[≠δ≠][^\n]*))$',
                            process_raw, re.MULTILINE,
                        )
                        if _bm2:
                            _bv = sorted(
                                [float(n) for n in re.findall(r'\d+(?:\.\d+)?', _bm2.group(1)) if float(n) >= 5],
                                reverse=True,
                            )
                            if _bv and _bv[0] >= _min3:
                                _fix = f"≠{_T}×{_sl}×{_sw}"
                                _ob = _bm2.group(1)
                                _nb = re.sub(r'[≠δ]\s*\d+\s*[×xX]\s*\d+\s*[×xX]\s*\d+', _fix, _ob, count=1)
                                if _nb == _ob:
                                    _nb = re.sub(r'\d{3,}\s*[×xX]\s*\d{2,}(?:\s*[×xX]\s*\d+)?', f'{_sl}×{_sw}', _ob, count=1)
                                if _nb != _ob:
                                    process_raw = process_raw.replace(_ob, _nb, 1)
                    if _needs_frame:
                        _fr = 15 if _L <= 150 else (20 if _L <= 300 else 25)
                        _L_blank = int(_L + _fr * 2 + 5)
                        _W_blank = int(_W + _fr * 2 + 5)
                        # 扫描生成工序中的备料行（匹配含"备料/下料"关键字或含≠/δ毛坯符号的行）
                        _bm = re.search(
                            r'^((?:-\s*)?\d{4}\s*[:：@\-\|,，;；\s]*'
                            r'(?:[^\n]*?(?:备料|下料|毛坯)[^\n]*|[≠δ≠][^\n]*))$',
                            process_raw, re.MULTILINE,
                        )
                        if _bm:
                            _bcurr = re.findall(r'\d+(?:\.\d+)?', _bm.group(1))
                            _bvals = sorted([float(n) for n in _bcurr if float(n) >= 5], reverse=True)
                            _cur_max = _bvals[0] if _bvals else 0
                            if _cur_max < _L_blank - 10:
                                _t_prefix = f"≠{_T}×" if _T else "≠"
                                _correct = f"{_t_prefix}{_L_blank}×{_W_blank}"
                                _old_b = _bm.group(1)
                                _new_b = re.sub(
                                    r'[≠δ]\s*\d+\s*[×xX]\s*\d+\s*[×xX]\s*\d+',
                                    _correct, _old_b, count=1,
                                )
                                if _new_b == _old_b:
                                    _new_b = re.sub(
                                        r'\d{3,}\s*[×xX]\s*\d{3,}(?:\s*[×xX]\s*\d+)?',
                                        f'{_L_blank}×{_W_blank}', _old_b, count=1,
                                    )
                                if _new_b != _old_b:
                                    process_raw = process_raw.replace(_old_b, _new_b, 1)

        # ── ④ 铣四边缺失兜底（LLM 不遵从提示词时的后处理） ──
        _mf = hard.get("material_form", "")
        if "板料" in _mf and "铣四边" not in process_raw and "铣六面" not in process_raw:
            _outer = hard.get("outer_size", "")
            if _outer and _outer != "无":
                _nums = re.findall(r'\d+(?:\.\d+)?', _outer)
                if len(_nums) >= 3:
                    _vals = sorted([float(n) for n in _nums], reverse=True)
                    _l, _w = int(_vals[0]), int(_vals[1])
                    _lines = process_raw.split("\n")
                    _insert_at = -1
                    for _i, _line in enumerate(_lines):
                        if not _line.strip():
                            continue
                        if re.search(r'（工种：(备料|检)）', _line):
                            _insert_at = _i + 1
                        else:
                            if _insert_at >= 0:
                                break
                    if 0 < _insert_at < len(_lines):
                        _mill_line = f"- 0100: 铣四边{_l}×{_w} （工种：铣）"
                        _check_line = f"- 0105: 外观检验 （工种：检）"
                        _lines.insert(_insert_at, _check_line)
                        _lines.insert(_insert_at, _mill_line)
                        # Renumber subsequent lines (+50 to avoid clashes)
                        _step_pat = re.compile(r'^(-\s*)(\d{4})(\s*[:：])')
                        _base = 150  # first renumbered step
                        for _j in range(_insert_at + 2, len(_lines)):
                            _s = _lines[_j]
                            if _step_pat.match(_s):
                                _new_num = _base + (_j - _insert_at - 2) * 50
                                _lines[_j] = _step_pat.sub(
                                    lambda m: f"{m.group(1)}{_new_num:04d}{m.group(3)}", _s
                                )
                        process_raw = "\n".join(_lines)

        # ── ② 孔数量覆盖 ──
        geo_hole_count = hard.get("geo_hole_count", 0)
        if geo_hole_count > 0:
            def _fix_hole_count(m):
                n_str = m.group(1)
                if int(n_str) != geo_hole_count:
                    return m.group(0).replace(n_str, str(geo_hole_count), 1)
                return m.group(0)

            hole_pat = re.compile(r'(\d+)\s*[×x\*]\s*(?:[Mφ]\d+|螺纹孔|通孔)')
            process_raw = hole_pat.sub(_fix_hole_count, process_raw)

        # ── ③ 孔径范围标记 ──
        geo_bore_range = hard.get("geo_bore_range", "")
        if geo_bore_range:
            m_range = re.match(r'([\d.]+)~([\d.]+)mm', geo_bore_range)
            if m_range:
                bore_lo = float(m_range.group(1)) - 1.0
                bore_hi = float(m_range.group(2)) + 1.0

                bore_pat = re.compile(r'[Φφ]([\d.]+)')
                result_lines = []
                for line in process_raw.split('\n'):
                    hits = bore_pat.findall(line)
                    out_of_range = [d for d in hits if not (bore_lo <= float(d) <= bore_hi)]
                    if out_of_range:
                        line = line.rstrip() + f"  ⚠几何孔径范围:{geo_bore_range}"
                    result_lines.append(line)
                process_raw = '\n'.join(result_lines)

        # ── ⑤ 检验末步：恢复 1）2）条目序号 ──
        process_raw = self._restore_inspection_numbering(process_raw)

        # ── ⑥ 连续相同前缀子条目合并 ──
        process_raw = self._merge_same_prefix_subitems(process_raw)

        return process_raw

    # ── Controlled Prompt ───────────────────────────────────────────────────

    def _build_controlled_prompt(
        self,
        fused_description: str,
        expert_judgment: str,
        rag_context: str,
        rag_results: Optional[Dict[str, Any]],
        constraints: dict,
        use_blueprint: bool,
        allowed_fragments: dict,
    ) -> str:
        """构建受约束的工艺生成提示。

        以当前审阅特征为主约束源，蓝本仅提供流程框架。
        """
        # 候选信息（Plan C：注入结构维度）
        curr_t, curr_area = self._parse_structural_dims(fused_description)
        struct_hint = ""
        if curr_t is not None:
            struct_hint = f"当前零件结构维度：厚度≈{curr_t:.0f}mm"
            if curr_area is not None:
                struct_hint += f"，面积≈{curr_area / 10000:.1f}万mm²"
            struct_hint += "\n"
        candidates_info = struct_hint
        if rag_results and rag_results.get("matches"):
            for i, m in enumerate(rag_results["matches"][:3], 1):
                candidates_info += f"候选{i}: {m.get('drawing_id')} (相似度:{m.get('similarity'):.3f}, 类型:{m.get('match_type')})\n"

        # 约束摘要
        hard = constraints.get("hard_constraints", {})
        soft = constraints.get("soft_features", {})

        hard_lines = []
        for k, label in [("blank_size", "毛坯尺寸"), ("outer_size", "外形尺寸"), ("key_dims", "关键尺寸")]:
            v = hard.get(k, "")
            if v:
                hard_lines.append(f"- {label}：{v}")
            else:
                hard_lines.append(f"- {label}：（当前特征未明确给出，不可由蓝本补充）")
        hard_summary = "\n".join(hard_lines)

        # 允许补充的片段
        frag_lines = []
        for k, v in allowed_fragments.items():
            if v:
                frag_lines.append(f"- {k}：{v}")
        frag_summary = "\n".join(frag_lines) if frag_lines else ""

        # 模式描述
        if use_blueprint:
            mode_instruction = (
                "当前精确图号命中且相似度≥80%，蓝本工艺可作为主流程框架。\n"
                "但蓝本中的毛坯尺寸、外形尺寸、关键尺寸若与当前审阅特征冲突，必须以当前特征为准。"
            )
        else:
            mode_instruction = (
                "当前图号不匹配或相似度<80%，蓝本仅提供流程参考，不得覆盖当前零件的主体几何尺寸。\n"
                "历史候选仅允许在指定软特征字段进行局部补充；工序可按当前零件事实裁剪，不必保持与蓝本相同步骤数。"
            )

        hard_constr_instruction = """## 硬约束（必须遵守）
以下字段只能来自【当前审阅特征】，历史蓝本/候选的任何不同值都**不允许沿用**：
- 毛坯尺寸：不可被蓝本或历史候选覆盖
- 外形尺寸：不可被蓝本或历史候选覆盖
- 关键尺寸：不可被蓝本或历史候选覆盖
- 任何会改变零件主体几何的尺寸都不可由蓝本推定

**禁止行为：**
- ❌ 不允许让 LLM 自行折中当前特征与蓝本的冲突值
- ❌ 不允许按蓝本比例估算后覆盖当前值
- ❌ 不允许在毛坯尺寸/外形尺寸无明确值时由蓝本补充"""

        soft_section = ""
        existing_soft = [f"- {k}：{v}" for k, v in soft.items() if v]
        if existing_soft:
            soft_section = "\n## 当前审阅特征的可用软特征\n以下字段已由当前审阅特征给出，同样不可被历史覆盖：\n" + "\n".join(existing_soft) + "\n"

        fragment_section = ""
        if frag_summary:
            fragment_section = f"""\n## 低相似度局部补充（允许使用）
以下字段来自历史候选的局部特征片段，仅当当前审阅特征未明确给出时才启用：
{frag_summary}

注意：即使历史候选很像，以下字段也**禁止补充**：
- 毛坯厚度/长宽/外形包络
- 总体外轮廓尺寸
- 与主体结构绑定的关键尺寸
- 当前审阅特征已明确但历史值不同的数值"""

        # ── 吊面/翻面约束段落 ──
        flip_face = hard.get("flip_face", "")
        flip_face_section = ""
        if flip_face:
            flip_face_section = f"""
## 吊面/翻面约束（重要，不可省略）
当前零件存在吊面（背面需加工的特征）：{flip_face}
⚠️ 工艺规程**必须包含翻面操作**，具体要求：
- 正面加工工序完成后，必须有一道"翻面，加工背面"的翻面步骤（可合并在数控铣工序工步中）
- 背面特征（孔/螺纹孔/沉孔/槽等）须在翻面后的工步中单独列出，不可遗漏
- 蓝本若无翻面步骤，必须新增；不可因蓝本无翻面步骤而省略
- 工种保持与正面加工工序一致（通常为数铣或数控铣）

**翻面工序格式模板（根据当前零件背面实际特征替换方括号内容，禁止照抄）：**
写法A（翻面独立工序，背面特征较多时推荐）：
  00XX  数控铣  以底面定位，铣削正面[特征描述]；钻攻正面[孔规格，如4×M6深10]；
  00XX  翻面    翻面，以正面为基准重新装夹，压紧底面两侧；
  00XX  数控铣  铣削背面[平面/槽，注明尺寸和粗糙度]；钻攻背面[孔规格]；
写法B（翻面作工步，背面特征简单时可合并在同一工序）：
  00XX  数控铣
    工步1：以底面定位，铣削正面[特征]；钻攻正面[孔规格]；
    工步2：翻面，以正面为基准重新装夹；铣削/钻攻背面[背面具体特征]；
"""

        geo_summary = self._extract_key_geo_fields(fused_description)
        geo_summary_line = f"\n**当前零件关键参数**: {geo_summary}" if geo_summary else ""
        authoritative_blank = hard.get("geo_blank_spec", "") or hard.get("blank_size", "")
        part_count = hard.get("part_count", 1) or 1
        if authoritative_blank:
            authoritative_blank = re.sub(r'=\d+$', f'={part_count}', authoritative_blank)
        blank_instruction = ""
        if authoritative_blank:
            blank_instruction = f"""
## 0010 备料硬约束
0010 备料必须直接使用当前零件的权威毛坯规格，不允许写"按毛坯尺寸备料"或省略尺寸：
- 权威毛坯规格：{authoritative_blank}
- 数量：{part_count}
- 若蓝本 0010 与此不一致，必须改写为当前规格
"""

        mill_blank_instruction = self._build_mill_blank_instruction(
            fused_description, authoritative_blank, rag_context=rag_context
        )

        # ── 物料形态约束 ──
        material_form = hard.get("material_form", "")
        material_form_section = ""
        if material_form:
            material_form_section = f"\n## 物料形态约束\n当前零件物料形态：**{material_form}**\n"
            if "板料" in material_form:
                # 板厚判断：薄板铣四边，厚板（>40mm）铣六面
                _thickness_for_mill = None
                _outer_val = hard.get("outer_size", "")
                if _outer_val and _outer_val != "无":
                    _outer_nums = re.findall(r'\d+(?:\.\d+)?', _outer_val)
                    _outer_vals = sorted([float(n) for n in _outer_nums if float(n) >= 3])
                    if _outer_vals:
                        _thickness_for_mill = _outer_vals[0]
                if _thickness_for_mill and _thickness_for_mill > 40:
                    material_form_section += (
                        f"- 当前零件板厚 {_thickness_for_mill:.0f}mm > 40mm，属于厚板\n"
                        "- 铣工序内容必须写**铣六面**（厚板需加工六个面），禁止写铣四边\n"
                        "- 铣六面工序的**工种必须写铣**，禁止写数控铣；铣六面是普通铣床工序\n"
                        "- 备料格式：≠板厚×长×宽\n"
                        "- 铣方保证尺寸：长×宽×厚，均带 ±0.1 公差\n"
                    )
                else:
                    material_form_section += (
                        "- 铣四边工序的**工种必须写铣**，禁止写数控铣；铣四边是普通铣床工序\n"
                        "- 铣工序内容必须写**铣四边**，禁止出现铣六面\n"
                        "- 备料格式：≠板厚×长×宽\n"
                        "- 铣工序保证尺寸只含长×宽，不含厚度\n"
                        "- **禁止**在数控铣工序中出现铣大底面、铣底面步骤；板料厚度已由备料保证，无需再铣底面\n"
                    )
            blueprint_form = self._infer_blueprint_material_form(rag_context)
            if blueprint_form and blueprint_form != material_form:
                material_form_section += (
                    f"⚠️ **蓝本物料形态（{blueprint_form}）与当前零件（{material_form}）不匹配**：\n"
                    "- 蓝本的备料规格、铣削工序结构**不可参考**\n"
                    "- 仅可参考蓝本的检验、表处、包装等通用工序的组织方式\n"
                )

        # ── 热处理约束 ──
        heat_val = hard.get("heat_treatment", "")
        _is_al   = hard.get("is_aluminum_alloy", False)
        _is_cav  = hard.get("is_cavity_part", False)
        _is_lg   = hard.get("is_large_part", False)
        if not heat_val or heat_val == "无":
            if _is_al and _is_cav and _is_lg:
                # 铝合金大型腔体件：图纸虽未注明，但工程上需要去应力，不强制禁止
                heat_treatment_section = (
                    "\n## 热处理约束\n"
                    "当前零件图纸【热处理与探伤】字段为无，通常不添加热处理工序。\n"
                    "**但当前零件属于铝合金大型腔体件（外形≥500mm），工程实践中粗铣后常需**：\n"
                    "- 方案A（推荐）：粗铣完卸料，**静置12~24h** 自然释放应力，再精铣\n"
                    "- 方案B：如客户/工艺协议有要求，可安排**低温去应力退火**（约150~180℃）\n"
                    "若图纸/技术协议未明确要求退火，优先使用方案A（卸料静置），不单独列热处理工序。\n"
                    "蓝本中若含淬火/调质/高温退火等与铝合金腔体无关的热处理，必须删除。\n"
                )
            else:
                heat_treatment_section = (
                    "\n## 热处理约束\n"
                    "当前零件【热处理与探伤】字段为无，**禁止添加任何热处理工序**"
                    "（退火、时效、淬火、回火、调质等均不允许出现）。"
                    "蓝本中若含热处理工序，必须删除。\n"
                )
        else:
            heat_treatment_section = (
                f"\n## 热处理约束\n"
                f"当前零件热处理要求：{heat_val}\n"
                f"必须按此添加对应热处理工序，不可省略。\n"
            )

        # ── 表面处理/镀覆约束 ──
        st_val = hard.get("surface_treatment", "")
        if not st_val or st_val == "无":
            surface_treatment_section = (
                "\n## 表面处理约束\n"
                "当前零件【表面处理与镀层特征】字段为无，**禁止添加任何镀覆/表处工序**"
                "（镀覆、阳极化、氧化、涂漆、喷漆等均不允许出现）。"
                "蓝本中若含镀覆/表处工序，必须删除。\n"
            )
        else:
            surface_treatment_section = (
                f"\n## 表面处理约束\n"
                f"当前零件表面处理要求：{st_val}\n"
                f"必须按此添加对应表处工序，不可省略。\n"
            )
            # 特定涂漆规范需要前处理（化学氧化/镀覆）
            _paint_pre_treat_specs = ["Ts96-61", "海依", "Ts96"]
            if any(spec in st_val for spec in _paint_pre_treat_specs):
                surface_treatment_section += (
                    "- 当前涂漆规范（Ts96-61/海依）要求涂漆前进行化学氧化（镀覆）前处理\n"
                    "- 应在涂漆工序前单独列一道**表处（化学氧化/镀覆）**工序，"
                    "或在涂漆工序内容中注明包括前处理\n"
                )

        # ── 腔体件特殊制造规则 ──
        cavity_manufacturing_section = ""
        if hard.get("is_cavity_part"):
            _cav_rules = [
                "当前零件含**复杂内腔结构**，必须遵循以下腔体件制造规则：",
                "- **数控铣须分阶段**：至少分粗加工、半精加工、精加工三个独立工序，不可合并为一道",
                "  - 粗铣：去大余量，单面留余量4~5mm",
                "  - 半精铣：单面留余量0.5~1mm",
                "  - 精铣：达到图纸尺寸和公差",
                "- **工艺凸台**：粗铣外形时沿一周保留宽≥50mm工艺凸台（防薄板翻转变形），"
                "精铣前最后一道工序铣去",
                "- **卸料静置**：粗铣完毕后卸料放置12~24h，令残余应力自然释放后再精加工",
            ]
            if hard.get("is_aluminum_alloy") and hard.get("is_large_part"):
                _cav_rules.append(
                    "- **铝合金大型腔体**：因变形风险高，粗铣→半精铣→精铣各阶段之间"
                    "均需卸料检测平面度，超差需校平后再继续"
                )
            cavity_depth = hard.get("cavity_depth_hint", "")
            if cavity_depth:
                _cav_rules.append(f"- 备料厚度参考：{cavity_depth}，备料厚度应为成品厚度 + 内腔最大深度 + 双面加工余量")
            cavity_manufacturing_section = "\n## 腔体件特殊制造规则（重要，必须遵守）\n" + "\n".join(_cav_rules) + "\n"

        # ── 数控铣位置尺寸映射提示 ──
        key_dims_val = hard.get("key_dims", "")
        cnc_dim_section = ""
        if key_dims_val:
            cnc_dim_section = (
                f"\n## 数控铣工步尺寸映射\n"
                f"当前零件【关键尺寸】：{key_dims_val}\n"
                "生成数控铣工序内容时，规则如下：\n"
                "- 铣槽/铣缺口/铣异型面的工步必须写出保证尺寸，从上述关键尺寸中选取相关数值\n"
                "- 角度、半径、定位距离（如6.8°、R3、R5、定位坐标）须写入对应工步\n"
                "- 钻孔/攻丝工步须包含孔径和深度（如5×φ2.5,深8；3×M5,深12）\n"
                "- 不要只写操作动词，必须同时写保证尺寸\n"
            )

        # ── 板料备料余量规则（有外形尺寸且无权威毛坯规格时触发，不依赖物料形态） ──
        blank_allowance_section = ""
        if not authoritative_blank:
            outer_val = hard.get("outer_size", "")
            if outer_val and outer_val != "无":
                _nums = re.findall(r'\d+(?:\.\d+)?', outer_val)
                _plate_hint = ""
                if len(_nums) >= 3:
                    _vals = sorted([float(n) for n in _nums[:3]])
                    _thickness = _vals[0]
                    _l, _w = _vals[2], _vals[1]
                    # 腔体件：备料厚度需加上内腔深度余量
                    # 从关键尺寸中估计最大腔深（取关键尺寸中 5~60mm 的最大值作为腔深上限）
                    if hard.get("is_cavity_part") and _thickness < 150:
                        _key_nums_for_depth = [
                            float(n) for n in re.findall(r'\d+(?:\.\d+)?', hard.get("key_dims", "") or "")
                            if 5 <= float(n) <= 60
                        ]
                        _est_cavity_depth = max(_key_nums_for_depth, default=0)
                        if _est_cavity_depth >= 5:
                            _raw_thickness = _thickness + _est_cavity_depth + 5  # 腔深 + 5mm 双面余量
                            _raw_thickness = (int(_raw_thickness // 10) + 1) * 10  # 向上取整到10的倍数
                            _thickness = max(_thickness, _raw_thickness)
                    # 掏铣外形检测：文本关键字 OR 几何规则（薄方板：小边≥150mm且长厚比≥20）
                    _has_profile_mill = any(
                        "掏铣" in (src or "")
                        for src in [rag_context, expert_judgment, fused_description]
                    ) or (
                        _w >= 150
                        and _thickness > 0
                        and _l / _thickness >= 20
                    )
                    if _has_profile_mill:
                        # 三段式：最终外形 → 铣四边中间尺寸 → 毛坯
                        # 夹持框余量：≤150mm取15，≤300mm取20，>300mm取25（每边）
                        _frame = 15 if _l <= 150 else (20 if _l <= 300 else 25)
                        _l_inter = int(_l + _frame * 2)
                        _w_inter = int(_w + _frame * 2)
                        _l_blank = _l_inter + 5
                        _w_blank = _w_inter + 5
                        _plate_hint = (
                            f"  三段式计算结果（夹持框每边{_frame}mm）：\n"
                            f"  毛坯：≠{int(_thickness)}×{_l_blank}×{_w_blank}\n"
                            f"  铣四边中间尺寸：{_l_inter}×{_w_inter}\n"
                            f"  最终外形：{int(_l)}×{int(_w)}\n"
                        )
                        blank_allowance_section = (
                            f"\n## 备料余量规则（掏铣外形三段式）\n"
                            f"当前外形尺寸：{outer_val}\n"
                            "当前零件为薄板件（需夹持框掏铣外形），必须使用三段式备料策略：\n"
                            f"{_plate_hint}"
                            "- 第1步 备料：毛坯按上述尺寸，板厚不加余量，长宽各加(夹持框x2+5)mm\n"
                            "- 第2步 铣四边：铣到中间尺寸（保留夹持框供后续掏铣装夹），工种写铣\n"
                            "- 第3步 数控铣：掏铣外形到最终尺寸\n"
                            "- 工序必须包含：备料->检->铣(铣四边)->钳(去毛刺)->检->数控铣(掏铣外形)\n"
                            "- 备料工序必须写出具体规格，禁止只写备料二字\n"
                        )
                    else:
                        _l_blank = int(_l + 5) if _l <= 100 else int(_l + 7)
                        _w_blank = int(_w + 5) if _w <= 100 else int(_w + 7)
                        blank_allowance_section = (
                            f"\n## 备料余量规则\n"
                            f"当前外形尺寸：{outer_val}\n"
                            f"  备料规格（已锁定）：≠{int(_thickness)}×{_l_blank}×{_w_blank}\n"
                            "要求：\n"
                            "- 备料工序**必须使用上述已锁定规格**，禁止自行修改尺寸\n"
                            "- 此零件小边<150mm，**禁止三段式备料**（无夹持框需求）\n"
                            "- **禁止**在备料和数控铣之间插入独立的铣四边工序作为夹持框收缩步\n"
                            "- 备料后直接进数控铣，外形轮廓在数控铣工步内完成\n"
                        )

        prompt = f"""你是一名资深工艺工程师。从候选工艺中选出最合适的蓝本，按最小改动原则输出最终工艺。{geo_summary_line}

## 模式
{mode_instruction}

## 当前审阅特征（最高优先级）
{hard_summary}
{soft_section}
{fragment_section}

## 蓝本使用边界
- 蓝本只提供工艺框架和语言风格参考，最终工序必须以**当前零件的审阅特征和几何描述**为准
- 可以复用蓝本的工序组织逻辑、工艺术语、常见收尾动作
- 不可以照搬与当前零件无关的试装、组合加工、特殊表处等工序
- **视图交叉验证（重要）**：蓝本中出现的"按主/俯/仰/左/右视图，钻/铣/攻…"等按视图标注的操作，必须与当前零件的几何描述或专家分析中的视图/孔位信息交叉核对。若当前零件对应视图中不存在这些特征，必须删除该操作或改为适合当前零件的描述。无对应视图信息的蓝本操作不应原样保留

{hard_constr_instruction}
{material_form_section}
{heat_treatment_section}
{surface_treatment_section}
{cavity_manufacturing_section}
{flip_face_section}
{cnc_dim_section}
{blank_allowance_section}
{blank_instruction}
{mill_blank_instruction}

## 选型规则
- 工序数为 0 的候选视为无效，不可作为蓝本
- 优先选择备料工序中≠厚度与当前零件接近、长宽面积量级相当的蓝本
- 大面积薄板（面积>10万mm²）工艺复杂度接近厚板，不应选用小尺寸薄板蓝本
- 如果所有候选工序数都为 0，或所有候选图号与当前零件差异过大，请直接从零编制
- 如果看到 `ENDD$$`，把它当作空格分隔符忽略，不要写进结果

## 最小改动原则
**以蓝本工序为框架参考，以当前零件特征为最终依据进行增删改。**
- 蓝本只是流程框架，允许删除不适用工序、新增必要工序、修改与当前特征冲突的内容
- 不得推演、估算或虚构当前零件特征中未出现的数值
- **数值验证（关键）**：蓝本中的具体数值（孔数如"18-M2.5"、螺纹规格如"ST2.5×0.45×12"、孔径如"φ2深5"、深度等）必须与当前零件特征中的对应数值逐一核对。规则如下：
  1. 若当前特征中有相同数值 → 保留
  2. 若当前特征中有相近数值 → 替换为当前特征的数值
  3. 若当前特征中完全没有对应数值 → 删除该数值，只保留工序描述（如"钻孔""攻丝"），不写具体规格
- 若蓝本某工序在当前零件特征中找不到依据，则删除该工序
- 若当前零件存在蓝本没有覆盖的必要工序，可新增，但内容须来自当前的几何描述或专家分析
- 若当前特征未提供某项信息，保持中性，不补数值

## 候选工艺概览:
{candidates_info}

## 候选工艺详情:
{rag_context}

## 专家分析结果:
{expert_judgment}

## 当前零件几何描述:
{fused_description[:800]}

## 输出格式:
```markdown
## 候选选择
选择: [图号]
理由: [一句话，说明与当前零件最匹配的原因]

## 生成的工艺规程
- 0010: 工序内容 （工种：料）
...
```
- **每一道工序必须标注工种**，格式为 （工种：xx），不得省略
- 若蓝本工序行已有工种则沿用；若无，则根据工序内容推断最合适的工种
- 常见工种参考：料（备料）、热处理（退火/时效）、铣（铣外形/铣方）、数铣（数控铣/CNC）、车（车削）、钻（钻孔）、钳（去毛刺/攻丝/清洗）、钳装（试装/组合加工/装配）、镀覆（外协镀覆，如AL/Ct.Ocd等规范）、表处（阳极化/化学氧化/喷漆）、检（检验/标识入库）
- ⚠️ 镀覆与表处区别：外协送镀（AL/Ct、铬酸阳极化等规范+按外协技术协议）→工种填【镀覆】；本厂阳极化/化学氧化/喷漆→工种填【表处】"""
        return prompt

    def _build_llm_prompt(
        self,
        fused_description: str,
        expert_judgment: str,
        rag_context: str,
        rag_results: Optional[Dict[str, Any]],
    ) -> str:
        """Build LLM prompt with RAG context."""
        curr_t, curr_area = self._parse_structural_dims(fused_description)
        struct_hint = ""
        if curr_t is not None:
            struct_hint = f"当前零件结构维度：厚度≈{curr_t:.0f}mm"
            if curr_area is not None:
                struct_hint += f"，面积≈{curr_area / 10000:.1f}万mm²"
            struct_hint += "\n"
        candidates_info = struct_hint
        if rag_results and rag_results.get("matches"):
            for i, m in enumerate(rag_results["matches"][:3], 1):
                candidates_info += f"候选{i}: {m.get('drawing_id')} (相似度:{m.get('similarity'):.3f}, 类型:{m.get('match_type')})\n"

        geo_summary = self._extract_key_geo_fields(fused_description)
        geo_summary_line = f"\n**当前零件关键参数**: {geo_summary}" if geo_summary else ""

        prompt = f"""你是一名资深工艺工程师。从候选工艺中选出最合适的蓝本，按最小改动原则输出最终工艺。{geo_summary_line}

## 选型规则
- 工序数为 0 的候选视为无效，不可作为蓝本
- 优先选择备料工序中≠厚度与当前零件接近、长宽面积量级相当的蓝本
- 大面积薄板（面积>10万mm²）工艺复杂度接近厚板，不应选用小尺寸薄板蓝本
- 如果所有候选工序数都为 0，或所有候选图号与当前零件差异过大，请直接从零编制
- 如果看到 `ENDD$$`，把它当作空格分隔符忽略，不要写进结果

## 蓝本使用边界
- 蓝本只提供工艺框架和语言风格参考，最终工序必须以**当前零件的审阅特征和几何描述**为准
- 可以复用蓝本的工序组织逻辑、工艺术语、常见收尾动作
- 不可以照搬与当前零件无关的试装、组合加工、特殊表处等工序
- **视图交叉验证（重要）**：蓝本中出现的"按主/俯/仰/左/右视图，钻/铣/攻…"等按视图标注的操作，必须与当前零件的几何描述或专家分析中的视图/孔位信息交叉核对。若当前零件对应视图中不存在这些特征，必须删除该操作或改为适合当前零件的描述

## 最小改动原则
**以蓝本工序为框架参考，以当前零件特征为最终依据进行增删改。**
- 蓝本只是流程框架，允许删除不适用工序、新增必要工序、修改与当前特征冲突的内容
- 不得推演、估算或虚构当前零件特征中未出现的数值
- **数值验证（关键）**：蓝本中的具体数值（孔数如"18-M2.5"、螺纹规格如"ST2.5×0.45×12"、孔径如"φ2深5"、深度等）必须与当前零件特征中的对应数值逐一核对。规则如下：
  1. 若当前特征中有相同数值 → 保留
  2. 若当前特征中有相近数值 → 替换为当前特征的数值
  3. 若当前特征中完全没有对应数值 → 删除该数值，只保留工序描述（如"钻孔""攻丝"），不写具体规格
- 若蓝本某工序在当前零件特征中找不到依据，则删除该工序
- 若当前零件存在蓝本没有覆盖的必要工序，可新增，但内容须来自当前的几何描述或专家分析
- 若当前特征未提供某项信息，保持中性，不补数值

## 候选工艺概览:
{candidates_info}

## 候选工艺详情:
{rag_context}

## 专家分析结果:
{expert_judgment}

## 当前零件几何描述:
{fused_description[:800]}

## 输出格式:
```markdown
## 候选选择
选择: [图号]
理由: [一句话，说明与当前零件最匹配的原因]

## 生成的工艺规程
- 0010: 工序内容 （工种：料）
...
```
- **每一道工序必须标注工种**，格式为 （工种：xx），不得省略
- 若蓝本工序行已有工种则沿用；若无，则根据工序内容推断最合适的工种
- 常见工种参考：料（备料）、热处理（退火/时效）、铣（铣外形/铣方）、数铣（数控铣/CNC）、车（车削）、钻（钻孔）、钳（去毛刺/攻丝/清洗）、钳装（试装/组合加工/装配）、镀覆（外协镀覆，如AL/Ct.Ocd等规范）、表处（阳极化/化学氧化/喷漆）、检（检验/标识入库）
- ⚠️ 镀覆与表处区别：外协送镀（AL/Ct、铬酸阳极化等规范+按外协技术协议）→工种填【镀覆】；本厂阳极化/化学氧化/喷漆→工种填【表处】"""
        return prompt

    def _build_fallback_prompt(
        self, fused_description: str, expert_judgment: str, constraints: dict = None
    ) -> str:
        """Build LLM prompt without RAG context."""
        geo_summary = self._extract_key_geo_fields(fused_description)
        geo_summary_line = f"\n**当前零件关键参数**: {geo_summary}" if geo_summary else ""

        flip_face = ""
        material_form = ""
        outer_size = ""
        if constraints:
            hard_c = constraints.get("hard_constraints") or {}
            flip_face = hard_c.get("flip_face", "")
            material_form = hard_c.get("material_form", "")
            outer_size = hard_c.get("outer_size", "")

        # fallback 独立检测：若融合特征含 ≠/δ 板厚符号，强制为板料
        if "板料" not in material_form and re.search(r'[≠δ]\s*\d+', fused_description):
            material_form = "板料"

        flip_face_section = ""
        if flip_face:
            flip_face_section = f"""
## 吊面/翻面约束（重要，不可省略）
当前零件存在吊面（背面需加工的特征）：{flip_face}
⚠️ 工艺规程**必须包含翻面操作**：正面加工完成后增加翻面步骤，背面特征在翻面后工步中单独列出。

**翻面工序格式模板（根据当前零件背面实际特征替换方括号内容，禁止照抄）：**
写法A（翻面独立工序，背面特征较多时推荐）：
  00XX  数控铣  以底面定位，铣削正面[特征描述]；钻攻正面[孔规格，如4×M6深10]；
  00XX  翻面    翻面，以正面为基准重新装夹，压紧底面两侧；
  00XX  数控铣  铣削背面[平面/槽，注明尺寸和粗糙度]；钻攻背面[孔规格]；
写法B（翻面作工步，背面特征简单时可合并在同一工序）：
  00XX  数控铣
    工步1：以底面定位，铣削正面[特征]；钻攻正面[孔规格]；
    工步2：翻面，以正面为基准重新装夹；铣削/钻攻背面[背面具体特征]；
"""

        material_form_section = ""
        if "板料" in material_form:
            _thickness_for_mill = None
            if outer_size and outer_size != "无":
                _outer_nums = re.findall(r'\d+(?:\.\d+)?', outer_size)
                _outer_vals = sorted([float(n) for n in _outer_nums if float(n) >= 3])
                if _outer_vals:
                    _thickness_for_mill = _outer_vals[0]
            if _thickness_for_mill and _thickness_for_mill > 40:
                material_form_section = (
                    f"\n## 物料形态约束（板料·厚板）\n"
                    f"当前零件物料形态：**{material_form}**，板厚{_thickness_for_mill:.0f}mm > 40mm，属于厚板\n"
                    "- 备料（0010）之后**必须**有**铣六面**工序（工种：铣），将毛坯各面铣平，保证尺寸\n"
                    "- 铣六面是普通铣床工序，工种填**铣**，禁止填数控铣\n"
                    "- 之后才是数控铣精加工工序\n"
                )
            else:
                material_form_section = (
                    f"\n## 物料形态约束（板料·薄板）\n"
                    f"当前零件物料形态：**{material_form}**\n"
                    "- 备料（0010）之后**必须**有**铣四边**工序（工种：铣），将板料四周铣平，保证平面度和尺寸\n"
                    "- 铣四边是普通铣床工序，工种填**铣**，禁止填数控铣\n"
                    "- 铣四边保证尺寸只含长×宽，不含厚度（厚度已由备料保证）\n"
                    "- 之后才是数控铣精加工工序\n"
                )

        return f"""你是一名工艺工程师。知识库中无匹配参考，根据图纸分析结果从零编制工艺规程。{geo_summary_line}

{flip_face_section}{material_form_section}
## 规则
- 如果看到 `ENDD$$`，把它当作空格分隔符忽略，不要写进结果
- 只输出能从专家分析或几何描述中直接读到的内容，不得推演或补全未提及的数值
- 工序描述简洁，与行业标准工艺卡格式一致

## 专家分析结果:
{expert_judgment}

## 当前零件几何描述:
{fused_description[:800]}

## 输出格式：
```markdown
- 0010: 工序内容 （工种：料）
...
```
- **每一道工序必须标注工种**，格式为 （工种：xx），不得省略
- 根据工序内容推断最合适的工种：料（备料）、热（退火/时效）、铣（铣外形/铣方）、车（车削）、钻（钻孔）、攻（攻丝）、钳（去毛刺/试装/清洗）、镀覆（外协镀覆，如AL/Ct.Ocd等规范）、表处（阳极化/化学氧化/喷漆）、检（检验/标识入库）
- ⚠️ 镀覆与表处区别：外协送镀（按外协技术协议）→工种填【镀覆】；本厂阳极化/化学氧化/喷漆→工种填【表处】"""
