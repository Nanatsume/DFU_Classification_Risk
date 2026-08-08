---
name: feature-roi
description: "Feature: ROI marking via VIA 2 — only Positive/undetermined sides load, per-side status shown everywhere, fully-Negative cases still visible"
metadata:
  type: reference
---

# Feature: ทำ ROI ในภาพ (ROI Annotation)

**คืออะไร (มุมผู้ใช้)**: มาร์กบริเวณแรงกดที่เสี่ยงบนภาพเท้าด้วย VIA 2 (เครื่องมือ annotation ภายนอก ปรับแต่ง UI ให้เรียบง่ายลง เหลือแค่สลับภาพ/ซูม/แก้ attribute/ลบ region ที่จำเป็นจริง) **นโยบายสำคัญ**: มาร์กเฉพาะข้างที่ผล IWGDF เป็น Positive หรือยังไม่มีผล (null, ฟอร์มกรอกไม่ครบ — ถือว่าต้องมาร์กไว้ก่อนเพื่อความปลอดภัย) ข้างที่ Negative ไม่ต้องมาร์กเพราะตามนิยาม IWGDF ไม่มี LOPS/PAD อยู่แล้ว ทุกหน้าที่เกี่ยวข้อง (picker, list, detail) แสดงสถานะ ROI **แยกราย ข้าง** ไม่ใช่รวมเป็นก้อนเดียว และเคสที่ทั้งสองข้าง Negative ยังคงโชว์ในรายการเสมอ (แค่ติดป้าย "ไม่ต้องทำ" แทนที่จะถูกซ่อน) ซูมเริ่มต้นอัตโนมัติที่ 3x หลังบันทึกมี dialog ถามว่าจะทำต่อหรือกลับหน้าหลัก มาร์กผิดหรืออยากเริ่มใหม่ทั้งชุดก็ลบทิ้งได้จากปุ่ม "ลบ ROI" ทั้งในหน้า picker และหน้ารายละเอียดเคส (ต้องพิมพ์รหัสวิจัยยืนยันก่อนลบจริง)

**เกี่ยวข้องกับไฟล์ไหนบ้าง**: [[pages-Roi]], [[html-roi]], [[main-roi]], [[pages-CrfDetail]] (แสดงกรอบที่มาร์กแล้ว + ปุ่มลบ), [[pages-CrfList]] (คอลัมน์สถานะ), [[lib-roiStatus]] (ตรรกะนโยบายฝั่ง TypeScript), [[_via_dfu]] (ตรรกะเดียวกันฝั่ง JS ของ VIA), [[via-vendored]] (ตัวเครื่องมือ), [[roi_store]] (backend), [[components-DeleteConfirmDialog]] (ยืนยันก่อนลบ)

**เกี่ยวข้องกับ API endpoint ไหนบ้าง**: [[api-get-crf-pid]] (เช็ค label เพื่อตัดสินว่าข้างไหนต้องมาร์ก), [[api-get-roi-list]], [[api-get-roi-rid]], [[api-post-roi-rid]], [[api-delete-roi-rid]]

**เกี่ยวข้องกับ state ตัวไหนบ้าง**: [[db-roi_annotations-table]], [[db-crf_forms-table]] (label ที่ใช้ตัดสินนโยบาย), [[via-global-state]], [[dfu-rid-constant]], [[url-query-params]] (`?rid=`)
