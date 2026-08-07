---
name: html-index
description: Vite MPA entry HTML for the dashboard page — loads main-home.tsx into #root
metadata:
  type: reference
---

# frontend/index.html

**หน้าที่**: ไฟล์ HTML entry ของ Vite multi-page app สำหรับหน้าแรก (dashboard) — โครง `<div id="root">` เปล่า + โหลด font IBM Plex Sans Thai + `<script type="module" src="/src/main-home.tsx">` เมื่อ build แล้วจะกลายเป็น `static/index.html` ที่ FastAPI เสิร์ฟจริง

**Functions/Variables (global scope)**: ไม่มี (ไฟล์ HTML ล้วน)

**Called by**: ผู้ใช้เปิดตรง (`/index.html` หรือ `/`), ลิงก์จากทุกหน้าในระบบ (navbar "หน้าแรก") — ดู [[components-Navbar]]

**Depends on**: [[main-home]] (`<script src="/src/main-home.tsx">`), ถูก build โดย [[vite-config]] เป็น entry ชื่อ `index`
