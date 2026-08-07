---
name: api-post-crf
description: "POST /api/crf — create or overwrite a CRF-07 form; computes/stores derived IWGDF category"
metadata:
  type: reference
---

# POST /api/crf

**Method**: POST — ต้อง auth

**เรียกใช้จากไฟล์ไหนบ้าง**: [[pages-CrfForm]] (`onSave()`)

**ส่งข้อมูลอะไรไป (payload)**: `{ pid, nurse, nurse2, savedAt, data: { form, savedAt, fields, derived: {L, R} } }` — `fields` คือคำตอบดิบ, `derived` คือผลคำนวณจาก [[lib-crfScoring]] (`toDerived()`) ที่ฝั่ง frontend คำนวณไว้แล้วก่อนส่ง

**รับข้อมูลอะไรกลับมา (response)**: `CrfRecord` ที่บันทึกแล้ว (อ่านย้อนกลับจาก DB) — `400` ถ้า `pid` ไม่ขึ้นต้นด้วย `P` — เขียนทับได้เสมอ (ไม่มี versioning ตามการตัดสินใจที่ตกลงกันไว้)

**ไฟล์ backend ที่ handle**: [[crf_store]] (`save_record()`) → [[db]] (`save_crf()`, `log_audit()`)
