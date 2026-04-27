# DFU Classification with Deep Learning

Automated classification of Diabetic Foot Ulcer (DFU) images using deep learning with attention mechanisms (CBAM), compared against a handcrafted-feature baseline (BPNN).

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
CBAM (reduction_ratio=16)
    |-- Channel Attention : AvgPool + MaxPool -> Shared MLP -> sigmoid
    +-- Spatial Attention : AvgPool + MaxPool along C -> Conv2D(7x7) -> sigmoid
    |
GlobalAveragePooling2D
    |
Dense(256, relu) -> Dropout(0.5)
    |
Dense(64, relu)  -> Dropout(0.5)
    |
Dense(1, sigmoid)
```

**Backbones tested**: EfficientNetB0, ResNet50, ConvNeXt-Tiny

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
- **Trials**: 10 trials on Fold 1 only

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
| EfficientNetB0 | 0.4500 | 1.0000 | 0.0000 | ✗ |
| **ResNet50** | **0.8235** | **0.9846** | **0.1981** | ✗ |
| ConvNeXt-Tiny | 0.8207 | 0.8359 | 0.6257 | ✗ |

> No backbone passed all three criteria. **ResNet50** was selected as it achieved the highest AUC (CBAM helped ResNet50 outperform ConvNeXt-Tiny).

---

### RQ2 — Threshold Optimization (Youden's Index)

**Objective**: Compare default threshold (0.5) against Youden's Index threshold on ResNet50+CBAM.

$$J = \text{Sensitivity} + \text{Specificity} - 1 \qquad \text{threshold}^* = \arg\max(\text{TPR} - \text{FPR})$$

**Per-fold Youden threshold**:

| Fold | Youden thr | Sensitivity | Specificity |
|------|-----------|-------------|-------------|
| 1 | 0.6754 | 0.9231 | 0.5333 |
| 2 | 0.6990 | 0.8974 | 0.5333 |
| 3 | 0.7006 | 0.8462 | 0.8571 |
| 4 | 0.6401 | 0.9231 | 0.9286 |
| 5 | 0.7847 | 0.7436 | 0.8571 |
| **Mean** | **0.7000** | — | — |

**Default (0.5) vs Youden (0.7000)**:

| Metric | Default 0.5 | Youden 0.7000 | Delta |
|--------|------------|--------------|-------|
| Sensitivity | 0.9846 ± 0.0205 | 0.7795 ± 0.1176 | −0.2051 (−20.8%) |
| Specificity | 0.1981 ± 0.1779 | 0.7267 ± 0.1492 | +0.5286 (+266.9%) |

> Youden threshold trades −20.8% Sensitivity for +266.9% Specificity, bringing Specificity above the ≥0.70 criterion.

---

### RQ3 — Final Evaluation on Test Set

**Strategy**:
1. Record average stopping epoch from 5-fold CV
2. Retrain on full training set (267 images) for that fixed number of epochs
3. No early stopping in the final retrain
4. Evaluate with Youden threshold (0.7146)

**Average stopping epochs** (ResNet50+CBAM): Phase 1 = **20**, Phase 2 = **49**

**Test set results**:

| Metric | Value |
|--------|-------|
| AUC-ROC | **0.8447** |
| Sensitivity | **0.7551** |
| Specificity | **0.6667** |
| PPV | 0.8605 |
| NPV | 0.5000 |
| F1-Score | 0.8043 |
| Accuracy | 0.7313 |

---

### RQ4 — Explainability (Grad-CAM)

**Objective**: Visualize which image regions the model attends to.

| Method | Concept |
|--------|---------|
| **Grad-CAM** | Weight feature maps by global-avg-pooled gradients |
| **Grad-CAM++** | Weight by alpha coefficients from 2nd-order gradients |
| **Eigen-CAM** | Gradient-free — uses PC1 from SVD of the feature map |

Output: 4-panel images (Original / Grad-CAM / Grad-CAM++ / Eigen-CAM) saved to `results/rq4_gradcam/`

---

### RQ5 — CNN vs BPNN

**Objective**: Compare the proposed CNN against a BPNN trained on handcrafted features.

**BPNN feature extraction (24-dim)**:

| Features | Details | Dim |
|----------|---------|-----|
| GLCM | 8-level, 4 angles (0/45/90/135°), 4 properties × 4 angles | 16 |
| HOG | 8×8 cells, 8 statistics (mean, std, var, median, max, min, skew, kurtosis) | 8 |

**Best BPNN**: architecture=(256, 128), activation=tanh, α=0.0001, Youden thr=0.5792

**Comparison on test set**:

| Metric | ResNet50+CBAM | BPNN (GLCM+HOG) | Delta |
|--------|--------------|-----------------|-------|
| Sensitivity | 0.7551 | 0.8367 | +0.0816 |
| Specificity | 0.6667 | 0.6111 | −0.0556 |
| AUC-ROC | 0.8447 | 0.8526 | +0.0079 |
| PPV | 0.8605 | 0.8542 | −0.0063 |
| NPV | 0.5000 | 0.5789 | +0.0789 |
| F1-Score | 0.8043 | 0.8454 | +0.0411 |

**Statistical tests**: McNemar's Test + Bootstrap AUC p-value (2,000 samples)

---

### RQ6 — BPNN Feature Interpretability (Supplementary)

**Objective**: Understand which features drive the BPNN's decisions.

| Method | Concept | Output |
|--------|---------|--------|
| Permutation Importance | Shuffle each feature, measure AUC drop | bar chart |
| SHAP KernelExplainer | Shapley value per feature per sample | beeswarm + bar |

**Key findings**:
- **HOG Median and HOG Mean** are the most important features — overall gradient magnitude is the primary signal
- DM feet show lower HOG values than CT — more uniform pressure distribution
- **Homogeneity 0° and Contrast 0°** are the most important GLCM features
- Correlation features have almost no effect on predictions

---

## File Structure

```
Project/
├── dfu_common.py                  # Shared config, data loader, trainer, Optuna tuner
├── train_resnet.py                # Train ResNet50 (Optuna + 5-fold CV)
├── train_efficientnet.py          # Train EfficientNetB0
├── train_convnext.py              # Train ConvNeXt-Tiny
├── rq1_backbone_comparison.py     # RQ1
├── rq2_threshold_optimization.py  # RQ2
├── rq3_final_evaluation.py        # RQ3
├── rq4_gradcam.py                 # RQ4
├── rq5_bpnn_comparison.py         # RQ5
├── rq6_bpnn_interpretability.py   # RQ6 (Supplementary)
├── run_gpu.sh                     # Helper script for GPU execution
├── DFU_Project_Overview.ipynb     # Interactive project overview notebook
├── model_checkpoints/             # best_params.json, val_preds.npz, avg_epochs.json
└── results/                       # JSON results, log files, CAM images
```

---

## How to Run

```bash
# 1. Train backbones
./run_gpu.sh train_resnet.py
./run_gpu.sh train_efficientnet.py
./run_gpu.sh train_convnext.py

