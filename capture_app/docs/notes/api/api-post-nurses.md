---
name: api-post-nurses
description: "POST /api/nurses — add a new nurse name to the dropdown source"
metadata:
  type: reference
---

# POST /api/nurses

**Method**: POST — ต้อง auth

**เรียกใช้จากไฟล์ไหนบ้าง**: [[pages-CrfForm]] (`onAddNurse()` — ลิงก์ "+ เพิ่มชื่อพยาบาลใหม่" ใต้ dropdown คนที่ 1/คนที่ 2 เปิด input ชื่อ กด "เพิ่ม" แล้วรีเฟรช dropdown ทันทีจาก response)

**ส่งข้อมูลอะไรไป (payload)**: `{ name: string }`

**รับข้อมูลอะไรกลับมา (response)**: `string[]` รายชื่อพยาบาลทั้งหมดหลังเพิ่ม — `400` ถ้าชื่อว่าง

**ไฟล์ backend ที่ handle**: [[crf_store]] (`add_nurse()`, ใน `nurses_router`) → [[db]] (`add_nurse()`)
