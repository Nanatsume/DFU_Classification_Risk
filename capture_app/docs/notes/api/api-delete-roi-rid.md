---
name: api-delete-roi-rid
description: "DELETE /api/roi/{rid} — deletes a case's saved ROI project"
metadata:
  type: reference
---

# DELETE /api/roi/{rid}

**Method**: DELETE — ต้อง auth

**เรียกใช้จากไฟล์ไหนบ้าง**: [[pages-CrfDetail]] (ปุ่ม "ลบ ROI" ในแถบปุ่มบนสุด โชว์เมื่อมีข้างใดข้างหนึ่งมาร์กแล้ว ยืนยันด้วย [[components-DeleteConfirmDialog]] แบบพิมพ์รหัสวิจัย), [[pages-Roi]] (ปุ่ม "ลบ ROI" ต่อแถวในตาราง picker เมื่อ `anyDone`, ยืนยันแบบเดียวกัน)

**ส่งข้อมูลอะไรไป (payload)**: `rid` ใน URL path

**รับข้อมูลอะไรกลับมา (response)**: `{ deleted: rid }` — `404` ถ้าไม่มี ROI ของเคสนั้น

**ไฟล์ backend ที่ handle**: [[roi_store]] (`delete_roi()`) → [[db]] (`delete_roi()`, `log_audit()`)
