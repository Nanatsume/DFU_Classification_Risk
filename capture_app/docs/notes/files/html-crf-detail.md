---
name: html-crf-detail
description: Vite MPA entry HTML for the single-case detail page — loads main-crf-detail.tsx into #root
metadata:
  type: reference
---

# frontend/crf-detail.html

**หน้าที่**: ไฟล์ HTML entry ของหน้ารายละเอียดเคส (`?pid=`) — โหลด `main-crf-detail.tsx` build แล้วกลายเป็น `static/crf-detail.html`

**Functions/Variables (global scope)**: ไม่มี

**Called by**: [[html-crf-list]] ("ดูรายละเอียด"), [[html-gallery]] (คลิกรหัสวิจัย), [[html-crf-form]] (redirect หลังบันทึกสำเร็จ), navbar ไฮไลต์แท็บนี้เป็น "ประวัติการบันทึก" (ดู `ALIAS` ใน [[components-Navbar]])

**Depends on**: [[main-crf-detail]], build โดย [[vite-config]] เป็น entry ชื่อ `crf-detail`
