from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SELFTEST_DIR = Path(__file__).resolve().parent / "kb_import_selftest"
ZIP_PATH = SELFTEST_DIR / "kb_import_selftest.zip"


def ensure_fixtures() -> None:
    if ZIP_PATH.exists():
        return
    generator = ROOT / "scripts" / "generate_kb_import_selftest.py"
    subprocess.check_call([sys.executable, str(generator)], cwd=str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ZIP KB import self-test")
    parser.add_argument("--vision-mode", default=os.getenv("VISION_MODE", "local"), choices=["local", "doubao"], help="Vision mode used during PDF analysis")
    parser.add_argument("--conflict-mode", default="replace", choices=["replace", "keep", "skip"], help="Conflict handling mode")
    args = parser.parse_args()

    os.environ["VISION_MODE"] = args.vision_mode
    ensure_fixtures()

    sys.path.insert(0, str(ROOT))
    from backend.api.kb_import import import_zip_knowledge

    report = import_zip_knowledge(str(ZIP_PATH), ZIP_PATH.name, conflict_mode=args.conflict_mode)

    summary = report.get("summary", {})
    print("=== ZIP KB Import Self-Test ===")
    print(f"Zip: {ZIP_PATH}")
    print(f"Batch: {report.get('batch_id')}")
    print(f"Mode: vision={args.vision_mode}, conflict={args.conflict_mode}")
    print(
        "Summary: "
        f"pairs={summary.get('matched_pairs', 0)}, "
        f"imported={summary.get('imported_count', 0)}, "
        f"skipped={summary.get('skipped_count', 0)}, "
        f"errors={summary.get('error_count', 0)}, "
        f"pdf={summary.get('pdf_count', 0)}, "
        f"xlsx={summary.get('xlsx_count', 0)}"
    )
    print(f"Report: {report.get('report_path')}")
    if report.get("errors"):
        print("Errors:")
        for item in report["errors"]:
            print(f"- {item.get('pdf_name')} + {item.get('xlsx_name')}: {item.get('error')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
