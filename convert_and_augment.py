"""
小批量数据：JSON→YOLO TXT 转换 + 数据增广
输入: temp/samll_batch/ (PNG + JSON)
输出: temp/samll_batch_augmented/{train,val}/ (images + labels) + data.yaml

5类: threaded_hole=0, through_hole=1, counterbore=2, countersink=3, Chamfer=4
"""
import json
import random
import shutil
import numpy as np
from pathlib import Path
from PIL import Image
import albumentations as A
from albumentations import BboxParams

SRC = Path(r'F:\小桌面\yolo\temp\samll_batch')
DST = Path(r'F:\小桌面\yolo\temp\samll_batch_augmented')

CLASSES = ['threaded_hole', 'through_hole', 'counterbore', 'countersink', 'Chamfer']
LABEL_MAP = {
    'threaded_hole': 'threaded_hole',
    'through_hole': 'through_hole',
    'counterbore': 'counterbore',
    'countersink': 'countersink',
    'Chamfer': 'Chamfer',
    'chamfer': 'Chamfer',
}

SEED = 42
VAL_RATIO = 0.15
BASE_AUG = 6
EXTRA_AUG = 3  # 少数类额外增广
RARE_CLASSES = {2, 3, 4}  # counterbore, countersink, Chamfer


# ── Step 1: JSON → YOLO TXT ──────────────────────────

def convert_json_to_txt(json_path: Path) -> int:
    """JSON → YOLO TXT，返回标注框数"""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    iw = data.get('imageWidth', 0)
    ih = data.get('imageHeight', 0)
    if iw == 0 or ih == 0:
        return 0

    lines = []
    for shape in data.get('shapes', []):
        label = LABEL_MAP.get(shape.get('label', ''), '')
        if not label or label not in CLASSES:
            continue
        pts = shape.get('points', [])
        if len(pts) < 2:
            continue
        x1, y1 = pts[0]
        x2, y2 = pts[1]
        cx = (x1 + x2) / 2 / iw
        cy = (y1 + y2) / 2 / ih
        bw = abs(x2 - x1) / iw
        bh = abs(y2 - y1) / ih
        cls_id = CLASSES.index(label)
        lines.append(f"{cls_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")

    txt_path = json_path.with_suffix('.txt')
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    return len(lines)


# ── Step 2: 增广 ──────────────────────────────────────

def build_transform() -> A.Compose:
    return A.Compose([
        A.HorizontalFlip(p=0.5),
        A.VerticalFlip(p=0.5),
        A.RandomRotate90(p=0.75),
        A.RandomScale(scale_limit=(-0.3, 0.3), p=0.8),
        A.RandomBrightnessContrast(brightness_limit=0.15, contrast_limit=0.2, p=0.7),
        A.GaussNoise(std_range=(0.02, 0.06), p=0.3),
        A.Blur(blur_limit=3, p=0.3),
        A.Downscale(scale_range=(0.3, 0.7), p=0.3),
        A.ImageCompression(quality_range=(30, 70), p=0.2),
    ], bbox_params=BboxParams(
        format='yolo',
        label_fields=['class_labels'],
        min_visibility=0.3,
    ))


def read_labels(txt_path: Path) -> tuple[list[int], list[list[float]]]:
    if not txt_path.exists() or txt_path.stat().st_size == 0:
        return [], []
    cls_ids, bboxes = [], []
    for line in txt_path.read_text().strip().splitlines():
        parts = line.strip().split()
        if len(parts) != 5:
            continue
        cls_ids.append(int(parts[0]))
        bboxes.append([float(x) for x in parts[1:]])
    return cls_ids, bboxes


def write_labels(txt_path: Path, cls_ids: list[int], bboxes: list):
    lines = [f"{c} {b[0]:.6f} {b[1]:.6f} {b[2]:.6f} {b[3]:.6f}"
             for c, b in zip(cls_ids, bboxes)]
    txt_path.write_text('\n'.join(lines), encoding='utf-8')


def augment_pair(src_img: Path, src_txt: Path, img_dir: Path, lbl_dir: Path,
                 stem: str, n: int, transform: A.Compose) -> int:
    img = np.array(Image.open(src_img).convert('RGB'))
    cls_ids, bboxes = read_labels(src_txt)

    generated = 0
    attempts = 0
    while generated < n and attempts < n * 4:
        attempts += 1
        try:
            result = transform(image=img, bboxes=bboxes, class_labels=cls_ids)
        except Exception:
            continue
        aug_bboxes = list(result['bboxes'])
        aug_cls = list(result['class_labels'])
        if cls_ids and not aug_bboxes:
            continue
        out_stem = f"{stem}_aug{generated + 1:03d}"
        Image.fromarray(result['image']).save(img_dir / f"{out_stem}.png")
        write_labels(lbl_dir / f"{out_stem}.txt", aug_cls, aug_bboxes)
        generated += 1
    return generated


