---
name: api-get-crf-pid
description: "GET /api/crf/{pid} — single CRF record fetch"
metadata:
  type: reference
---

# GET /api/crf/{pid}

**Method**: GET — ต้อง auth

**เรียกใช้จากไฟล์ไหนบ้าง**: [[pages-CrfDetail]] (โหลดข้อมูลเคสที่จะแสดง), [[pages-CrfForm]] (โหมดแก้ไข, query param `?edit=`), [[_via_dfu]] (`dfu_needed_sides()`, เช็คว่าข้างไหนเป็น Negative)

**ส่งข้อมูลอะไรไป (payload)**: `pid` ใน URL path

**รับข้อมูลอะไรกลับมา (response)**: `CrfRecord` เดียว ([[lib-crfTypes]]) — `404` ถ้าไม่มีฟอร์มของ pid นี้

**ไฟล์ backend ที่ handle**: [[crf_store]] (`get_record()`) → [[db]] (`get_crf()`)
