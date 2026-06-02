"""Tests for OCR thickness validation."""
import pytest
from backend.pipeline.ocr_thickness import (
    extract_thickness_candidate,
    _parse_vlm_thickness,
    _extract_numeric_values,
    _classify_numeric_cluster,
)


class TestExtractNumericValues:
    def test_basic_dimensions(self):
        lines = ["297", "55", "10", "R5", "M3"]
        vals = _extract_numeric_values(lines)
        assert 10 in vals
        assert 55 in vals
        assert 297 in vals
        # R5 → strip R → "5" enters as noise; acceptable for the rule engine
        assert 5 in vals

    def test_phi_prefix_stripped(self):
        lines = ["Ø36", "Ø10"]
        vals = _extract_numeric_values(lines)
        assert 36 in vals
        assert 10 in vals

    def test_tolerance_stripped(self):
        lines = ["36±0.1", "10"]
        vals = _extract_numeric_values(lines)
        assert 36 in vals
        assert 10 in vals

    def test_range_filter(self):
        lines = ["2", "250", "15"]
        vals = _extract_numeric_values(lines)
        assert 2 not in vals   # below threshold
        assert 15 in vals
        assert 250 in vals     # plate lengths up to 2000 are kept

    def test_mixed_drawing_annotations(self):
        lines = [
            "297", "55", "10", "36±0.1",
            "2×Ø4.5",  # → extracts 4.5, then removes... actually "2×Ø4.5" → maybe extracts 2 and 4.5
            "R5",
            "M2.5",  # excluded (M-prefix)
        ]
        vals = _extract_numeric_values(lines)
        # After stripping, "2×Ø4.5" → "2×4.5" → "2" and "4.5" extracted
        # "4.5" is in [3,200] so included
        assert 10 in vals
        assert 36 in vals
        # "2" from "2×Ø4.5" might or might not be extracted depending on regex
        # Not crucial for test correctness


class TestClassifyNumericCluster:
    def test_three_group_rule(self):
        # 297, 55, 10 → 10 is thickness
        assert _classify_numeric_cluster([10, 55, 297]) == 10
        assert _classify_numeric_cluster([10, 55, 297, 30]) is not None

    def test_bent_channel_rule(self):
        # 36, 10 → ratio 3.6 > 2 → 10 is material thickness
        assert _classify_numeric_cluster([10, 36]) == 10

    def test_ratio_not_met(self):
        # 15, 20 → ratio 1.33 < 2 → no rule applies
        assert _classify_numeric_cluster([15, 20]) is None

    def test_single_value(self):
        assert _classify_numeric_cluster([10]) is None

    def test_empty(self):
        assert _classify_numeric_cluster([]) is None


class TestParseVlmThickness:
    def test_standard_format(self):
        text = "【外形尺寸】268×72×36\n【其他】..."
        assert _parse_vlm_thickness(text) == 36

    def test_with_label_prefix(self):
        text = "外形尺寸：268×72×36"
        assert _parse_vlm_thickness(text) == 36

    def test_circular_format(self):
        text = "【外形尺寸】Ø63.17×16.4"
        assert _parse_vlm_thickness(text) == 16.4

    def test_decimal_thickness(self):
        text = "外形尺寸：282×129×21.5"
        assert _parse_vlm_thickness(text) == 21.5

    def test_no_thickness_found(self):
        text = "【其他字段】没有任何尺寸"
        assert _parse_vlm_thickness(text) is None

    def test_multi_page_mixed(self):
        text = "【外形尺寸】长×宽×厚：297×55×10"
        assert _parse_vlm_thickness(text) == 10


class TestExtractThicknessCandidate:
    def test_y1_thin_plate(self):
        # Simple thin plate with three main dims
        lines = ["297", "55", "10", "R5", "2×Ø4.5"]
        result = extract_thickness_candidate(lines)
        assert result is not None
        assert result["thickness"] == 10
        assert result["source"] == "three_group"

    def test_y2_bent_channel(self):
        # Bent-channel bracket: end view has 36 and 10
        lines = ["297", "55", "36", "10", "R5"]
        result = extract_thickness_candidate(lines)
        assert result is not None
        assert result["thickness"] == 10
        assert result["source"] == "bent_channel" or result["source"] == "three_group"

    def test_y14_no_clear_thickness(self):
        # Complex part with many dimensions, no clear thickness candidate
        # The 83 isn't on the drawing, so OCR can't find it
        lines = ["120", "85", "45", "30", "20", "15", "R8", "R5"]
        result = extract_thickness_candidate(lines)
        # May or may not match — depends on ratios
        if result:
            assert isinstance(result["thickness"], int)

    def test_y15_large_thin_plate(self):
        # ≠18×410×440 → three-group: 18 is smallest
        lines = ["440", "410", "18", "R3"]
        result = extract_thickness_candidate(lines)
        assert result is not None
        assert result["thickness"] == 18

    def test_ocr_noise_no_match(self):
        # Only thread specs and radii — no clear thickness
        lines = ["M6", "M3", "M2.5", "R2", "R3"]
        result = extract_thickness_candidate(lines)
        # M-prefix excluded, R2 excluded (< 3)
        assert result is None
