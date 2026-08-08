---
name: html-crf-form
description: Vite MPA entry HTML for the CRF-07 form page — loads main-crf-form.tsx into #root
metadata:
  type: reference
---

# frontend/crf-form.html

**หน้าที่**: ไฟล์ HTML entry ของหน้ากรอกแบบฟอร์ม CRF-07 — โหลด `main-crf-form.tsx` build แล้วกลายเป็น `static/crf-form.html`

**Functions/Variables (global scope)**: ไม่มี

**Called by**: [[html-index]]/[[components-Navbar]] ("กรอกฟอร์มใหม่"), [[html-crf-detail]] ("แก้ไขข้อมูล", ผ่าน `?edit=`), [[html-capture]] ("เปิดแบบฟอร์ม CRF เพื่อลงทะเบียนเคสใหม่")

**Depends on**: [[main-crf-form]], build โดย [[vite-config]] เป็น entry ชื่อ `crf-form`
