---
name: feature-crf-form
description: "Feature: CRF-07 case record form — sections ก-จ, live IWGDF category scoring, create + edit"
metadata:
  type: reference
---

# Feature: กรอกแบบฟอร์ม CRF-07

**คืออะไร (มุมผู้ใช้)**: พยาบาลกรอกผลตรวจเท้าผู้ป่วยเบาหวานทีละเคสตามแบบฟอร์มกระดาษเดิม (ก การตรวจ LOPS ด้วยโมโนฟิลาเมนต์ → ข การตรวจ PAD ด้วย ABI/TBI → ค deformity → ง ประวัติแผล/ตัดรยางค์/CKD → จ หมายเหตุ+ผู้บันทึก) ระบบคำนวณประเภทความเสี่ยง IWGDF (0-3) และ Binary label (Positive/Negative) ให้อัตโนมัติแบบ real-time ระหว่างกรอก แต่ละเคสได้รหัสวิจัยอัตโนมัติ (`P0001`, `P0002`, ...) รองรับทั้งสร้างใหม่และแก้ไขเคสเดิม ถ้าชื่อพยาบาลผู้ตรวจยังไม่มีในรายชื่อ กด "+ เพิ่มชื่อพยาบาลใหม่" เพิ่มเข้า dropdown ได้ทันทีโดยไม่ต้องออกจากฟอร์ม

**เกี่ยวข้องกับไฟล์ไหนบ้าง**: [[pages-CrfForm]], [[html-crf-form]], [[main-crf-form]], [[lib-crfScoring]] (ตรรกะคำนวณหลัก), [[lib-crfTypes]], [[crf_store]] (backend)

**เกี่ยวข้องกับ API endpoint ไหนบ้าง**: [[api-post-session-new]] (ขอรหัสวิจัยใหม่), [[api-get-crf-pid]] (โหมดแก้ไข), [[api-post-crf]] (บันทึก), [[api-get-nurses]] (dropdown ผู้ตรวจ), [[api-post-nurses]] (เพิ่มชื่อพยาบาลใหม่)

**เกี่ยวข้องกับ state ตัวไหนบ้าง**: [[db-crf_forms-table]], [[db-cases-table]] (จองรหัสวิจัย), [[db-nurses-table]], [[url-query-params]] (`?edit=`)
