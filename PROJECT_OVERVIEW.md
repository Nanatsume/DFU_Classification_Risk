# DFU Classification — Project Overview

## Background

โปรเจกต์นี้พัฒนาระบบ **Deep Learning** เพื่อจำแนกแผล Diabetic Foot Ulcer (DFU) ออกเป็นสองกลุ่ม:

| Label | กลุ่ม | ความหมาย |
|-------|-------|-----------|
| CT    | 0     | แผลธรรมดา (Control) |
| DM    | 1     | แผลเบาหวาน (Diabetic) |

ใช้ชุดข้อมูล **INAOE** (334 ภาพ: CT=90, DM=244) ที่ผ่านการ preprocess มาเป็นขนาด 224×224 พิกเซล, normalized [0,1], เก็บในรูป `.npy`

---

## Dataset & Splits

- **Total**: 334 ภาพ
- **Test set** (held-out): 20% → ~67 ภาพ (แยกไว้ตั้งแต่ต้น ไม่แตะระหว่าง train)
- **Training set**: 80% → ~267 ภาพ แบ่ง 5-fold Stratified CV
- **Seed**: 42 (คงที่ทุกไฟล์ เพื่อให้ split เหมือนกัน)

```
334 ภาพ
├── Test Set (~67 ภาพ) ─────────── ประเมินขั้นสุดท้ายเท่านั้น
└── Train+Val (~267 ภาพ)
    ├── Fold 1 (train ~213 / val ~54)
    ├── Fold 2
    ├── Fold 3
    ├── Fold 4
    └── Fold 5
```

---

## Research Questions (RQ)

| RQ | คำถาม | สคริปต์ |
|----|-------|---------|
| RQ1 | Backbone ไหนดีที่สุด? | `rq1_backbone_comparison.py` |
| RQ2 | Youden's Index threshold ช่วยอะไร? | `rq2_threshold_optimization.py` |
| RQ3 | ประสิทธิภาพสุดท้ายบน test set | `rq3_final_evaluation.py` |
| RQ4 | XAI ด้วย Grad-CAM / Grad-CAM++ / Eigen-CAM | `rq4_gradcam.py` |
| RQ5 | CNN vs BPNN (GLCM+HOG) | `rq5_bpnn_comparison.py` |
| RQ6 | BPNN Feature Interpretability (Supplementary) | `rq6_bpnn_interpretability.py` |

---

## System Architecture

### Model Architecture (CNN)

```
Input (224×224×3)
    ↓
Backbone (ImageNet pretrained, frozen in Phase 1)
    ↓
CBAM (reduction_ratio=16)          ← Channel + Spatial Attention
    ├─ Channel Attention: AvgPool + MaxPool → Shared MLP → sigmoid
    └─ Spatial Attention: AvgPool + MaxPool along C → Conv2D(7×7) → sigmoid
    ↓
GlobalAveragePooling2D
    ↓
Dense(256, relu) → Dropout(0.5)
    ↓
Dense(64, relu)  → Dropout(0.5)
    ↓
Dense(1, sigmoid)   ← output probability
```

**Backbones ที่ทดสอบ**: EfficientNetB0, ResNet50, ConvNeXt-Tiny

### Two-Phase Training

| Phase | Backbone | Epochs (max) | Early Stopping | LR |
|-------|----------|-------------|----------------|----|
| Phase 1 | Frozen | 50 | patience=5 (val_loss) | 1e-3 |
| Phase 2 | Unfreeze top 30% | 50 | patience=15 (val_loss) | 1e-4 (Exp decay) |

- **Augmentation**: Random rotation ±10° บน training set เท่านั้น (online, ไม่เพิ่มจำนวน)
- **Class weights**: ปรับสมดุล imbalanced dataset (DM:CT ≈ 2.7:1)
- **Optimizer**: Adam (Phase 1), Adam + ExponentialDecayScheduler (Phase 2)
- `jit_compile=False` — ป้องกัน XLA hang บน NVIDIA Blackwell (sm_120a)
- `save_checkpoint=False` ใน Optuna trials — ไม่บันทึก `.h5` ระหว่าง search (EarlyStopping ใช้ `restore_best_weights=True` แทน)

### Hyperparameter Tuning — Optuna

- **Sampler**: TPE (Tree-structured Parzen Estimator), Seed=42
- **Trials**: 10 trials, ประเมินบน Fold 1 เท่านั้น (เพื่อความเร็ว)
- **Search space**:
  - `dropout_rate`: 0.2–0.5
  - `l2_reg`: 1e-5–1e-2
  - `dense_units_1`: {128, 256, 512}
  - `dense_units_2`: {64, 128, 256}
  - `batch_size`: {16, 32}
  - `phase1_lr`: 1e-4–1e-2
  - `phase2_lr`: 1e-6–1e-4

