---
name: api-post-commit
description: "POST /api/commit — finalizes a case's captures, writes the meta/{rid}.json mirror, saves the commit row"
metadata:
  type: reference
---

# POST /api/commit

**Method**: POST — ต้อง auth

**เรียกใช้จากไฟล์ไหนบ้าง**: [[pages-Capture]] (`commit()`, ปุ่ม "✓ ยืนยันและบันทึก")

**ส่งข้อมูลอะไรไป (payload)**: `{ rid: string, operator: string }`

**รับข้อมูลอะไรกลับมา (response)**: record เต็ม `{ schema_version, research_id, captured_at, operator, podoscope: {raw, preprocessing}, thermal: {image, radiometric}, status: 'complete'|'partial', app_version }` — `404` ถ้าไม่มีภาพเลยสักส่วน SQLite เป็น source of truth, ไฟล์ `data/meta/{rid}.json` เป็นแค่สำเนาไว้ดูด้วยตา

**ไฟล์ backend ที่ handle**: [[server]] (`commit()`) → [[db]] (`upsert_case()`, `save_commit()`, `log_audit()`)
