---
name: migrate_to_sqlite
description: One-off idempotent migration script — flat JSON/CSV files to data/app.db
metadata:
  type: reference
---

# migrate_to_sqlite.py

**หน้าที่**: สคริปต์ migration ที่รันครั้งเดียวด้วยมือ (ไม่รันอัตโนมัติตอนเซิร์ฟเวอร์สตาร์ท) แปลงข้อมูลจากไฟล์แบบเก่า (`data/crf/*.json`, `data/roi/*.json`, `data/meta/*.json`, `data/manifest.csv`) เข้า SQLite (`data/app.db`) ทุกการเขียนเป็น upsert จึงรันซ้ำได้โดยไม่เกิดข้อมูลซ้ำ

**Functions/Variables (global scope)**:
- `BASE`, `DATA_DIR` (ดึงมาจาก [[db]])
- `migrate_crf()` — จาก `data/crf/*.json` → ตาราง `crf_forms`
- `migrate_meta()` — จาก `data/meta/*.json` → ตาราง `cases`/`captures`/`preprocessing`
- `migrate_manifest()` — จาก `data/manifest.csv` → ตาราง `commits`
- `migrate_roi()` — จาก `data/roi/*.json` → ตาราง `roi_annotations`
- `main()` — รันทุกฟังก์ชันด้านบนตามลำดับ แล้วพิมพ์สรุปจำนวนแถวต่อตาราง

**Called by**: รันด้วยมือผ่าน `python migrate_to_sqlite.py` — ไม่มีไฟล์อื่นในระบบ import ไฟล์นี้

⚠️ ไม่ถูกเรียกใช้จากโค้ดอื่นเลย (dead-code ในแง่ import graph) แต่ไม่ใช่ dead code จริง — เป็นเครื่องมือ migration ที่ตั้งใจให้รันแยกต่างหากครั้งเดียว ตามที่ docstring ของไฟล์ระบุไว้

**Depends on**: [[db]] (`db.save_crf`, `db.upsert_case`, `db.save_capture`, `db.save_preprocessing`, `db.save_commit`, `db.save_roi`, `db.tx`, `db.init_db`)
