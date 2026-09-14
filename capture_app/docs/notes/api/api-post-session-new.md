---
name: api-post-session-new
description: "POST /api/session/new — reserves the next research id up front; no longer used by the UI (ids are minted on save)"
metadata:
  type: reference
---

# POST /api/session/new

**Method**: POST — ต้อง auth

**เรียกใช้จากไฟล์ไหนบ้าง**: **ไม่มีหน้าไหนเรียกแล้ว** — [[pages-CrfForm]] เคยเรียกตอนเปิดฟอร์มใหม่ แต่เลิกแล้ว เพราะการจองรหัสตั้งแต่เปิดหน้าทำให้เกิดเคสเปล่าทุกครั้งที่เปิดแล้วปิดทิ้ง ตอนนี้รหัสถูก mint ตอนกดบันทึกแทน (ดู [[api-post-crf]]) endpoint นี้เก็บไว้เผื่อ client ภายนอก/ทดสอบ

**ส่งข้อมูลอะไรไป (payload)**: ไม่มี body

**รับข้อมูลอะไรกลับมา (response)**: `{ research_id: string, started_at: string }` — จองรหัสไว้ทันที (`db.upsert_case(rid)`) แม้ฟอร์มจะยังไม่ถูกบันทึกจริง เพื่อให้ตัวนับไม่ซ้ำแม้ผู้ใช้ปิดฟอร์มทิ้งกลางคัน

**ไฟล์ backend ที่ handle**: [[server]] (`session_new()`) → [[db]] (`next_research_id()`, `upsert_case()`)
