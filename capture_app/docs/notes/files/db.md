---
name: db
description: SQLite data layer (data/app.db) — the single source of truth for cases, CRF forms, captures, ROI, sessions, settings
metadata:
  type: reference
---

# db.py

**หน้าที่**: เลเยอร์ข้อมูล SQLite เพียงชั้นเดียวของทั้งระบบ แทนที่ไฟล์ flat-file เดิม 5 รูปแบบ (`data/crf/*.json`, `data/roi/*.json`, `data/meta/*.json`, `data/manifest.csv`, `data/crf_manifest.csv`) เก็บทุกตารางไว้ในไฟล์เดียว `data/app.db` — เปิด connection ใหม่ทุกครั้งที่เรียก (WAL mode + busy_timeout) เพื่อรองรับ multi-thread ของ FastAPI ทุกโมดูล backend อื่น ([[server]], [[auth]], [[crf_store]], [[roi_store]]) เรียกใช้ฟังก์ชันในไฟล์นี้แทนการต่อ SQLite เอง

**Functions/Variables (global scope)**:
- `TZ`, `BASE`, `DATA_DIR`, `DB_PATH`, `SCHEMA` (DDL string), `SEED_NURSES` — ค่าคงที่/สคีมา
- `now_iso()`, `get_conn()`, `tx()` (context manager: 1 connection = 1 transaction), `init_db()` (รัน schema + seed พยาบาล)
- **cases / id minting**: `upsert_case()`, `next_research_id()` (นับเลขถัดไปแบบ `PNNNN`), `list_cases_with_status()`
- **CRF**: `has_crf()`, `get_crf()`, `list_crf()`, `_crf_row_to_dict()`, `save_crf()`, `delete_crf()`
- **captures/preprocessing/commits**: `has_capture()`, `save_capture()`, `get_capture()`, `save_preprocessing()`, `get_preprocessing()`, `save_commit()`, `list_commits()`, `committed_max()`, `crf_max()`
- **ROI**: `get_roi()`, `list_roi()`, `save_roi()`, `delete_roi()`
- **nurses**: `list_nurses()`, `add_nurse()`
- **settings**: `get_setting()`, `set_setting()`
- **sessions**: `create_session()`, `get_session()`, `delete_session()`, `purge_expired_sessions()`
- **audit**: `log_audit()`

ตารางที่สร้างจาก `SCHEMA` แต่ละตารางถือเป็น shared state ข้ามไฟล์ — ดู `docs/notes/state/` (เช่น [[db-cases-table]], [[db-crf_forms-table]], [[session-cookie]] ฯลฯ)

**Called by**: [[server]], [[auth]], [[crf_store]], [[roi_store]], [[migrate_to_sqlite]], [[conftest]], [[test_db]]

**Depends on**: ไม่มี (เป็นเลเยอร์ล่างสุด ไม่ import โมดูลอื่นในโปรเจกต์นี้ นอกจาก stdlib `sqlite3`/`json`)
