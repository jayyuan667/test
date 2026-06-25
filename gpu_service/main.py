"""GPU YOLO detection service — FastAPI.

Environment:
  YOLO_MODEL_DIR      path to binary_*.pt files (default ./models_binary)
  YOLO_DEVICE         torch device (default cuda:0)
  YOLO_SERVICE_TOKEN  shared secret for /detect auth (required — refuses startup if empty)
  YOLO_MAX_IMAGE_MB   max single image size in MB (default 20)
"""
import base64
import io
import os

import numpy as np
from fastapi import FastAPI, Header, HTTPException
from PIL import Image

from chain_detector import BinaryChainDetector

MODEL_DIR  = os.getenv("YOLO_MODEL_DIR", "./models_binary")
DEVICE     = os.getenv("YOLO_DEVICE", "cuda:0")
TOKEN      = os.getenv("YOLO_SERVICE_TOKEN", "")
if not TOKEN:
    raise RuntimeError("YOLO_SERVICE_TOKEN must be set — refusing to start without auth")

MAX_IMG_MB = int(os.getenv("YOLO_MAX_IMAGE_MB", "20"))

app = FastAPI(title="YOLO Binary Chain Detector")

# Load all 7 models at startup (blocking; takes ~10-30s)
detector = BinaryChainDetector(MODEL_DIR, DEVICE)


@app.get("/health")
def health():
    gpu_ok = False
    if DEVICE.startswith("cuda"):
        try:
            import torch
            gpu_ok = torch.cuda.is_available()
        except ImportError:
            pass
    return {
        "ok": True,
        "models_loaded": len(detector.models),
        "gpu_available": gpu_ok,
        "device": DEVICE,
    }


@app.post("/detect")
def detect(body: dict, authorization: str = Header(None)):
    # Auth — TOKEN is guaranteed non-empty (checked at startup)
    expected = f"Bearer {TOKEN}"
    if authorization != expected:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing authorization token",
        )

    name = body.get("name", "unknown.png")
    raw = base64.b64decode(body["data"])

    # Size limit
    if len(raw) > MAX_IMG_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"Image exceeds {MAX_IMG_MB}MB limit",
        )

    img = Image.open(io.BytesIO(raw)).convert("RGB")
    detections = detector.detect(np.array(img))
    return {"name": name, "detections": detections}
