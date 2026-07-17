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
        import time as _time

        name = Path(image_path).name
        data = Path(image_path).read_bytes()
        payload = {
            "name": name,
            "data": base64.b64encode(data).decode(),
        }

        # Retry transient connection errors (e.g. brief tunnel drop)
        last_exc = None
        for attempt in range(3):
            try:
                r = httpx.post(
                    f"{self.base_url}/detect",
                    json=payload,
                    headers=self._headers,
                    timeout=self.timeout,
                )
                r.raise_for_status()
                return r.json()
            except (httpx.ConnectError, httpx.RemoteProtocolError,
                    httpx.TransportError) as exc:
                last_exc = exc
                _time.sleep(1 << attempt)  # 1s, 2s, 4s backoff
        raise last_exc  # type: ignore[misc]
