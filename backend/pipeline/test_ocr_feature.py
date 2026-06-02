import pytest
from backend.pipeline.ocr_feature import classify_ocr_tokens


def test_classify_tongkong_plain_phi():
    result = classify_ocr_tokens(["24-Ø2.8", "20-Ø3"])
    assert result["通孔"] == ["24-Ø2.8", "20-Ø3"]
    assert result["螺纹孔"] == []
    assert result["沉孔沉槽"] == []


def test_classify_tongkong_with_keyword():
    result = classify_ocr_tokens(["4-M3通孔"])
    assert result["通孔"] == ["4-M3通孔"]
    assert result["螺纹孔"] == []


def test_classify_chenkong_angle():
    result = classify_ocr_tokens(["∅5.6×90°"])
    assert result["沉孔沉槽"] == ["∅5.6×90°"]


def test_classify_chenkong_keyword():
    result = classify_ocr_tokens(["沉孔深3"])
    assert result["沉孔沉槽"] == ["沉孔深3"]


def test_classify_luowen_with_depth():
    result = classify_ocr_tokens(["24-M3孔深6 底孔深7"])
    assert result["螺纹孔"] == ["24-M3孔深6 底孔深7"]
    assert result["通孔"] == []


def test_classify_luowen_螺纹孔_keyword():
    result = classify_ocr_tokens(["26-M2.5螺纹孔深8.1 底孔深9.1"])
    assert result["螺纹孔"] == ["26-M2.5螺纹孔深8.1 底孔深9.1"]


def test_classify_special_taper():
    result = classify_ocr_tokens(["∅80锥孔"])
    assert result["特殊孔"] == ["∅80锥孔"]


def test_classify_special_keywords():
    for kw in ["异形孔深4", "定位孔∅6", "销孔H7"]:
        result = classify_ocr_tokens([kw])
        assert result["特殊孔"] == [kw], f"expected 特殊孔 for: {kw}"


def test_classify_priority_chen_over_luowen():
    result = classify_ocr_tokens(["∅5.6×90°"])
    assert result["沉孔沉槽"] == ["∅5.6×90°"]
    assert result["螺纹孔"] == []


def test_classify_empty_lines_ignored():
    result = classify_ocr_tokens(["", "  ", "abc"])
    assert result["通孔"] == []
    assert result["螺纹孔"] == []
    assert result["沉孔沉槽"] == []
    assert result["特殊孔"] == []


def test_classify_phi_variants_normalized():
    result = classify_ocr_tokens(["12-φ3.2", "8-∅4"])
    assert len(result["通孔"]) == 2


from backend.pipeline.ocr_feature import merge_ocr_into_field


def test_merge_appends_new_ocr_item():
    result = merge_ocr_into_field("24-Ø2.8；20-Ø3", ["8-Ø4"])
    assert "8-Ø4" in result
    assert "24-Ø2.8" in result


def test_merge_dedup_same_spec():
    result = merge_ocr_into_field("24-Ø2.8；20-Ø3", ["24-Ø2.8"])
    assert result.count("24-Ø2.8") == 1


def test_merge_dedup_phi_variant():
    # VLM has "24-Ø2.8", OCR finds "24-φ2.8" — normalized same, not appended
    result = merge_ocr_into_field("24-Ø2.8", ["24-φ2.8"])
    assert result.count("2.8") == 1


def test_merge_vlm_wu_replaced_by_ocr():
    result = merge_ocr_into_field("无", ["24-Ø2.8", "20-Ø3"])
    assert "24-Ø2.8" in result
    assert "20-Ø3" in result
    assert "无" not in result


def test_merge_ocr_empty_no_change():
    result = merge_ocr_into_field("24-Ø2.8", [])
    assert result == "24-Ø2.8"


def test_merge_both_empty_returns_wu():
    result = merge_ocr_into_field("无", [])
    assert result == "无"
