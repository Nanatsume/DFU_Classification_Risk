---
name: api-get-roi-rid
description: "GET /api/roi/{rid} — full VIA project JSON + summary for one case (reopenable in VIA)"
metadata:
  type: reference
---

# GET /api/roi/{rid}

**Method**: GET — ต้อง auth

**เรียกใช้จากไฟล์ไหนบ้าง**: [[pages-CrfDetail]] (วาด SVG overlay กรอบ ROI ทับ thumbnail), [[_via_dfu]] (`_via_load_submodules()`, เช็คว่ามีงานเก่าบันทึกไว้หรือยัง ถ้ามีเปิดกลับเข้า VIA)

**ส่งข้อมูลอะไรไป (payload)**: `rid` ใน URL path

**รับข้อมูลอะไรกลับมา (response)**: `{ rid, savedAt, summary, project }` — `project` คือ VIA project JSON เต็ม (`_via_img_metadata`, `_via_settings` ฯลฯ) เปิดกลับเข้า VIA ได้ตรงๆ — `404` ถ้ายังไม่เคยมาร์ก ROI เคสนี้เลย

**ไฟล์ backend ที่ handle**: [[roi_store]] (`get_roi()`) → [[db]] (`get_roi()`)
