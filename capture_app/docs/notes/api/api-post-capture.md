---
name: api-post-capture
description: "POST /api/capture — grabs one photo (podoscope or thermal) for a case; 409 if the id was never issued"
metadata:
  type: reference
---

# POST /api/capture

**Method**: POST — ต้อง auth

**เรียกใช้จากไฟล์ไหนบ้าง**: [[pages-Capture]] (`capture(m)`)

**ส่งข้อมูลอะไรไป (payload)**: `{ rid: string, modality: 'podoscope'|'thermal' }`

**รับข้อมูลอะไรกลับมา (response)**: สำเร็จ → `{ rid, modality, url }`; ล้มเหลว → `400` ถ้า modality ผิด, **`409`** ถ้าเป็นรหัสที่ระบบไม่เคยออกให้

**ด่านนี้เคยเป็นคนละเงื่อนไข**: เดิมบังคับว่า *ต้องมีฟอร์ม CRF ก่อน* ซึ่งใช้ไม่ได้กับลำดับงานจริง (ถ่ายก่อน กรอกทีหลัง — ดู [[api-post-session-start]]) ตอนนี้เงื่อนไขคือ **เคสต้องถูกสร้างไว้แล้วพร้อม HN** เจตนาเดิมยังอยู่: ไม่ให้เกิดภาพที่ไม่รู้ว่าเป็นของใคร

**ไฟล์ backend ที่ handle**: [[server]] (`capture()`) → [[capture_source]] (`SOURCE.grab()`), [[db]] (`case_exists()`, `save_capture()`, `log_audit()`)
