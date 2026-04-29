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
- **Test set** (held-out): 20% → ~67 images (separated at the start, never touched during training)
- **Training set**: 80% → ~267 images, split into 5-fold Stratified CV
- **Seed**: 42 (fixed across all files to ensure identical splits)

```
334 images
├── Test Set (~67 images) ─────────── evaluated at the end only
└── Train+Val (~267 images)
    ├── Fold 1 (train ~213 / val ~54)
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
| RQ2 | How does Youden's Index threshold help? | `rq2_threshold_optimization.py` |
| RQ3 | Final performance on the test set | `rq3_final_evaluation.py` |
| RQ4 | Localization Evaluation (Grad-CAM / Grad-CAM++ / Eigen-CAM + Top-Region Pointing Game) | `rq4_gradcam.py` |
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
- **Trials**: 10 trials, evaluated on Fold 1 only (for speed)
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
├── rq2_threshold_optimization.py    ← RQ2
├── rq3_final_evaluation.py          ← RQ3
├── rq4_gradcam.py                   ← RQ4
├── rq5_bpnn_comparison.py           ← RQ5
├── rq6_bpnn_interpretability.py     ← RQ6 (Supplementary — Permutation + SHAP)
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

**Results** (mean across 5 folds, threshold = 0.5, with CBAM):

| Backbone | AUC | Sens | Spec | Passes? |
|----------|-----|------|------|---------|
| EfficientNetB0 | 0.4298 | 1.0000 | 0.0000 | ✗ |
| ResNet50 | 0.7483 | 1.0000 | 0.0000 | ✗ |
| **ConvNeXt-Tiny** | **0.8277** | **0.8205** | **0.6800** | ✗ |

> No backbone passed all three criteria. **ConvNeXt-Tiny** was selected as it achieved the highest AUC and came closest to meeting the specificity criterion (0.68 vs threshold 0.70).

**Results saved to**: `results/rq1_results.json`

---

## RQ2 — Threshold Optimization (Youden's Index)

**Objective**: Compare threshold = 0.5 vs Youden's Index threshold on ConvNeXt-Tiny+CBAM.

**Youden's J formula**:
```
J = Sensitivity + Specificity − 1
threshold* = argmax(TPR − FPR)
```

**Step 1 — Per-fold Youden threshold** (ConvNeXt-Tiny+CBAM):

| Fold | Youden thr | Sens | Spec |
|------|-----------|------|------|
| 1 | 0.8759 | 0.6923 | 0.8667 |
| 2 | 0.6932 | 0.8205 | 0.8000 |
| 3 | 0.7001 | 0.7436 | 0.7857 |
| 4 | 0.8053 | 0.7692 | 0.9286 |
| 5 | 0.7146 | 0.8718 | 0.8571 |
| **Mean** | **0.7578** | | |

**Step 2 — Default (0.5) vs Mean Youden (0.7578) applied to all folds**:

| Metric | Default 0.5 | Youden 0.7578 | Δ |
|--------|------------|--------------|---|
| Sensitivity | 0.8205 ± 0.0429 | 0.7641 ± 0.0470 | −0.0564 (−6.9%) |
| Specificity | 0.6800 ± 0.0373 | 0.8210 ± 0.0667 | +0.1410 (+20.7%) |

> Youden threshold trade-off: Sensitivity drops −6.9% but Specificity gains +20.7% — rising from 0.68 to 0.82, exceeding the ≥0.70 criterion.

**Results saved to**: `results/rq2_results.json`

---

## RQ3 — Final Evaluation on Test Set

**Objective**: Evaluate the proposed model (ConvNeXt-Tiny+CBAM) on the held-out test set.

**Strategy**:
1. Record the average stopping epoch from 5-fold CV (`ConvNeXt-Tiny_avg_epochs.json`)
2. Retrain on **full training set (267 images)** for exactly that many epochs
3. No early stopping in the final retrain
4. Evaluate with Youden threshold (0.7578) from RQ2

**Avg stopping epochs** (ConvNeXt-Tiny+CBAM):
- Phase 1: **50 epochs**
- Phase 2: **47 epochs**

**Test set results**:

| Metric | Value |
|--------|-------|
| Sensitivity | **0.8163** |
| Specificity | **0.6667** |
| AUC-ROC | **0.8333** |
| PPV | 0.8696 |
| NPV | 0.5714 |
| F1-Score | 0.8421 |

**Results saved to**: `results/rq3_results.json`, `results/rq3_test_probs.npy`

---

## RQ4 — Localization Evaluation

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

**Output**: 4-panel images (Original / Grad-CAM / Grad-CAM++ / Eigen-CAM) saved to `results/rq4_gradcam/`

---

## RQ5 — CNN vs BPNN

**Objective**: Compare the proposed CNN against a BPNN using handcrafted features.

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

| Metric | ConvNeXt-Tiny+CBAM | BPNN (GLCM+HOG) | Δ |
|--------|-------------------|-----------------|---|
| Sensitivity | 0.8163 | 0.8367 | +0.0204 |
| Specificity | 0.6667 | 0.6111 | −0.0556 |
| AUC-ROC | 0.8333 | 0.8526 | +0.0193 |
| PPV | 0.8696 | 0.8542 | −0.0154 |
| NPV | 0.5714 | 0.5789 | +0.0075 |
| F1-Score | 0.8421 | 0.8454 | +0.0033 |

**Statistical Tests** (CNN thr=0.7578, BPNN thr=0.5792):

| Test | H₀ | Result | p-value | Sig. |
|------|----|--------|---------|------|
| McNemar's Test | Both models make same errors | b=8 (CNN✓/BPNN✗), c=8 (CNN✗/BPNN✓) | 1.0000 | ns |
| Bootstrap AUC | AUC_CNN = AUC_BPNN (n=2,000) | ΔAUC = −0.0193 | 0.7820 | ns |

> Neither test reached significance — the two models are statistically equivalent on this test set.

**Results saved to**: `results/rq5_results.json`

---

## RQ6 — BPNN Feature Interpretability (Supplementary)

**Objective**: Understand which features drive the BPNN's decisions.

**Methods used**:

| Method | Concept | Output |
|--------|---------|--------|
| **Permutation Importance** | Shuffle each feature, measure AUC drop | bar chart |
| **SHAP KernelExplainer** | Compute Shapley contribution per feature per sample | beeswarm + bar |

**Key findings**:
- **HOG Median and HOG Mean** are the most important features — overall gradient magnitude is the primary signal
- DM feet show lower HOG values than CT — more uniform pressure distribution
- **Homogeneity 0° and Contrast 0°** are the most important GLCM features
- Correlation features have almost no effect on predictions

**Output**: `results/rq6_bpnn_interpretability/` (permutation_importance.png, shap_beeswarm.png, shap_bar.png)

---

## Running Order

```bash
# 1. Train backbones
bash run_gpu.sh train_resnet.py
bash run_gpu.sh train_efficientnet.py
bash run_gpu.sh train_convnext.py

# 2. RQ1 — select backbone
bash run_gpu.sh rq1_backbone_comparison.py

# 3. RQ2 — optimize threshold
bash run_gpu.sh rq2_threshold_optimization.py

# 4. RQ3 — final test evaluation
bash run_gpu.sh rq3_final_evaluation.py

# 5. RQ4 — XAI visualizations
bash run_gpu.sh rq4_gradcam.py

# 6. RQ5 — BPNN comparison
bash run_gpu.sh rq5_bpnn_comparison.py

# 7. RQ6 — BPNN interpretability (supplementary, run after rq5)
bash run_gpu.sh rq6_bpnn_interpretability.py
```

> `run_gpu.sh` sets `LD_LIBRARY_PATH` from CUDA pip wheels in the `tf_gpu` conda environment.

---

## Technical Notes

| Topic | Detail |
|-------|--------|
| Framework | TensorFlow 2.21 + Keras 3 |
| Checkpoint format | `.keras` (not `.h5`) |
| GPU | NVIDIA Blackwell (RTX 5060 Ti, sm_120a) — requires `jit_compile=False` |
| Load model | `compile=False` + `custom_objects={'CBAM': CBAM}` — avoids deserialization errors |
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
