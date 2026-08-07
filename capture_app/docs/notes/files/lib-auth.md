---
name: lib-auth
description: Client-side session guard (AuthGuard) that wraps every protected page and redirects to login.html when not authenticated
metadata:
  type: reference
---

# frontend/src/lib/auth.tsx

**หน้าที่**: component `AuthGuard` ที่ทุกหน้าที่ต้อง login ใช้ห่อ content ของตัวเอง — เช็ค `GET /api/session` ตอน mount, ถ้ายังไม่ login จะ redirect ไป `login.html` พร้อมพารามิเตอร์ `?next=` ถ้า login แล้วจะ render `Navbar` + children การป้องกันจริงอยู่ฝั่ง backend (ทุก endpoint มี `require_session`) — ตัวนี้เป็นแค่ UX gate ไม่ให้เห็น content ก่อนเช็คเสร็จ พอร์ตมาจาก `static/js/auth.js` + `static/js/nav.js` เดิม

**Functions/Variables (global scope)**:
- `SessionResponse` (interface)
- `logout()` — เรียก `POST /api/logout` แล้ว redirect ไป `login.html`
- `AuthGuard({ children })` — component หลัก, มี state `'checking' | 'authenticated'`

**Called by**: ทุกไฟล์ `main-*.tsx` ยกเว้น [[main-login]] — [[main-home]], [[main-crf-form]], [[main-crf-list]], [[main-crf-detail]], [[main-capture]], [[main-roi]], [[main-gallery]]; `logout()` ถูกเรียกจาก [[components-Navbar]]

**Depends on**: [[lib-api]] (`api()`), [[components-Navbar]]
