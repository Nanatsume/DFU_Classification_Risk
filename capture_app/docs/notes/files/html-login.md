---
name: html-login
description: Vite MPA entry HTML for the login page — loads main-login.tsx into #root
metadata:
  type: reference
---

# frontend/login.html

**หน้าที่**: ไฟล์ HTML entry ของหน้า login — โหลด `main-login.tsx` build แล้วกลายเป็น `static/login.html`

**Functions/Variables (global scope)**: ไม่มี

**Called by**: [[lib-auth]] (`AuthGuard` redirect ไปที่นี่เมื่อยังไม่ login), เปิดตรง `/login.html`

**Depends on**: [[main-login]], build โดย [[vite-config]] เป็น entry ชื่อ `login`
