from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.services.capabilities import collect_capabilities
from backend.services.startup_checks import run_startup_checks


def main() -> int:
    run_startup_checks()
    capabilities = collect_capabilities()
    print(json.dumps(capabilities, ensure_ascii=False, indent=2))
    optional_unavailable = [
        name
        for name in ("yolo", "creo", "freecad", "vision_api")
        if not capabilities[name]["available"]
    ]
    if optional_unavailable:
        print("可选能力不可用：" + ", ".join(optional_unavailable))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
