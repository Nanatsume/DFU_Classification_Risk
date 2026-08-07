---
name: url-query-params
description: URL query-string parameters used as lightweight cross-page state — ?rid=, ?pid=, ?edit=, ?next=
metadata:
  type: reference
---

# State: URL query parameters (`?rid=`, `?pid=`, `?edit=`, `?next=`)

**คืออะไร**: เพราะ frontend เป็น multi-page app จริง (ไม่ใช่ SPA/router) การส่ง "จะเปิดเคสไหน" ระหว่างหน้าทำผ่าน query string ของ URL ตรงๆ แทนที่จะเป็น state ในหน่วยความจำ — เป็นวิธีสื่อสาร state ข้ามหน้าแบบเดียวที่ระบบนี้ใช้ (นอกจาก HTTP call ไป backend)

- **`?rid=`**: รหัสวิจัยของเคสที่จะเปิด — ใช้ใน `capture.html?rid=`, `via/index.html?rid=`
- **`?pid=`**: รหัสวิจัยของเคสที่จะดูรายละเอียด — ใช้ใน `crf-detail.html?pid=`
- **`?edit=`**: รหัสวิจัยของเคสที่จะแก้ไขฟอร์ม — ใช้ใน `crf-form.html?edit=`
- **`?next=`**: path ที่จะ redirect กลับไปหลัง login สำเร็จ — ใช้ใน `login.html?next=`

**ถูกสร้าง/แก้ไขที่ไฟล์ไหนบ้าง (คือฝั่งที่สร้างลิงก์ใส่ query param)**: [[pages-Home]] (ลิงก์ไปหน้าต่างๆ), [[pages-CrfDetail]] (ลิงก์ `?edit=`, `?rid=` ไปยัง VIA), [[pages-CrfList]] (ลิงก์ `crf-detail.html?pid=`), [[pages-Capture]] (ลิงก์ `via/index.html?rid=`), [[pages-Roi]] (ลิงก์ `via/index.html?rid=`), [[lib-auth]] (`AuthGuard` สร้าง `?next=` ตอน redirect ไป login), [[_via_dfu]] (`dfu_add_toolbar()` ลิงก์กลับ `crf-detail.html?pid=`)

**ถูกอ่านไปใช้ที่ไฟล์ไหนบ้าง**: [[pages-Capture]] (`new URLSearchParams(location.search).get('rid')`), [[pages-CrfDetail]] (`?pid=`), [[pages-CrfForm]] (`?edit=`), [[pages-Login]] (`?next=`), [[_via_dfu]] (`DFU_RID` — global const อ่านตั้งแต่บรรทัดแรกของไฟล์)
