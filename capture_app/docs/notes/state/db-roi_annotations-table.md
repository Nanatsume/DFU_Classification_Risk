---
name: db-roi_annotations-table
description: SQLite `roi_annotations` table — full VIA project JSON + a small per-side region-count summary
metadata:
  type: reference
---

# State: SQLite `roi_annotations` table

**คืออะไร**: เก็บผลมาร์ก ROI ต่อเคส 2 รูปแบบคู่กัน — `project_json` (VIA project JSON เต็ม เปิดกลับเข้า VIA ได้) และ `summary_json` (สรุปย่อ region count ต่อข้าง ใช้แสดงในตาราง list โดยไม่ต้องโหลด blob ใหญ่) เป็น state สำคัญที่ตรรกะ "ข้างไหนทำ ROI แล้ว" ([[lib-roiStatus]]) อ่าน `region_count` จากตรงนี้

**ถูกสร้าง/แก้ไขที่ไฟล์ไหนบ้าง**: [[db]] (`save_roi()`, `delete_roi()`) เรียกจาก [[roi_store]] ([[api-post-roi-rid]], [[api-delete-roi-rid]]) ซึ่งถูกเรียกจาก [[_via_dfu]] (`dfu_save_roi()`), [[migrate_to_sqlite]] (`migrate_roi()`)

**ถูกอ่านไปใช้ที่ไฟล์ไหนบ้าง**: [[db]] (`get_roi()`, `list_roi()`) → [[api-get-roi-list]], [[api-get-roi-rid]] — ใช้โดย [[pages-Roi]], [[pages-CrfList]] (region count ต่อข้าง), [[pages-CrfDetail]] (SVG overlay + region count), [[_via_dfu]] (เปิดงานเก่ากลับเข้า VIA)