---

## File Structure

```
DFU/
├── dfu_common.py              ← shared config, data loader, trainer, tuner
├── train_resnet.py            ← train ResNet50  (Optuna + 5-fold)
├── train_efficientnet.py      ← train EfficientNetB0
├── train_convnext.py          ← train ConvNeXt-Tiny
├── rq1_backbone_comparison.py ← RQ1
├── rq2_threshold_optimization.py ← RQ2
├── rq3_final_evaluation.py    ← RQ3
├── rq4_gradcam.py             ← RQ4
├── rq5_bpnn_comparison.py     ← RQ5
├── rq6_bpnn_interpretability.py ← RQ6 (Supplementary — Permutation + SHAP)
├── run_gpu.sh                 ← helper script สำหรับรันด้วย GPU
├── model_checkpoints/         ← fold checkpoints, best_params, val_preds, avg_epochs
└── results/                   ← JSON results, log files, CAM images
```

---

## RQ1 — Backbone Comparison

**วัตถุประสงค์**: เลือก backbone ที่ดีที่สุดจาก 3 ตัว โดยใช้ 5-fold CV บน training set

**เกณฑ์ผ่าน** (Clinical screening criteria):
- AUC-ROC ≥ 0.80
- Sensitivity ≥ 0.85
- Specificity ≥ 0.70

**ผลลัพธ์** (Mean across 5 folds, threshold = 0.5, with CBAM):

| Backbone | AUC | Sens | Spec | ผ่านเกณฑ์? |
|----------|-----|------|------|------------|
| EfficientNetB0 | 0.4500 | 1.0000 | 0.0000 | ✗ |
| **ResNet50** | **0.8235** | **0.9846** | **0.1981** | ✗ |
| ConvNeXt-Tiny | 0.8207 | 0.8359 | 0.6257 | ✗ |

> ไม่มี backbone ใดผ่านครบทั้ง 3 เกณฑ์ → เลือก **ResNet50** เพราะ AUC สูงสุด (CBAM ช่วยให้ ResNet50 แซง ConvNeXt-Tiny)

**บันทึกผล**: `results/rq1_results.json`

---

## RQ2 — Threshold Optimization (Youden's Index)

**วัตถุประสงค์**: เปรียบเทียบ threshold = 0.5 vs Youden's Index threshold บน ConvNeXt-Tiny

**สูตร Youden's J**:
```
J = Sensitivity + Specificity − 1
threshold* = argmax(TPR − FPR)
```

**Step 1 — Per-fold Youden threshold** (ResNet50 with CBAM):

| Fold | Youden thr | Sens | Spec |
|------|-----------|------|------|
| 1 | 0.6754 | 0.9231 | 0.5333 |
| 2 | 0.6990 | 0.8974 | 0.5333 |
| 3 | 0.7006 | 0.8462 | 0.8571 |
| 4 | 0.6401 | 0.9231 | 0.9286 |
| 5 | 0.7847 | 0.7436 | 0.8571 |
| **Mean** | **0.7000** | | |

**Step 2 — Default (0.5) vs Mean Youden (0.7000) applied to all folds**:

| Metric | Default 0.5 | Youden 0.7000 | Δ |
|--------|------------|--------------|---|
| Sensitivity | 0.9846 ± 0.0205 | 0.7795 ± 0.1176 | −0.2051 pp (−20.8%) |
| Specificity | 0.1981 ± 0.1779 | 0.7267 ± 0.1492 | +0.5286 pp (+266.9%) |

> Youden threshold trade-off: Sens ลด −20.8% แต่ Spec เพิ่ม +266.9% — จาก 0.1981 เป็น 0.7267 ผ่านเกณฑ์ ≥ 0.70 แล้ว

**บันทึกผล**: `results/rq2_results.json`

---

## RQ3 — Final Evaluation on Test Set

**วัตถุประสงค์**: ประเมิน proposed model (ConvNeXt-Tiny) บน held-out test set

**กลยุทธ์**:
1. ดู average stopping epoch จาก 5-fold CV (บันทึกใน `ConvNeXt-Tiny_avg_epochs.json`)
2. Retrain ใหม่บน **full training set (267 ภาพ)** เป็นจำนวน epoch เฉลี่ยนั้น
3. ไม่ใช้ early stopping ในรอบสุดท้าย
4. ประเมินด้วย Youden threshold (0.7146) จาก RQ2

