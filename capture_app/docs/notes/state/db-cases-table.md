---
name: db-cases-table
description: SQLite `cases` table — the root row every other table foreign-keys against, the research-id counter, and the only column holding a hospital number
metadata:
  type: reference
---

# State: SQLite `cases` table

**คืออะไร**: ตารางแม่ที่ทุกตารางอื่น (`crf_forms`, `captures`, `preprocessing`, `commits`, `roi_annotations`) อ้าง foreign key กลับมา (`research_id TEXT PRIMARY KEY`) เป็นแหล่งที่มาของ `next_research_id()` (นับเลขสูงสุดที่เคยมี +1) — แถวถูกสร้างแบบ defensive upsert จากแทบทุกฟังก์ชันเขียนข้อมูลใน [[db]] เพื่อกัน FK constraint พังไม่ว่าจะเรียกจากลำดับไหนก็ตาม

**ถูกสร้าง/แก้ไขที่ไฟล์ไหนบ้าง**: [[db]] (`upsert_case()`, และเรียกซ้ำจากภายใน `save_crf()`, `save_capture()`, `save_preprocessing()`, `save_commit()`, `save_roi()`), [[migrate_to_sqlite]] (`migrate_meta()`, `migrate_manifest()`)

**ถูกอ่านไปใช้ที่ไฟล์ไหนบ้าง**: [[db]] (`next_research_id()`, `list_cases_with_status()` และ `list_pending_crf()` ผ่าน JOIN) — ทางอ้อมทุก endpoint ที่แสดงรายชื่อเคส เช่น [[api-get-cases]], [[api-get-pending]]

## คอลัมน์ `hn` — ข้อมูลระบุตัวบุคคลชิ้นเดียวในระบบ

เก็บ HN ของโรงพยาบาล เพราะลำดับงานจริงบังคับ: ถ่ายภาพที่คลินิกก่อน (พยาบาลไม่มีเวลากรอกฟอร์ม 30 ช่องตอนนั้น) แล้วค่อยคัดลอกข้อมูลจาก CRF ตรวจประจำปีของโรงพยาบาลทีหลัง ซึ่งค้นด้วย HN และไม่มีรหัสวิจัย — HN จึงเป็นตัวเชื่อมเดียวระหว่างสองฝั่ง เขียนที่ [[db]] (`start_case_with_hn()`) จาก [[api-post-session-start]]

**ถูกกักไว้ที่คอลัมน์นี้คอลัมน์เดียวโดยเจตนา** ไม่ไปโผล่ที่:

- ชื่อไฟล์ภาพ (ตั้งชื่อด้วยรหัสวิจัยตั้งแต่เขียนครั้งแรก — เหตุผลที่ mint รหัสตอนถ่าย ไม่ใช่ตอนกรอกฟอร์ม)
- `meta/*.json`, `fields_json`
- CSV export ทั้งสองแบบ ([[pages-CrfList]])
- cloud backup — `tools/backup.py` ล้าง `hn` ออกจาก snapshot แล้ว VACUUM ก่อนอัปโหลด สำเนาบนคลาวด์จึงไม่มีตัวระบุตัวตนแม้ remote จะเข้ารหัสอยู่แล้ว

**ทำไมไม่ลบทิ้งทันทีที่จับคู่เสร็จ**: การคัดลอกด้วยมือมีโอกาสผิด ถ้าลบ HN ไปแล้วจะตรวจสอบค่าที่สงสัยกับต้นฉบับไม่ได้อีกเลย จึงเก็บไว้ระหว่างเก็บข้อมูล แล้วล้างทีเดียวตอนปิดโครงการผ่าน [[api-hn]] (`DELETE`) ซึ่งย้อนกลับไม่ได้
