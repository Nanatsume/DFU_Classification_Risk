---
name: db-cases-table
description: SQLite `cases` table — the root row every other table foreign-keys against; also the source of the monotonic research-id counter
metadata:
  type: reference
---

# State: SQLite `cases` table

**คืออะไร**: ตารางแม่ที่ทุกตารางอื่น (`crf_forms`, `captures`, `preprocessing`, `commits`, `roi_annotations`) อ้าง foreign key กลับมา (`research_id TEXT PRIMARY KEY`) เป็นแหล่งที่มาของ `next_research_id()` (นับเลขสูงสุดที่เคยมี +1) — แถวถูกสร้างแบบ defensive upsert จากแทบทุกฟังก์ชันเขียนข้อมูลใน [[db]] เพื่อกัน FK constraint พังไม่ว่าจะเรียกจากลำดับไหนก็ตาม

**ถูกสร้าง/แก้ไขที่ไฟล์ไหนบ้าง**: [[db]] (`upsert_case()`, และเรียกซ้ำจากภายใน `save_crf()`, `save_capture()`, `save_preprocessing()`, `save_commit()`, `save_roi()`), [[migrate_to_sqlite]] (`migrate_meta()`, `migrate_manifest()`)

**ถูกอ่านไปใช้ที่ไฟล์ไหนบ้าง**: [[db]] (`next_research_id()`, `list_cases_with_status()` ผ่าน JOIN) — ทางอ้อมทุก endpoint ที่แสดงรายชื่อเคส เช่น [[api-get-cases]]
