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
├── Test Set  (~67 images, 20%)  — held out, evaluated once at the end
└── Train+Val (~267 images, 80%)
    ├── Fold 1 (train ~213 / val ~54)
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
Backbone (ImageNet pretrained, frozen in Phase 1)
    |
GlobalAveragePooling2D
    |
Dense(256, relu) -> Dropout(0.5)
    |
Dense(64, relu)  -> Dropout(0.5)
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
- **Class weights**: applied to handle imbalance (DM:CT ≈ 2.7:1)
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

---

## Research Questions & Results

### RQ1 — Backbone Comparison

**Objective**: Select the best backbone from 3 candidates using 5-fold CV.

**Clinical screening criteria** (all three must be met):
- AUC-ROC ≥ 0.80 &nbsp;·&nbsp; Sensitivity ≥ 0.85 &nbsp;·&nbsp; Specificity ≥ 0.70

**Results** (mean across 5 folds, threshold = 0.5):

| Backbone | AUC | Sensitivity | Specificity | Pass All |
|----------|-----|-------------|-------------|----------|
| EfficientNetB0 | 0.6379 | 0.5949 | 0.4181 | ✗ |
| ResNet50 | 0.7875 | 0.9897 | 0.1533 | ✗ |
| **ConvNeXt-Tiny** | **0.8390** | **0.7846** | **0.6657** | ✗ |

> No backbone passed all three criteria. **ConvNeXt-Tiny** was selected as it achieved the highest AUC and came closest to meeting the specificity threshold (0.67 vs criterion 0.70).

---

### Threshold Optimization (Youden's Index)

**Objective**: Compare default threshold (0.5) against Youden's Index threshold on ConvNeXt-Tiny.

$$J = \text{Sensitivity} + \text{Specificity} - 1 \qquad \text{threshold}^* = \arg\max(\text{TPR} - \text{FPR})$$

**Per-fold Youden threshold**:

| Fold | Youden thr | Sensitivity | Specificity |
|------|-----------|-------------|-------------|
| 1 | 0.8860 | 0.6923 | 0.8667 |
| 2 | 0.3423 | 0.8718 | 0.7333 |
| 3 | 0.9378 | 0.5641 | 0.9286 |
| 4 | 0.9578 | 0.5897 | 0.9286 |
| 5 | 0.3404 | 0.9487 | 0.8571 |
| **Mean** | **0.6929** | — | — |

**Default (0.5) vs Youden (0.6929)**:

| Metric | Default 0.5 | Youden 0.6929 | Delta |
|--------|------------|--------------|-------|
| Sensitivity | 0.7846 ± 0.0205 | 0.7231 ± 0.0377 | −0.0615 (−7.8%) |
| Specificity | 0.6657 ± 0.1400 | 0.7352 ± 0.0850 | +0.0695 (+10.4%) |

> Youden threshold trades −7.8% Sensitivity for +10.4% Specificity, bringing Specificity above the ≥0.70 criterion.

---

### Final Evaluation on Test Set

**Strategy**:
1. Record average stopping epoch from 5-fold CV
2. Retrain on full training set (267 images) for that fixed number of epochs
3. No early stopping in the final retrain
4. Evaluate with Youden threshold (0.5859)

**Average stopping epochs** (ConvNeXt-Tiny): Phase 1 = **50**, Phase 2 = **47**

**Test set results** (threshold = 0.6929):

| Metric | Value |
|--------|-------|
| AUC-ROC | **0.9070** |
| Sensitivity | **0.9184** |
| Specificity | **0.8333** |
| PPV | 0.9375 |
| NPV | 0.7895 |
| F1-Score | 0.9278 |

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

### RQ3 — CNN vs BPNN

**Objective**: Compare the proposed CNN against a BPNN trained on handcrafted features.

**BPNN feature extraction (24-dim)**:

| Features | Details | Dim |
|----------|---------|-----|
| GLCM | 8-level, 4 angles (0/45/90/135°), 4 properties × 4 angles | 16 |
| HOG | 8×8 cells, 8 statistics (mean, std, var, median, max, min, skew, kurtosis) | 8 |

**Best BPNN**: architecture=(256, 128), activation=tanh, α=0.0001, Youden thr=0.5792

**Comparison on test set**:

| Metric | ConvNeXt-Tiny | BPNN (GLCM+HOG) | Delta |
|--------|--------------|-----------------|-------|
| Sensitivity | 0.9184 | 0.8367 | −0.0817 |
| Specificity | 0.8333 | 0.6111 | −0.2222 |
| AUC-ROC | 0.9070 | 0.8526 | −0.0544 |
| PPV | 0.9375 | 0.8542 | −0.0833 |
| NPV | 0.7895 | 0.5789 | −0.2105 |
| F1-Score | 0.9278 | 0.8454 | −0.0825 |

**Statistical tests** (CNN thr=0.6929, BPNN thr=0.5792):

| Test | Result | p-value | Significance |
|------|--------|---------|--------------|
| McNemar's Test (H₀: same error pattern) | b=11 (CNN✓/BPNN✗), c=3 (CNN✗/BPNN✓) | 0.0574 | ns |
| DeLong's Test (H₀: AUC_CNN = AUC_BPNN) | ΔAUC = +0.0544 | 0.4482 | ns |

> Neither test reached significance — the two models are statistically equivalent on this test set.

---

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
├── model_checkpoints/             # best_params.json, val_preds.npz, avg_epochs.json
└── results/                       # JSON results, log files, CAM images
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
