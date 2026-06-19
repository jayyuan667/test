# 7-Class YOLO Training Architecture Design Spec

> Date: 2026-06-18
> Status: Pending Review
> Dataset: Other_label (122 images, 113 JSON annotations)

---

## 1. Problem Statement

Build a YOLO11 object detection model for industrial engineering drawings with **7 feature classes**:

| Class ID | Name | Description | Count |
|----------|------|-------------|-------|
| 0 | `threaded_hole` | Threaded holes with crosshair marks | 458 |
| 1 | `through_hole` | Plain through holes | 205 |
| 2 | `code_hole` | Special process through holes | 5117 |
| 3 | `counterbore` | Stepped/sunken holes | 75 |
| 4 | `countersink` | Conical countersink holes | 74 |
| 5 | `blind_hole` | Blind holes (no through) | 17 |
| 6 | `chamfer` | Chamfer edge features | 252 |

**Total annotations: 6198**

---

## 2. Key Challenges

### 2.1 Class Imbalance (Critical)

```
code_hole:  ████████████████████████████████████████  5117 (82.6%)
threaded:   ████                                       458 (7.4%)
chamfer:    ██                                         252 (4.1%)
through:    ██                                         205 (3.3%)
counterbr:  █                                           75 (1.2%)
countersnk: █                                           74 (1.2%)
blind:      ▏                                           17 (0.3%)
```

`code_hole` dominates the dataset. Without intervention, rare classes (`blind_hole`, `countersink`, `counterbore`) will have near-zero recall.

### 2.2 Mixed Data Sources

| Source | Format | Resolution | Files |
|--------|--------|------------|-------|
| Original (1-100) | JPG | 2526x1785 | 100 images, 91 JSON |
| New batch (Y1-Y22) | PNG | 4678x3308 | 22 images, 22 JSON |

Different resolutions require normalization during training.

### 2.3 Annotation Quality Variance

- **Y-series**: Clean labels, consistent bounding boxes, good coverage
- **Original series**: Larger boxes (include surrounding text), some images have incomplete annotations (holes without text labels missed)

---

## 3. Architecture: Single Model 7-Class (Recommended)

### Why Single Model?

- Simple: one model, one inference pass
- Compatible with existing project pipeline (augment.py, train scripts)
- Sufficient for current data scale (~122 images)
- Easily extensible for future classes

### Alternatives Considered

| Approach | Pros | Cons | Verdict |
|----------|------|------|---------|
| **A: Single 7-class** | Simple, fast inference | Class imbalance needs careful handling | **Selected** |
| B: Two-stage (detect then classify) | Better rare class handling | 2x latency, complex pipeline | Overkill for 122 images |
| C: Split models (6-class + code_hole) | Balanced main model | Two models to maintain | Unnecessary complexity |

---

## 4. Data Pipeline Design

```
Source Images (122)
    |
    v
[1] convert_to_yolo.py
    - JSON -> YOLO TXT (normalized cx cy w h)
    - Class mapping: threaded_hole=0, through_hole=1, code_hole=2,
                     counterbore=3, countersink=4, blind_hole=5, chamfer=6
    |
    v
[2] prepare_dataset.py
    - Train/val split (80/20, stratified by class)
    - Copy images + labels to dataset/ structure
    - Generate data.yaml
    |
    v
[3] augment.py (modified)
    - Class-weighted augmentation
    - Heavy augmentation for rare classes
    - Undersampling for code_hole
    |
    v
[4] train_7class.py
    - YOLO11m training with class weights
    - Local: imgsz=800, batch=2
    - Server: imgsz=2560, batch=2/GPU, DDP
```

### 4.1 Directory Structure (After Pipeline)

```
Other_label/
├── *.jpg, *.png              # Source images (unchanged)
├── *.json                    # Unified JSON annotations (done)
├── docs/
│   └── design-spec.md        # This document
├── convert_to_yolo.py        # NEW: JSON -> YOLO TXT
├── prepare_dataset.py        # NEW: train/val split + data.yaml
├── train_7class.py           # NEW: 7-class training script
└── dataset/                  # NEW: YOLO format dataset
    ├── train/
    │   ├── images/
    │   └── labels/
    ├── val/
    │   ├── images/
    │   └── labels/
    └── data.yaml
```

### 4.2 data.yaml Template

```yaml
path: ./dataset
train: train/images
val: val/images

nc: 7
names:
  0: threaded_hole
  1: through_hole
  2: code_hole
  3: counterbore
  4: countersink
  5: blind_hole
  6: chamfer
```

---

## 5. Class Balancing Strategy

### 5.1 Loss Weights (cls_pw)

```python
CLASS_WEIGHTS = {
    0: 2.0,    # threaded_hole - moderate
    1: 3.0,    # through_hole - moderate-high
    2: 0.2,    # code_hole - very low (oversampled)
    3: 5.0,    # counterbore - high
    4: 5.0,    # countersink - high
    5: 15.0,   # blind_hole - highest (only 17 samples)
    6: 2.0,    # chamfer - moderate
}
```

### 5.2 Augmentation Strategy

| Class | Current Count | Target Count | Multiplier | Method |
|-------|---------------|--------------|------------|--------|
| blind_hole | 17 | ~200 | 12x | Copy + rotate + scale + color |
| countersink | 74 | ~250 | 3.4x | Copy + random transform |
| counterbore | 75 | ~250 | 3.3x | Copy + random transform |
| through_hole | 205 | ~300 | 1.5x | Light augmentation |
| threaded_hole | 458 | ~458 | 1x | Standard augmentation |
| chamfer | 252 | ~300 | 1.2x | Light augmentation |
| code_hole | 5117 | ~2000 | 0.4x | **Undersample** (skip 60%) |

