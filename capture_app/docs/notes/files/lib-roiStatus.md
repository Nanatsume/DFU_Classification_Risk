---
name: lib-roiStatus
description: Shared per-side "does this foot need ROI marking" logic (roiSideStatus, categoryToLabel) — the clinical ROI-marking policy in code form
metadata:
  type: reference
---

# frontend/src/lib/roiStatus.ts

**หน้าที่**: เก็บตรรกะนโยบาย "ข้างไหนของเท้าต้องมาร์ก ROI" ไว้ที่เดียว — ข้าง Negative ไม่ต้องมาร์ก (ไม่มี LOPS/PAD ตามนิยาม IWGDF), ข้างที่ label ยังเป็น `null` (ฟอร์มกรอกไม่ครบ) ถือว่ายังต้องมาร์กไว้ก่อนเพื่อความปลอดภัย ใช้ร่วมกันทั้ง [[pages-Roi]], [[pages-CrfDetail]], [[pages-CrfList]] — และมีเวอร์ชัน JS คู่ขนานที่เขียนแยกด้วยมือใน [[_via_dfu]] เพราะไฟล์นั้น import ไฟล์ TypeScript นี้ไม่ได้ (เป็น vanilla JS ฝั่ง VIA)

**Functions/Variables (global scope)**:
- `RoiSideStatus` (type) — `'not_needed' | 'pending' | 'done'`
- `roiSideStatus(label, regionCount)` — คืนสถานะของข้างนั้น
- `categoryToLabel(category)` — แปลงเลข IWGDF category → `'Positive' | 'Negative' | null`
- `ROI_STATUS_TEXT` — ข้อความภาษาไทยสำหรับแต่ละสถานะ (ไม่ต้องทำ/ยังไม่ทำ/ทำแล้ว)

**Called by**: [[pages-Roi]], [[pages-CrfDetail]], [[pages-CrfList]]

**Depends on**: ไม่มี (pure logic) — มีคู่ขนานที่ไม่ import กันโดยตรงคือ [[_via_dfu]] (`dfu_needed_sides()`), ต้องแก้พร้อมกันด้วยมือถ้าตรรกะเปลี่ยน
