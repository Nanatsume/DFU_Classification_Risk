---
name: feature-capture
description: "Feature: photo-capture station — podoscope + thermal, auto preprocessing, LIVE/DEMO mode, commit flow"
metadata:
  type: reference
---

# Feature: ถ่ายภาพเก็บข้อมูล (Capture)

**คืออะไร (มุมผู้ใช้)**: สถานีถ่ายภาพ — เลือกเคสที่กรอกฟอร์มแล้วแต่ยังไม่ครบภาพ → ถ่าย podoscope (ระบบรัน preprocessing อัตโนมัติทันที แยกซ้าย-ขวา + แสดง QC preview ให้ตรวจว่าแยกถูก) → ถ่าย thermal → "ยืนยันและบันทึก" เพื่อ commit เคส รองรับ DEMO mode (จำลองภาพด้วย canvas) เมื่อต่อเซิร์ฟเวอร์ไม่ได้ หลังบันทึกสำเร็จมี dialog ถามว่าจะกลับหน้าหลักหรือทำ ROI ต่อเลย นโยบาย: ต้องมีฟอร์ม CRF ก่อนถึงจะถ่ายภาพได้ (409 ถ้าไม่มี)

**เกี่ยวข้องกับไฟล์ไหนบ้าง**: [[pages-Capture]], [[html-capture]], [[main-capture]], [[lib-captureTypes]], [[capture_source]] (backend, กล้องจำลอง/จริง), [[preprocessing]] (backend, pipeline)

**เกี่ยวข้องกับ API endpoint ไหนบ้าง**: [[api-get-cases]] (picker), [[api-post-capture]], [[api-post-preprocess]], [[api-post-commit]], [[api-get-manifest]] (ตารางเคสที่บันทึกแล้ว)

**เกี่ยวข้องกับ state ตัวไหนบ้าง**: [[db-captures-preprocessing-tables]], [[db-commits-table]], [[localstorage-capture_records]] (DEMO mode), [[url-query-params]] (`?rid=`)
