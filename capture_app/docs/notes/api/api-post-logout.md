---
name: api-post-logout
description: "POST /api/logout — deletes the session row and clears the cookie"
metadata:
  type: reference
---

# POST /api/logout

**Method**: POST — ต้อง auth ในทางปฏิบัติ (ไม่มี `require_session` ผูกไว้ตรงๆ แต่ router `auth.router` ไม่ได้ห่อ dependency นี้เหมือน router อื่น — เรียกได้แม้ไม่มี session ก็แค่ไม่มีอะไรให้ลบ)

**เรียกใช้จากไฟล์ไหนบ้าง**: [[lib-auth]] (`logout()`), เรียกจากปุ่ม "ออกจากระบบ" ใน [[components-Navbar]]

**ส่งข้อมูลอะไรไป (payload)**: ไม่มี body (อ่าน cookie จาก request เอง)

**รับข้อมูลอะไรกลับมา (response)**: `{ ok: true }` + ลบ cookie `capture_session`

**ไฟล์ backend ที่ handle**: [[auth]] (`logout()`) → [[db]] (`delete_session()`)
