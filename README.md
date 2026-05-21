# DFU Risk Classification

> **Note**: This repository contains **preliminary results** using the publicly available INAOE dataset as a proxy. The full study will use a proprietary dataset captured with a **podoscope**, which provides standardized plantar foot images under controlled conditions. Results here are intended to validate the pipeline and methodology before the podoscope data is collected.

---

## Dataset

**INAOE Dataset** — 334 images (224×224 px, normalized [0,1], stored as `.npy`)

| Class | Label | Count |
|-------|-------|-------|
| Control (normal wound) | CT = 0 | 90 |
| Diabetic wound | DM = 1 | 244 |

**Splits** (Seed=42, Stratified):

```
334 images
├── Test Set  (67 images, 20%)  — held out, evaluated once at the end
└── Train+Val (267 images, 80%)
    ├── Fold 1 (train 214 / val 53)
    ├── Fold 2
    ├── Fold 3
    ├── Fold 4
    └── Fold 5
```

---

## Model Architecture

```
Input (224×224×3)
    |
Backbone (ImageNet pretrained, frozen in Phase 1 / top 30% unfrozen in Phase 2)
    |
GlobalAveragePooling2D
    |
Dense(n₁, relu) -> Dropout
    |
Dense(n₂, relu) -> Dropout
    |
Dense(1, sigmoid)
```

**Backbones Compared**: EfficientNetB0, ResNet50, ConvNeXt-Tiny

### Two-Phase Training

| Phase | Backbone | Max Epochs | Early Stopping | LR |
|-------|----------|-----------|----------------|-----|
| 1 | Frozen | 50 | patience=5 (val_loss) | 1e-3 |
| 2 | Unfreeze top 30% | 50 | patience=15 (val_loss) | 1e-4 (Exp decay) |

- **Augmentation**: RandomRotation(±10°) on training set only
- **Class weights**: sklearn balanced class weighting to address class imbalance
- **Optimizer**: Adam (Phase 1), Adam + ExponentialDecayScheduler (Phase 2)

### Hyperparameter Tuning — Optuna

- **Sampler**: TPE (Tree-structured Parzen Estimator), Seed=42
- **Trials**: 10 trials, each evaluated with fold 1 only (for speed)

| Parameter | Search Space |
|-----------|-------------|
| `dropout_rate` | 0.2 – 0.5 |
| `l2_reg` | 1e-5 – 1e-2 |
| `dense_units_1` | {128, 256, 512} |
| `dense_units_2` | {64, 128, 256} |
| `batch_size` | {16, 32} |
| `phase1_lr` | 1e-4 – 1e-2 |
| `phase2_lr` | 1e-6 – 1e-4 |

**Best hyperparameters per backbone** (Optuna result):

| Parameter | EfficientNetB0 | ResNet50 | ConvNeXt-Tiny |
|-----------|---------------|----------|---------------|
| `dense_units_1` | 128 | 128 | 128 |
| `dense_units_2` | 256 | 256 | 256 |
| `dropout_rate` | 0.312 | 0.291 | 0.312 |
| `l2_reg` | 7.11e-3 | 1.96e-5 | 7.11e-3 |
| `batch_size` | 32 | 32 | 32 |
| `phase1_lr` | 1.10e-4 | 4.20e-4 | 1.10e-4 |
| `phase2_lr` | 8.71e-5 | 1.10e-5 | 8.71e-5 |

---

## Research Questions & Results

### RQ1 — Backbone Comparison

**Objective**: Select the best backbone from 3 candidates using 5-fold CV.

**Selection criterion**: Highest AUC-ROC

**Results** (mean across 5 folds, threshold = 0.5):

| Backbone | AUC | Sensitivity | Specificity |
|----------|-----|-------------|-------------|
| EfficientNetB0 | 0.6379 | 0.5949 | 0.4181 |
| ResNet50 | 0.7875 | 0.9897 | 0.1533 |
| **ConvNeXt-Tiny** | **0.8293** | **0.8000** | **0.6952** |

