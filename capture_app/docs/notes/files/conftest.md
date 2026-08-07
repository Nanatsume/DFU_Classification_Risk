---
name: conftest
description: Shared pytest fixtures — tmp_db (isolated db.py), client (isolated FastAPI TestClient), auth_client (pre-logged-in client)
metadata:
  type: reference
---

# tests/conftest.py

**หน้าที่**: fixture กลางของชุดทดสอบ backend ทั้งหมด — สิ่งสำคัญที่สุดคือห้ามแตะ `data/app.db`/`data/` จริงเด็ดขาด จึง monkeypatch ตัวแปรระดับโมดูลของ [[db]] (และ [[server]]) ให้ชี้ไปที่ `tmp_path` ของ pytest ก่อนโค้ดจริงจะ import/แตะไฟล์ใดๆ

**Functions/Variables (global scope)**:
- `tmp_db(tmp_path, monkeypatch)` — fixture: [[db]] ที่ผูกกับ DB ชั่วคราวแยกทุกเทสต์ (ไม่ import [[server]])
- `client(tmp_path, monkeypatch)` — fixture: `TestClient` ของ [[server]] ที่ผูกกับ DB+data folder ชั่วคราว (ต้อง re-import `server` module หลัง patch เพราะ `server.py` รัน `db.init_db()`/`auth.bootstrap_password()` ตอน import)
- `auth_client(client)` — fixture: เหมือน `client` แต่ login ไว้แล้ว (มี session cookie ติดมา)

**Called by**: [[test_api]], [[test_auth]], [[test_db]] (pytest fixture injection ผ่านชื่อพารามิเตอร์)

**Depends on**: [[db]], [[server]] (import แบบ dynamic ผ่าน `importlib`)
