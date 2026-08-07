---
name: dfu-rid-constant
description: DFU_RID — the module-level constant in _via_dfu.js parsed once from ?rid= and referenced throughout the connector
metadata:
  type: reference
---

# State: `DFU_RID` (module-level const ใน [[_via_dfu]])

**คืออะไร**: ค่าคงที่ที่อ่านจาก query param `?rid=` ครั้งเดียวตอนโหลดสคริปต์ (`const DFU_RID = new URLSearchParams(location.search).get('rid')`) แล้วใช้ซ้ำทั่วทั้งไฟล์ — เป็นตัวเชื่อมว่าตอนนี้ VIA session นี้กำลังทำงานกับเคสไหน แยกจาก [[url-query-params]] เพราะ note นี้โฟกัสเฉพาะการใช้ค่านี้เป็น state ภายในไฟล์ JS ไฟล์เดียว ไม่ใช่การส่ง query param ข้ามหน้า

**ถูกสร้าง/แก้ไขที่ไฟล์ไหนบ้าง**: [[_via_dfu]] (บรรทัดแรกของไฟล์ อ่านครั้งเดียว ไม่มีจุดไหนเขียนทับ)

**ถูกอ่านไปใช้ที่ไฟล์ไหนบ้าง**: [[_via_dfu]] ทุกฟังก์ชัน — `_via_load_submodules()` (เช็คว่ามีค่าหรือไม่ก่อนเริ่ม), `dfu_needed_sides()` (ยิง fetch `/api/crf/{DFU_RID}`), `dfu_add_case_images()` (สร้าง URL ภาพ), `dfu_add_toolbar()` (แสดงรหัสเคส + ลิงก์กลับ), `dfu_save_roi()` (ยิง `POST /api/roi/{DFU_RID}`)
