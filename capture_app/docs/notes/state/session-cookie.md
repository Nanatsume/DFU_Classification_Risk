---
name: session-cookie
description: capture_session cookie + sessions table — the one piece of state gating every data-bearing endpoint
metadata:
  type: reference
---

# State: `capture_session` cookie / `sessions` table

**คืออะไร**: session token แบบ httponly cookie (12 ชม.) เก็บคู่กับแถวใน SQLite ตาราง `sessions` (`token, created_at, expires_at`) เป็น state เดียวที่บอกว่า "ผู้ใช้คนนี้ login อยู่หรือไม่" ทั้งระบบใช้รหัสผ่านทีมเดียว ไม่มีแนวคิด "ผู้ใช้คนไหน" แยกจากกัน

**ถูกสร้าง/แก้ไขที่ไฟล์ไหนบ้าง**: [[auth]] (`_new_session()` สร้างตอน login, `delete_session()` ลบตอน logout หรือหมดอายุ) เขียนผ่าน [[db]] (`create_session()`, `delete_session()`, `purge_expired_sessions()` เรียกตอน [[server]] สตาร์ท)

**ถูกอ่านไปใช้ที่ไฟล์ไหนบ้าง**: [[auth]] (`require_session()` — dependency ของทุก endpoint ใน [[server]], [[crf_store]], [[roi_store]]), [[lib-auth]] (`AuthGuard` เช็คผ่าน [[api-get-session]] ก่อน render หน้าใดๆ)
