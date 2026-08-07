---
name: lib-crfTypes
description: Shared TypeScript types for a saved CRF record — mirrors crf_store.py's CrfRecord model
metadata:
  type: reference
---

# frontend/src/lib/crfTypes.ts

**หน้าที่**: นิยาม TypeScript type ของข้อมูลฟอร์ม CRF ที่ได้จาก backend ให้ตรงกับ `CrfRecord` ใน [[crf_store]] — ใช้ร่วมกันในหลายหน้าเพื่อไม่ต้องประกาศ shape ซ้ำ

**Functions/Variables (global scope)**:
- `DerivedSide` (interface) — ผลคำนวณต่อข้าง (`lops, pad, deformity, deformities, history, category, label`)
- `CrfData` (interface) — `{ form, savedAt, fields, derived: { L, R } }`
- `CrfRecord` (interface) — `{ pid, nurse, nurse2, savedAt, data, schema_version? }`
- `ManifestRow` (interface) — แถวจาก `GET /api/manifest`
- `RoiSummaryRow` (interface) — แถวจาก `GET /api/roi`

**Called by**: [[pages-CrfList]], [[pages-CrfDetail]], [[pages-CrfForm]], [[pages-Gallery]]

**Depends on**: ไม่มี (type declarations เท่านั้น)
