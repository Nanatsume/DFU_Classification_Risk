---
name: api-get-roi-list
description: "GET /api/roi — ROI summaries (region counts per side) for every case that has one, no project blob"
metadata:
  type: reference
---

# GET /api/roi

**Method**: GET — ต้อง auth

**เรียกใช้จากไฟล์ไหนบ้าง**: [[pages-Roi]] (สถานะ ROI ต่อเคสในตาราง picker), [[pages-CrfList]] (คอลัมน์ ROI ต่อข้าง)

**ส่งข้อมูลอะไรไป (payload)**: ไม่มี

**รับข้อมูลอะไรกลับมา (response)**: array ของ `{ rid, savedAt, summary: { L?: {region_count, has_risk_area, filename}, R?: {...} } }` — ไม่มี `project` blob เต็ม (อาจใหญ่) จงใจให้เบา

**ไฟล์ backend ที่ handle**: [[roi_store]] (`list_roi()`) → [[db]] (`list_roi()`)
