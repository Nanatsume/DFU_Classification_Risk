---
name: api-get-cases
description: "GET /api/cases — every case that has a CRF form, joined with capture status"
metadata:
  type: reference
---

# GET /api/cases

**Method**: GET — ต้อง auth

**เรียกใช้จากไฟล์ไหนบ้าง**: [[pages-Capture]] (picker เลือกเคสถ่ายภาพ), [[pages-Roi]] (picker เลือกเคสทำ ROI, กรองเฉพาะที่ `has_podo && has_thermal`)

**ส่งข้อมูลอะไรไป (payload)**: ไม่มี

**รับข้อมูลอะไรกลับมา (response)**: array ของ `{ research_id, nurse, iwgdf: {L: number|null, R: number|null}, has_podo: bool, has_thermal: bool }` — เฉพาะเคสที่มีฟอร์ม CRF แล้วเท่านั้น (JOIN กับ `crf_forms`)

**ไฟล์ backend ที่ handle**: [[server]] (`cases()`) → [[db]] (`list_cases_with_status()`)
