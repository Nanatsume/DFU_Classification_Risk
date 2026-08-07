---
name: server
description: Main FastAPI app — routes for capture, preprocess, commit, file serving; mounts all sub-routers and the static frontend
metadata:
  type: reference
---

# server.py

**หน้าที่**: จุดรวม FastAPI app หลักของ `capture_app` — ประกาศ endpoint สำหรับ health check, รายชื่อเคส, การถ่ายภาพ (podoscope/thermal), การรัน preprocessing, การ commit เคส, และการเสิร์ฟไฟล์ภาพ นอกจากนี้ยัง `include_router` เอา [[crf_store]], [[roi_store]] เข้ามา และ `mount` โฟลเดอร์ static (`static/` และ `via_static/`) เพื่อเสิร์ฟ frontend ที่ build แล้ว เป็นไฟล์เดียวที่ประกอบทุกอย่างเข้าด้วยกันตอน `uvicorn server:app` สตาร์ท

**Functions/Variables (global scope)**:
- `APP_VERSION`, `SCHEMA_VERSION`, `TZ`, `BASE`, `DATA_DIR`, `STATIC_DIR`, `META_DIR`, `MODALITIES` — ค่าคงที่ระดับโมดูล
- `app` — FastAPI instance
- `SOURCE` — instance จาก `get_source()` ([[capture_source]]) กำหนดว่าใช้กล้องจำลองหรือกล้องจริง
- `require_session` — FastAPI `Depends(auth.require_session)` ใช้เป็น dependency guard ของทุก endpoint ที่ต้อง login
- `now_iso()` — timestamp ปัจจุบันแบบ ISO ในโซนเวลา Bangkok
- `raw_path(rid, modality)`, `prepro_path(rid, side)`, `prepro_full_path(rid, side)`, `prepro_original_path(rid, side)`, `rel(p)`, `url(p)` — ฟังก์ชันคำนวณ path ของไฟล์ภาพแต่ละแบบใต้ `data/`
- `CaptureReq`, `RidReq`, `CommitReq` — pydantic request models
- Routes: `GET /api/health`, `GET /api/cases`, `POST /api/session/new`, `POST /api/capture`, `POST /api/preprocess`, `GET /api/file/{path}`, `POST /api/commit`, `GET /api/manifest` — รายละเอียดแต่ละ endpoint ดูใน `docs/notes/api/`

**Called by**: เรียกใช้งานผ่าน `uvicorn server:app` (entry point ของทั้งระบบ), ทดสอบผ่าน [[test_api]] และ [[conftest]] (fixture `client`)

**Depends on**: [[auth]] (session + login router), [[db]] (SQLite data layer), [[capture_source]] (กล้อง/แหล่งภาพ), [[preprocessing]] (pipeline ประมวลผลภาพเท้า), [[crf_store]] (router ฟอร์ม CRF), [[roi_store]] (router ROI) — และ mount โฟลเดอร์ `static/` (ผลลัพธ์ build ของ frontend) กับ `via_static/` ([[_via_dfu]])
