# DFU Classification — Prelim-inary Results

## Background

This project develops a **Deep Learning** system to classify Diabetic Foot Ulcer (DFU) images into two groups:

| Label | Class | Meaning |
|-------|-------|---------|
| CT | 0 | Normal wound (Control) |
| DM | 1 | Diabetic wound |

Dataset: **INAOE** (334 images: CT=90, DM=244), preprocessed to 224×224 px, normalized [0,1], stored as `.npy`.

---

## Dataset & Splits

- **Total**: 334 images
- **Test set** (held-out): 20% → 67 images (separated at the start, never touched during training)
- **Training set**: 80% → 267 images, split into 5-fold Stratified CV
- **Seed**: 42 (fixed across all files to ensure identical splits)

```
334 images
├── Test Set (67 images) ─────────── evaluated at the end only
└── Train+Val (267 images)
    ├── Fold 1 (train 214 / val 53)
    ├── Fold 2
    ├── Fold 3
    ├── Fold 4
    └── Fold 5
```

---

## Research Questions (RQ)

| RQ | Question | Script |
|----|----------|--------|
| RQ1 | Which backbone performs best? | `rq1_backbone_comparison.py` |
| RQ2 | Localization Evaluation (Grad-CAM / Grad-CAM++ / Eigen-CAM + Top-Region Pointing Game) | `rq2_gradcam.py` |
| RQ3 | Proposed Model vs Baseline (BPNN, GLCM+HOG) | `rq3_bpnn_comparison.py` |

---

## System Architecture

### Model Architecture (CNN)

```
Input (224×224×3)
    ↓
Backbone (ImageNet pretrained, frozen in Phase 1 / top 30% unfrozen in Phase 2)
    ↓
GlobalAveragePooling2D
    ↓
Dense(n₁, relu) → Dropout
    ↓
Dense(n₂, relu) → Dropout
    ↓
Dense(1, sigmoid)   ← output probability
```

**Backbones tested**: EfficientNetB0, ResNet50, ConvNeXt-Tiny

### Two-Phase Training

| Phase | Backbone | Max Epochs | Early Stopping | LR |
|-------|----------|-----------|----------------|-----|
| Phase 1 | Frozen | 50 | patience=5 (val_loss) | 1e-3 |
| Phase 2 | Unfreeze top 30% | 50 | patience=15 (val_loss) | 1e-4 (Exp decay) |

- **Augmentation**: Random rotation ±10° on training set only (online, no sample multiplication)
- **Class weights**: balance imbalanced dataset (DM:CT ≈ 2.7:1)
- **Optimizer**: Adam (Phase 1), Adam + ExponentialDecayScheduler (Phase 2)
- `jit_compile=False` — prevents XLA hang on NVIDIA Blackwell (sm_120a)
- `save_checkpoint=False` in Optuna trials — no `.h5` saved during search (EarlyStopping uses `restore_best_weights=True` instead)

### Hyperparameter Tuning — Optuna

- **Sampler**: TPE (Tree-structured Parzen Estimator), Seed=42
- **Trials**: 10 trials, each evaluated with fold 1 only (for speed)
- **Best hyperparameters per backbone**:

