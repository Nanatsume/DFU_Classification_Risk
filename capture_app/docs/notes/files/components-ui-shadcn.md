---
name: components-ui-shadcn
description: Vendored shadcn/ui primitive components (button, card, dialog, select, etc.) — generated boilerplate, not hand-authored business logic
metadata:
  type: reference
---

# frontend/src/components/ui/*.tsx (11 ไฟล์, รวมเป็นโน้ตเดียว)

**หน้าที่**: ชุด component พื้นฐานที่ได้จากคำสั่ง `npx shadcn add` (สร้างจาก Radix UI primitives + `class-variance-authority` + Tailwind) ไม่ใช่โค้ด business logic ที่เขียนเอง จึงรวมเป็นโน้ตเดียวแทนที่จะแยกไฟล์ละโน้ตเต็มรูปแบบ — ทุกไฟล์ import [[lib-utils]] (`cn()`) เป็นมาตรฐาน และถูกเรียกใช้กระจายอยู่ทั่วทั้ง `frontend/src/pages/` และ `frontend/src/components/`

**ไฟล์ในกลุ่มนี้**:
- `badge.tsx` — Badge (ป้ายสถานะสี)
- `button.tsx` — Button (รองรับ `variant`, `size`, `asChild`)
- `card.tsx` — Card, CardContent ฯลฯ
- `checkbox.tsx` — Checkbox (Radix)
- `dialog.tsx` — Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter (Radix)
- `input.tsx` — Input
- `label.tsx` — Label (Radix)
- `radio-group.tsx` — RadioGroup (Radix)
- `select.tsx` — Select, SelectTrigger, SelectContent, SelectItem, SelectValue (Radix)
- `separator.tsx` — Separator (Radix)
- `table.tsx` — Table, TableHeader, TableBody, TableRow, TableHead, TableCell
- `textarea.tsx` — Textarea

**Called by**: [[pages-Home]], [[pages-Login]], [[pages-CrfForm]], [[pages-CrfList]], [[pages-CrfDetail]], [[pages-Capture]], [[pages-Roi]], [[pages-Gallery]], [[components-Navbar]], [[components-DeleteConfirmDialog]]

**Depends on**: [[lib-utils]] (`cn()`), `radix-ui`, `class-variance-authority`, `lucide-react` (npm packages ภายนอก)
