# Review Notes

## Review: abstract.tex + chapter1-3.tex (ตรวจความสอดคล้องทั้งเล่ม) — 2026-08-04

ผู้ตรวจ Orchestrator (ตรวจก่อนตั้งทีม subagent) ขอบเขต ความสอดคล้องของเนื้อหาข้ามบท
ตรวจเชิงกลไก และไล่ตัวเลขในตาราง/กราฟกลับไปเทียบกับโค้ดและไฟล์ผลจริง

---

### ปัญหาที่ต้องแก้ (blocking)

**1. [dfu_common.py:116 / rq1_run_combo.py:80 / rq2_baseline.py:455] ผลเบื้องต้นทั้งหมดแบ่งข้อมูลระดับภาพ ขัดกับระเบียบวิธีที่ประกาศไว้เอง**

`chapter3.tex:187` ประกาศว่าต้องแบ่งระดับผู้ป่วยเพื่อกัน leakage และ `chapter3.tex:387` อ้างว่าผลเบื้องต้นยืนยันว่า cross-validation strategy ทำงานถูกต้อง
แต่สคริปต์ทุกตัว (`rq1_run_combo.py`, `rq1_final_eval.py`, `rq2_baseline.py`, `rq2_final_eval.py`, `rq3_xai.py`) เรียก `create_fold_splits()` ซึ่งเป็น `StratifiedKFold` ระดับภาพ ไม่ส่ง `groups`
ฟังก์ชัน `create_patient_fold_splits()` (dfu_common.py:139) ที่ใช้ `StratifiedGroupKFold` มีอยู่แต่ไม่ถูกเรียกจากที่ใดเลย

→ เท้าซ้าย-ขวาของคนเดียวกันคร่อม train/test ได้ ซึ่งคือ leakage แบบเดียวกับที่บทที่ 3 บอกว่าต้องกัน น่าจะดันตัวเลข AUC 0.9803 / 0.9950 / 0.9966 ให้สูงเกินจริง
→ **ต้องแก้ก่อนข้ออื่น เพราะถ้ารันใหม่ ตัวเลขเบื้องต้นเปลี่ยนทั้งชุด**

**2. [chapter3.tex:361 vs 756 vs 807] Age เป็นฟีเจอร์อันดับหนึ่งของ Baseline แต่ข้อสรุป RQ2 ไม่พูดถึง**

`chapter3.tex:361` วางนโยบายว่าตัดข้อมูลประชากรออกจากทั้งสองโมเดล เพราะการให้ Baseline เห็น Age ขณะที่ CNN เห็นแต่พิกเซลจะทำให้ RQ2 confounded
แต่ `chapter3.tex:756` รายงานว่า Age คือฟีเจอร์สำคัญที่สุด (importance 0.3291 มากกว่าอันดับสองสามเท่า) และ Gender ก็ติด top-22
ส่วน Answer to RQ2 ที่ `chapter3.tex:807` สรุปว่า Baseline ชนะเพราะ thermal zone features ล้วน ๆ

→ สิ่งที่นโยบายตัวเองบอกว่าจะทำให้ confounded เกิดขึ้นจริงแล้วในผลเบื้องต้น แต่ข้อความไม่ยอมรับ ต้องระบุตรง ๆ ว่า Baseline เห็นตัวแปรที่ CNN ไม่เห็น

**3. [chapter3.tex:208 vs 234] Hyperparameter tuning ขัดกันเองห่างกัน 26 บรรทัด**

- บรรทัด 208 "hyperparameter tuning via GPyOpt Bayesian Optimisation over 5-fold cross-validation"
- บรรทัด 234 "each trial is evaluated on the first cross-validation fold rather than on all five"

→ ตัวหลังคือของจริง แก้บรรทัด 208

**4. [chapter3.tex:125 vs 835] Threats to Internal Validity บรรยาย dilation kernel ผิดจากระเบียบวิธี**

- บรรทัด 125 บอกว่าคัด kernel จากภาพใน training partition เท่านั้น "so that no test image contributes to the choice" คือปิดช่องรั่วแล้ว
- บรรทัด 835 กลับเขียนว่า "is calibrated on the first several images of the hospital dataset, and if any of those images belong to patients later allocated to the test partition..."

→ บรรยายภัยที่ระเบียบวิธีตัดไปแล้ว อ่านแล้วสับสนว่าตกลงทำแบบไหน

**5. [chapter3.tex:822 vs 824] RQ3 เนื้อความขัดกับ Answer box**

- บรรทัด 822 กรณี CT ปกติ "produce near-zero activations across the entire foot"
- บรรทัด 824 Answer box "producing diffuse activations for normal cases"

→ near-zero กับ diffuse คนละความหมาย และ Answer box เพิ่ม "and toe regions" ที่เนื้อความไม่ได้พูด (เนื้อความบอกแค่ forefoot)

**6. [chapter2.tex:47 vs chapter3.tex:45] เกณฑ์ monofilament ต่างกันระหว่างบท**

- ch2 "cannot correctly sense the pressure in two out of three applications at any site" (เกณฑ์ต่อจุด ตาม IWGDF)
- ch3 "fails to perceive the monofilament at two or more of the three sites" (เกณฑ์นับจุด)

