---
name: api-post-roi-rid
description: "POST /api/roi/{rid} — save (overwrite) the VIA project + region-count summary for a case"
metadata:
  type: reference
---

# POST /api/roi/{rid}

**Method**: POST — ต้อง auth

**เรียกใช้จากไฟล์ไหนบ้าง**: [[_via_dfu]] (`dfu_save_roi()`, ปุ่ม "บันทึก ROI" ในแถบเครื่องมือที่เพิ่มเข้าไปใน VIA)

**ส่งข้อมูลอะไรไป (payload)**: `{ rid, project (VIA project JSON เต็ม), summary ({L,R: {region_count, has_risk_area, filename}}) }`

**รับข้อมูลอะไรกลับมา (response)**: `{ rid, savedAt, summary }` — `400` ถ้า `rid` ใน URL กับใน body ไม่ตรงกัน — เขียนทับได้เสมอ (ไม่มี versioning)

**ไฟล์ backend ที่ handle**: [[roi_store]] (`save_roi()`) → [[db]] (`save_roi()`, `log_audit()`)
