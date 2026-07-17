# -*- coding: utf-8 -*-
"""PDF to PNG conversion step.

Tries PyMuPDF (fitz) first — no Poppler required.
Falls back to pdf2image + Poppler if fitz is unavailable.
"""

import os
from typing import List, Callable, Optional


def _convert_with_fitz(pdf_path: str, output_dir: str, dpi: int, on_image_ready) -> List[str]:
    import fitz  # PyMuPDF
    doc = fitz.open(pdf_path)
    scale = dpi / 72.0
    mat = fitz.Matrix(scale, scale)
    png_paths = []
    total = len(doc)
    for i, page in enumerate(doc):
        pix = page.get_pixmap(matrix=mat)
        png_path = os.path.join(output_dir, f"page_{i + 1}.png")
        pix.save(png_path)
        png_paths.append(png_path)
        if on_image_ready:
            on_image_ready(i + 1, total, png_path)
    doc.close()
    return png_paths


def _convert_with_pdf2image(pdf_path: str, output_dir: str, dpi: int, on_image_ready) -> List[str]:
    from pdf2image import convert_from_path
    from ..config import ensure_poppler_path
    ensure_poppler_path()
    images = convert_from_path(pdf_path, dpi=dpi)
    png_paths = []
    total = len(images)
    for i, image in enumerate(images):
        png_path = os.path.join(output_dir, f"page_{i + 1}.png")
        image.save(png_path, "PNG")
        png_paths.append(png_path)
        if on_image_ready:
            on_image_ready(i + 1, total, png_path)
    return png_paths


class PDFConversionUnavailable(RuntimeError):
    pass


def convert_pdf_to_images(
    pdf_path: str,
    output_dir: str,
    dpi: int = 200,
    on_image_ready: Optional[Callable[[int, int, str], None]] = None,
) -> List[str]:
    """Convert PDF file to PNG images.

    Uses PyMuPDF if available (no Poppler needed), otherwise falls back to pdf2image.
    """
    from backend.services.capabilities import inspect_pdf_capability

    os.makedirs(output_dir, exist_ok=True)
    capability = inspect_pdf_capability()
    provider = capability.get("provider")
    if provider == "pymupdf":
        return _convert_with_fitz(pdf_path, output_dir, dpi, on_image_ready)
    if provider == "poppler":
        return _convert_with_pdf2image(pdf_path, output_dir, dpi, on_image_ready)
    raise PDFConversionUnavailable(capability.get("reason") or "PDF转换不可用")
