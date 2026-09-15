---
name: api-get-pending
description: "GET /api/pending — photographed cases whose CRF has not been transcribed yet (the working queue)"
metadata:
  type: reference
---

# GET /api/pending

**Method**: GET — ต้อง auth

**เรียกใช้จากไฟล์ไหนบ้าง**: [[pages-CrfList]] (กล่อง "รอกรอกแบบฟอร์ม" ด้านบนตาราง)

**รับข้อมูลอะไรกลับมา (response)**: `[{ research_id, hn, created_at, has_podo, has_thermal }]` เรียงใหม่สุดก่อน

**เงื่อนไข**: เคสที่ **มีภาพแล้ว** แต่ **ยังไม่มีแถวใน `crf_forms`** — เคสที่ยังไม่ได้ถ่ายจะไม่อยู่ในคิว เพราะยังไม่มีอะไรให้กรอกอ้างอิง

**ทำไมต้องโชว์ HN กับเวลา**: HN คือสิ่งที่ใช้เปิดผลตรวจของโรงพยาบาล ส่วนเวลาที่ถ่ายคือสิ่งที่แยกผู้ป่วยสองคนที่ HN ใกล้กันออกจากกันตอนมานั่งกรอกทีหลัง

**ไฟล์ backend ที่ handle**: [[server]] (`pending()`) → [[db]] (`list_pending_crf()`)
