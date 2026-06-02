# encoding: utf-8
import sys, re
sys.path.insert(0, r"F:\Work_Dir\2D-v")
from pathlib import Path
from backend.pipeline.ocr_feature import _get_ocr
from PIL import Image, ImageDraw

ocr = _get_ocr()
img_path = r"F:\Work_Dir\2D-v\output\5c36716b-8810-478a-8c17-5346c2128a4a\pages\page_1.png"
result = ocr.ocr(img_path, cls=True)

img = Image.open(img_path)
w, h = img.size
draw = ImageDraw.Draw(img)

items = []
for page in result:
    if not page: continue
    for item in page:
        bbox = item[0]
        text = item[1][0].strip()
        conf = item[1][1]
        cx = sum(p[0] for p in bbox) / 4
        cy = sum(p[1] for p in bbox) / 4
        x1 = min(p[0] for p in bbox)
        y1 = min(p[1] for p in bbox)
        x2 = max(p[0] for p in bbox)
        y2 = max(p[1] for p in bbox)
        items.append({"text": text, "cx": cx, "cy": cy, "conf": conf, "bbox": (x1,y1,x2,y2)})

for it in items:
    x, y = it["cx"], it["cy"]
    x1, y1, x2, y2 = it["bbox"]
    t = it["text"]

    if x > w * 0.65 and y > h * 0.8:
        region = "TITLE"
        color = (128, 128, 128)
    elif x > w * 0.5 and y < h * 0.3:
        region = "DETAIL"
        color = (0, 0, 255)
    elif "A-A" in t or "B-B" in t or "4-4" in t:
        region = "SECTION"
        color = (0, 255, 255)
    else:
        region = "MAIN"
        color = (0, 255, 0)

    it["region"] = region
    draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
    draw.text((x1, max(0, int(y1-15))), region, fill=color)

out_path = r"F:\Work_Dir\2D-v\output\5c36716b-8810-478a-8c17-5346c2128a4a\pages\annotated.png"
img.save(out_path)
print(f"Saved: {out_path}")
print(f"Size: {w}x{h}, Items: {len(items)}")

for it in items:
    print(f'{it["region"]:10s} ({it["cx"]:6.0f},{it["cy"]:6.0f}) {it["text"]:30s} conf={it["conf"]:.2f}')
