# -*- coding: utf-8 -*-
"""GPU YOLO 服务 HTTP 客户端 — 逐页调用 /detect 端点。
"""
import base64
from pathlib import Path

import httpx


class YOLOServiceClient:
    """Thin HTTP wrapper around GPU YOLO detection service."""

    def __init__(self, base_url: str, token: str, timeout: float = 15):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._headers = {}
        if token:
            self._headers["Authorization"] = f"Bearer {token}"

    def health(self) -> dict:
        """GET /health — check service availability."""
        r = httpx.get(f"{self.base_url}/health", timeout=5)
        r.raise_for_status()
        return r.json()

    def detect(self, image_path: str) -> dict:
        """POST /detect — single-page chain inference.

        Returns: {"name": "page_1.png", "detections": [...]}
        """
        name = Path(image_path).name
        data = Path(image_path).read_bytes()

        r = httpx.post(
            f"{self.base_url}/detect",
            json={
                "name": name,
                "data": base64.b64encode(data).decode(),
            },
            headers=self._headers,
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()
