import pytest

from backend.pipeline import pdf_converter


def test_converter_uses_pymupdf_provider(monkeypatch, tmp_path):
    from backend.services import capabilities
    monkeypatch.setattr(
        capabilities,
        "inspect_pdf_capability",
        lambda: {"available": True, "provider": "pymupdf", "reason": ""},
    )
    monkeypatch.setattr(pdf_converter, "_convert_with_fitz", lambda *args: ["page.png"])
    assert pdf_converter.convert_pdf_to_images("a.pdf", str(tmp_path)) == ["page.png"]


def test_converter_uses_poppler_provider(monkeypatch, tmp_path):
    from backend.services import capabilities
    monkeypatch.setattr(
        capabilities,
        "inspect_pdf_capability",
        lambda: {"available": True, "provider": "poppler", "reason": ""},
    )
    monkeypatch.setattr(pdf_converter, "_convert_with_pdf2image", lambda *args: ["page.png"])
    assert pdf_converter.convert_pdf_to_images("a.pdf", str(tmp_path)) == ["page.png"]


def test_converter_raises_actionable_error_without_provider(monkeypatch, tmp_path):
    from backend.services import capabilities
    monkeypatch.setattr(
        capabilities,
        "inspect_pdf_capability",
        lambda: {"available": False, "provider": None, "reason": "run uv sync"},
    )
    with pytest.raises(pdf_converter.PDFConversionUnavailable, match="uv sync"):
        pdf_converter.convert_pdf_to_images("a.pdf", str(tmp_path))
