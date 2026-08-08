---
name: pages-Gallery
description: Cross-case image browser (gallery.html) — 4 thumbnails per committed case for a quick QC sweep before training
metadata:
  type: reference
---

# frontend/src/pages/Gallery.tsx

**หน้าที่**: หน้าไล่ดูรูปทุกเคสที่บันทึกแล้วในหน้าเดียว (level-2 follow-up ของส่วน "รูปภาพ" ใน [[pages-CrfDetail]] ซึ่งดูได้ทีละเคส) แสดง thumbnail 4 รูปต่อเคส (Podoscope, Thermal, เท้าซ้าย-full, เท้าขวา-full) ใช้สแกนหาภาพที่คุณภาพแย่ก่อนเอาไปเทรนโมเดล

**Functions/Variables (global scope)**:
- `Thumb({ src, label })` — thumbnail component, ซ่อนตัวเอง/โชว์ placeholder ถ้าโหลดรูปไม่ได้
- `Gallery()` — component หลัก, state: `rows, error`

**Called by**: [[main-gallery]]

**Depends on**: [[lib-api]], [[lib-crfTypes]] (`ManifestRow`), shadcn `Badge`/`Card` ([[components-ui-shadcn]])
