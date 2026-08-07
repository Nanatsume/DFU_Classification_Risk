---
name: api-get-crf-list
description: "GET /api/crf — every saved CRF form, newest research id first"
metadata:
  type: reference
---

# GET /api/crf

**Method**: GET — ต้อง auth

**เรียกใช้จากไฟล์ไหนบ้าง**: [[pages-CrfList]] (`loadAll()`, ตารางประวัติทั้งหมด + ที่มาของ CSV export ทั้งสองแบบ), [[pages-Home]] (นับจำนวนฟอร์มโชว์ในปุ่ม)

**ส่งข้อมูลอะไรไป (payload)**: ไม่มี

**รับข้อมูลอะไรกลับมา (response)**: array ของ `CrfRecord` ([[lib-crfTypes]]) เรียงจากรหัสวิจัยใหม่ไปเก่า

**ไฟล์ backend ที่ handle**: [[crf_store]] (`list_records()`) → [[db]] (`list_crf()`)