**Avg stopping epochs** (ResNet50 with CBAM):
- Phase 1: **20 epochs**
- Phase 2: **49 epochs**

**ผลลัพธ์บน Test Set**:

| Metric | ค่า |
|--------|-----|
| Sensitivity | **0.7551** |
| Specificity | **0.6667** |
| AUC-ROC | **0.8447** |
| PPV | 0.8605 |
| NPV | 0.5000 |
| F1-Score | 0.8043 |
| Accuracy | 0.7313 |

**บันทึกผล**: `results/rq3_results.json`, `results/rq3_test_probs.npy`

---

## RQ4 — Explainability (Grad-CAM)

**วัตถุประสงค์**: แสดง heatmap ว่า model สนใจบริเวณไหนของภาพ

**วิธีที่ใช้**:

| Method | แนวคิด |
|--------|--------|
| **Grad-CAM** | ถ่วงน้ำหนัก feature map ด้วย gradient (global avg pooled) |
| **Grad-CAM++** | ถ่วงด้วย alpha weights จาก 2nd-order gradient — แม่นขึ้นเมื่อมีหลาย object |
| **Eigen-CAM** | Gradient-free — ใช้ PC1 จาก SVD ของ feature map |

**Implementation (Keras 3 compatible)**:

```
model แบ่งออกเป็น 2 ส่วน:
feat_model  : Input → backbone → spatial feature map (H×W×C)
clf_model   : feature map → prediction

ใช้ GradientTape.watch(conv_out) ก่อนรัน clf_model
```

> แก้ปัญหา `KeyError: tensor_dict[id(x)]` ใน Keras 3 Functional model

**Pointing Game** (เพิ่ม skeleton ไว้ — รอ annotations.json):
- เมื่อมี `annotations.json` (bounding box ของ lesion จาก expert)
- สร้างเอง: `[{filename, orig_w, orig_h, bbox: [x1,y1,x2,y2]}]`
- สคริปต์จะ scale bbox → 224×224 อัตโนมัติ

**วิธีวัด (Instance-level, 95th-percentile + spatial offset variant)**:
- ขยาย GT bbox ออก **τ = 15 px** ทุกด้าน → ได้ "neighbourhood" รอบ annotation
- Threshold CAM ที่ percentile ที่ 95 → ได้ "high-activation region" (top 5%)
- **Hit** = มี pixel ใดใน region นั้น overlap กับ expanded bbox
- τ แก้ได้ที่ค่าคงที่ `POINTING_GAME_TAU` ด้านบนของไฟล์

**Output**: ภาพ 4-panel (Original / Grad-CAM / Grad-CAM++ / Eigen-CAM) บันทึกใน `results/rq4_gradcam/`

---

## RQ5 — CNN vs BPNN

**วัตถุประสงค์**: เปรียบเทียบ proposed CNN กับ BPNN แบบ handcrafted features

### BPNN Pipeline

**Feature Extraction (24-dim)**:

| Features | รายละเอียด | มิติ |
|----------|-----------|------|
| GLCM | 8-level quantized, 4 angles (0°,45°,90°,135°), 4 properties × 4 angles | 16-dim |
| HOG | 8×8 cells, 8 statistics (mean,std,var,median,max,min,skew,kurtosis) | 8-dim |
| **รวม** | | **24-dim** |

**GLCM properties**: Contrast, Correlation, Energy, Homogeneity (แยกต่อมุม ไม่เฉลี่ย)

**Model**:
- MLPClassifier (sklearn), activation=tanh, solver=Adam
- Hyperparameter search: **GridSearchCV** 5-fold, scoring=AUC
  - `hidden_layer_sizes`: {(64,32), (128,64), (128,64,32), (256,128), (256,128,64)}
  - `alpha`: {1e-4, 1e-3, 1e-2}
- Best architecture: **(256, 128), tanh, α=0.0001**
- Avg stopping iterations: **28** (per fold: 24, 24, 24, 39, 30)
- Threshold: Youden's Index จาก 5-fold CV = **0.5792**

**Comparison Table**:

| Metric | ResNet50+CBAM (CNN) | BPNN (GLCM+HOG) | Δ |
|--------|---------------------|-----------------|---|
| Sensitivity | 0.7551 | 0.8367 | +0.0816 |
| Specificity | 0.6667 | 0.6111 | −0.0556 |
| AUC-ROC | 0.8447 | 0.8526 | +0.0079 |
| PPV | 0.8605 | 0.8542 | −0.0063 |
| NPV | 0.5000 | 0.5789 | +0.0789 |
| F1-Score | 0.8043 | 0.8454 | +0.0411 |

