---
name: html-capture
description: Vite MPA entry HTML for the photo-capture station page — loads main-capture.tsx into #root
metadata:
  type: reference
---

# frontend/capture.html

**หน้าที่**: ไฟล์ HTML entry ของหน้าถ่ายภาพ (`?rid=` เปิดตรงไปยังเคสที่ระบุได้) — โหลด `main-capture.tsx` build แล้วกลายเป็น `static/capture.html`

**Functions/Variables (global scope)**: ไม่มี

**Called by**: [[html-index]]/[[components-Navbar]] ("ถ่ายภาพ"), [[html-crf-detail]] ("ถ่ายภาพ"/"ดูภาพของ")

**Depends on**: [[main-capture]], build โดย [[vite-config]] เป็น entry ชื่อ `capture`
