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
| RQ2 | Localization Evaluation (Grad-CAM / Grad-CAM++ / Eigen-CAM + Top-Region Pointing Game) | `rq2_gradcam.py` |
| RQ3 | CNN vs BPNN (GLCM+HOG) | `rq3_bpnn_comparison.py` |

---

## System Architecture

### Model Architecture (CNN)

```
Input (224×224×3)
    ↓
Backbone (ImageNet pretrained, frozen in Phase 1)
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
- **Trials**: 10 trials, each evaluated with 5-Fold CV
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
| EfficientNetB0 | 0.5601 | 0.9795 | 0.0000 | ✗ |
| ResNet50 | 0.6558 | 0.9949 | 0.0429 | ✗ |
| **ConvNeXt-Tiny** | **0.8252** | **0.7795** | **0.6667** | ✗ |

> No backbone passed all three criteria. **ConvNeXt-Tiny** was selected as it achieved the highest AUC and came closest to meeting the specificity criterion (0.67 vs threshold 0.70).

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
| 1 | 0.3679 | 0.8974 | 0.6667 |
| 2 | 0.5854 | 0.8205 | 0.6667 |
| 3 | 0.6694 | 0.6923 | 0.7857 |
| 4 | 0.9660 | 0.5897 | 1.0000 |
| 5 | 0.3408 | 0.9231 | 0.8571 |
| **Mean** | **0.5859** | | |

**Step 2 — Default (0.5) vs Mean Youden (0.5859) applied to all folds**:

| Metric | Default 0.5 | Youden 0.5859 | Δ |
|--------|------------|--------------|---|
| Sensitivity | 0.7795 ± 0.0384 | 0.7590 ± 0.0476 | −0.0205 (−2.6%) |
| Specificity | 0.6667 ± 0.1137 | 0.7238 ± 0.0833 | +0.0571 (+8.6%) |

> Youden threshold trade-off: Sensitivity drops −2.6% but Specificity gains +8.6% — rising from 0.67 to 0.72, exceeding the ≥0.70 criterion.

**Results saved to**: `results/rq2_results.json`

---

## Final Evaluation on Test Set

**Objective**: Evaluate the proposed model (ConvNeXt-Tiny) on the held-out test set.

**Strategy**:
1. Record the average stopping epoch from 5-fold CV (`ConvNeXt-Tiny_avg_epochs.json`)
2. Retrain on **full training set (267 images)** for exactly that many epochs
3. No early stopping in the final retrain
4. Evaluate with Youden threshold (0.5859) from RQ2

**Avg stopping epochs** (ConvNeXt-Tiny):
- Phase 1: **50 epochs**
- Phase 2: **43 epochs**

**Test set results**:

| Metric | Value |
|--------|-------|
| Sensitivity | **0.7755** |
| Specificity | **0.8889** |
| AUC-ROC | **0.8968** |
| PPV | 0.9500 |
| NPV | 0.5926 |
| F1-Score | 0.8539 |

**Results saved to**: `results/rq3_results.json`, `results/rq3_test_probs.npy`

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

## RQ3 — CNN vs BPNN

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

| Metric | ConvNeXt-Tiny | BPNN (GLCM+HOG) | Δ |
|--------|--------------|-----------------|---|
| Sensitivity | 0.7755 | 0.8367 | +0.0612 |
| Specificity | 0.8889 | 0.6111 | −0.2778 |
| AUC-ROC | 0.8968 | 0.8526 | −0.0442 |
| PPV | 0.9500 | 0.8542 | −0.0958 |
| NPV | 0.5926 | 0.5789 | −0.0137 |
| F1-Score | 0.8539 | 0.8454 | −0.0085 |

**Statistical Tests** (CNN thr=0.5859, BPNN thr=0.5792):

| Test | H₀ | Result | p-value | Sig. |
|------|----|--------|---------|------|
| McNemar's Test | Both models make same errors | b=9 (CNN✓/BPNN✗), c=7 (CNN✗/BPNN✓) | 0.8036 | ns |
| Bootstrap AUC | AUC_CNN = AUC_BPNN (n=2,000) | ΔAUC = +0.0442 | 0.4730 | ns |

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
