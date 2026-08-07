---
name: auth
description: Shared-password login/session system — one team password, PBKDF2 hash, cookie-based sessions stored in SQLite
metadata:
  type: reference
---

# auth.py

**หน้าที่**: ระบบ login แบบรหัสผ่านทีมเดียว (ไม่ใช่บัญชีต่อพยาบาล เพราะการระบุตัวผู้บันทึกอยู่ในฟิลด์ `nurse`/`nurse2` ของฟอร์ม CRF อยู่แล้ว) ทำหน้าที่ hash/verify รหัสผ่านด้วย PBKDF2, สร้าง/ตรวจสอบ session cookie, และเป็น FastAPI dependency (`require_session`) ที่ทุก endpoint ที่ต้อง login เรียกใช้

**Functions/Variables (global scope)**:
- `SESSION_COOKIE`, `SESSION_TTL_HOURS`, `PBKDF2_ITERATIONS`, `TZ`, `router` (APIRouter prefix `/api`)
- `_hash(password, salt)`, `_verify(password, stored)` — PBKDF2 hash/verify
- `bootstrap_password()` — เรียกตอนเซิร์ฟเวอร์สตาร์ท อ่าน `APP_PASSWORD` env var หรือสุ่มรหัสผ่านครั้งเดียว
- `_now()`, `_new_session()`, `_session_valid(token)`
- `require_session(request)` — FastAPI dependency, raise 401 ถ้าไม่มี session ที่ยังไม่หมดอายุ
- `LoginReq` (pydantic model)
- Routes: `POST /api/login`, `POST /api/logout`, `GET /api/session` — ดูรายละเอียดใน `docs/notes/api/`

**Called by**: [[server]] (`app.include_router(auth.router)`, `auth.bootstrap_password()` ตอน startup, `require_session` เป็น dependency ของทุก router อื่น), [[test_auth]]

**Depends on**: [[db]] (เก็บ `password_hash` ใน settings table, เก็บ session ใน sessions table)
