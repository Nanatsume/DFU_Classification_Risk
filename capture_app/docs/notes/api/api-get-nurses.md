---
name: api-get-nurses
description: "GET /api/nurses — the nurse-name dropdown list, seeded + editable"
metadata:
  type: reference
---

# GET /api/nurses

**Method**: GET — ต้อง auth

**เรียกใช้จากไฟล์ไหนบ้าง**: [[pages-CrfForm]] (dropdown "พยาบาลผู้ตรวจ" คนที่ 1/2)

**ส่งข้อมูลอะไรไป (payload)**: ไม่มี

**รับข้อมูลอะไรกลับมา (response)**: `string[]` รายชื่อพยาบาลเรียงตามตัวอักษร

**ไฟล์ backend ที่ handle**: [[crf_store]] (`list_nurses()`, ใน `nurses_router`) → [[db]] (`list_nurses()`)
