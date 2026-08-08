---
name: components-Navbar
description: Shared navbar rendered at the top of every protected page — active-link highlighting, LIVE/DEMO badge, logout button
metadata:
  type: reference
---

# frontend/src/components/Navbar.tsx

**หน้าที่**: navbar ที่ [[lib-auth]] (`AuthGuard`) render ไว้บนสุดของทุกหน้าที่ต้อง login แสดงลิงก์เมนูทั้งหมด (หน้าแรก/กรอกฟอร์มใหม่/ประวัติการบันทึก/ถ่ายภาพ/ทำ ROI/คลังภาพ), ไฮไลต์แท็บปัจจุบัน, badge LIVE/DEMO (จาก `probeMode()`), และปุ่มออกจากระบบ พอร์ตมาจาก `static/js/nav.js` เดิม เต็มความกว้างหน้าจอ (ไม่มี max-width)

**Functions/Variables (global scope)**:
- `LINKS` — array ของ `{ href, label }` เมนูทั้ง 6 รายการ
- `ALIAS` — map พิเศษ ให้ `crf-detail.html` ไฮไลต์แท็บ `crf-list.html` แทน
- `Navbar()` — component หลัก

**Called by**: [[lib-auth]] (`AuthGuard` render `<Navbar />` ก่อน children)

**Depends on**: [[lib-api]] (`probeMode()`), [[lib-auth]] (`logout()`), shadcn `Badge`/`Button` ([[components-ui-shadcn]])
