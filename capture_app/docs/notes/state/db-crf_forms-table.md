---
name: db-crf_forms-table
description: SQLite `crf_forms` table — the CRF-07 answers (fields_json) plus the cached IWGDF scoring result (derived_json)
metadata:
  type: reference
---

# State: SQLite `crf_forms` table

**คืออะไร**: เก็บฟอร์ม CRF-07 ต่อเคส — `fields_json` คือคำตอบดิบทุกฟิลด์, `derived_json` คือผลคำนวณ IWGDF ที่แคชไว้ (ผลจาก [[lib-crfScoring]]`.toDerived()` ฝั่ง frontend คำนวณแล้วส่งมาให้บันทึกพร้อมกัน) [[db]] เตือนไว้ในคอมเมนต์ว่าสองคอลัมน์นี้ต้อง "ไม่มีวันไม่ตรงกัน" (เขียนพร้อมกันเสมอในคำสั่งเดียว)

**ถูกสร้าง/แก้ไขที่ไฟล์ไหนบ้าง**: [[db]] (`save_crf()`, `delete_crf()`) เรียกจาก [[crf_store]] ([[api-post-crf]], [[api-delete-crf-pid]]), [[migrate_to_sqlite]] (`migrate_crf()`)

**ถูกอ่านไปใช้ที่ไฟล์ไหนบ้าง**: [[db]] (`get_crf()`, `list_crf()`, `has_crf()`, `crf_max()`, `list_cases_with_status()`) — ทางอ้อมทุกหน้าที่แสดงข้อมูล CRF: [[pages-CrfList]], [[pages-CrfDetail]], [[pages-CrfForm]] (โหมดแก้ไข), [[_via_dfu]] (`dfu_needed_sides()`)