→ คนละเกณฑ์จริง ๆ และมันคือสิ่งที่กำหนด label ของงานนี้

**7. [chapter2.tex:195 vs chapter3.tex:716] TCI ชื่อไม่ตรงกัน**

- ch2 "Thermal Change Index" (ถูกตาม Khandakar et al. 2021)
- ch3 "Thermal Comfort Index"

**8. [chapter3.tex:11 vs sec:evaluation_plan vs chapter3.tex:88] multiclass ประกาศไว้แต่ไม่มีในแผนประเมิน**

บรรทัด 11 เขียนว่า "with a multiclass extension explored as a secondary analysis" แต่ Evaluations Plan มีแค่ RQ1-RQ3 และบรรทัด 88 เองบอกว่าเป็น future work
→ เลือกอย่างใดอย่างหนึ่ง

**9. [chapter3.tex:787, 791, 805] เรียก n = 49 ว่า "DM patients" ทั้งที่เป็นภาพเท้า**

`chapter3.tex:714` บอกว่า test set คือ 67 images ส่วน INAOE มี 167 pairs = 334 ภาพ
→ 49 คือภาพเท้า ไม่ใช่คน แก้คำในเนื้อความและ caption ตาราง McNemar (เกี่ยวโยงกับข้อ 1 โดยตรง)

**10. [chapter3.tex:716, 756] จัดกลุ่มฟีเจอร์ผิด 3 จุด**

- บรรทัด 716 เรียก FullFoot ว่าเป็นหนึ่งใน "five angiosome zones" แต่ `chapter2.tex:195` บอกว่า angiosome มี 4 โซน
- บรรทัด 756 เรียก `FullFoot_SD` ว่า "demographic feature" (จริง ๆ เป็น zone statistic)
- บรรทัด 756 เอา TCI ไปอยู่กลุ่ม "zone temperature statistics" ทั้งที่ตาราง `tab:rq2_features` จัดไว้ในกลุ่ม global/demographic

**11. [chapter2.tex:195 vs tab:related_work] ตัวเลขงานคนอื่นไม่ตรงกันเอง**

- เนื้อความบอก Khandakar F1 97% ตารางบอก 96.70%
- ตารางให้ Acc = Sens = 96.71% เท่ากันเป๊ะ (น่าสงสัย ควรตรวจกับต้นฉบับ)
- ตารางใส่ "AUC: 1.00" ให้ Eldin ทั้งที่เนื้อความไม่เคยรายงาน AUC

**12. [chapter2.tex ทั้งบท] บทที่ 2 ขาดพื้นฐานของสิ่งที่บทที่ 3 ใช้จริง**

นับจำนวนครั้งที่ปรากฏ (ch2 / ch3) — transfer learning 0/2, fine-tuning 1/13, Bayesian+GPyOpt 0/5, SMOTE 1/6, GLCM 0/4, LBP 0/5, bootstrap 0/4, McNemar 0/5
บทที่ 3 เปรียบเทียบ 8 fine-tuning strategies เป็นแกนหลักของ RQ1 แต่บทที่ 2 ไม่เคยอธิบายว่ามันคืออะไร
→ ช่องว่างเชิงโครงสร้างที่ใหญ่ที่สุดรองจากข้อ 1

---

### ข้อสังเกต (non-blocking)

**13. [main.tex:2, 83] รูปแบบการอ้างอิงขัดกับ CLAUDE.md §13**

ใช้ `natbib[numbers]` + `unsrtnat` ซึ่งได้เลข [1] แต่ CLAUDE.md §13 กำหนด name-year และระบุชัดว่า "Do not use numbered citations"
→ ถ้าตั้งใจเปลี่ยนแล้ว ควรอัปเดต CLAUDE.md ให้ตรง

**14. [chapter2.tex:180-189 vs chapter3.tex:372] บทที่ 2 นิยาม Pointing Game คนละแบบกับที่ใช้จริง**

ch2 นิยามแบบ peak activation point เดียว แต่ abstract, RQ3 ในบทที่ 1 และ ch3 ใช้ top-region pointing game ที่ top-5% region
ch2 ไม่เคยเกริ่นถึงเวอร์ชันดัดแปลง แต่ใส่ tau = 15 px ไว้แล้วราวกับเป็นของเรา

**15. จุดย่อยอื่น ๆ**

