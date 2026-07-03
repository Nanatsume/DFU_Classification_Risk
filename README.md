# DFU Risk Classification — CNN + XAI on Plantar Pressure Footprint Images

Master's thesis proposal, Mahidol University ICT.

> **Preliminary study**: All current results use the publicly available **INAOE thermal foot dataset** (334 images) as a proxy to validate the pipeline. The full study will use a proprietary **podoscope plantar pressure dataset** (300 patients) collected at Buddhachinaraj Hospital, Phitsanulok, Thailand.

---

## Research Questions

| RQ | Question |
|----|---------|
| **RQ1** | Which combination of CNN backbone × fine-tuning strategy × input orientation achieves the highest AUC-ROC? (48 combinations) |
| **RQ2** | Does flipping the left foot image to match right-foot orientation (S2) significantly outperform original orientation (S1)? |
| **RQ3** | How does the best CNN model compare with a Traditional ML baseline (AdaBoost + Khandakar thermal features)? |
| **RQ4** | How do Grad-CAM, Grad-CAM++, and Eigen-CAM compare in localizing pressure risk regions? |

---

## Dataset

### Preliminary (INAOE Thermal Foot Dataset)
334 images (224×224 px) from 167 patient pairs — 90 Control (CT), 244 Diabetic (DM).

### Target (Podoscope Plantar Pressure — to be collected)
300 diabetic patients, Buddhachinaraj Hospital. Both feet assessed independently; patients with unilateral amputation contribute one foot image. No pre-specified IWGDF category quota — natural clinical distribution.

**Splits** (Seed=42, stratified, patient-level):
```
├── Test Set  (20%, held out)
└── Train+Val (80%, 5-fold CV)
```

---

## Model Architecture

**Proposed Model**: Three CNN backbones with ImageNet pre-trained weights + shared classification head.

| Backbone | Output Dim |
|----------|-----------|
| EfficientNetB0 | 1280 |
| ResNet50 | 2048 |
| ConvNeXt-Tiny | 768 |

**Classification head**: GlobalAveragePooling → Dense(n₁, relu) → Dropout → Dense(n₂, relu) → Dropout → Dense(1, sigmoid)

**8 Fine-tuning strategies**: FT, LP, G-LF, G-FL, LP-FT, L1-SP, L2-SP, Auto-RGN

**2 Input strategies**: S1 (original orientation), S2 (left foot horizontally flipped)

**Total RQ1 combinations**: 3 × 8 × 2 = **48**

**Hyperparameter tuning**: GPyOpt Bayesian Optimization (Gaussian Process + Expected Improvement), 10 trials per combination.

---

## Baseline Model (RQ3)

AdaBoost with top-10 thermal features selected from Khandakar et al. (2021):
- Features: Age, Gender, TCI, HighestTemp, NTR class fractions (5), zone statistics (Mean, Median, SD, ET, ETD, HSE) for 5 angiosome zones
- Pipeline: Correlation filter (>95%) → SMOTE → RF importance ranking → top-10 → AdaBoost (decision stump, balanced class weight)

---

## XAI Methods (RQ4)

Grad-CAM, Grad-CAM++, and Eigen-CAM applied to the final model. Evaluated via **top-region pointing game** against expert-annotated ROI bounding boxes (top-5% activation, spatial tolerance τ=15px).

---

## File Structure

```
Project/
├── dfu_common.py              # Shared config, data loader, DFUModelTrainer, GPyOpt tuner
├── rq1_run_combo.py           # Train one combo (backbone × strategy × input), resume-aware
├── rq1_run_all.sh             # Loop over all 48 combos sequentially
├── rq1_compare.py             # Summarise RQ1 results, select best config
├── rq2_final_eval.py          # Retrain best S1+S2 configs, evaluate on test set
├── rq3_comparison.py          # AdaBoost baseline (full 39-feature Khandakar pipeline)
├── rq4_xai.py                 # Grad-CAM / Grad-CAM++ / Eigen-CAM + pointing game
├── Model/
│   └── split_feet.py          # Left/right foot separation from podoscope images
├── results/
│   ├── rq1/                   # Per-combo: best_params.json, metrics.json, fold*.keras, val_preds.npz
│   ├── rq4_xai/               # CAM heatmap images
│   └── *.json / *.npy         # Final eval results
└── 69b7a55ef1c9f8e33a9cbb5a/  # LaTeX thesis proposal
    ├── chapter1.tex
    ├── chapter2.tex
    ├── chapter3.tex
    └── abstract.tex
```

---

## How to Run

```bash
# RQ1 — train all 48 combinations (resume-aware, skips completed combos)
bash rq1_run_all.sh >> rq1_run_all.log 2>&1 &

# RQ1 — summarise results and select best config
python rq1_compare.py

# RQ2 — retrain best S1 and S2 configs, compare on test set
python rq2_final_eval.py

# RQ3 — AdaBoost baseline comparison
python rq3_comparison.py

# RQ4 — XAI heatmaps + pointing game
python rq4_xai.py
```

---

## Preliminary Results (INAOE Dataset — In Progress)

RQ1 full 48-combo run currently in progress. Partial results (mean ± SD across 5-fold CV, threshold = 0.5):

| Backbone | Strategy | Input | AUC-ROC | Sensitivity | Specificity |
|----------|----------|-------|---------|-------------|-------------|
| EfficientNetB0 | FT | S1 | 0.8675 ± 0.0746 | 0.9077 ± 0.1602 | 0.3552 ± 0.3511 |
| EfficientNetB0 | LP-FT | S1 | 0.9566 ± 0.0194 | 0.9385 ± 0.0140 | 0.8048 ± 0.0943 |
| ResNet50 | LP-FT | S1 | 0.9223 ± 0.0241 | 0.9539 ± 0.0335 | 0.6505 ± 0.0955 |
| ConvNeXt-Tiny | LP-FT | S1 | **0.9644 ± 0.0253** | 0.9436 ± 0.0556 | 0.8057 ± 0.0906 |

*Full 48-combo table will be updated upon completion.*

---

## Technical Notes

| Topic | Detail |
|-------|--------|
| Framework | TensorFlow 2.21 + Keras 3 |
| GPU | NVIDIA RTX 5060 Ti (sm_120a) — TF JIT-compiles PTX on first run (~30 min) |
| Checkpoint format | `.keras` (Keras 3 native) |
| Augmentation | RandomRotation(±10°), training only |
| Epoch policy | CV uses early stopping; final retrain uses mean stopped epoch across folds |
| Results location | `results/rq1/<combo>/` — best_params, fold checkpoints, val_preds, metrics |
| Khandakar cache | `model_checkpoints/khandakar_features_39.npz` (auto-generated on first RQ3 run) |