> **ConvNeXt-Tiny** was selected as the best backbone (highest AUC-ROC = 0.8293).

---

### Threshold Optimization (Youden's Index)

**Objective**: Compare default threshold (0.5) against Youden's Index threshold on ConvNeXt-Tiny.

$$J = \text{Sensitivity} + \text{Specificity} - 1 \qquad \text{threshold}^* = \arg\max(\text{TPR} - \text{FPR})$$

**Per-fold Youden threshold**:

| Fold | Youden thr | Sensitivity | Specificity |
|------|-----------|-------------|-------------|
| 1 | 0.8586 | 0.6923 | 0.8667 |
| 2 | 0.4464 | 0.8205 | 0.6667 |
| 3 | 0.7798 | 0.6923 | 0.7857 |
| 4 | 0.6629 | 0.7949 | 0.8571 |
| 5 | 0.9112 | 0.7436 | 1.0000 |
| **Mean** | **0.7318** | — | — |

**Default (0.5) vs Youden (0.7318)**:

| Metric | Default 0.5 | Youden 0.7318 | Delta |
|--------|------------|--------------|-------|
| Sensitivity | 0.8000 ± 0.0192 | 0.7333 ± 0.0205 | −0.0667 (−8.3%) |
| Specificity | 0.6952 ± 0.0508 | 0.7657 ± 0.0777 | +0.0705 (+10.1%) |

> Youden threshold trades −8.3% Sensitivity for +10.1% Specificity (0.695 → 0.766).

---

### Threshold Optimization (Threshold Sweep)

**Objective**: Select the optimal threshold by sweeping 0.05–0.95 (step=0.05) on combined 5-fold validation predictions.

**Selection rule**: Highest Sensitivity where both Sensitivity ≥ 0.70 and Specificity ≥ 0.70. If no threshold satisfies both, fall back to max Youden's J.

| Threshold | Sensitivity | Specificity | Selected |
|-----------|-------------|-------------|----------|
| 0.50 | 0.8000 | 0.6944 | |
| 0.55 | 0.7846 | 0.6944 | |
| **0.60** | **0.7744** | **0.7361** | ✓ |
| 0.65 | 0.7744 | 0.7500 | |
| 0.70 | 0.7333 | 0.7500 | |

> **Selected threshold = 0.60** — highest Sensitivity with both Sens ≥ 0.70 and Spec ≥ 0.70.

---

### Final Evaluation on Test Set

**Strategy**:
1. Record average stopping epoch from 5-fold CV
2. Retrain on full training set (267 images) for that fixed number of epochs
3. No early stopping in the final retrain
4. Evaluate with both Youden (0.7318) and Sweep (0.60) thresholds

**Average stopping epochs** (ConvNeXt-Tiny): Phase 1 = **50**, Phase 2 = **46**

**Test set results**:

| Metric | Youden (thr=0.7318) | Sweep (thr=0.60) |
|--------|---------------------|------------------|
| AUC-ROC | **0.9150** | **0.9150** |
| Sensitivity | 0.9592 | **0.9796** |
| Specificity | **0.6667** | **0.6667** |
| PPV | 0.8868 | 0.8889 |
| NPV | 0.8571 | 0.9231 |
| F1-Score | 0.9216 | 0.9320 |

---

### RQ2 — Localization Evaluation

**Objective**: Evaluate whether the model correctly localizes lesion regions using three CAM methods, quantified by the Top-Region Pointing Game.

| Method | Concept |
|--------|---------|
| **Grad-CAM** | Weight feature maps by global-avg-pooled gradients |
| **Grad-CAM++** | Weight by alpha coefficients from 2nd-order gradients |
| **Eigen-CAM** | Gradient-free — uses PC1 from SVD of the feature map |

**Metric**: **Top-Region Pointing Game** — checks whether the highest-activation region (top 5% of CAM, thresholded at 95th percentile) overlaps with the ground-truth lesion bounding box (expanded by τ=15 px).

