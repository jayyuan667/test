#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ExpertJudge Step A 字段覆盖率验证脚本

用法（激活虚拟环境后）：
    python scripts/validate_expert_judge.py

从 db_data/kb_previews/ 加载已有 feature_report.json 作为输入，
不重新调用 VisionAnalyzer，只验证新版 ExpertJudge 的输出质量。
"""

import json
import os
import sys
from pathlib import Path

# 确保能 import backend 包
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 加载 .env
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from backend.pipeline.expert_judge import ExpertJudge, ExpertJudgmentOutput

# ── 关键字段，这些不应为 "未知" ──────────────────────────────────
# material 只在描述里含材料信息时才要求提取成功（旧版 VLM 描述无 【材料】 字段）
REQUIRED_KNOWN_ALWAYS = ["part_type", "dimensions"]
REQUIRED_NOT_NONE = [
    "part_number", "part_type", "material", "dimensions",
    "surface_treatment", "tolerances", "heat_treatment",
    "special_requirements", "confidence",
]

# 描述中含有这些关键词时，认为材料信息可提取
_MATERIAL_KEYWORDS = [
    "材料", "铝合金", "AL2A12", "2A12", "6061", "6063", "7075",
    "45钢", "40Cr", "Q235", "不锈钢", "钛合金", "铜合金", "黄铜",
]

PREVIEW_DIR = ROOT / "db_data" / "kb_previews"

# 选取 Y1–Y8 各一张（批次 060639）
TARGETS = [
    f"kb_kb_20260603_060639_641578_Y{i}" for i in range(1, 9)
]


def load_description(preview_name: str) -> dict | None:
    """从 feature_report.json 读取第一页的 description。"""
    path = PREVIEW_DIR / preview_name / "feature_report.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    pages = data.get("pages", [])
    if not pages:
        return None
    return {
        "description": pages[0].get("description", ""),
        "prefix_hint": data.get("prefix_hint", preview_name),
    }


def has_material_in_desc(description: str) -> bool:
    return any(kw in description for kw in _MATERIAL_KEYWORDS)


def check_output(name: str, out: ExpertJudgmentOutput, description: str = "") -> dict:
    issues = []
    for field in REQUIRED_NOT_NONE:
        val = getattr(out, field, None)
        if val is None:
            issues.append(f"{field}=None（字段缺失）")
    for field in REQUIRED_KNOWN_ALWAYS:
        val = getattr(out, field, "")
        if val in ("未知", "", None):
            issues.append(f"{field}='未知'（关键字段未提取）")
    # material 只在描述中有材料信息时才要求
    if has_material_in_desc(description) and out.material in ("未知", "", None):
        issues.append(f"material='未知'（描述含材料信息但未提取）")
    if out.confidence < 0.5:
        issues.append(f"confidence={out.confidence:.2f}（低于 0.5）")
    return {"name": name, "ok": len(issues) == 0, "issues": issues}


def main():
    judge = ExpertJudge()
    results = []
    passed = 0

    print("=" * 60)
    print("  ExpertJudge Step A 字段覆盖率验证")
    print("=" * 60)

    for target in TARGETS:
        data = load_description(target)
        if data is None:
            print(f"\n[SKIP] {target}：feature_report.json 不存在")
            continue

        prefix = data["prefix_hint"]
        desc = data["description"]
        if not desc.strip():
            print(f"\n[SKIP] {target}：description 为空")
            continue

        print(f"\n[测试] {prefix} ...")
        try:
            out = judge.analyze([{"description": desc}])
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({"name": prefix, "ok": False, "issues": [str(e)]})
            continue

        check = check_output(prefix, out, description=desc)
        results.append(check)

        # 打印结构化输出
        print(f"  零件类型  : {out.part_type}")
        print(f"  图号      : {out.part_number}")
        print(f"  材料      : {out.material}")
        print(f"  外形尺寸  : {out.dimensions}")
        print(f"  表面处理  : {out.surface_treatment}")
        print(f"  公差等级  : {out.tolerances}")
        print(f"  热处理    : {out.heat_treatment}")
        print(f"  特殊要求  : {out.special_requirements}")
        print(f"  置信度    : {out.confidence:.2f}")

        if check["ok"]:
            print(f"  结果      : ✓ PASS")
            passed += 1
        else:
            print(f"  结果      : ✗ FAIL")
            for issue in check["issues"]:
                print(f"              → {issue}")

    total = len(results)
    print("\n" + "=" * 60)
    print(f"  验证完成：{passed}/{total} 通过")
    if passed == total:
        print("  ✓ 全部通过，可以执行 Step B")
    else:
        print("  ✗ 存在失败项，请检查后再执行 Step B")
    print("=" * 60)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
