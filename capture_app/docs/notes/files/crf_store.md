---
name: crf_store
description: CRF-07 form API router — save/get/list/delete case record forms, plus the nurses dropdown endpoints
metadata:
  type: reference
---

# crf_store.py

**หน้าที่**: FastAPI router สำหรับแบบฟอร์ม CRF-07 (ผลตรวจ IWGDF) — บันทึก/อ่าน/ลบฟอร์มต่อเคส และ router ย่อยสำหรับรายชื่อพยาบาล (dropdown source) ย้ายจากไฟล์ `data/crf/*.json` เดิมมาเป็น SQLite ([[db]]) ทั้งหมด แต่ route contract เดิมไม่เปลี่ยน

**Functions/Variables (global scope)**:
- `SCHEMA_VERSION`, `TZ`, `router` (prefix `/api/crf`), `nurses_router` (prefix `/api/nurses`)
- `now_iso()`, `crf_max()` (proxy ไป `db.crf_max()`)
- `CrfRecord` (pydantic model: `pid, nurse, nurse2, savedAt, data`)
- Routes: `GET /api/crf`, `GET /api/crf/{pid}`, `POST /api/crf`, `DELETE /api/crf/{pid}`
- `_has_photos(pid)` — เช็คว่าเคสมีภาพถ่ายผูกอยู่หรือไม่ (ใช้กัน delete)
- `NurseReq` (pydantic model), Routes: `GET /api/nurses`, `POST /api/nurses`

**Called by**: [[server]] (`app.include_router(crf_router, ...)`, `app.include_router(nurses_router, ...)`), [[test_api]]

**Depends on**: [[db]] (`save_crf`, `get_crf`, `list_crf`, `delete_crf`, `has_capture`, `list_nurses`, `add_nurse`, `log_audit`, `crf_max`)