- `chapter3.tex:819` รูปของ RQ3 ใช้ label `fig:rq2_cam`
- `chapter3.tex:266` label ยังเป็น `sec:baseline_bpnn` ทั้งที่ไม่มี BPNN แล้ว (CLAUDE.md ก็ยังเขียนว่า baseline คือ GLCM+HOG+BPNN ควรอัปเดต)
- Section "Model Training" มี subsubsection ชื่อ "Model Training" ซ้อนอยู่ข้างใน
- `chapter1.tex:55` และ `chapter2.tex:3` เรียกหัวข้อ CNN ว่า "CNN for DFU risk prediction" แต่หัวข้อจริงคือ "Convolutional Neural Networks" ซึ่งเป็นเนื้อหาสถาปัตยกรรมทั่วไป
- `chapter1.tex:11` นิยาม (CNNs) ซ้ำจากบรรทัด 9
- หัวข้อ "Evaluations Plan" ควรเป็น "Evaluation Plan"
- `chapter1.tex:56` ไล่เนื้อหาบทที่ 3 ไม่ครบ ไม่ได้พูดถึงหัวข้อ Conclusion
- `chapter3.tex:842` เขียน "to 1 March 2027" แต่ตารางกับ bullet จบที่ Feb 2027
- CLAUDE.md ระบุ tuning ด้วย Optuna แต่บทที่ 3 ใช้ GPyOpt

---

### ผลตรวจเชิงกลไก

- **ref ที่ไม่มี label**: `fig:rq1_radar_ch4` (อ้างที่ `chapter4_pre.tex:8`) — latent ยังไม่พังเพราะ ch4 ถูก comment ไว้ใน main.tex
- **label ซ้ำ**: `sec:threats` อยู่ทั้ง `chapter3.tex:825` และ `chapter4_pre.tex:122` — latent เช่นกัน จะพังทันทีที่เปิดใช้บทที่ 4
- **cite key ที่ไม่มีใน .bib**: ไม่มี (ใช้จริง 41 key มีครบทุกตัวใน references.bib ที่มี 92 entry)
- **ไฟล์รูปที่หาย**: ไม่มี ทุก `\includegraphics` ชี้ไปยังไฟล์ที่มีอยู่จริง
- **compile**: ไม่ได้รัน build ใหม่ในรอบนี้ แต่ตรวจ `main.log` ของ build ล่าสุด (2026-08-02) แล้วไม่พบ undefined reference หรือ undefined citation

---

### สิ่งที่ตรวจแล้วถูกต้อง (ไม่ต้องตรวจซ้ำ)

- ค่าใน forest plot ทั้ง 3 รูปเรียงลำดับตรงกับค่าเฉลี่ย S1/S2 ในตารางทุกแถว
- พิกัด radar chart ถูกต้องทุกจุดตามสูตร `r = (v - 0.60) / 0.40 * 2.5` ครบทั้ง 18 ค่า
- ตาราง `tab:rq1_summary` ตรงกับตารางรายละเอียดของแต่ละ backbone
- ตาราง McNemar (a=42, b=0, c=6, d=1) สอดคล้องกับ Sensitivity 42/49 = 0.8571 และ 48/49 = 0.9796 และ p = 2 x 0.5^6 = 0.0312
- INAOE 167 pairs = 334 ภาพ = CT 90 / DM 244 ตรงกันระหว่าง ch2 กับ ch3 และสัดส่วน test set 67 ภาพ (DM 49 / CT 18) สอดคล้องกับ 20%
- จำนวนฟีเจอร์ 16+8+8+11 = 43 (podoscope) และ 4+5+30 = 39 (INAOE) ถูกต้อง
- รายชื่อ top-22 features ที่ไล่ในบรรทัด 756 นับได้ 22 ตัวพอดี

---

### เช็คลิสต์

- [x] Citation ตรวจครบ (เชิงกลไก)
- [ ] ตัวเลขตรงกับ analysis/results.json — ยังไม่มีไฟล์นี้ รอบนี้เทียบกับ `results/*.json` และโค้ดแทน
- [x] ตัวเลขในกราฟ TikZ ตรงกับตาราง
- [ ] ไม่ขัดกับบทที่ 1-3 — **ไม่ผ่าน** ดูข้อ 3-8
- [ ] สไตล์ตาม CLAUDE.md — ยังไม่ได้ตรวจรอบนี้
- [x] Compile ผ่าน (จาก log ของ build ล่าสุด ไม่ได้ build ใหม่)

---

### ลำดับที่แนะนำให้แก้

1. ข้อ 1 ก่อน (patient-level split) เพราะต้องรันใหม่และตัวเลขจะเปลี่ยนทั้งชุด — งานของ analyst
2. ข้อ 2 (Age confound) แก้พร้อมกันได้ เพราะเป็นการเขียนข้อสรุป RQ2 ใหม่
3. ข้อ 3-11 เป็นการแก้ข้อความล้วน ไม่ต้องรันอะไร — งานของ writer
4. ข้อ 12 (เติมพื้นฐานบทที่ 2) เป็นงานเขียนใหม่ก้อนใหญ่ ควรแยกรอบทำ ต้องให้ researcher หาอ้างอิงเพิ่มก่อน
5. ข้อ 13-15 เก็บกวาดท้ายสุด

---

### งานที่ยังไม่ได้ตรวจในรอบนี้

- ตรวจสไตล์ตาม CLAUDE.md ทั้ง 17 หัวข้อ (ทำเฉพาะการสังเกตผ่าน ๆ)
- `chapter4_pre.tex` และ `chapter5_pre.tex` (ยังไม่ถูก include ใน main.tex)
- ความถูกต้องของเนื้อหาที่อ้างจากเปเปอร์ต้นฉบับ (ต้องมี research/findings.md ก่อน)
