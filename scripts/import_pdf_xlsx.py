#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
批量入库脚本 — PDF图纸 + XLSX工艺
======================================
将 ZIP 包（含 PDF 图纸 + XLSX 工艺文件）批量导入知识库（2d-v.db）。

用法
----
    python scripts/import_pdf_xlsx.py <zip文件路径> [选项]

选项
----
    --library-key  KEY    目标工艺库标识（已有库）
    --library-name NAME   新建库时使用的显示名称
    --conflict     MODE   冲突处理：replace（覆盖）/ keep（保留旧）/ skip（跳过）
                          默认 replace
    --dry-run             仅扫描配对情况，不写入数据库
    --env          PATH   .env 文件路径（默认：项目根目录 .env）
    --db           PATH   数据库路径（默认：db_data/2d-v.db）

ZIP 结构示例
-----------
    archive.zip
    ├── drawing/          ← PDF 图纸（必须放在 drawing/drawings/图纸/ 子目录）
    │   ├── Y1.pdf
    │   └── Y2.pdf
    └── craft/            ← XLSX 工艺（可放任意位置，按文件名与图纸配对）
        ├── Y1.xlsx
        └── Y2.xlsx

配对规则：图纸 PDF 与工艺 XLSX 去掉所有扩展名后的文件名相同即可配对，
大小写不敏感。例如 Y1.pdf ↔ Y1.xlsx，01.prt.5 ↔ 01.xlsx。
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# ── 项目根目录加入 sys.path ──────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _load_dotenv(env_path: str) -> None:
    """加载 .env 文件；优先用 python-dotenv，没有则手动解析。"""
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path, override=False)
        return
    except ImportError:
        pass
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            v = v.strip().strip("\"'")
            if k and k not in os.environ:
                os.environ[k] = v


def _setup_env(env_path: str, db_path: str) -> None:
    _load_dotenv(env_path)
    # FEATURIZER_BASE_DIR 决定 vector_map_rag.py 中 DB_PATH 的解析位置
    if not os.environ.get("FEATURIZER_BASE_DIR"):
        os.environ["FEATURIZER_BASE_DIR"] = str(ROOT)
    # 如果显式传了 --db，覆盖默认路径（通过环境变量传递给 vector_map_rag）
    if db_path:
        os.environ["_OVERRIDE_DB_PATH"] = os.path.abspath(db_path)


def _patch_db_path(db_path: str) -> None:
    """如果指定了自定义 DB 路径，在导入 vector_map_rag 后动态覆盖。"""
    if not db_path:
        return
    try:
        import backend.vector_map_rag as _rag
        _rag.DB_PATH = os.path.abspath(db_path)
        import backend.api.library as _lib
        # library.py 直接从 vector_map_rag 引用 DB_PATH，需要同步
        import backend.api.kb_import as _kb
    except Exception:
        pass


