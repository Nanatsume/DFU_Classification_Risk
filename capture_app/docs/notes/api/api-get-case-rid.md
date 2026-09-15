---
name: api-get-case-rid
description: "GET /api/case/{rid} — a case's HN, for the transcription form"
metadata:
  type: reference
---

# GET /api/case/{rid}

**Method**: GET — ต้อง auth

**เรียกใช้จากไฟล์ไหนบ้าง**: [[pages-CrfForm]] (โหมด `?pid=` — กรอกฟอร์มให้เคสที่ถ่ายภาพไว้แล้ว)

**รับข้อมูลอะไรกลับมา (response)**: `{ research_id, hn }` — `404` ถ้าไม่มีเคสนั้น

**ใช้ทำอะไร**: หน้าฟอร์มเอา HN มาโชว์ให้คนกรอกใช้เปิด CRF ตรวจประจำปีของโรงพยาบาล ตัว HN ไม่ถูกบันทึกกลับลงฟอร์ม — อยู่ใน `cases.hn` ที่เดียวตลอด

**ไฟล์ backend ที่ handle**: [[server]] (`case_detail()`) → [[db]] (`case_exists()`, `get_hn()`)
