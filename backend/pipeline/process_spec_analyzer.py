# -*- coding: utf-8 -*-
"""
工艺规程 PDF 专用视觉解析器。

工艺规程的格式与零件图纸完全不同：
  - 图纸：几何特征、尺寸公差、技术要求 → 用 VisionAnalyzer 提取
  - 工艺规程：表格，每行是一道工序（工序号、名称、内容、设备…）

使用与 VisionAnalyzer 相同的 API，但换用专门面向工序表格的 prompt，
输出 "0010@粗车：加工内容（设备）" 格式，下游直接存入 process_list。
"""

import os
import base64
import re
import logging
from typing import List, Dict, Any
from datetime import datetime
from openai import OpenAI

from ..config import validate_vision_config

logger = logging.getLogger(__name__)

PROCESS_SPEC_PROMPT = """\
你是一名机械加工工艺规程解析专家。请从输入的工艺过程卡、工艺规程 PDF 或图片中，准确提取所有"工序"信息，并按指定格式输出。

【提取目标】
只提取工序表中的内容，通常位于表格列：
- 序号
- 工种
- 工序内容

【输出格式】
必须只输出 JSON 数组，不要输出解释、不要输出 Markdown、不要输出多余文字。

格式如下（三段式，用 @ 分隔）：
[
  "0010@工种@工序内容",
  "0020@工种@工序内容",
  "0030@工种@工序内容"
]

工种字段规则：
- 直接读取工序表"工种"列的原始值，如：料、热、铣、数铣、车、钻、检、刻字 等。
- 如果该工序没有工种列，或工种单元格为空，则输出空字符串，格式为 "0010@@工序内容"。
- 不要推断或补充工种，只填写表中已有的值。
- 工种值本身不得包含 @ 符号。

【编号规则】
1. 原表中的序号如果是 1、2、3……，请转换为四位工序号：
   1 → 0010
   2 → 0020
   3 → 0030
   10 → 0100
2. 编号规则为：原序号 × 10，然后补足四位。
3. 如果原文已经是 0010、0020 这类编号，则保持原编号。
4. 不要遗漏跨页延续的工序。

【内容合并规则】
1. 每一道工序只输出一条字符串。
2. 工序内容如果分多行、多条 1）、2）、3），需要合并到同一条中。
3. 合并时保留原文含义，尽量保留原始数字、尺寸、公差、符号、孔数、螺纹规格等。
4. 可以去掉明显的换行和多余空格。
5. 工序内容中不要重复写入工种名称。
6. 不要提取材料栏、标题栏、签名栏、更改栏、页码、产品名称、产品代号等非工序内容。

【严格要求】
1. 不得编造图中没有的工序。
2. 不得改写技术参数。
3. 不得把 Φ、±、M、H7、h7、G1/2、N·m 等符号改错。
4. 如果某行被遮挡或无法识别，请输出：
   "编号@工种@【无法确认】原文可见部分"
5. 如果某道工序跨页显示，必须结合上下页合并。
6. 最终只输出 JSON 数组。

【示例】
输入中如果看到：
序号 1，工种：料，工序内容：备料：δ30×250×173=1。
序号 2，工种：热，工序内容：去应力退火。
序号 3，工种：铣，工序内容：
1）按工艺说明图，余量均分，铣方至尺寸27±0.1×246±0.1×169±0.1；
2）钻攻对6-M5螺纹孔，底孔深4.8；
3）锐边倒钝，去除毛刺。
序号 4，工种列为空，工序内容：按图检验。

则输出：
[
  "0010@料@备料：δ30×250×173=1。",
  "0020@热@去应力退火。",
  "0030@铣@按工艺说明图，余量均分，铣方至尺寸27±0.1×246±0.1×169±0.1；钻攻对6-M5螺纹孔，底孔深4.8；锐边倒钝，去除毛刺。",
  "0040@@按图检验。"
]

请优先读取表格线内"工种"和"工序内容"列，不要根据图纸内容自行生成加工路线；你只负责提取，不负责推理。\
"""


def _normalize_base_url(base_url: str | None) -> str | None:
    if not base_url:
        return None
    value = base_url.strip()
    if not value.startswith(("http://", "https://")):
        value = f"https://{value}"
    return value.rstrip("/")