Output: 4-panel images (Original / Grad-CAM / Grad-CAM++ / Eigen-CAM) saved to `results/rq2_gradcam/`

> **Note**: Top-Region Pointing Game evaluation has not been conducted, as the INAOE dataset does not provide ground-truth ROI annotations. Localization results are therefore **qualitative only**.

---

### RQ3 — Proposed Model vs Baseline

**Objective**: Compare the proposed CNN (ConvNeXt-Tiny) against a Baseline BPNN trained on handcrafted features.

**Baseline feature extraction (24-dim)**:

| Features | Details | Dim |
|----------|---------|-----|
| GLCM | 8-level, 4 angles (0/45/90/135°), 4 properties × 4 angles | 16 |
| HOG | 8×8 cells, 8 statistics (mean, std, var, median, max, min, skew, kurtosis) | 8 |

**Best Baseline (BPNN)**: architecture=(256, 128), activation=tanh, α=0.0001, sweep thr=0.55

Thresholds selected via sweep (0.05–0.95, step=0.05) on combined 5-fold validation predictions — highest Sensitivity where both Sens ≥ 0.70 and Spec ≥ 0.70.

**Comparison on test set** (Proposed thr=0.60, Baseline thr=0.55):

| Metric | Proposed Model (ConvNeXt-Tiny) | Baseline (BPNN, GLCM+HOG) | Δ |
|--------|-------------------------------|--------------------------|---|
| Sensitivity | 0.9796 | 0.8776 | +0.1020 |
| Specificity | 0.6667 | 0.6111 | +0.0556 |
| AUC-ROC | 0.9150 | 0.8526 | +0.0624 |
| PPV | 0.8889 | 0.8600 | +0.0289 |
| NPV | 0.9231 | 0.6471 | +0.2760 |
| F1-Score | 0.9320 | 0.8687 | +0.0634 |

**Statistical tests** (Proposed thr=0.60, Baseline thr=0.55):

| Test | Result | p-value | Significance |
|------|--------|---------|--------------|
| McNemar's Test (H₀: same error pattern) | b=8 (Proposed✓/Baseline✗), c=2 (Proposed✗/Baseline✓) | 0.1094 | ns |
| DeLong's Test (H₀: AUC_Proposed = AUC_Baseline) | ΔAUC = +0.0624 | 0.3591 | ns |

> Neither test reached significance — the two models are statistically equivalent on this test set.

---

## File Structure

```
Project/
├── dfu_common.py                  # Shared config, data loader, trainer, Optuna tuner
├── train_resnet.py                # Train ResNet50 (Optuna + 5-fold CV)
├── train_efficientnet.py          # Train EfficientNetB0
├── train_convnext.py              # Train ConvNeXt-Tiny
├── rq1_backbone_comparison.py     # RQ1
├── threshold_optimization.py      # Youden threshold (pipeline step)
├── final_evaluation.py            # Final retrain + test eval (pipeline step)
├── rq2_gradcam.py                 # RQ2
├── rq3_bpnn_comparison.py         # RQ3
├── run_gpu.sh                     # Helper script for GPU execution
├── DFU_Project_Overview.ipynb     # Interactive project overview notebook
├── Image_Preprocessing_Pipeline.ipynb  # Image preprocessing pipeline
├── Prelim_preprocessing.ipynb     # Preliminary preprocessing exploration
├── model_checkpoints/             # best_params.json, val_preds.npz, avg_epochs.json
└── results/                       # JSON results, .npy test probs, log files, CAM images, model architecture plots
```

---

## How to Run

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
| Epoch policy | 5-fold CV uses max 50 + early stopping; final retrain uses avg stopping epoch from CV |
| Feature cache | GLCM+HOG cached at `model_checkpoints/glcm_hog_features.npz` |
| Shared code | `dfu_common.py` — CONFIG, data loader, DFUModelTrainer, Optuna tuner |
