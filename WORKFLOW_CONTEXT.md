# DFU Classification — Workflow

## ภาพรวม

จำแนก DFU (Diabetic Foot Ulcer) เป็น 2 กลุ่ม: CT (Control=0) และ DM (Diabetic=1)
ใช้ Transfer Learning CNN เปรียบเทียบกับ BPNN ที่ใช้ handcrafted features

---

## ขั้นตอนที่ 1 — เตรียมข้อมูล

1. โหลด dataset INAOE (334 ภาพ: CT=90, DM=244)
2. แบ่ง **Test set 20%** (67 ภาพ) แยกออกไปก่อน ไม่แตะจนกว่าจะถึงขั้นตอนประเมินผล
3. แบ่ง **Train+Val 80%** (267 ภาพ) → 5-Fold Stratified CV

---

## ขั้นตอนที่ 2 — Hyperparameter Tuning (Optuna)

- ทำ **ทีละ backbone** (EfficientNetB0, ResNet50, ConvNeXt-Tiny)
- ใช้ **Fold 1 เท่านั้น** ต่อ trial (เพื่อความเร็ว)
- 10 trials, TPE Sampler
- objective: maximize AUC-ROC จาก fold 1
- ได้ `best_params.json` ต่อ 1 backbone

---

## ขั้นตอนที่ 3 — 5-Fold Cross-Validation (CNN)

ทำสำหรับแต่ละ backbone โดยใช้ best_params จากขั้นตอนที่ 2

**ต่อ 1 fold:**
1. Build model (backbone + Dense head)
2. **Phase 1**: freeze backbone → train classifier head → early stopping (patience=5)
3. **Phase 2**: unfreeze top 30% ของ backbone → fine-tune → early stopping (patience=15)
4. บันทึก val predictions และ stopping epoch ของแต่ละ phase

**หลังครบ 5 folds:**
- รวม val predictions ทุก fold → `val_preds.npz`
- คำนวณ avg stopping epoch → `avg_epochs.json`

---

## ขั้นตอนที่ 4 — RQ1: เลือก Backbone ที่ดีที่สุด

**Input**: `val_preds.npz` ของทั้ง 3 backbone

1. ใช้ threshold = 0.5 คำนวณ AUC, Sensitivity, Specificity (mean 5 folds)
2. เลือก backbone ที่มี AUC-ROC สูงสุด

**ผลลัพธ์**: เลือก **ConvNeXt-Tiny** (AUC=0.8293)

---

## ขั้นตอนที่ 5 — ปรับ Threshold

**Input**: `val_preds.npz` ของ ConvNeXt-Tiny

**5.1 Youden's Index**
1. คำนวณ ROC curve ต่อ fold → หา threshold ที่ max(Sensitivity + Specificity − 1)
2. เฉลี่ย Youden threshold ทั้ง 5 folds
3. เปรียบเทียบ default 0.5 กับ Youden threshold บน val set

**ผลลัพธ์**: Mean Youden threshold = **0.7318**
(Sensitivity ลดจาก 0.80 → 0.73, Specificity เพิ่มจาก 0.70 → 0.77)

**5.2 Threshold Sweep (0.05–0.95, step=0.05)**
1. รวม val predictions ทั้ง 5 folds เป็น pool เดียว
2. ไล่ threshold 0.05–0.95 ทีละ 0.05
3. เลือก threshold ที่ให้ Sensitivity สูงสุด โดยมีทั้ง Sens ≥ 0.70 และ Spec ≥ 0.70

| Threshold | Sensitivity | Specificity | Selected |
|-----------|-------------|-------------|----------|
| 0.50 | 0.8000 | 0.6944 | |
| 0.55 | 0.7846 | 0.6944 | |
| **0.60** | **0.7744** | **0.7361** | ✓ |
| 0.65 | 0.7744 | 0.7500 | |
| 0.70 | 0.7333 | 0.7500 | |

**ผลลัพธ์**: Sweep threshold = **0.60** (Sens=0.774, Spec=0.736)

---

## ขั้นตอนที่ 6 — ประเมินบน Test Set

**Input**: `avg_epochs.json`, `best_params.json`

1. Retrain ConvNeXt-Tiny บน **full training set** (267 ภาพ)
   - Phase 1: 50 epochs (avg จาก CV), **ไม่มี** early stopping
   - Phase 2: 46 epochs (avg จาก CV), **ไม่มี** early stopping
2. ทำนายบน Test set (67 ภาพ) → บันทึก probabilities ไว้ใน `final_eval_probs.npy`
3. ประเมินด้วย 2 threshold:
   - **Youden (0.7318)**: AUC=0.9150, Sens=0.9592, Spec=0.6667
   - **Sweep (0.60)**: AUC=0.9150, Sens=0.9796, Spec=0.6667

---

## ขั้นตอนที่ 7 — RQ2: Grad-CAM Localization

**Input**: โมเดล ConvNeXt-Tiny จากขั้นตอนที่ 6

1. แยกโมเดลเป็น 2 ส่วน: backbone (feature extractor) และ classifier head
2. สร้าง heatmap ด้วย 3 วิธี: Grad-CAM, Grad-CAM++, Eigen-CAM
3. visualize overlay บนภาพต้นฉบับ (4 CT + 4 DM)

**ผลลัพธ์**: qualitative เท่านั้น (ไม่มี ground-truth annotation)

---

## ขั้นตอนที่ 8 — RQ3: เปรียบเทียบ Proposed Model กับ Baseline

**Baseline Branch (BPNN, ทำคู่ขนานกับ CNN):**

1. **สกัด features** (24 มิติ ต่อภาพ):
   - GLCM 16-dim (8 ระดับ, 4 มุม, 4 properties)
   - HOG 8-dim (8×8 cells, 8 statistics)
2. **GridSearchCV** 5-fold หา best BPNN architecture
3. Retrain BPNN บน full training set, ทำนายบน Test set ด้วย sweep threshold
4. เปรียบเทียบ metrics กับ CNN
5. ทดสอบ statistical significance: McNemar's Test + DeLong's Test

**ผลลัพธ์** (CNN thr=0.60, BPNN thr=0.55):
- Proposed Model (ConvNeXt-Tiny): AUC=0.9150, Sens=0.9796, Spec=0.6667
- Baseline (BPNN, GLCM+HOG): AUC=0.8526, Sens=0.8776, Spec=0.6111
- ไม่พบความแตกต่างที่ significant (McNemar p=0.1094, DeLong p=0.3591)
