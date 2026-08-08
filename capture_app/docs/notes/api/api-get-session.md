---
name: api-get-session
description: "GET /api/session — reports whether the current cookie is a valid, unexpired session"
metadata:
  type: reference
---

# GET /api/session

**Method**: GET — **ไม่ต้อง auth** (ต้องเรียกได้เสมอเพื่อ "เช็คว่า login อยู่ไหม")

**เรียกใช้จากไฟล์ไหนบ้าง**: [[lib-auth]] (`AuthGuard`, เช็คทุกครั้งที่เปิดหน้าที่ต้อง login), [[pages-Login]] (เช็คว่า login ค้างอยู่แล้วหรือไม่ตอนเปิดหน้า login)

**ส่งข้อมูลอะไรไป (payload)**: ไม่มี (อ่าน cookie จาก request)

**รับข้อมูลอะไรกลับมา (response)**: `{ authenticated: bool }`

**ไฟล์ backend ที่ handle**: [[auth]] (`session_status()`) → `_session_valid()` → [[db]] (`get_session()`, `delete_session()` ถ้าหมดอายุ)
