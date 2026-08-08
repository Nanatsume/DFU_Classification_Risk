---
name: api-get-manifest
description: "GET /api/manifest — every committed case (podo/thermal/prepro paths + status), newest first"
metadata:
  type: reference
---

# GET /api/manifest

**Method**: GET — ต้อง auth

**เรียกใช้จากไฟล์ไหนบ้าง**: [[pages-Capture]] (ตาราง "เคสที่บันทึกแล้ว"), [[pages-Gallery]] (ที่มาของทุก thumbnail), [[pages-CrfDetail]] (เช็คว่าเคสนี้ถ่ายภาพแล้วหรือยัง), [[pages-CrfList]] (คอลัมน์ "ภาพ")

**ส่งข้อมูลอะไรไป (payload)**: ไม่มี

**รับข้อมูลอะไรกลับมา (response)**: array ของ `{ research_id, captured_at, status, podo_raw, podo_prepro: 'yes'|'', thermal }`

**ไฟล์ backend ที่ handle**: [[server]] (`manifest()`) → [[db]] (`list_commits()`)
