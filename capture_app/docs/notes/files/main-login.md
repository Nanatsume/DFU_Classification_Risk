---
name: main-login
description: Vite entry script that mounts Login (without AuthGuard) onto #root of login.html
metadata:
  type: reference
---

# frontend/src/main-login.tsx

**หน้าที่**: entry script ของ `login.html` — render `<Login />` โดยตรง **ไม่ห่อด้วย** `AuthGuard` (เพราะนี่คือหน้าเข้าสู่ระบบเอง)

**Functions/Variables (global scope)**: ไม่มี

**Called by**: `login.html` (ดู [[html-login]])

**Depends on**: [[pages-Login]], `frontend/src/index.css` ([[index-css]])
