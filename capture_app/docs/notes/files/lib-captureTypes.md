---
name: lib-captureTypes
description: Shared TypeScript types for the capture flow — CaseRow, CommitRecord, ManifestRow, Modality
metadata:
  type: reference
---

# frontend/src/lib/captureTypes.ts

**หน้าที่**: นิยาม type สำหรับหน้าถ่ายภาพโดยเฉพาะ — รูปร่างของเคสที่รอถ่ายภาพ (`CaseRow`), record ที่ได้จากการ commit (`CommitRecord`, ตรงกับ response ของ `POST /api/commit` ใน [[server]]), แถว manifest, และชนิดของโมดัลลิตี้

**Functions/Variables (global scope)**:
- `CaseRow` (interface) — `{ research_id, nurse, iwgdf: {L,R}, has_podo, has_thermal }`
- `CommitRecord` (interface) — ตรงกับ record ที่ `POST /api/commit` คืนกลับ
- `ManifestRow` (interface)
- `Modality` (type) — `'podoscope' | 'thermal'`

**Called by**: [[pages-Capture]]

**Depends on**: ไม่มี (type declarations เท่านั้น)
