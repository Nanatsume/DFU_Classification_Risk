---
name: api-delete-crf-pid
description: "DELETE /api/crf/{pid} — deletes a form; blocked with 409 if the case already has photos"
metadata:
  type: reference
---

# DELETE /api/crf/{pid}

**Method**: DELETE — ต้อง auth

**เรียกใช้จากไฟล์ไหนบ้าง**: [[pages-CrfList]] (`doDelete(pid)`, ผ่าน [[components-DeleteConfirmDialog]])

**ส่งข้อมูลอะไรไป (payload)**: `pid` ใน URL path

**รับข้อมูลอะไรกลับมา (response)**: `{ deleted: pid }` — `404` ถ้าไม่มีฟอร์ม, **`409`** ถ้าเคสนั้นมีภาพถ่ายผูกอยู่แล้ว (นโยบาย: ต้องลบภาพก่อนถึงจะลบฟอร์มได้ กันข้อมูลภาพกำพร้า)

**ไฟล์ backend ที่ handle**: [[crf_store]] (`delete_record()`, เช็ค `_has_photos()`) → [[db]] (`delete_crf()`, `has_capture()`, `log_audit()`)
