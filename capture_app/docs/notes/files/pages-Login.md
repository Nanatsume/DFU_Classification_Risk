---
name: pages-Login
description: Login page — shared team password form, redirects to ?next= or index.html on success
metadata:
  type: reference
---

# frontend/src/pages/Login.tsx

**หน้าที่**: หน้า login รหัสผ่านทีมเดียว (ไม่มีชื่อผู้ใช้) เช็คก่อนว่า login ค้างอยู่แล้วหรือไม่ (ถ้าใช่ redirect ผ่านไปเลยไม่ต้องโชว์ฟอร์ม) ส่ง `POST /api/login` ตอน submit สำเร็จแล้ว redirect ไป query param `?next=` หรือ `index.html`

**Functions/Variables (global scope)**:
- `Login()` — component เดียวในไฟล์, state: `password`, `err`, `submitting`
- `onSubmit(e)` — handler ฟอร์ม

**Called by**: [[main-login]]

**Depends on**: [[lib-api]] (`api()`, `ApiError`), shadcn `Button`/`Card`/`Input` ([[components-ui-shadcn]]) — เป็นหน้าเดียวที่**ไม่**ห่อด้วย `AuthGuard` ([[lib-auth]]) เพราะเป็นทางเข้าระบบเอง
