#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Unit tests for kb_import new format support (PNG/JPG image + TXT process).

Covers:
  1. _parse_txt_process   — pure-function behaviour
  2. _IMAGE_EXTS          — constant completeness
  3. _strip_all_exts      — handles image / txt extensions
  4. ZIP scan             — new formats routed to correct buckets
  5. Folder scan          — drawing_dir accepts images, craft_dir accepts TXT
  6. Stem pairing         — cross-format pairs resolve correctly
  7. PDF paths unchanged  — original drawing-PDF / craft-PDF logic still works

No API calls, no database, no VisionAnalyzer invoked.

Run with:
    python backend/test_kb_import_formats.py
"""
import os
import sys
import tempfile
import uuid
import zipfile
import io
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _mod():
    from backend.api import kb_import
    return kb_import


# ── 1. _parse_txt_process ─────────────────────────────────────────────────────

def test_parse_txt_basic():
    mod = _mod()
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", prefix="Y1_",
        encoding="utf-8", delete=False
    ) as f:
        f.write("0010 下料\n0020 车端面\n\n0030 铣槽\n")
        tmp = f.name
    try:
        r = mod._parse_txt_process(tmp)
        assert r["rows"] == ["0010 下料", "0020 车端面", "0030 铣槽"], r["rows"]
        assert r["text"] == "0010 下料\n0020 车端面\n0030 铣槽"
        assert r["source_kind"] == "txt"
        assert r["page_count"] == 0
        print("PASS: _parse_txt_process — rows, text, source_kind, page_count")
    finally:
        os.unlink(tmp)


def test_parse_txt_empty_file():
    mod = _mod()
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", encoding="utf-8", delete=False
    ) as f:
        f.write("\n\n   \n\t\n")
        tmp = f.name
    try:
        r = mod._parse_txt_process(tmp)
        assert r["rows"] == [], r["rows"]
        assert r["text"] == ""
        print("PASS: _parse_txt_process — blank-only file yields empty rows")
    finally:
        os.unlink(tmp)


def test_parse_txt_prefix_key_from_stem():
    mod = _mod()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = os.path.join(tmpdir, "XF25YS4101.txt")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("0010 下料\n")
        r = mod._parse_txt_process(tmp)
        assert r["prefix_key"] == "XF25YS4101", f"got {r['prefix_key']!r}"
        assert r["prefix_hint"] == "XF25YS4101"
        print(f"PASS: _parse_txt_process — prefix_key={r['prefix_key']!r}")


def test_parse_txt_nonexistent_returns_empty():
    mod = _mod()
    ghost = os.path.join(tempfile.gettempdir(), f"ghost_{uuid.uuid4()}.txt")
    r = mod._parse_txt_process(ghost)
    assert r["rows"] == []
    assert r["text"] == ""
    assert r["source_kind"] == "txt"
    print("PASS: _parse_txt_process — nonexistent file returns empty gracefully")


# ── 2. _IMAGE_EXTS ────────────────────────────────────────────────────────────

def test_image_exts_completeness():
    mod = _mod()
    for ext in (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"):
        assert ext in mod._IMAGE_EXTS, f"{ext} missing from _IMAGE_EXTS"
    for ext in (".pdf", ".txt", ".xlsx", ".prt", ".zip"):
        assert ext not in mod._IMAGE_EXTS, f"{ext} should NOT be in _IMAGE_EXTS"
    print(f"PASS: _IMAGE_EXTS = {sorted(mod._IMAGE_EXTS)}")


# ── 3. _strip_all_exts ────────────────────────────────────────────────────────

def test_strip_all_exts_image_and_txt():
    mod = _mod()
    cases = [
        ("Y1.png",          "Y1"),
        ("Y1.jpg",          "Y1"),
        ("Y1.jpeg",         "Y1"),
        ("Y1.txt",          "Y1"),
        ("Y1.pdf",          "Y1"),
        ("XF25YS4101.prt",  "XF25YS4101"),
        ("01.prt.5",        "01"),
        ("part.prt.12",     "part"),
    ]
    for filename, expected in cases:
        got = mod._strip_all_exts(filename)
        assert got == expected, f"_strip_all_exts({filename!r}) = {got!r}, want {expected!r}"
    print("PASS: _strip_all_exts — image, txt, prt multi-ext all stripped correctly")


# ── 4. ZIP scan classification ────────────────────────────────────────────────


def test_zip_scan_new_formats():
    mod = _mod()
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, "test.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            # drawing: 1 PDF + 1 PNG + 1 JPG
            zf.writestr("drawing/Y1.pdf", "drawing pdf")
            zf.writestr("drawing/Y2.png", "png bytes")
            zf.writestr("drawing/Y3.jpg", "jpg bytes")
            # craft: 1 PDF + 2 TXT
            zf.writestr("craft/Y1.pdf",   "craft pdf")
            zf.writestr("craft/Y2.txt",   "0010 下料\n0020 车端面\n")
            zf.writestr("craft/Y3.txt",   "0010 铣槽\n")
            # root-level image (not in drawing folder) → still image bucket
            zf.writestr("Y4.jpeg",        "jpeg bytes")
            # xlsx
            zf.writestr("data/Y5.xlsx",   "xlsx bytes")
            # prt
            zf.writestr("models/Y6.prt",  "prt bytes")

        extract_dir = os.path.join(tmpdir, "extract")
        os.makedirs(extract_dir)
        with zipfile.ZipFile(zip_path) as arc:
            arc.extractall(extract_dir)

        buckets = mod._scan_zip_dir(extract_dir)

    assert len(buckets["drawing_pdf"])   == 1,  f"drawing_pdf: {buckets['drawing_pdf']}"
    assert len(buckets["drawing_image"]) == 3,  f"drawing_image: {buckets['drawing_image']}"  # Y2.png, Y3.jpg, Y4.jpeg
    assert len(buckets["craft_pdf"])     == 1,  f"craft_pdf: {buckets['craft_pdf']}"
    assert len(buckets["craft_txt"])     == 2,  f"craft_txt: {buckets['craft_txt']}"
    assert len(buckets["xlsx"])          == 1,  f"xlsx: {buckets['xlsx']}"
    assert len(buckets["prt"])           == 1,  f"prt: {buckets['prt']}"
    print("PASS: ZIP scan — PNG/JPG/JPEG → drawing_image, TXT → craft_txt, existing buckets unchanged")


def test_zip_scan_image_outside_drawing_folder():
    """Images anywhere in the ZIP go to drawing_image, not just inside drawing/."""
    mod = _mod()
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, "test.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("Y1.png",            "root png")
            zf.writestr("subdir/Y2.jpg",     "subdir jpg")
            zf.writestr("drawing/Y3.png",    "drawing png")

        extract_dir = os.path.join(tmpdir, "extract")
        os.makedirs(extract_dir)
        with zipfile.ZipFile(zip_path) as arc:
            arc.extractall(extract_dir)

        buckets = mod._scan_zip_dir(extract_dir)

    assert len(buckets["drawing_image"]) == 3
    assert len(buckets["drawing_pdf"]) == 0
    print("PASS: ZIP scan — images at any folder depth land in drawing_image bucket")


def test_zip_scan_ignores_macos_metadata_files():
    """macOS __MACOSX / ._* metadata entries must not be treated as images."""
    mod = _mod()
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, "macos.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("new/drawing/Y1.png", "real png")
            zf.writestr("__MACOSX/new/drawing/._Y1.png", "appledouble metadata")
            zf.writestr("new/drawing/.DS_Store", "finder metadata")
            zf.writestr("new/craft/Y1.pdf", "craft pdf")

        extract_dir = os.path.join(tmpdir, "extract")
        os.makedirs(extract_dir)
        with zipfile.ZipFile(zip_path) as arc:
            arc.extractall(extract_dir)

        buckets = mod._scan_zip_dir(extract_dir)

    image_names = [os.path.basename(path) for path in buckets["drawing_image"]]
    assert image_names == ["Y1.png"], image_names
    assert len(buckets["craft_pdf"]) == 1
    print("PASS: ZIP scan — macOS metadata files ignored")


def test_zip_build_record_writes_enterprise_id(monkeypatch, tmp_path):
    """ZIP import records must inherit the importing user's enterprise_id."""
    mod = _mod()
    captured = {}

    def fake_build_feature_report(*_args, **_kwargs):
        return {"report_text": "【图号】Y1\n【材料】45钢", "pages": []}

    def fake_build_draft(prefix, source_name, source_type, source_text, content_rows):
        return {
            "prefix": prefix,
            "source_name": source_name,
            "source_type": source_type,
            "context": source_text,
            "process_list": content_rows,
        }

    def fake_upsert_record(draft, replace, library_key):
        captured["draft"] = dict(draft)
        captured["replace"] = replace
        captured["library_key"] = library_key

    monkeypatch.setattr(mod, "KB_PREVIEW_FOLDER", str(tmp_path / "previews"))
    monkeypatch.setattr(mod, "build_feature_report", fake_build_feature_report)
    monkeypatch.setattr(mod.library_api, "_build_draft", fake_build_draft)
    monkeypatch.setattr(mod.library_api, "_fetch_existing_record", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(mod.library_api, "_upsert_record", fake_upsert_record)
    monkeypatch.setattr(mod, "write_feature_report_json", lambda *_args, **_kwargs: str(tmp_path / "report.json"))

    item = mod._build_record_from_prefix(
        "batch-1",
        "Y1",
        [{"content": "0010@下料", "rows": ["0010@下料"], "sheet_name": "Y1.pdf", "xlsx_name": "Y1.pdf"}],
        [{"source_kind": "image", "text": "【图号】Y1", "source_path": str(tmp_path / "Y1.png"), "page_count": 1}],
        "replace",
        "my_db",
        enterprise_id=6,
    )

    assert item["status"] == "imported"
    assert captured["library_key"] == "my_db"
    assert captured["draft"]["enterprise_id"] == 6
    print("PASS: ZIP build record — enterprise_id propagated to library draft")


def test_zip_import_keeps_unmatched_pdf_bucket_separate(monkeypatch, tmp_path):
    """Final report must not overwrite unmatched_pdfs with unmatched_prts."""
    mod = _mod()
    zip_path = tmp_path / "empty.zip"
    with zipfile.ZipFile(zip_path, "w"):
        pass

    monkeypatch.setattr(mod, "OUTPUT_FOLDER", str(tmp_path / "output"))
    monkeypatch.setattr(mod, "UPLOAD_FOLDER", str(tmp_path / "upload"))
    monkeypatch.setattr(mod, "_scan_zip_dir", lambda _extract_dir: {
        "prt": [],
        "xlsx": [],
        "drawing_pdf": [],
        "craft_pdf": [],
        "drawing_image": [],
        "craft_txt": [],
    })
    monkeypatch.setattr(mod, "_ensure_import_tables", lambda: None)
    monkeypatch.setattr(mod, "_write_batch_summary", lambda _report: None)
    monkeypatch.setattr(mod, "mark_scope_batch", lambda *_args, **_kwargs: None)

    def fake_drain_visual(_futs, _visual_groups, report, _err_key):
        report["unmatched_pdfs"].append("missing-drawing.pdf")
        report["unmatched_prts"].append("missing-part.prt")

    monkeypatch.setattr(mod, "_drain_visual_futs", fake_drain_visual)

    report = mod.import_zip_knowledge(
        str(zip_path),
        "empty.zip",
        target_scope={
            "library_key": "public",
            "library_name": "Public",
            "vector_table": "vectors_v2",
            "feature_table": "drawing_features",
        },
    )

    assert report["unmatched_pdfs"] == ["missing-drawing.pdf"]
    assert report["unmatched_prts"] == ["missing-part.prt"]
    print("PASS: ZIP import — unmatched PDFs and PRTs stay in separate buckets")


def test_zip_scan_pdf_routing_unchanged():
    """Original rule: PDF in drawing/ → drawing_pdf, PDF elsewhere → craft_pdf."""
    mod = _mod()
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, "test.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("drawing/Y1.pdf", "drawing pdf")
            zf.writestr("drawings/Y2.pdf", "drawings pdf")
            zf.writestr("图纸/Y3.pdf",    "图纸 pdf")
            zf.writestr("craft/Y4.pdf",   "craft pdf")
            zf.writestr("Y5.pdf",         "root pdf")

        extract_dir = os.path.join(tmpdir, "extract")
        os.makedirs(extract_dir)
        with zipfile.ZipFile(zip_path) as arc:
            arc.extractall(extract_dir)

        buckets = mod._scan_zip_dir(extract_dir)

    assert len(buckets["drawing_pdf"]) == 3, f"Expected 3 drawing PDFs, got {buckets['drawing_pdf']}"
    assert len(buckets["craft_pdf"])   == 2, f"Expected 2 craft PDFs, got {buckets['craft_pdf']}"
    print("PASS: ZIP scan — original PDF routing (drawing/ vs craft/) unchanged")


def test_sample_zip_route_contains_valid_pdf_bytes():
    """Downloaded sample ZIP must not contain placeholder text named .pdf."""
    from backend.app import app
    import fitz

    response = app.test_client().get("/api/kb/sample_zip")
    assert response.status_code == 200

    with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
        pdf_names = [name for name in archive.namelist() if name.lower().endswith(".pdf")]
        assert pdf_names, "sample ZIP should include PDF examples"
        for name in pdf_names:
            payload = archive.read(name)
            assert payload.startswith(b"%PDF"), f"{name} is not a valid PDF payload"
            with fitz.open(stream=payload, filetype="pdf") as doc:
                assert doc.page_count >= 1, f"{name} should be openable by PyMuPDF"


# ── 5. Folder scan detects new formats ────────────────────────────────────────

def test_folder_scan_mixed_formats():
    mod = _mod()
    with tempfile.TemporaryDirectory() as tmpdir:
        d_dir = os.path.join(tmpdir, "drawing")
        c_dir = os.path.join(tmpdir, "craft")
        os.makedirs(d_dir); os.makedirs(c_dir)

        for name in ("Y1.pdf", "Y2.png", "Y3.jpeg", "Y4.tiff"):
            open(os.path.join(d_dir, name), "w").close()
        for name in ("Y1.pdf", "Y2.txt", "Y3.txt"):
            open(os.path.join(c_dir, name), "w").close()
        # xlsx in craft should be ignored
        open(os.path.join(c_dir, "Y4.xlsx"), "w").close()

        drawing_pdfs, craft_pdfs = mod._scan_folder_dirs(d_dir, c_dir)

    assert len(drawing_pdfs) == 4, f"drawing: {list(drawing_pdfs.keys())}"
    assert drawing_pdfs["Y1"].endswith(".pdf")
    assert drawing_pdfs["Y2"].endswith(".png")
    assert drawing_pdfs["Y3"].endswith(".jpeg")
    assert drawing_pdfs["Y4"].endswith(".tiff")

    assert len(craft_pdfs) == 3, f"craft: {list(craft_pdfs.keys())}"
    assert craft_pdfs["Y1"].endswith(".pdf")
    assert craft_pdfs["Y2"].endswith(".txt")
    assert craft_pdfs["Y3"].endswith(".txt")
    assert "Y4" not in craft_pdfs, "XLSX must not be picked up by folder import"
    print("PASS: folder scan — PDF+image in drawing_dir, PDF+TXT in craft_dir, XLSX ignored")


def test_folder_scan_pdf_only_unchanged():
    """Original PDF-only case must still work."""
    mod = _mod()
    with tempfile.TemporaryDirectory() as tmpdir:
        d_dir = os.path.join(tmpdir, "drawing")
        c_dir = os.path.join(tmpdir, "craft")
        os.makedirs(d_dir); os.makedirs(c_dir)

        for name in ("Y1.pdf", "Y2.pdf"):
            open(os.path.join(d_dir, name), "w").close()
        for name in ("Y1.pdf", "Y2.pdf"):
            open(os.path.join(c_dir, name), "w").close()

        drawing_pdfs, craft_pdfs = mod._scan_folder_dirs(d_dir, c_dir)

    assert set(drawing_pdfs.keys()) == {"Y1", "Y2"}
    assert set(craft_pdfs.keys())   == {"Y1", "Y2"}
    assert all(v.endswith(".pdf") for v in drawing_pdfs.values())
    assert all(v.endswith(".pdf") for v in craft_pdfs.values())
    print("PASS: folder scan — original PDF-only case unchanged")


# ── 6. Stem pairing across formats ────────────────────────────────────────────

def test_stem_pairing_cross_format():
    mod = _mod()
    should_pair = [
        ("Y1.png",  "Y1.txt"),
        ("Y1.png",  "Y1.pdf"),
        ("Y1.pdf",  "Y1.pdf"),
        ("Y1.pdf",  "Y1.txt"),
        ("Y1.jpeg", "Y1.txt"),
        ("Y1.jpg",  "Y1.pdf"),
    ]
    should_not_pair = [
        ("Y1.png",  "Y2.txt"),
        ("Y1.pdf",  "Y2.pdf"),
    ]
    for d, c in should_pair:
        d_stem = mod._strip_all_exts(d).upper()
        c_stem = mod._strip_all_exts(c).upper()
        assert d_stem == c_stem, f"Expected {d} + {c} to pair, stems: {d_stem!r} vs {c_stem!r}"
    for d, c in should_not_pair:
        d_stem = mod._strip_all_exts(d).upper()
        c_stem = mod._strip_all_exts(c).upper()
        assert d_stem != c_stem, f"Expected {d} + {c} NOT to pair"
    print("PASS: stem pairing — all 6 cross-format pairs match, 2 non-pairs correctly rejected")


# ── 7. PDF import helper functions (regression: verify pages → [] fix) ──────────

def test_parse_pdf_document_returns_rows_list(monkeypatch):
    """_parse_pdf_document must return rows=[] (single drawing analysis, not per-page)."""
    mod = _mod()
    from backend.pipeline import pdf_converter as pc_mod
    monkeypatch.setattr(pc_mod, "convert_pdf_to_images", lambda *a, **kw: ["/tmp/p1.png", "/tmp/p2.png"])
    monkeypatch.setattr(mod, "ensure_poppler_path", lambda: None)

    class FakeResult:
        def get(self, key, default=""):
            return "drawing desc"

    class FakeAnalyzer:
        def analyze_drawing(self, paths):
            return FakeResult()

    monkeypatch.setattr(mod, "_vision_analyzer", lambda: FakeAnalyzer())
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF-1.4")
        tmp = f.name
    try:
        r = mod._parse_pdf_document(tmp, tempfile.gettempdir())
        assert r["rows"] == [], f"expected [], got {r['rows']!r}"
        assert r["source_kind"] == "pdf"
        assert r["page_count"] == 2
        assert len(r["png_paths"]) == 2
        print("PASS: _parse_pdf_document — rows=[], source_kind=pdf, page_count from converter")
    finally:
        os.unlink(tmp)


def test_parse_drawing_pdf_for_visual_returns_rows_list(monkeypatch):
    """_parse_drawing_pdf_for_visual must return rows=[]."""
    mod = _mod()
    from backend.pipeline import pdf_converter as pc_mod
    monkeypatch.setattr(pc_mod, "convert_pdf_to_images", lambda *a, **kw: ["/tmp/d1.png"])
    monkeypatch.setattr(mod, "ensure_poppler_path", lambda: None)

    class FakeResult:
        def get(self, key, default=""):
            return "feature text"

    class FakeAnalyzer:
        def analyze_drawing(self, paths):
            return FakeResult()

    monkeypatch.setattr(mod, "_vision_analyzer", lambda: FakeAnalyzer())
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF-1.4")
        tmp = f.name
    try:
        r = mod._parse_drawing_pdf_for_visual(tmp, tempfile.gettempdir())
        assert r["rows"] == [], f"expected [], got {r['rows']!r}"
        assert r["source_kind"] == "drawing_pdf"
        print("PASS: _parse_drawing_pdf_for_visual — rows=[], source_kind=drawing_pdf")
    finally:
        os.unlink(tmp)


# ── runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_parse_txt_basic()
    test_parse_txt_empty_file()
    test_parse_txt_prefix_key_from_stem()
    test_parse_txt_nonexistent_returns_empty()
    test_image_exts_completeness()
    test_strip_all_exts_image_and_txt()
    test_zip_scan_new_formats()
    test_zip_scan_image_outside_drawing_folder()
    test_zip_scan_pdf_routing_unchanged()
    test_folder_scan_mixed_formats()
    test_folder_scan_pdf_only_unchanged()
    test_stem_pairing_cross_format()
    print("\nAll kb_import format tests passed.")
    print("Additional pytest-only tests: test_parse_pdf_document_returns_rows_list, test_parse_drawing_pdf_for_visual_returns_rows_list")
