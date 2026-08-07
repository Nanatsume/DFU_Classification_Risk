---
name: api-post-session-new
description: "POST /api/session/new — mints and reserves the next research id (P0001, P0002, ...)"
metadata:
  type: reference
---

# POST /api/session/new

**Method**: POST — ต้อง auth

**เรียกใช้จากไฟล์ไหนบ้าง**: [[pages-CrfForm]] (ตอนเปิดฟอร์มใหม่ ไม่ใช่โหมดแก้ไข)

**ส่งข้อมูลอะไรไป (payload)**: ไม่มี body

**รับข้อมูลอะไรกลับมา (response)**: `{ research_id: string, started_at: string }` — จองรหัสไว้ทันที (`db.upsert_case(rid)`) แม้ฟอร์มจะยังไม่ถูกบันทึกจริง เพื่อให้ตัวนับไม่ซ้ำแม้ผู้ใช้ปิดฟอร์มทิ้งกลางคัน

**ไฟล์ backend ที่ handle**: [[server]] (`session_new()`) → [[db]] (`next_research_id()`, `upsert_case()`)