# 2. RQ1 — backbone selection
./run_gpu.sh rq1_backbone_comparison.py

# 3. RQ2 — threshold optimization
./run_gpu.sh rq2_threshold_optimization.py

# 4. RQ3 — final test evaluation
./run_gpu.sh rq3_final_evaluation.py

# 5. RQ4 — XAI visualizations
./run_gpu.sh rq4_gradcam.py

# 6. RQ5 — BPNN comparison
./run_gpu.sh rq5_bpnn_comparison.py

# 7. RQ6 — BPNN interpretability (run after RQ5)
./run_gpu.sh rq6_bpnn_interpretability.py
```

> `run_gpu.sh` sets `LD_LIBRARY_PATH` from CUDA pip wheels in the `tf_gpu` conda environment.

---

## Technical Notes

| Topic | Detail |
|-------|--------|
| Framework | TensorFlow 2.21 + Keras 3 |
| Checkpoint format | `.keras` (not `.h5`) |
| GPU | NVIDIA Blackwell (RTX 5060 Ti, sm_120a) — requires `jit_compile=False` |
| Load model | `compile=False` + `custom_objects={'CBAM': CBAM}` |
| Augmentation | `RandomRotation(±10°)` via tf.data pipeline, training only |
| Epoch policy | 5-fold CV uses max 50 + early stopping; final retrain uses avg stopping epoch from CV |
| Feature cache | GLCM+HOG cached at `model_checkpoints/glcm_hog_features.npz` |
| Shared code | `dfu_common.py` — CONFIG, data loader, DFUModelTrainer, Optuna tuner |