### 5.3 Augmentation Transforms

```python
# For rare classes (blind, countersink, counterbore)
rare_transforms = A.Compose([
    A.Rotate(limit=15, p=0.8),
    A.RandomScale(scale_limit=0.2, p=0.7),
    A.ShiftScaleRotate(shift_limit=0.1, p=0.7),
    A.RandomBrightnessContrast(brightness_limit=0.2, contrast_limit=0.2, p=0.5),
    A.GaussNoise(var_limit=(10, 50), p=0.3),
], bbox_params=A.BboxParams(format='yolo', label_fields=['class_labels']))

# For standard classes
standard_transforms = A.Compose([
    A.HorizontalFlip(p=0.5),
    A.RandomBrightnessContrast(brightness_limit=0.1, contrast_limit=0.1, p=0.3),
], bbox_params=A.BboxParams(format='yolo', label_fields=['class_labels']))
```

---

## 6. Training Configuration

### 6.1 Hyperparameters

| Parameter | Local (GTX 1650) | Server (2x 4090) |
|-----------|------------------|-------------------|
| Model | yolo11m.pt | yolo11m.pt |
| imgsz | 800 | 2560 |
| batch | 2 | 2 per GPU |
| epochs | 150 | 200 |
| optimizer | AdamW | AdamW |
| lr0 | 0.001 | 0.001 |
| workers | 2 | 8 |
| device | 0 | 0,1 (DDP) |

### 6.2 Key Training Arguments

```python
args = dict(
    model='yolo11m.pt',
    data='dataset/data.yaml',
    epochs=150,
    imgsz=800,
    batch=2,
    optimizer='AdamW',
    lr0=0.001,
    cls_pw=CLASS_WEIGHTS,  # class-specific loss weights
    patience=50,           # early stopping
    augment=True,
    mosaic=0.5,            # reduce mosaic for engineering drawings
    mixup=0.0,             # disable mixup (not suitable for technical drawings)
)
```

### 6.3 Special Considerations for Engineering Drawings

- **Mosaic reduced to 0.5**: Full mosaic can cut through annotation boundaries
- **Mixup disabled**: Not suitable for precise bounding box tasks
- **No HSV augmentation**: Engineering drawings are black/white, color jitter is harmful
- **imgsz consideration**: Small holes need higher resolution; 800 may miss tiny features

---

## 7. Expected Performance

### 7.1 Without Class Balancing (Baseline)

| Metric | Estimate |
|--------|----------|
| mAP@50 | 0.55-0.65 |
| mAP@50:95 | 0.35-0.50 |
| blind_hole AP | 0.10-0.30 |
| countersink AP | 0.20-0.40 |
| code_hole AP | 0.80-0.90 |

### 7.2 With Class Balancing (Target)

| Metric | Local (imgsz=800) | Server (imgsz=2560) |
|--------|-------------------|---------------------|
| mAP@50 | 0.78-0.88 | 0.82-0.90 |
| mAP@50:95 | 0.60-0.75 | 0.70-0.82 |
| blind_hole AP | 0.50-0.70 | 0.60-0.80 |
| countersink AP | 0.55-0.75 | 0.65-0.82 |
| code_hole AP | 0.85-0.92 | 0.88-0.95 |

---

## 8. Implementation Steps

### Phase 1: Data Preparation (convert_to_yolo.py)
- [ ] Read all 113 JSON files
- [ ] Convert rectangle annotations to YOLO format (cx, cy, w, h normalized)
- [ ] Write .txt label files alongside images
- [ ] Handle both JPG and PNG images

### Phase 2: Dataset Assembly (prepare_dataset.py)
- [ ] Stratified train/val split (80/20)
- [ ] Copy files to dataset/ structure
- [ ] Generate data.yaml
- [ ] Print class distribution report

### Phase 3: Augmentation (augment.py modification)
- [ ] Implement class-weighted augmentation
- [ ] Rare class oversampling
- [ ] code_hole undersampling
- [ ] Validation: augmented labels must be correct

### Phase 4: Training (train_7class.py)
- [ ] Local training script (imgsz=800)
- [ ] Server training script (imgsz=2560, DDP)
- [ ] Class weight configuration
- [ ] Logging and checkpoint management

### Phase 5: Evaluation
- [ ] Per-class AP analysis
- [ ] Confusion matrix
- [ ] Error analysis (false positives / false negatives per class)

---

## 9. Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| blind_hole too few samples | Model can't detect | Heavy augmentation + highest class weight |
| code_hole dominates training | Suppresses other classes | Undersample + lowest class weight |
| Original data has imprecise boxes | Lower mAP | Tighten boxes in review step (optional) |
| Mixed resolutions cause issues | Inconsistent features | Normalize to single imgsz during training |
| Overfitting on 122 images | Poor generalization | augmentation + early stopping + small model |

---

## 10. Open Questions

1. ~~Should `code_hole` map to `circle_hole`?~~ → **No, code_hole is independent class**
2. ~~Should `Blind Hole` be independent?~~ → **Yes, independent class**
3. Should we re-annotate the 9 images without JSON? → **No, they don't contain target features**
4. Should we tighten the original Chamfer boxes? → **TBD, optional improvement**
5. What model size? yolo11s (fast) vs yolo11m (balanced) vs yolo11l (accurate)? → **TBD**
