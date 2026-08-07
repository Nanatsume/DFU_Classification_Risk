---
name: api-post-capture
description: "POST /api/capture — grabs one photo (podoscope or thermal) for a case; 409 if no CRF form yet"
metadata:
  type: reference
---

# POST /api/capture

**Method**: POST — ต้อง auth

**เรียกใช้จากไฟล์ไหนบ้าง**: [[pages-Capture]] (`capture(m)`)

**ส่งข้อมูลอะไรไป (payload)**: `{ rid: string, modality: 'podoscope'|'thermal' }`

**รับข้อมูลอะไรกลับมา (response)**: สำเร็จ → `{ rid, modality, url }`; ล้มเหลว → `400` ถ้า modality ผิด, **`409`** ถ้าเคสนั้นยังไม่มีฟอร์ม CRF (นโยบาย "ต้องกรอกฟอร์มก่อนถึงจะถ่ายภาพได้")

**ไฟล์ backend ที่ handle**: [[server]] (`capture()`) → [[capture_source]] (`SOURCE.grab()`), [[db]] (`has_crf()`, `save_capture()`, `log_audit()`)
