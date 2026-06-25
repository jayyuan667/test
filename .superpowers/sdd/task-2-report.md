# Task 2 Report: GPU Service — BinaryChainDetector + FastAPI `/detect`

## Status

- **Complete.** All code written, validated on local environment, committed.

## Commit

```
a9268c7 feat: add GPU detection service with BinaryChainDetector + /detect endpoint
```

## Files Created

| File | Lines | Purpose |
|------|-------|---------|
| `gpu_service/chain_detector.py` | 113 | `BinaryChainDetector` class — threadsafe chain detection via 7 binary YOLO models |
| `gpu_service/main.py` | 190 | FastAPI app — `GET /health` (no auth) and `POST /detect` (Bearer auth) |
| `gpu_service/requirements.txt` | 4 | Dependencies: ultralytics, fastapi, uvicorn, pillow |

## Validation Summary

1. **Dependency install:** Succeeded with `python3.11` (Homebrew `/opt/homebrew/bin/python3.11`). Torch 2.12.1, ultralytics 8.4.77, fastapi 0.138.0.
2. **Token enforcement:** Confirmed — empty `YOLO_SERVICE_TOKEN` raises `RuntimeError` at module import.
3. **BinaryChainDetector construction:** Cannot test locally — no `models_binary/binary_*.pt` files present. Produces expected `FileNotFoundError`. Requires liu4th (or environment with actual model weights) for full validation.
4. **Endpoints:** Import structure verified; `GET /health` and `POST /detect` route syntax confirmed.

Full validation on liu4th requires:
```bash
cd gpu_service
YOLO_SERVICE_TOKEN=<actual_token> YOLO_DEVICE=cpu python3.11 -c "
from chain_detector import BinaryChainDetector
import numpy as np
d = BinaryChainDetector('./models_binary', 'cpu')
print(f'Loaded {len(d.models)} models')
result = d.detect(np.zeros((640,640,3), dtype=np.uint8))
print(f'Blank image detections: {len(result)} (expected 0)')
"
```

## Concerns

1. **Python 3.9 on PATH** — the system default `python3` is 3.9.6. The plan requires Python 3.11+. A Homebrew 3.11 exists at `/opt/homebrew/bin/python3.11`. The service should be launched explicitly with `python3.11` (or the liu4th default), and production should pin `.python-version` or use a venv.
2. **No .pt model files locally** — full integration test requires liu4th or a test environment with the 7 binary model weights. Cannot confirm `YOLO(path)` succeeds until then.
3. **Torch CPU-only on macOS** — `cuda:0` will fail on this Mac (no GPU). Service defaults to `cuda:0`; liu4th must set `YOLO_DEVICE` appropriately, or the fastapi app will crash at `YOLO(path).to(device)`.
