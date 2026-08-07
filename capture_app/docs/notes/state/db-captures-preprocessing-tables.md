---
name: db-captures-preprocessing-tables
description: SQLite `captures` + `preprocessing` tables — raw photo paths per modality, and the L/R training-image path per case
metadata:
  type: reference
---

# State: SQLite `captures` / `preprocessing` tables

**คืออะไร**: `captures` เก็บ path ของภาพดิบต่อ modality (`podoscope`/`thermal`) ต่อเคส (`PRIMARY KEY (research_id, modality)`), `preprocessing` เก็บ path ของภาพเทรน 224×224 ต่อข้าง (`PRIMARY KEY (research_id, side)`) — ทั้งสองตารางเก็บแค่ **path** ไปยังไฟล์บนดิสก์ (`data/podo/...`, `data/thermal/...`) ตัว byte ของภาพไม่ได้อยู่ใน SQLite

**ถูกสร้าง/แก้ไขที่ไฟล์ไหนบ้าง**: [[db]] (`save_capture()`, `save_preprocessing()`) เรียกจาก [[server]] ([[api-post-capture]], [[api-post-preprocess]]), [[migrate_to_sqlite]] (`migrate_meta()`)

**ถูกอ่านไปใช้ที่ไฟล์ไหนบ้าง**: [[db]] (`has_capture()`, `get_capture()`, `get_preprocessing()`, `list_cases_with_status()`, `list_commits()`) — ใช้ตัดสินใจ 409 gate ใน [[api-post-capture]]/[[api-delete-crf-pid]], และแสดงสถานะถ่ายภาพใน [[pages-Capture]], [[pages-CrfList]], [[pages-Roi]]
