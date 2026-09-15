---
name: api-post-session-start
description: "POST /api/session/start — HN in, research id out; begins a case at the clinic before any form exists"
metadata:
  type: reference
---

# POST /api/session/start

**Method**: POST — ต้อง auth

**เรียกใช้จากไฟล์ไหนบ้าง**: [[pages-Capture]] (`startFromHn()`)

**ส่งข้อมูลอะไรไป (payload)**: `{ hn: string }` — HN ของผู้ป่วย (ตัดช่องว่างหน้า-หลังให้)

**รับข้อมูลอะไรกลับมา (response)**: `{ research_id, hn, started_at }` — `400` ถ้า HN ว่าง

**ทำไมต้องมี**: พยาบาลไม่มีเวลากรอกฟอร์ม 30 ช่องขณะที่ผู้ป่วยนั่งรออยู่ ลำดับงานจริงจึงเป็น *ถ่ายภาพก่อน แล้วค่อยกรอกฟอร์มทีหลัง* จาก CRF ตรวจประจำปีของโรงพยาบาลซึ่งค้นด้วย HN และไม่มีรหัสวิจัย — HN จึงเป็นตัวเชื่อมสองฝั่ง

**ทำไม mint รหัสตรงนี้ ไม่ใช่ตอนกรอกฟอร์ม**: เพราะไฟล์ภาพถูกตั้งชื่อด้วยรหัสวิจัยตั้งแต่เขียนครั้งแรก ทำให้ **ไม่มี HN โผล่ในชื่อไฟล์ ในรายการโฟลเดอร์ หรือใน backup เลย** ถ้า mint ทีหลังจะต้องตั้งชื่อไฟล์ด้วย HN ไปก่อนแล้วเปลี่ยนชื่อภายหลัง ซึ่งเก็บกวาดไม่หมด

**ไฟล์ backend ที่ handle**: [[server]] (`session_start()`) → [[db]] (`start_case_with_hn()`, `log_audit()`)