**Statistical Tests** (เมื่อมี `rq3_test_probs.npy`):
- **McNemar's Test**: H₀ = both models make same errors (paired)
- **Bootstrap AUC p-value**: H₀ = AUC_CNN = AUC_BPNN (2,000 bootstrap samples)

**บันทึกผล**: `results/rq5_results.json`

---

## RQ6 — BPNN Feature Interpretability (Supplementary)

**วัตถุประสงค์**: ทำความเข้าใจว่า BPNN ใช้ feature ไหนในการตัดสินใจ

**วิธีที่ใช้**:

| วิธี | แนวคิด | Output |
|------|--------|--------|
| **Permutation Importance** | สุ่มสลับค่าแต่ละ feature แล้วดู AUC ลดลงแค่ไหน | bar chart |
| **SHAP KernelExplainer** | คำนวณ contribution ของแต่ละ feature ต่อ prediction แต่ละ sample | beeswarm + bar |

**ผลลัพธ์ที่น่าสนใจ**:
- **HOG Median และ HOG Mean** สำคัญที่สุด — gradient magnitude โดยรวมเป็นสัญญาณหลัก
- เท้า DM มี HOG ต่ำกว่า CT → pressure กระจายสม่ำเสมอกว่า
- **Homogeneity 0° และ Contrast 0°** เป็น GLCM features ที่สำคัญที่สุด
- Correlation features แทบไม่มีผลต่อ prediction เลย

**Output**: `results/rq6_bpnn_interpretability/` (permutation_importance.png, shap_beeswarm.png, shap_bar.png)

---

## Running Order

```bash
# 1. Train backbones (ใช้เวลานาน)
./run_gpu.sh train_resnet.py
./run_gpu.sh train_efficientnet.py
./run_gpu.sh train_convnext.py

# 2. RQ1 — เลือก backbone
./run_gpu.sh rq1_backbone_comparison.py

# 3. RQ2 — optimize threshold
./run_gpu.sh rq2_threshold_optimization.py

# 4. RQ3 — final test evaluation
./run_gpu.sh rq3_final_evaluation.py

# 5. RQ4 — XAI visualizations
./run_gpu.sh rq4_gradcam.py

# 6. RQ5 — BPNN comparison
./run_gpu.sh rq5_bpnn_comparison.py

# 7. RQ6 — BPNN interpretability (supplementary, run after rq5)
./run_gpu.sh rq6_bpnn_interpretability.py
```

> `run_gpu.sh` ตั้งค่า `LD_LIBRARY_PATH` จาก CUDA pip wheels ใน conda env `tf_gpu`

---

## Technical Notes

| หัวข้อ | รายละเอียด |
|-------|-----------|
| Framework | TensorFlow 2.21 + Keras 3 |
| Format checkpoint | `.keras` (ไม่ใช่ `.h5`) |
| GPU | NVIDIA Blackwell (RTX 5060 Ti, sm_120a) — ต้องใช้ `jit_compile=False` |
| Load model | `compile=False` + `custom_objects={'CBAM': CBAM}` — หลีกเลี่ยง deserialization error |
| Augmentation | `RandomRotation(±10°)` ผ่าน tf.data pipeline, training only |
| Epoch policy | 5-fold CV ใช้ max 50 + early stopping; final retrain ใช้ **avg stopping epoch** จาก CV |
| Feature cache | GLCM+HOG cached ที่ `model_checkpoints/glcm_hog_features.npz` |
| Shared code | `dfu_common.py` — CONFIG, data loader, DFUModelTrainer, Optuna tuner, helpers |

### Key Functions in `dfu_common.py`

| Function / Class | หน้าที่ |
|-----------------|--------|
| `load_preprocessed_inaoe()` | โหลด .npy images + labels |
| `create_fold_splits()` | สร้าง stratified splits (test + 5-fold) |
| `DFUModelTrainer` | build, train_phase1, train_phase2, save |
| `DFUModelTrainer.phase1_best_epoch` | **stopping epoch** ของ phase 1 (= len of val_loss history) |
| `DFUModelTrainer.phase2_best_epoch` | **stopping epoch** ของ phase 2 (= len of val_loss history) |
| `train_phase1/2(fixed_epochs=N)` | retrain บน full set, N epoch คงที่, ไม่มี early stop |
| `OptunaHyperparameterTuner` | Optuna TPE, fold 1 only |
| `compute_youden_threshold()` | argmax(TPR−FPR) → threshold, sens, spec |
| `train_one_model()` | Optuna → 5-fold train → save val_preds + avg_epochs.json |
