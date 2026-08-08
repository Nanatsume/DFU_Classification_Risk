---
name: lib-utils
description: Tiny className-merging helper (cn) used by every shadcn/ui component
metadata:
  type: reference
---

# frontend/src/lib/utils.ts

**หน้าที่**: helper มาตรฐานของ shadcn/ui — รวม `clsx` (merge conditional class names) กับ `tailwind-merge` (แก้ conflict ของ Tailwind class ที่ซ้ำกัน) เป็นฟังก์ชันเดียว `cn()` ที่ component ทุกตัวใน `components/ui/` เรียกใช้

**Functions/Variables (global scope)**:
- `cn(...inputs: ClassValue[])` — `twMerge(clsx(inputs))`

**Called by**: [[components-ui-shadcn]] (ทุก component ใน `components/ui/`), [[components-Navbar]], [[components-DeleteConfirmDialog]]

**Depends on**: `clsx`, `tailwind-merge` (npm packages ภายนอก)
