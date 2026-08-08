---
name: api-get-operators
description: "GET /api/operators — the photographer dropdown source (nurses + research team) for capture.html"
metadata:
  type: reference
---

# GET /api/operators

**Method**: GET — ต้อง auth

**เรียกใช้จากไฟล์ไหนบ้าง**: [[pages-Capture]] (dropdown "ผู้ถ่ายภาพ")

**ส่งข้อมูลอะไรไป (payload)**: ไม่มี

**รับข้อมูลอะไรกลับมา (response)**: `string[]` รายชื่อเรียงตามตัวอักษร — พยาบาลทั้ง 4 คนใน [[db-nurses-table]] บวกทีมวิจัยอีก 3 คน (`db.SEED_OPERATORS`)

**ไฟล์ backend ที่ handle**: [[server]] (`operators()`) → [[db]] (`list_operators()`)