class ProcessSpecAnalyzer:
    """
    调用与 VisionAnalyzer 相同的多模态 API，
    但 prompt 专门面向工艺规程表格，输出结构化工序行。
    """

    def __init__(self):
        config_error = validate_vision_config("doubao")
        if config_error:
            raise ValueError(f"视觉 API 未配置，无法解析工艺规程 PDF：{config_error}")

        self.api_key = os.getenv("VISION_API_KEY")
        self.base_url = _normalize_base_url(os.getenv("VISION_API_BASE"))
        model_param = os.getenv("VISION_MODEL_ID", "")
        self.model = model_param.replace("model_id=", "").strip()
        self.max_tokens = min(int(os.getenv("VISION_MAX_TOKENS", "4096")), 4096)
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def analyze_page(self, image_path: str, page_num: int = 0, total: int = 0) -> Dict[str, Any]:
        """分析工艺规程的单页图片（独立识别，不依赖其他页上下文）。"""
        logger.info("[ProcessSpec] 分析页面: %s", image_path)
        try:
            with open(image_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")

            if total > 1:
                user_text = f"请识别本页（第{page_num}/{total}页）工艺规程表格，按要求输出每道工序。如果某道工序跨页（本页开头是上一页末尾的延续），请输出完整的工序内容。"
            else:
                user_text = "请识别工艺规程表格，按要求输出每道工序。"

            response = self.client.chat.completions.create(
                model=self.model,
                temperature=0.1,
                messages=[
                    {"role": "system", "content": PROCESS_SPEC_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                            {"type": "text", "text": user_text},
                        ],
                    },
                ],
                max_tokens=self.max_tokens,
                timeout=600,
            )
            raw = response.choices[0].message.content or ""
            rows = _parse_process_rows(raw)
            logger.info("[ProcessSpec] 提取工序 %d 条 from %s", len(rows), image_path)
            return {"image_path": image_path, "raw": raw, "rows": rows, "ok": True}

        except Exception as exc:
            logger.error("[ProcessSpec] 分析失败 %s: %s", image_path, exc)
            return {"image_path": image_path, "raw": "", "rows": [], "ok": False, "error": str(exc)}

    def analyze_pages(self, image_paths: List[str]) -> List[Dict[str, Any]]:
        """逐页独立分析（不传跨页上下文，避免记忆锚定导致幻觉）。"""
        results = []
        total = len(image_paths)
        for i, path in enumerate(image_paths):
            result = self.analyze_page(path, page_num=i + 1, total=total)
            results.append(result)
            logger.info("[ProcessSpec] 进度 %d/%d", i + 1, total)
        return results


def _parse_process_rows(raw: str) -> List[str]:
    """
    从模型输出中提取合法工序行，输出三段式格式：'NNNN@工种@工序内容'。

    新 prompt 输出：["0010@工种@内容", "0020@@内容"]（工种可空）
    兼容旧格式：["0010@内容"]（两段式，工种置空）
    """
    import json as _json

    rows = []
    seen_codes: set = set()

    def _build_row(code: str, trade: str, content: str) -> str:
        return f"{code}@{trade.strip()}@{content.strip()}"

    # ── 优先尝试 JSON 数组解析 ────────────────────────────────────────────────
    stripped = raw.strip()
    json_match = re.search(r'\[[\s\S]*\]', stripped)
    if json_match:
        try:
            candidates = _json.loads(json_match.group(0))
            if isinstance(candidates, list):
                for item in candidates:
                    item = str(item).strip()
                    # 三段式：0010@工种@内容（工种可空 → 0010@@内容）
                    m3 = re.match(r'^(\d{4})@([^@]*)@(.+)$', item)
                    if m3:
                        code, trade, content = m3.group(1), m3.group(2), m3.group(3)
                    else:
                        # 兼容旧两段式：0010@内容
                        m2 = re.match(r'^(\d{4})@(.+)$', item)
                        if not m2:
                            continue
                        code, trade, content = m2.group(1), '', m2.group(2)
                    content = content.strip()
                    if not content or code in seen_codes:
                        continue
                    seen_codes.add(code)
                    rows.append(_build_row(code, trade, content))
                if rows:
                    return rows
        except (_json.JSONDecodeError, ValueError):
            pass

    # ── 回退：逐行正则匹配（兼容旧格式，工种置空） ───────────────────────────
    for line in raw.splitlines():
        line = line.strip().lstrip("-*•·\"'")
        if not line:
            continue
        m = re.match(r'^(\d{4})\s*[@:：\-\|\s]\s*(.+)$', line)
        if not m:
            continue
        code = m.group(1)
        content = m.group(2).strip().rstrip("\"',")
        if not content or code in seen_codes:
            continue
        seen_codes.add(code)
        rows.append(_build_row(code, '', content))
    return rows


def merge_multipage_rows(page_results: List[Dict[str, Any]]) -> List[str]:
    """
    合并多页结果，按工序号排序去重。
    同一工序号跨页重复出现时保留先出现的版本（通常是更完整的那页）。
    """
    seen_codes = set()
    all_rows: List[str] = []
    for result in page_results:
        for row in result.get("rows", []):
            code = row.split("@")[0] if "@" in row else ""
            if code and code in seen_codes:
                continue
            if code:
                seen_codes.add(code)
            all_rows.append(row)

    # 按工序号数值排序
    def _sort_key(row: str) -> int:
        m = re.match(r'^(\d{4})', row)
        return int(m.group(1)) if m else 9999

    return sorted(all_rows, key=_sort_key)
