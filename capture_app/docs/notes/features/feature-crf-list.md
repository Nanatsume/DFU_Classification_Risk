---
name: feature-crf-list
description: "Feature: history table of every saved case — status pills, per-side ROI status, CSV exports, typed-confirmation delete"
metadata:
  type: reference
---

# Feature: ประวัติการบันทึก (CRF List + CSV Export)

**คืออะไร (มุมผู้ใช้)**: ตารางรวมทุกเคสที่กรอกฟอร์มแล้ว — เห็น IWGDF ทั้งสองข้าง, สถานะถ่ายภาพ, สถานะ ROI แยกราย ข้าง ในหน้าเดียว มีปุ่ม export CSV 2 แบบ: "CSV ทั้งหมด" (ทุกฟิลด์ตามลำดับแบบฟอร์มกระดาษ + ผล IWGDF ระดับข้าง/ผู้ป่วย, ไว้ให้คนตรวจย้อนกลับกับแบบฟอร์มต้นฉบับ) และ "CSV สำหรับเทรนโมเดล" (long format แถวละข้าง, ตัด field ที่ไม่เกี่ยวกับการเทรนออก) ลบเคสได้เฉพาะที่ยังไม่มีภาพถ่ายผูกอยู่ ต้องพิมพ์รหัสวิจัยยืนยันก่อนลบจริง

**เกี่ยวข้องกับไฟล์ไหนบ้าง**: [[pages-CrfList]], [[html-crf-list]], [[main-crf-list]], [[components-DeleteConfirmDialog]], [[lib-crfScoring]] (คอลัมน์ CSV), [[lib-roiStatus]]

**เกี่ยวข้องกับ API endpoint ไหนบ้าง**: [[api-get-crf-list]], [[api-get-manifest]] (คอลัมน์ภาพ), [[api-get-roi-list]] (คอลัมน์ ROI), [[api-delete-crf-pid]]

**เกี่ยวข้องกับ state ตัวไหนบ้าง**: [[db-crf_forms-table]], [[db-captures-preprocessing-tables]], [[db-roi_annotations-table]]
