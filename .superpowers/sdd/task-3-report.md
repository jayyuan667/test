# Task 3 Report: YOLOServiceClient HTTP Client

## Changes Made

### 1. `backend/config.py` — Added YOLO GPU service configuration (lines 213-216)
- **Added:** `YOLO_SERVICE_URL` (default `http://127.0.0.1:8000`)
- **Added:** `YOLO_SERVICE_TOKEN` (default `""`)
- **Added:** `YOLO_SERVICE_TIMEOUT` (default `15`)
- Existing `YOLO_WEIGHT_PATH` / `YOLO_ONNX_PATH` kept unchanged

### 2. `backend/pipeline/yolo_service_client.py` — New file
- **`YOLOServiceClient(base_url, token, timeout=15)`** — HTTP client constructor
- **`client.health() -> dict`** — GET /health with 5s timeout
- **`client.detect(image_path: str) -> dict`** — POST /detect with base64-encoded image, returns `{name, detections}`

## Verification

- **Unit test (health):** Correct URL and timeout — PASS
- **Unit test (detect):** Sends Authorization header, returns correct name — PASS

## Commit

`70618f3` — `feat: add YOLOServiceClient for per-page GPU service calls`
