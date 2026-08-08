---
name: index-css
description: Tailwind entry + design tokens (teal accent, IWGDF cat-0..3 colors) ported from the old static/css/shared.css
metadata:
  type: reference
---

# frontend/src/index.css

**หน้าที่**: จุดรวม Tailwind CSS + shadcn theme variables ของทั้งแอป กำหนด design token (สี, radius, font) ให้ตรงกับเอกลักษณ์เดิมของแอป (สี teal accent, สีระดับความเสี่ยง IWGDF cat-0 ถึง cat-3) แทนที่จะใช้สี default ของ shadcn — พอร์ตมาจาก `static/css/shared.css` เดิม รองรับทั้ง light (`:root`) และ dark (`.dark`) mode

**Functions/Variables (global scope)**: ไม่ใช่โค้ด JS — เป็นไฟล์ CSS มี `@theme inline` (แม็บตัวแปร Tailwind), `:root` / `.dark` (ตัวแปรสี), `@layer base` (base style)

**Called by**: import โดยทุกไฟล์ `main-*.tsx` ([[main-home]], [[main-login]], [[main-crf-form]], [[main-crf-list]], [[main-crf-detail]], [[main-capture]], [[main-roi]], [[main-gallery]])

**Depends on**: `tailwindcss`, `tw-animate-css`, `shadcn/tailwind.css` (npm packages)
