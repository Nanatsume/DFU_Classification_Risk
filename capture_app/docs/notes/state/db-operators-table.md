---
name: db-operators-table
description: SQLite `operators` table — the photographer dropdown source (4 nurses + 3 research team members), seeded directly, no add-via-web-form UI
metadata:
  type: reference
---

# State: SQLite `operators` table

**คืออะไร**: รายชื่อสำหรับ dropdown "ผู้ถ่ายภาพ" ในหน้าถ่ายภาพ — แยกจากตาราง [[db-nurses-table]] เพราะขอบเขตต่างกัน (`nurses` = พยาบาลผู้ตรวจในฟอร์ม CRF เท่านั้น, `operators` = ใครก็ได้ที่มาถ่ายภาพ ซึ่งรวมทั้งพยาบาลทั้ง 4 คนและทีมวิจัยอีก 3 คน) seed ไว้ตรงๆ ใน `db.SEED_OPERATORS` ตอน `init_db()` จงใจไม่มีปุ่มเพิ่มชื่อผ่านหน้าเว็บ (เหมือนกับ [[db-nurses-table]]) เพราะเป็นรายชื่อคงที่ที่เปลี่ยนไม่บ่อย

**ถูกสร้าง/แก้ไขที่ไฟล์ไหนบ้าง**: [[db]] (`init_db()` seed ตอนเริ่มต้น, `add_operator()`) เรียกจาก [[server]] ([[api-post-operators]] — ปัจจุบันยังไม่มี UI ผูก)

**ถูกอ่านไปใช้ที่ไฟล์ไหนบ้าง**: [[db]] (`list_operators()`) → [[api-get-operators]] → [[pages-Capture]] (dropdown "ผู้ถ่ายภาพ")
