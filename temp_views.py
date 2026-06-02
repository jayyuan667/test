# encoding: utf-8
"""Split Y20 drawing into separate views and annotate for VLM."""
import sys
sys.path.insert(0, r"F:\Work_Dir\2D-v")
from PIL import Image, ImageDraw

img = Image.open(r"F:\Work_Dir\2D-v\output\5c36716b-8810-478a-8c17-5346c2128a4a\pages\page_1.png")
w, h = img.size
print(f"Image: {w}x{h}")

# Y20 layout (from OCR position analysis):
# - Main view (俯视图): top ~70%, left ~70%. Shows square plate with steps.
# - Section A-A: bottom-center area, shows cross-section
# - Section B-B: bottom-center area, shows another cross-section
# - Detail view: top-right area, shows thickness annotations (13, 10, 7)
# - Title block: bottom-right

draw = ImageDraw.Draw(img)

# Draw view boundaries
colors = {
    "main":     (0, 255, 0),
    "detail":   (0, 0, 255),
    "section_aa": (255, 255, 0),
    "section_bb": (255, 0, 255),
    "title":    (128, 128, 128),
}

# Main view: left 2/3, top 2/3 (large area showing the square plate outline)
main_x1, main_y1, main_x2, main_y2 = 0, 0, int(w * 0.62), int(h * 0.72)
draw.rectangle([main_x1, main_y1, main_x2, main_y2], outline=colors["main"], width=5)
draw.text((10, 10), "MAIN VIEW (俯视图) - LxW here", fill=colors["main"])

# Detail/section view: top-right (shows thickness 13, 10, 7)
det_x1, det_y1, det_x2, det_y2 = int(w * 0.65), 0, int(w * 0.9), int(h * 0.28)
draw.rectangle([det_x1, det_y1, det_x2, det_y2], outline=colors["detail"], width=5)
draw.text((det_x1, 10), "SECTION/DETAIL (端视图) - THICKNESS here", fill=colors["detail"])

# Section A-A: bottom-center-left
sec_x1, sec_y1, sec_x2, sec_y2 = 0, int(h * 0.72), int(w * 0.55), int(h * 0.88)
draw.rectangle([sec_x1, sec_y1, sec_x2, sec_y2], outline=colors["section_aa"], width=5)
draw.text((10, sec_y1), "SECTION A-A - thickness check", fill=colors["section_aa"])

# Section B-B: bottom-center
sec2_x1, sec2_y1, sec2_x2, sec2_y2 = int(w * 0.55), int(h * 0.72), int(w * 0.75), int(h * 0.88)
draw.rectangle([sec2_x1, sec2_y1, sec2_x2, sec2_y2], outline=colors["section_bb"], width=5)
draw.text((sec2_x1, sec2_y1), "SECTION B-B", fill=colors["section_bb"])

# Title block: bottom-right
t_x1, t_y1, t_x2, t_y2 = int(w * 0.75), int(h * 0.88), w, h
draw.rectangle([t_x1, t_y1, t_x2, t_y2], outline=colors["title"], width=5)
draw.text((t_x1, t_y1), "TITLE BLOCK", fill=colors["title"])

# Add legend text at the bottom
draw.text((10, h - 30), "GREEN=Main(outer LxW) | BLUE=Detail(thickness) | YELLOW/MAGENTA=Sections | GRAY=Title", fill=(0, 0, 0))

out_path = r"F:\Work_Dir\2D-v\output\5c36716b-8810-478a-8c17-5346c2128a4a\pages\views_annotated.png"
img.save(out_path)
print(f"Saved: {out_path}")

# Also save as lower quality jpg for sending to VLM
img_jpg = img.convert("RGB")
img_jpg.save(r"F:\Work_Dir\2D-v\output\5c36716b-8810-478a-8c17-5346c2128a4a\pages\views_annotated.jpg", quality=85)
print("Saved JPG version")
