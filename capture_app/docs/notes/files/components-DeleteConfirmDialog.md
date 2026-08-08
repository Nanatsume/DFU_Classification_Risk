---
name: components-DeleteConfirmDialog
description: Generic typed-code delete confirmation dialog — requires typing the exact research ID before the delete button enables
metadata:
  type: reference
---

# frontend/src/components/DeleteConfirmDialog.tsx

**หน้าที่**: dialog ยืนยันการลบแบบต้องพิมพ์ค่ายืนยัน (เช่นรหัสวิจัย) ให้ตรงก่อนปุ่ม "ลบถาวร" จะกดได้ — เข้มงวดกว่า `confirm()` ธรรมดาที่กดผ่านเผลอได้ง่าย เขียนเป็น generic component ให้ action "ลบ X" อื่นในระบบใช้ซ้ำได้ ปัจจุบันมีผู้ใช้จริงรายเดียวคือหน้า CRF list

**Functions/Variables (global scope)**:
- `DeleteConfirmDialog({ open, onOpenChange, code, title, description, onConfirm })` — component หลัก, มี state `typed`/`busy` ภายใน

**Called by**: [[pages-CrfList]] (ลบเคสออกจากประวัติ)

**Depends on**: shadcn `Button`/`Input`/`Dialog` ([[components-ui-shadcn]])
