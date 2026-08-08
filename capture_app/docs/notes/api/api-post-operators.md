---
name: api-post-operators
description: "POST /api/operators — add a new photographer name; not wired to any UI by design"
metadata:
  type: reference
---

# POST /api/operators

**Method**: POST — ต้อง auth

**เรียกใช้จากไฟล์ไหนบ้าง**: ไม่มีหน้า UI เรียกใช้ (จงใจไม่มีปุ่ม "เพิ่มชื่อ" เหมือนกับ [[api-post-nurses]] — รายชื่อผู้ถ่ายภาพเปลี่ยนไม่บ่อย ควรแก้ที่ backend ตรงๆ) เก็บ endpoint ไว้เผื่อสคริปต์/curl ยิงตรงตอนต้องเพิ่มชื่อจริง

**ส่งข้อมูลอะไรไป (payload)**: `{ name: string }`

**รับข้อมูลอะไรกลับมา (response)**: `string[]` รายชื่อผู้ถ่ายภาพทั้งหมดหลังเพิ่ม — `400` ถ้าชื่อว่าง

**ไฟล์ backend ที่ handle**: [[server]] (`add_operator()`) → [[db]] (`add_operator()`)
