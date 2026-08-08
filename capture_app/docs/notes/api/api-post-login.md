---
name: api-post-login
description: "POST /api/login — verifies the shared team password, sets the session cookie"
metadata:
  type: reference
---

# POST /api/login

**Method**: POST — ไม่ต้อง auth (นี่คือ endpoint สร้าง auth เอง)

**เรียกใช้จากไฟล์ไหนบ้าง**: [[pages-Login]] (`onSubmit`)

**ส่งข้อมูลอะไรไป (payload)**: `{ password: string }`

**รับข้อมูลอะไรกลับมา (response)**: สำเร็จ → `{ ok: true }` + set-cookie `capture_session` (httponly, 12 ชม.); ผิด → `401` (มี `time.sleep(1)` กันบรูทฟอร์ซแบบพื้นฐาน)

**ไฟล์ backend ที่ handle**: [[auth]] (`login()`) → [[db]] (`get_setting('password_hash')`, `create_session()`, `log_audit()`)
