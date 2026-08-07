---
name: db-commits-table
description: SQLite `commits` table — one row per finalized case, the source of GET /api/manifest
metadata:
  type: reference
---

# State: SQLite `commits` table

**คืออะไร**: เก็บสถานะการ "ยืนยันและบันทึก" ของแต่ละเคส (`status: 'complete'|'partial'`, `committed_at`, `operator`) เป็นตารางที่แทน `data/manifest.csv` เดิม — `podo_raw`/`podo_prepro`/`thermal` ใน response ของ [[api-get-manifest]] ไม่ได้เก็บในตารางนี้โดยตรง แต่ประกอบขึ้นจาก JOIN กับ `captures`/`preprocessing` ตอนอ่าน (`list_commits()`)

**ถูกสร้าง/แก้ไขที่ไฟล์ไหนบ้าง**: [[db]] (`save_commit()`) เรียกจาก [[server]] ([[api-post-commit]]), [[migrate_to_sqlite]] (`migrate_manifest()`)

**ถูกอ่านไปใช้ที่ไฟล์ไหนบ้าง**: [[db]] (`list_commits()`, `committed_max()`) → [[api-get-manifest]], [[api-get-health]] (`count` field) — ทางอ้อม [[pages-Capture]], [[pages-Gallery]], [[pages-CrfDetail]], [[pages-CrfList]]