def stratified_split(pairs: list, val_ratio: float) -> tuple[list, list]:
    """按是否含少数类分层后分割"""
    with_rare = [(p, t) for p, t in pairs if RARE_CLASSES & set(read_labels(t)[0])]
    without_rare = [(p, t) for p, t in pairs if not (RARE_CLASSES & set(read_labels(t)[0]))]
    random.shuffle(with_rare)
    random.shuffle(without_rare)

    def split(lst):
        n_val = max(1, round(len(lst) * val_ratio)) if lst else 0
        return lst[n_val:], lst[:n_val]

    tr_wr, va_wr = split(with_rare)
    tr_nr, va_nr = split(without_rare)
    return tr_wr + tr_nr, va_wr + va_nr


def main():
    random.seed(SEED)

    # Step 1: 转换所有 JSON → TXT
    print("=" * 50)
    print("Step 1: JSON → YOLO TXT 转换")
    print("=" * 50)

    jsons = sorted(SRC.glob('*.json'))
    total_boxes = 0
    class_counts = {c: 0 for c in CLASSES}

    for jp in jsons:
        count = convert_json_to_txt(jp)
        if count > 0:
            cls_ids, _ = read_labels(jp.with_suffix('.txt'))
            for c in cls_ids:
                class_counts[CLASSES[c]] += 1
            print(f"  {jp.stem}: {count} 框")
        total_boxes += count

    print(f"\n总计: {total_boxes} 框")
    for cls, cnt in class_counts.items():
        pct = cnt / total_boxes * 100 if total_boxes > 0 else 0
        print(f"  {cls}: {cnt} ({pct:.1f}%)")

    # Step 2: 增广
    print(f"\n{'=' * 50}")
    print("Step 2: 数据增广")
    print("=" * 50)

    all_pairs = [(p, p.with_suffix('.txt'))
                 for p in sorted(SRC.glob('*.png'))
                 if p.with_suffix('.txt').exists() and p.with_suffix('.txt').stat().st_size > 0]
    print(f"有标注的图片: {len(all_pairs)} 张")

    train_set, val_set = stratified_split(all_pairs, VAL_RATIO)
    print(f"train: {len(train_set)} 张, val: {len(val_set)} 张")

    # 创建目录
    for split_name in ['train', 'val']:
        for sub in ['images', 'labels']:
            (DST / split_name / sub).mkdir(parents=True, exist_ok=True)

    transform = build_transform()

    # val: 只复制原图
    print("\n[val] 复制原图...")
    for png, txt in val_set:
        shutil.copy2(png, DST / 'val' / 'images' / png.name)
        shutil.copy2(txt, DST / 'val' / 'labels' / txt.name)

    # train: 复制 + 增广
    print("[train] 复制 + 增广...")
    total_aug = 0
    for png, txt in train_set:
        shutil.copy2(png, DST / 'train' / 'images' / png.name)
        shutil.copy2(txt, DST / 'train' / 'labels' / txt.name)

        cls_ids, _ = read_labels(txt)
        if not cls_ids:
            continue

        n = BASE_AUG + (EXTRA_AUG if RARE_CLASSES & set(cls_ids) else 0)
        aug_count = augment_pair(png, txt,
                                 DST / 'train' / 'images', DST / 'train' / 'labels',
                                 png.stem, n, transform)
        total_aug += aug_count
        print(f"  {png.stem}: 原图 + {aug_count} 增广 (含少数类={bool(RARE_CLASSES & set(cls_ids))})")

    # 统计
    train_imgs = len(list((DST / 'train' / 'images').glob('*.png')))
    val_imgs = len(list((DST / 'val' / 'images').glob('*.png')))

    print(f"\n{'=' * 50}")
    print("增广完成")
    print(f"  train: {train_imgs} 张（原图 {len(train_set)} + 增广 {total_aug}）")
    print(f"  val:   {val_imgs} 张")

    # 写 data.yaml
    yaml_content = (
        f"path: {DST.as_posix()}\n"
        f"train: train/images\n"
        f"val: val/images\n"
        f"nc: {len(CLASSES)}\n"
        f"names: {CLASSES}\n"
    )
    (DST / 'data.yaml').write_text(yaml_content, encoding='utf-8')
    print(f"\ndata.yaml → {DST / 'data.yaml'}")


if __name__ == '__main__':
    main()
