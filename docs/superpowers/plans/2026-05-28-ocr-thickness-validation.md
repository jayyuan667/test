# OCR Thickness Validation — Implementation Plan

## Step 1: `ocr_thickness.py` — Rule engine (new file)
- `extract_thickness_candidate(lines)` — filter numeric values, apply three-group rule and bent-channel rule
- `verify_drawing_thickness(vlm_text, image_paths, drawing_id)` — parse VLM 外形尺寸, run OCR, compare

## Step 2: `vision_analyzer.py` — Integration (5 lines)
- `analyze_drawing()` 末尾追加 env-gated call

## Step 3: Tests
- Unit tests for `extract_thickness_candidate` (Y1, Y2, Y10, Y14, Y15, Y20 cases)
- Integration test with env var disable
