---
name: feature-crf-detail
description: "Feature: single-case detail view — full readout per side, image gallery with saved ROI boxes overlaid"
metadata:
  type: reference
---

# Feature: รายละเอียดเคส (CRF Detail)

**คืออะไร (มุมผู้ใช้)**: ดูข้อมูลเคสเดียวแบบเต็ม — ผลตรวจทุกส่วนแยกซ้าย-ขวา, รูปภาพทั้งหมดของเคส (ต้นฉบับ Podoscope/Thermal + ภาพต่อข้าง 3 แบบ: สี/สำหรับมาร์ก ROI/สำหรับเทรน) กรอบ ROI ที่เคยมาร์กไว้จะวาดทับบนภาพ "Full (ROI)" ให้เห็นทันทีโดยไม่ต้องเปิด VIA มี banner เตือนถ้าฟอร์มยังไม่มีผล IWGDF ทั้งสองข้าง (ใช้เทรนไม่ได้) และปุ่มลัดไปทำ ROI/ถ่ายภาพ/แก้ไขฟอร์ม

**เกี่ยวข้องกับไฟล์ไหนบ้าง**: [[pages-CrfDetail]], [[html-crf-detail]], [[main-crf-detail]], [[lib-roiStatus]]

**เกี่ยวข้องกับ API endpoint ไหนบ้าง**: [[api-get-crf-pid]], [[api-get-manifest]], [[api-get-roi-rid]] (ดึง region มาวาด SVG overlay)

**เกี่ยวข้องกับ state ตัวไหนบ้าง**: [[db-crf_forms-table]], [[db-roi_annotations-table]], [[url-query-params]] (`?pid=`)
