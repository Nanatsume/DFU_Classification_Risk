---
name: db-settings-audit-tables
description: SQLite `settings` (key/value, e.g. password_hash) + `audit_log` (append-only action log) tables
metadata:
  type: reference
---

# State: SQLite `settings` / `audit_log` tables

**คืออะไร**: `settings` เป็น key/value ทั่วไป ปัจจุบันมีค่าเดียวที่ใช้จริงคือ `password_hash` (รหัสผ่านทีมที่ hash แล้ว) `audit_log` เป็น log แบบ append-only บันทึกทุก action สำคัญ (`login`, `crf_save`, `crf_delete`, `capture`, `commit`, `roi_save`, `roi_delete`) พร้อม `research_id` ที่เกี่ยวข้อง — ปัจจุบันยังไม่มีหน้า UI ใดอ่าน `audit_log` มาแสดง (เก็บไว้เผื่อสืบย้อนหลังด้วยมือ)

**ถูกสร้าง/แก้ไขที่ไฟล์ไหนบ้าง**: [[db]] (`set_setting()`, `log_audit()`) เรียกจาก [[auth]] (`bootstrap_password()` เขียน `password_hash`) และแทบทุกฟังก์ชันเขียนข้อมูลใน [[server]]/[[crf_store]]/[[roi_store]] (`log_audit()`)

**ถูกอ่านไปใช้ที่ไฟล์ไหนบ้าง**: [[db]] (`get_setting()`) → [[auth]] (`login()` ตรวจรหัสผ่าน) — `audit_log` ไม่มีจุดอ่านกลับจากโค้ดใดในระบบตอนนี้ (⚠️ เขียนอย่างเดียว ยังไม่มี endpoint/หน้าแสดงผล)