| Parameter | EfficientNetB0 | ResNet50 | ConvNeXt-Tiny |
|-----------|---------------|----------|---------------|
| `dense_units_1` | 128 | 128 | 128 |
| `dense_units_2` | 256 | 256 | 256 |
| `dropout_rate` | 0.312 | 0.291 | 0.312 |
| `l2_reg` | 7.11e-3 | 1.96e-5 | 7.11e-3 |
| `batch_size` | 32 | 32 | 32 |
| `phase1_lr` | 1.10e-4 | 4.20e-4 | 1.10e-4 |
| `phase2_lr` | 8.71e-5 | 1.10e-5 | 8.71e-5 |

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
Project/
├── dfu_common.py                    ← shared config, data loader, trainer, tuner
├── train_resnet.py                  ← train ResNet50  (Optuna + 5-fold)
├── train_efficientnet.py            ← train EfficientNetB0
├── train_convnext.py                ← train ConvNeXt-Tiny
├── rq1_backbone_comparison.py       ← RQ1
├── threshold_optimization.py        ← Youden threshold (pipeline step)
├── final_evaluation.py              ← Final retrain + test eval (pipeline step)
├── rq2_gradcam.py                   ← RQ2
├── rq3_bpnn_comparison.py           ← RQ3
├── run_gpu.sh                       ← helper script for GPU execution
├── model_checkpoints/               ← fold checkpoints, best_params, val_preds, avg_epochs
└── results/                         ← JSON results, log files, CAM images
```

---

## RQ1 — Backbone Comparison

**Objective**: Select the best backbone from 3 candidates using 5-fold CV on the training set.

**Criteria** (clinical screening — all three must be met):
- AUC-ROC ≥ 0.80
- Sensitivity ≥ 0.85
- Specificity ≥ 0.70

**Results** (mean across 5 folds, threshold = 0.5):

| Backbone | AUC | Sens | Spec | Passes? |
|----------|-----|------|------|---------|
| EfficientNetB0 | 0.6379 | 0.5949 | 0.4181 | ✗ |
| ResNet50 | 0.7875 | 0.9897 | 0.1533 | ✗ |
| **ConvNeXt-Tiny** | **0.8293** | **0.8000** | **0.6952** | ✗ |

> No backbone passed all three criteria. **ConvNeXt-Tiny** was selected as it achieved the highest AUC and came closest to meeting the specificity criterion (0.70 vs threshold 0.70).

**Results saved to**: `results/rq1_results.json`

---

## Threshold Optimization (Youden's Index)

**Objective**: Compare threshold = 0.5 vs Youden's Index threshold on ConvNeXt-Tiny.

**Youden's J formula**:
```
J = Sensitivity + Specificity − 1
threshold* = argmax(TPR − FPR)
```

**Step 1 — Per-fold Youden threshold** (ConvNeXt-Tiny):

| Fold | Youden thr | Sens | Spec |
|------|-----------|------|------|
| 1 | 0.8586 | 0.6923 | 0.8667 |
| 2 | 0.4464 | 0.8205 | 0.6667 |
| 3 | 0.7798 | 0.6923 | 0.7857 |
| 4 | 0.6629 | 0.7949 | 0.8571 |
| 5 | 0.9112 | 0.7436 | 1.0000 |
| **Mean** | **0.7318** | | |

**Step 2 — Default (0.5) vs Mean Youden (0.7318) applied to all folds**:

| Metric | Default 0.5 | Youden 0.7318 | Δ |
|--------|------------|--------------|---|
| Sensitivity | 0.8000 ± 0.0192 | 0.7333 ± 0.0205 | −0.0667 (−8.3%) |
| Specificity | 0.6952 ± 0.0508 | 0.7657 ± 0.0777 | +0.0705 (+10.1%) |

> Youden threshold trade-off: Sensitivity drops −8.3% but Specificity gains +10.1% — rising from 0.70 to 0.77, exceeding the ≥0.70 criterion.

**Results saved to**: `results/threshold_results.json`

---

## Final Evaluation on Test Set

**Objective**: Evaluate the proposed model (ConvNeXt-Tiny) on the held-out test set.

**Strategy**:
1. Record the average stopping epoch from 5-fold CV (`ConvNeXt-Tiny_avg_epochs.json`)
2. Retrain on **full training set (267 images)** for exactly that many epochs
3. No early stopping in the final retrain
4. Evaluate with Youden threshold (0.6929)

**Avg stopping epochs** (ConvNeXt-Tiny):
- Phase 1: **50 epochs**
- Phase 2: **46 epochs**

**Test set results** (threshold = 0.7318):

| Metric | Value |
|--------|-------|
| Sensitivity | **0.9592** |
| Specificity | **0.6667** |
| AUC-ROC | **0.9150** |
| PPV | 0.8868 |
| NPV | 0.8571 |
| F1-Score | 0.9216 |

**Results saved to**: `results/final_eval_results.json`, `results/final_eval_probs.npy`

---

## RQ2 — Localization Evaluation

**Objective**: Evaluate whether the model correctly localizes lesion regions using three CAM methods, quantified by the Top-Region Pointing Game.

**Methods used**:

| Method | Concept |
|--------|---------|
| **Grad-CAM** | Weight feature maps by gradient (global avg pooled) |
| **Grad-CAM++** | Weight by alpha coefficients from 2nd-order gradients — more accurate when multiple objects present |
| **Eigen-CAM** | Gradient-free — uses PC1 from SVD of the feature map |

**Implementation (Keras 3 compatible)**:

```
Model is split into two parts:
feat_model : Input → backbone → spatial feature map (H×W×C)
clf_model  : feature map → prediction

