"""Small, side-effect-free runtime readiness check used by CI and operators."""

import json

from backend.services.capabilities import collect_capabilities
from backend.services.startup_checks import run_startup_checks


def main() -> int:
    startup = run_startup_checks()
    capabilities = collect_capabilities()
    report = {"startup": startup, "capabilities": capabilities}
    print(json.dumps(report, ensure_ascii=False))
    database_ready = bool(startup.get("database", {}).get("available"))
    return 0 if database_ready and capabilities.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
