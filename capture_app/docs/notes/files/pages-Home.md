---
name: pages-Home
description: Dashboard page (index.html) — 5 cards linking to every feature, plus a live count of saved CRF forms
metadata:
  type: reference
---

# frontend/src/pages/Home.tsx

**หน้าที่**: หน้าแรกของระบบ (dashboard) แสดง card 01-05 ลิงก์ไปยังฟีเจอร์หลักทั้งหมด (กรอกฟอร์มใหม่, ถ่ายภาพ, ทำ ROI, ประวัติการบันทึก, คลังภาพ) — เป็น layout แบบ grid 2×2 บวก card ที่ 5 เต็มความกว้าง ดึงจำนวนฟอร์มที่บันทึกแล้วมาโชว์ในปุ่ม "ดูประวัติทั้งหมด"

**Functions/Variables (global scope)**:
- `Home()` — component เดียวในไฟล์, ใช้ `useState<number|null>` เก็บ `crfCount`

**Called by**: [[main-home]]

**Depends on**: [[lib-api]] (`api('/api/crf')` เพื่อนับจำนวนฟอร์ม), shadcn `Card`/`Button` ([[components-ui-shadcn]]) — ลิงก์ไปหน้าอื่นด้วย `<a href>` ธรรมดา (ไม่ใช้ router) ไปยัง `crf-form.html`, `capture.html`, `roi.html`, `crf-list.html`, `gallery.html`
