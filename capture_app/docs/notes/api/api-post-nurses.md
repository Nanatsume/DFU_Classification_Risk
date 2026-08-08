---
name: api-post-nurses
description: "POST /api/nurses — add a new nurse name to the dropdown source"
metadata:
  type: reference
---

# POST /api/nurses

**Method**: POST — ต้อง auth

**เรียกใช้จากไฟล์ไหนบ้าง**: ไม่มีหน้า UI เรียกใช้ (เคยมีปุ่ม "+ เพิ่มชื่อพยาบาลใหม่" ใน [[pages-CrfForm]] แล้วเอาออกตามการตัดสินใจของผู้ใช้ — รายชื่อพยาบาลเปลี่ยนไม่บ่อย ควรแก้ที่ backend ตรงๆ แทนเปิดให้แก้ผ่านฟอร์ม) เก็บ endpoint ไว้เผื่อสคริปต์/curl ยิงตรงตอนต้องเพิ่มชื่อจริง

**ส่งข้อมูลอะไรไป (payload)**: `{ name: string }`

**รับข้อมูลอะไรกลับมา (response)**: `string[]` รายชื่อพยาบาลทั้งหมดหลังเพิ่ม — `400` ถ้าชื่อว่าง

**ไฟล์ backend ที่ handle**: [[crf_store]] (`add_nurse()`, ใน `nurses_router`) → [[db]] (`add_nurse()`)
