---
name: roi_store
description: ROI annotation API router — save/get/list/delete VIA 2 project JSON and per-side region summaries
metadata:
  type: reference
---

# roi_store.py

**หน้าที่**: FastAPI router สำหรับผลมาร์ก ROI จาก VIA 2 — เก็บทั้ง VIA project JSON เต็ม (`project_json`, เปิดกลับเข้า VIA ได้) และสรุปย่อ (`summary_json`, ใช้แสดงในหน้า list โดยไม่ต้องโหลด blob ทั้งก้อน) ย้ายจากไฟล์ `data/roi/*.json` มาเป็น SQLite เช่นกัน route contract ไม่เปลี่ยน

**Functions/Variables (global scope)**:
- `TZ`, `router` (prefix `/api/roi`)
- `now_iso()`
- `RoiPayload` (pydantic model: `rid, project, summary`)
- Routes: `GET /api/roi`, `GET /api/roi/{rid}`, `POST /api/roi/{rid}`, `DELETE /api/roi/{rid}`

**Called by**: [[server]] (`app.include_router(roi_router, ...)`), [[_via_dfu]] (ฝั่ง frontend ยิง fetch ตรงมาที่ endpoint เหล่านี้), [[test_api]]

**Depends on**: [[db]] (`save_roi`, `get_roi`, `list_roi`, `delete_roi`, `log_audit`)
