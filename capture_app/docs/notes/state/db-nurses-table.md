---
name: db-nurses-table
description: SQLite `nurses` table — the dropdown source for "พยาบาลผู้ตรวจ", seeded with 4 names at init
metadata:
  type: reference
---

# State: SQLite `nurses` table

**คืออะไร**: รายชื่อพยาบาลสำหรับ dropdown 2 ช่องในฟอร์ม CRF (คนที่ 1/คนที่ 2) เดิมเคย hardcode เป็น array ใน JS, ย้ายมาเป็นตารางเพื่อแก้ไขได้โดยไม่ต้องแก้โค้ด — seed 4 ชื่อไว้ตอน `init_db()` (`SEED_NURSES` ใน [[db]])

**ถูกสร้าง/แก้ไขที่ไฟล์ไหนบ้าง**: [[db]] (`init_db()` seed ตอนเริ่มต้น, `add_nurse()`) เรียกจาก [[crf_store]] ([[api-post-nurses]] — ปัจจุบันยังไม่มี UI ผูก)

**ถูกอ่านไปใช้ที่ไฟล์ไหนบ้าง**: [[db]] (`list_nurses()`) → [[api-get-nurses]] → [[pages-CrfForm]] (dropdown)