def _print_report(report: dict, dry_run: bool) -> None:
    s = report.get("summary", {})
    lib = report.get("target_library", {})
    print()
    print("=" * 60)
    print("  入库完成" if not dry_run else "  扫描完成（dry-run，未写入数据库）")
    print("=" * 60)
    print(f"  批次 ID    : {report.get('batch_id', '-')}")
    print(f"  目标库     : {lib.get('library_name', '-')}  [{lib.get('library_key', '-')}]")
    print(f"  ZIP 文件   : {report.get('zip_name', '-')}")
    print(f"  扫描文件数 : {s.get('total_files', 0)}")
    print(f"    图纸 PDF : {s.get('drawing_pdf_count', 0)}")
    print(f"    工艺 XLSX: {s.get('xlsx_count', 0)}")
    print(f"    工艺 PDF : {s.get('craft_pdf_count', 0)}")
    print(f"    图片     : {s.get('image_count', 0)}")
    print(f"    工艺 TXT : {s.get('txt_count', 0)}")
    print("-" * 60)
    print(f"  配对成功   : {s.get('matched_pairs', 0)}")
    print(f"  已导入     : {s.get('imported_count', 0)}")
    print(f"  已跳过     : {s.get('skipped_count', 0)}")
    print(f"  错误数     : {s.get('error_count', 0)}")

    unmatched_d = report.get("unmatched_xlsx", [])   # 无对应图纸的工艺
    unmatched_v = report.get("unmatched_drawings", [])  # 无对应工艺的图纸（folder路径使用此键）
    if unmatched_d:
        print()
        print(f"  未配对工艺（{len(unmatched_d)} 个，缺少对应图纸）：")
        for name in unmatched_d[:20]:
            print(f"    - {name}")
        if len(unmatched_d) > 20:
            print(f"    ... 共 {len(unmatched_d)} 个")

    errors = report.get("errors", [])
    if errors:
        print()
        print(f"  错误详情（{len(errors)} 条）：")
        for e in errors[:20]:
            name = (
                e.get("pdf_name") or e.get("xlsx_name") or
                e.get("stem_key") or e.get("image_name") or
                e.get("txt_name") or "?"
            )
            print(f"    [{name}] {e.get('error', '')}")
        if len(errors) > 20:
            print(f"    ... 共 {len(errors)} 条")

    pairs = report.get("matched_pairs", [])
    if pairs:
        print()
        print(f"  配对明细（{len(pairs)} 条）：")
        col_w = 20
        print(f"  {'图号':<{col_w}} {'状态':<8} {'图纸':<25} {'工艺'}")
        print(f"  {'-'*col_w} {'-'*7} {'-'*24} {'-'*20}")
        for p in pairs:
            pdf = ", ".join(p.get("pdf_names", [])) or "-"
            xlsx = ", ".join(p.get("xlsx_names", [])) or "-"
            print(f"  {p.get('prefix',''):<{col_w}} {p.get('status',''):<8} {pdf:<25} {xlsx}")

    report_path = report.get("report_path")
    if report_path:
        print()
        print(f"  详细报告   : {report_path}")
    print("=" * 60)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="批量导入 PDF图纸 + XLSX工艺 到知识库",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("zip_file", help="ZIP 包路径")
    parser.add_argument("--library-key",  default="", help="目标工艺库标识（已有库）")
    parser.add_argument("--library-name", default="", help="新建库时的显示名称")
    parser.add_argument(
        "--conflict",
        choices=["replace", "keep", "skip"],
        default="replace",
        help="冲突处理方式（默认 replace）",
    )
    parser.add_argument(
        "--library-mode",
        choices=["private_seed_public", "private_empty", "public"],
        default="private_seed_public",
        help="新建库模式（默认 private_seed_public）",
    )
    parser.add_argument("--dry-run", action="store_true", help="仅扫描配对，不写入数据库")
    parser.add_argument(
        "--env",
        default=str(ROOT / ".env"),
        help=f"env 文件路径（默认 {ROOT / '.env'}）",
    )
    parser.add_argument(
        "--db",
        default="",
        help="数据库路径（默认 db_data/2d-v.db）",
    )
    args = parser.parse_args()

    zip_path = os.path.abspath(args.zip_file)
    if not os.path.isfile(zip_path):
        print(f"错误：找不到文件 {zip_path}", file=sys.stderr)
        return 1

    # ── 加载环境变量 ──────────────────────────────────────────────────────────
    _setup_env(args.env, args.db)

    # ── 导入后端模块（必须在 env 设置后） ────────────────────────────────────
    try:
        from backend.api.kb_import import import_zip_knowledge, _scan_zip_dir
    except ImportError as e:
        print(f"错误：无法加载后端模块，请确认在项目根目录运行并已安装依赖。\n{e}", file=sys.stderr)
        return 1

    if args.db:
        _patch_db_path(args.db)

    # ── dry-run：只扫描，不导入 ───────────────────────────────────────────────
    if args.dry_run:
        import zipfile, tempfile
        print(f"[dry-run] 解压 {zip_path} ...")
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                with zipfile.ZipFile(zip_path) as arc:
                    arc.extractall(tmpdir)
            except zipfile.BadZipFile as e:
                print(f"错误：ZIP 文件损坏 — {e}", file=sys.stderr)
                return 1
            buckets = _scan_zip_dir(tmpdir)

        print()
        print("扫描结果：")
        total = sum(len(v) for v in buckets.values())
        print(f"  图纸 PDF  : {len(buckets['drawing_pdf'])} 个")
        print(f"  工艺 XLSX : {len(buckets['xlsx'])} 个")
        print(f"  工艺 PDF  : {len(buckets['craft_pdf'])} 个")
        print(f"  图片      : {len(buckets['drawing_image'])} 个")
        print(f"  工艺 TXT  : {len(buckets['craft_txt'])} 个")
        print(f"  PRT 模型  : {len(buckets['prt'])} 个")
        print(f"  合计      : {total} 个文件")

        # 简单配对预览
        from backend.api.kb_import import _strip_all_exts
        drawings = {_strip_all_exts(os.path.basename(p)).upper(): p for p in buckets["drawing_pdf"]}
        crafts   = {_strip_all_exts(os.path.basename(p)).upper(): p for p in buckets["xlsx"]}
        paired   = sorted(drawings.keys() & crafts.keys())
        only_d   = sorted(drawings.keys() - crafts.keys())
        only_c   = sorted(crafts.keys() - drawings.keys())
        print()
        print(f"配对预览（图纸PDF ↔ XLSX）：配对 {len(paired)} 对，仅有图纸 {len(only_d)} 个，仅有工艺 {len(only_c)} 个")
        if paired:
            print("  已配对：", ", ".join(paired[:20]), ("..." if len(paired) > 20 else ""))
        if only_d:
            print("  无工艺：", ", ".join(only_d[:10]), ("..." if len(only_d) > 10 else ""))
        if only_c:
            print("  无图纸：", ", ".join(only_c[:10]), ("..." if len(only_c) > 10 else ""))
        return 0

    # ── 正式导入 ──────────────────────────────────────────────────────────────
    zip_name = os.path.basename(zip_path)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始导入 {zip_name} ...")
    print(f"  冲突策略 : {args.conflict}")
    print(f"  工艺库   : {args.library_key or '（自动创建）'}")

    try:
        report = import_zip_knowledge(
            zip_path=zip_path,
            zip_name=zip_name,
            conflict_mode=args.conflict,
            library_mode=args.library_mode,
            library_name=args.library_name,
            library_key=args.library_key,
        )
    except Exception as exc:
        print(f"\n错误：导入失败 — {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1

    _print_report(report, dry_run=False)
    return 0 if report.get("summary", {}).get("error_count", 0) == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
