---
name: localstorage-capture_records
description: browser localStorage key 'capture_records' — DEMO-mode fallback storage when the backend is unreachable
metadata:
  type: reference
---

# State: `localStorage['capture_records']`

**คืออะไร**: state ฝั่ง browser ล้วนๆ (ไม่ผ่าน backend เลย) ใช้เฉพาะตอน [[pages-Capture]] ตรวจพบว่าเซิร์ฟเวอร์ต่อไม่ได้ (`GET /api/health` fail) แล้วสลับเป็น "DEMO mode" — จำลองการถ่ายภาพด้วย `<canvas>` แล้วเก็บ record ไว้ใน `localStorage` แทนการ POST ไป backend จริง ไม่ persist ข้ามเครื่อง/เบราว์เซอร์

**ถูกสร้าง/แก้ไขที่ไฟล์ไหนบ้าง**: [[pages-Capture]] (`saveRecords()` เขียน, เรียกจาก `commit()` ตอน `mode === 'demo'`)

**ถูกอ่านไปใช้ที่ไฟล์ไหนบ้าง**: [[pages-Capture]] (`loadRecords()`, เรียกจาก `refreshSaved()` ตอน `mode === 'demo'`, แสดงในตาราง "เคสที่บันทึกแล้ว")
