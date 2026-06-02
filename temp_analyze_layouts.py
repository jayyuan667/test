# encoding: utf-8
"""Analyze OCR positions across 30 drawings to find view layout patterns."""
import sys, re, json
sys.path.insert(0, r"F:\Work_Dir\2D-v")
from pathlib import Path
from collections import defaultdict
from backend.pipeline.ocr_feature import _get_ocr

ocr = _get_ocr()
drawing_dir = Path(r"F:\小桌面\30张-修改-02所\drawing_png")

# Analyze a subset of drawings
results = {}
for p in sorted(drawing_dir.glob("Y*.png"))[:30]:
    name = p.stem
    try:
        result = ocr.ocr(str(p), cls=True)
    except Exception as e:
        print(f"{name}: OCR ERROR: {e}")
        continue

    items = []
    for page in result:
        if not page: continue
        for item in page:
            bbox = item[0]
            text = item[1][0].strip()
            conf = abs(item[1][1])  # sometimes negative in newer paddleocr
            cx = sum(p[0] for p in bbox) / 4
            cy = sum(p[1] for p in bbox) / 4
            items.append({"text": text, "cx": cx, "cy": cy, "conf": conf})

    # Extract numeric values by position zone
    # Zones: TL(top-left), TR(top-right), BL(bottom-left), BR(bottom-right), CENTER
    w, h = 4678, 3308
    zone_counts = defaultdict(int)
    numeric_items = []

    for it in items:
        x, y = it["cx"], it["cy"]
        zone = "center"
        if x < w * 0.25 and y < h * 0.3: zone = "tl"
        elif x > w * 0.6 and y < h * 0.3: zone = "tr"
        elif x < w * 0.3 and y > h * 0.65: zone = "bl"
        elif x > w * 0.6 and y > h * 0.65: zone = "br"
        elif y > h * 0.65: zone = "bottom"
        elif x > w * 0.6: zone = "right"
        zone_counts[zone] += 1

        # Numbers only
        nums = re.findall(r'\b\d+(?:\.\d+)?\b', it["text"])
        if nums:
            numeric_items.append({"text": it["text"], "zone": zone, "nums": nums, "cx": x, "cy": y})

    # Count dims that might be outer dimensions (values > 10, not GB/T, etc.)
    large_nums = []
    for ni in numeric_items:
        for n in ni["nums"]:
            v = float(n)
            if 10 < v < 2000 and not re.search(r'GB|T\.|TS', ni["text"], re.IGNORECASE):
                large_nums.append({"value": v, "zone": ni["zone"], "cx": ni["cx"], "cy": ni["cy"], "text": ni["text"]})

    print(f"\n{'='*60}")
    print(f"{name}: {len(items)} OCR items, {len(large_nums)} numeric values > 10")
    print(f"Zones: {dict(zone_counts)}")

    # Show large numbers by zone
    for z in ["tl", "tr", "center", "right", "bl", "bottom", "br"]:
        zone_nums = [n for n in large_nums if n["zone"] == z]
        if zone_nums:
            vals = sorted(set(n["value"] for n in zone_nums))
            # Show abbreviated values
            vals_str = ", ".join(str(int(v)) for v in vals[:15])
            if len(vals) > 15:
                vals_str += f" ... ({len(vals)} total)"
            print(f"  {z:8s}: {vals_str}")

    # Check for step pattern: multiple values clustered at similar x position
    center_nums = [n for n in large_nums if n["zone"] in ("center", "right")]
    if len(center_nums) >= 3:
        # Cluster by x coordinate
        xs = defaultdict(list)
        for n in center_nums:
            bucket = int(n["cx"] // 200) * 200  # 200px buckets
            xs[bucket].append(n["value"])
        for bucket, vals in xs.items():
            if len(vals) >= 3:
                print(f"  STEP CLUSTER at x~{bucket}: {sorted(set(int(v) for v in vals))}")

    results[name] = {
        "total_items": len(items),
        "numeric_count": len(large_nums),
        "zones": dict(zone_counts),
        "large_nums_by_zone": {z: sorted(set(n["value"] for n in large_nums if n["zone"] == z)) for z in ["tl", "tr", "center", "right", "bl", "bottom", "br"]},
    }

# Save for reference
with open(r"F:\Work_Dir\2D-v\temp_ocr_layout_analysis.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2, default=str)
print(f"\nSaved analysis to temp_ocr_layout_analysis.json")
