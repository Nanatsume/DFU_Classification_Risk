---
name: preprocessing
description: Foot image preprocessing pipeline (HMRF-EM segmentation, dilation, L/R crop, CLAHE, resize) — single source of truth for training + ROI + XAI image variants
metadata:
  type: reference
---

# preprocessing.py

**หน้าที่**: pipeline ประมวลผลภาพโพโดสโคปแบบ pure Python (numpy/scipy/opencv/PIL, ไม่มี model weights, ไม่ใช้ GPU) แปลงจากภาพดิบเป็นภาพเท้าซ้าย/ขวาแยกกัน ผ่านขั้นตอน segmentation → dilation → แยกซ้าย-ขวา+crop → grayscale+CLAHE → 3-channel → resize 224×224 → scale ÷255 เป็น single source of truth ทั้งของแอปเก็บข้อมูลและของงานเทรนโมเดล (ถูกดึงมาจาก `Image_Preprocessing_Pipeline.ipynb` เดิม) คืนค่าภาพ 3 แบบต่อข้าง: `*_foot` (224×224 สำหรับเทรน), `*_foot_full` (ความละเอียดเต็ม CLAHE แล้ว สำหรับมาร์ก ROI), `*_foot_original` (สี ก่อน grayscale/CLAHE สำหรับ XAI overlay) — `*_full` และ `*_original` มี (H,W) เท่ากันเสมอเพราะ pixel-wise ops ไม่กระทบขนาดภาพ

**Functions/Variables (global scope)**:
- `rgb_to_ydbdr()` — แปลงพื้นที่สี RGB → YDbDr
- `GaussianMixtureModel` (class) — GMM แบบ diagonal-covariance, fit ด้วย EM เอง (`fit`, `predict_proba`, `_init_params`, `_log_gaussian`)
- `_neighbourhood_label_counts()`, `hmrf_em_segmentation()` — HMRF-MAP segmentation
- `identify_foot_label()`, `create_foot_mask()`, `get_pure_sole_image()` — เลือก cluster ที่เป็นเท้า สร้าง mask
- `apply_morphological_dilation()` — ขยาย mask เพื่อเชื่อมส่วนที่ขาด (เช่นนิ้วเท้า)
- `pad_to_square()`, `separate_and_crop_feet()` — แยกซ้าย/ขวาด้วย connected-component labeling แล้ว crop เป็นสี่เหลี่ยมจัตุรัส
- `convert_to_grayscale()`, `apply_clahe()` — เพิ่ม contrast แบบ adaptive
- `convert_to_3channel_rgb()`, `resize_image()`, `scale_pixels()`
- `preprocess_foot_image(image_path, ...)` — ฟังก์ชันหลัก รวม pipeline ทั้งหมด คืน dict ผลลัพธ์ตามที่อธิบายด้านบน
- `batch_preprocess_images(input_folder, output_folder)` — รันทั้งโฟลเดอร์ (ใช้ตอนเตรียม dataset เทรน ไม่ได้เรียกจาก [[server]])

**Called by**: [[server]] (`POST /api/preprocess` เรียก `preprocess_foot_image()`), [[test_api]] (`test_preprocess_full_and_original_images_share_dimensions`)

**Depends on**: numpy, scipy, opencv (`cv2`), PIL — ไม่ import โมดูลอื่นในโปรเจกต์
