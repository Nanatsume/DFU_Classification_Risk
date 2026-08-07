---
name: api-post-preprocess
description: "POST /api/preprocess — runs the segmentation pipeline on the raw podoscope image, saves 3 files per side"
metadata:
  type: reference
---

# POST /api/preprocess

**Method**: POST — ต้อง auth

**เรียกใช้จากไฟล์ไหนบ้าง**: [[pages-Capture]] (`runPreprocess(rid)`, เรียกอัตโนมัติทันทีหลังถ่าย podoscope สำเร็จในโหมด LIVE)

**ส่งข้อมูลอะไรไป (payload)**: `{ rid: string }`

**รับข้อมูลอะไรกลับมา (response)**: สำเร็จ → `{ status: 'ok', left_url, right_url }` (URL ของภาพ 224×224 สำหรับเทรน); ล้มเหลว (segment ไม่ได้/แยกเท้าไม่ได้) → `{ status: 'failed', error }`; `404` ถ้ายังไม่มีภาพ podoscope ดิบ — บันทึกไฟล์ 3 แบบต่อข้างจริงๆ (train 224×224, `_full.png` ความละเอียดเต็ม, `_original.png` สีก่อน CLAHE) แม้ response จะบอกแค่ URL ของไฟล์เทรน

**ไฟล์ backend ที่ handle**: [[server]] (`preprocess()`) → [[preprocessing]] (`preprocess_foot_image()`), [[db]] (`save_preprocessing()`)
