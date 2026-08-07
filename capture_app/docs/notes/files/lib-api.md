---
name: lib-api
description: Shared fetch helper (api()) + LIVE/DEMO server-reachability probe used by every frontend page
metadata:
  type: reference
---

# frontend/src/lib/api.ts

**หน้าที่**: helper กลางสำหรับยิง fetch ไปหา backend — ทุกหน้าในระบบเรียกผ่านฟังก์ชันนี้ทั้งหมดแทนการเขียน `fetch()` เอง เพื่อให้รูปแบบ error เหมือนกันทุกที่ พอร์ตมาจาก `static/js/api.js` เดิม (สมัย vanilla JS) นอกจากนี้ยังมี `probeMode()` ใช้ตรวจว่าต่อกับเซิร์ฟเวอร์ได้จริงหรือไม่ (LIVE) หรือเปิดไฟล์ static เฉยๆ (DEMO)

**Functions/Variables (global scope)**:
- `ApiError` (class extends Error) — เก็บ `status` code ของ response ที่ไม่ ok
- `api<T>(path, body?, method?)` — ฟังก์ชัน fetch หลัก คืน `Promise<T>`, throw `ApiError` ถ้า response ไม่ ok
- `HealthResponse` (interface) — รูปร่างของ response จาก `GET /api/health`
- `probeMode()` — เรียก `api('/api/health')` แล้วคืน `{ live: true, health }` หรือ `{ live: false, health: null }`

**Called by**: แทบทุกไฟล์ใน `frontend/src/pages/` และ `frontend/src/lib/` — [[pages-Home]], [[pages-Login]], [[pages-CrfForm]], [[pages-CrfList]], [[pages-CrfDetail]], [[pages-Capture]], [[pages-Roi]], [[pages-Gallery]], [[lib-auth]], [[components-Navbar]]

**Depends on**: ไม่มี (เรียก browser `fetch` โดยตรง)
