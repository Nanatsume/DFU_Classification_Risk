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

## ขั้นตอนที่ 5 — Threshold Analysis (supplementary)

**Input**: `val_preds.npz` ของ ConvNeXt-Tiny

วิเคราะห์ Youden's Index เพื่อเปรียบเทียบกับ default 0.5 (เก็บไว้เป็น reference):
- Mean Youden threshold = **0.7318** (val set: Sens ลด 0.80→0.73, Spec เพิ่ม 0.70→0.77)
- แต่บน test set Youden ไม่ได้เพิ่ม Specificity → ใช้ **default threshold = 0.5** สำหรับ final evaluation

---

## ขั้นตอนที่ 6 — ประเมินบน Test Set

**Input**: `avg_epochs.json`, `best_params.json`

1. Retrain ConvNeXt-Tiny บน **full training set** (267 ภาพ)
   - Phase 1: 50 epochs (avg จาก CV), **ไม่มี** early stopping
   - Phase 2: 46 epochs (avg จาก CV), **ไม่มี** early stopping
2. ทำนายบน Test set (67 ภาพ) → บันทึก probabilities ไว้ใน `final_eval_probs.npy`
3. ประเมินด้วย threshold = 0.5:
   - **AUC=0.9002, Sens=0.9388, Spec=0.6667**

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
3. Retrain BPNN บน full training set, ทำนายบน Test set ด้วย threshold = 0.5
4. เปรียบเทียบ metrics กับ CNN
5. ทดสอบ statistical significance: McNemar's Test + DeLong's Test

**ผลลัพธ์** (ทั้งคู่ thr=0.5):
- Proposed Model (ConvNeXt-Tiny): AUC=0.9002, Sens=0.9388, Spec=0.6667
- Baseline (BPNN, GLCM+HOG): AUC=0.8526, Sens=0.8980, Spec=0.6111
- ไม่พบความแตกต่างที่ significant (McNemar b=7,c=4,p=0.5488; DeLong p=0.4700)