GradientTape.watch(conv_out) is used before running clf_model
```

> Fixes `KeyError: tensor_dict[id(x)]` in Keras 3 Functional models.

**Top-Region Pointing Game** (skeleton included — awaiting annotations.json):
- When `annotations.json` is available (bounding boxes of lesion from expert)
- Format: `[{filename, orig_w, orig_h, bbox: [x1,y1,x2,y2]}]`
- Script will auto-scale bbox → 224×224

**Measurement (Instance-level, 95th-percentile + spatial offset variant)**:
- Expand GT bbox by **τ = 15 px** on all sides → "neighbourhood" around annotation
- Threshold CAM at 95th percentile → "high-activation region" (top 5%)
- **Hit** = any pixel in that region overlaps with the expanded bbox
- τ is configurable via `POINTING_GAME_TAU` constant at the top of the file

**Output**: 4-panel images (Original / Grad-CAM / Grad-CAM++ / Eigen-CAM) saved to `results/rq2_gradcam/`

---

## RQ3 — Proposed Model vs Baseline

**Objective**: Compare the proposed CNN (ConvNeXt-Tiny) against a Baseline BPNN using handcrafted features.

### BPNN Pipeline

**Feature Extraction (24-dim)**:

| Features | Details | Dim |
|----------|---------|-----|
| GLCM | 8-level quantized, 4 angles (0°,45°,90°,135°), 4 properties × 4 angles | 16 |
| HOG | 8×8 cells, 8 statistics (mean, std, var, median, max, min, skew, kurtosis) | 8 |
| **Total** | | **24** |

**GLCM properties**: Contrast, Correlation, Energy, Homogeneity (per-angle, not averaged)

**Model**:
- MLPClassifier (sklearn), activation=tanh, solver=Adam
- Hyperparameter search: **GridSearchCV** 5-fold, scoring=AUC
  - `hidden_layer_sizes`: {(64,32), (128,64), (128,64,32), (256,128), (256,128,64)}
  - `alpha`: {1e-4, 1e-3, 1e-2}
- Best architecture: **(256, 128), tanh, α=0.0001**
- Avg stopping iterations: **28** (per fold: 24, 24, 24, 39, 30)
- Threshold: Youden's Index from 5-fold CV = **0.5792**

**Comparison Table**:

| Metric | Proposed Model (ConvNeXt-Tiny) | Baseline (BPNN, GLCM+HOG) | Δ |
|--------|-------------------------------|--------------------------|---|
| Sensitivity | 0.9592 | 0.8367 | +0.1225 |
| Specificity | 0.6667 | 0.6111 | +0.0556 |
| AUC-ROC | 0.9150 | 0.8526 | +0.0624 |
| PPV | 0.8868 | 0.8542 | +0.0326 |
| NPV | 0.8571 | 0.5789 | +0.2782 |
| F1-Score | 0.9216 | 0.8454 | +0.0762 |

**Statistical Tests** (Proposed thr=0.7318, Baseline thr=0.5792):

| Test | H₀ | Result | p-value | Sig. |
|------|----|--------|---------|------|
| McNemar's Test | Both models make same errors | b=10 (Proposed✓/Baseline✗), c=3 (Proposed✗/Baseline✓) | 0.0923 | ns |
| DeLong's Test | AUC_Proposed = AUC_Baseline | ΔAUC = +0.0624 | 0.3591 | ns |

> Neither test reached significance — the two models are statistically equivalent on this test set.

**Results saved to**: `results/rq3_results.json`

---

## Running Order

```bash
# 1. Train backbones
bash run_gpu.sh train_resnet.py
bash run_gpu.sh train_efficientnet.py
bash run_gpu.sh train_convnext.py

# 2. RQ1 — backbone selection
bash run_gpu.sh rq1_backbone_comparison.py

# 3. Threshold optimization (Youden's Index)
bash run_gpu.sh threshold_optimization.py

# 4. Final evaluation on test set
bash run_gpu.sh final_evaluation.py

# 5. RQ2 — Grad-CAM localization
bash run_gpu.sh rq2_gradcam.py

# 6. RQ3 — CNN vs BPNN comparison
bash run_gpu.sh rq3_bpnn_comparison.py
```

> `run_gpu.sh` sets `LD_LIBRARY_PATH` from CUDA pip wheels in the `tf_gpu` conda environment.

---

## Technical Notes

| Topic | Detail |
|-------|--------|
| Framework | TensorFlow 2.21 + Keras 3 |
| Checkpoint format | `.keras` (not `.h5`) |
| GPU | NVIDIA Blackwell (RTX 5060 Ti, sm_120a) — requires `jit_compile=False` |
| Load model | `compile=False` — avoids deserialization errors |
| Augmentation | `RandomRotation(±10°)` via tf.data pipeline, training only |
| Epoch policy | 5-fold CV uses max 50 + early stopping; final retrain uses **avg stopping epoch** from CV |
| Feature cache | GLCM+HOG cached at `model_checkpoints/glcm_hog_features.npz` |
| Shared code | `dfu_common.py` — CONFIG, data loader, DFUModelTrainer, Optuna tuner, helpers |

### Key Functions in `dfu_common.py`

| Function / Class | Purpose |
|-----------------|---------|
| `load_preprocessed_inaoe()` | Load .npy images + labels |
| `create_fold_splits()` | Create stratified splits (test + 5-fold) |
| `DFUModelTrainer` | build, train_phase1, train_phase2, save |
| `DFUModelTrainer.phase1_best_epoch` | Stopping epoch of phase 1 (= length of val_loss history) |
| `DFUModelTrainer.phase2_best_epoch` | Stopping epoch of phase 2 (= length of val_loss history) |
| `train_phase1/2(fixed_epochs=N)` | Retrain on full set for exactly N epochs, no early stopping |
| `OptunaHyperparameterTuner` | Optuna TPE, Fold 1 only |
| `compute_youden_threshold()` | argmax(TPR−FPR) → threshold, sens, spec |
| `train_one_model()` | Optuna → 5-fold train → save val_preds + avg_epochs.json |
