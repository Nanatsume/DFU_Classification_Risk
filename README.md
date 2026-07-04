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
| **RQ5** | Can the best CNN model distinguish between all four IWGDF risk categories (0–3)? *(exploratory, podoscope dataset only)* |

---

## Dataset

### Preliminary (INAOE Thermal Foot Dataset)
334 images (224×224 px) from 167 patient pairs — 90 Control (CT), 244 Diabetic (DM).

### Target (Podoscope Plantar Pressure — to be collected)
300 diabetic patients, Buddhachinaraj Hospital, Phitsanulok, Thailand. ~10 eligible patients/day over ~30 working days.

- Both feet assessed and labeled independently → fewer than 600 foot-level images (unilateral amputees contribute 1 foot)
- No pre-specified IWGDF category quota — natural clinical distribution from outpatient diabetic care clinic
- Recruitment begins only after IRB approval from Mahidol University and Buddhachinaraj Hospital EC

**Inclusion criteria**
- Type 2 Diabetes Mellitus diagnosis
- Age ≥ 18 years
- Able to stand independently on the podoscope platform (unilateral amputees who can bear weight on the remaining limb are included)
- Cognitively alert and able to follow verbal instructions
- Diabetes-related foot deformities (claw toes, hammer toes, prominent bony landmarks, Charcot foot) are explicitly included — these represent IWGDF category 2+ and are a key subgroup

**Exclusion criteria**
- Open wounds, active ulcers, or active infections on the plantar surface (prevents reliable contact image acquisition)
- Bilateral lower-limb amputation (cannot stand on the platform)
- Congenital foot deformities unrelated to diabetes (clubfoot, congenital pes planus)
- Autoimmune or connective tissue diseases (SLE, vasculitis, uncontrolled rheumatoid arthritis) — independently affect lower-limb vasculature and confound IWGDF classification

**Annotation**
- Expert wound-care nurse conducts full clinical assessment (monofilament test, tuning fork, ABI, visual inspection) alongside image capture
- Specialist doctor reviews findings, assigns IWGDF category (0–3), and marks ROI bounding boxes for XAI evaluation using VIA2
- Binary label: Cat 0 = negative, Cat 1/2/3 = positive
- Full 4-class label (0–3) also retained for RQ5

**Splits** (Seed=42, stratified, patient-level):
```
├── Test Set  (20%, held out — never used during training or tuning)
└── Train+Val (80%, 5-fold CV)
```

---

## Key Design Decisions

**Prediction unit: foot image level, not patient level.**
Each foot is annotated independently (left and right feet can have different IWGDF risk categories). Image-level output also aligns with the clinical workflow — if one foot is flagged, the clinician can act immediately without waiting for the other foot.

**Split unit: patient level.**
Despite image-level prediction, the 80/20 train/test split and 5-fold CV are stratified at the *patient* level so that both feet of the same patient always stay in the same partition, preventing data leakage.

**Binary labels: IWGDF Cat 0 = negative, Cat 1+2+3 = positive.**
The goal is *risk screening*, not severity grading. Any identifiable risk warrants clinical follow-up, so categories 1–3 are collapsed into a single positive class. Full four-class IWGDF labels (0–3) are retained for RQ5.

**Primary metrics: Sensitivity and Specificity — not Accuracy.**
The INAOE dataset is imbalanced (CT:DM = 90:244). A majority-class predictor achieves >70% accuracy while providing no clinical value. Sensitivity captures missed at-risk patients; Specificity captures unnecessary referrals. Accuracy is reported for completeness only.

**Statistical tests for RQ2 and RQ3: McNemar's + DeLong's.**
McNemar's tests whether models make different errors on the same individual samples (decision level). DeLong's tests whether AUC-ROC values differ significantly (ranking level). Both are needed because a model can have similar binary decisions but meaningfully different discriminative ability.

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

AdaBoost classifier with handcrafted features. The feature set differs between the preliminary and target studies.

**Preliminary (INAOE proxy):** Khandakar et al. (2021) top-10 thermal features, extracted from raw pixel temperature maps and angiosome CSV files of the INAOE dataset — the same dataset and features on which Khandakar et al. originally demonstrated strong AdaBoost performance.
- Features: Age, Gender, TCI, HighestTemp, NTR class fractions (5), zone statistics (Mean, Median, SD, ET, ETD, HSE) for 5 angiosome zones

**Target (Podoscope dataset):** Our own 43 handcrafted features extracted from plantar pressure footprint images, grouped into four categories.

| Feature Group | Features | Count |
|---|---|---|
| GLCM | Contrast, Correlation, Energy, Homogeneity × 4 orientations (0°, 45°, 90°, 135°) | 16 |
| LBP | Statistical moments from LBP histograms | 8 |
| HOG | Statistical distribution of HOG descriptors | 8 |
| Geometric | Foot arch indices and regional pressure areas | 11 |
| **Total** | | **43** |

**Pipeline (both datasets):** Correlation filter (>95%) → SMOTE → ensemble importance ranking (XGBoost + RF + ExtraTree) → top subset → AdaBoost (decision stump, balanced class weight)

---

## XAI Methods (RQ4)

Grad-CAM, Grad-CAM++, and Eigen-CAM applied to the final model. Evaluated via **top-region pointing game** against expert-annotated ROI bounding boxes (top-5% activation, spatial tolerance τ=15px).

---

## Multiclass Extension (RQ5)

The best CNN backbone from RQ1 is adapted for four-class IWGDF risk category classification (Cat 0, 1, 2, 3) by replacing the binary output head with a softmax layer. All other components (backbone, GAP, Dense layers) remain unchanged.

| Item | Detail |
|------|--------|
| Output head | Dense(4, softmax) — replaces Dense(1, sigmoid) |
| Loss | Categorical cross-entropy |
| Class weighting | Inverse class frequency per fold |
| Evaluation | Per-class sensitivity (one-vs-rest), macro AUC-ROC, confusion matrix |
| Significance tests | None — treated as exploratory |
| Dataset | Podoscope dataset only — INAOE has no IWGDF subcategory labels |

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
| BO trials | 10 trials for all strategies |
| G-LF/G-FL blocks | EfficientNetB0 uses 5 merged block groups (stem, block1+2, block3+4, block5+6, block7+top); ResNet50 and ConvNeXt-Tiny use 5 natural groups each |
| WSL memory | Requires `C:\Users\<user>\.wslconfig` with `memory=12GB` and `swap=16GB` — G-LF/G-FL accumulate TF graph state and will trigger WSL kernel restart without this cap |
