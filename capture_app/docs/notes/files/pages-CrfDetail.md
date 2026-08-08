---
name: pages-CrfDetail
description: Single-case detail page (crf-detail.html?pid=) — full form readout per side, image gallery with saved ROI boxes overlaid as SVG
metadata:
  type: reference
---

# frontend/src/pages/CrfDetail.tsx

**หน้าที่**: หน้ารายละเอียดเคสเดียว แสดงผลตรวจครบทุกส่วน (LOPS/PAD/deformity/ประวัติ/สรุป) แยกซ้าย-ขวา, ส่วน "รูปภาพ" (Podoscope/Thermal ต้นฉบับ + ภาพต่อข้าง 3 แบบ: Original สี/Full สำหรับ ROI/Train 224×224) วาดกรอบ ROI ที่เคยมาร์กไว้ทับบนภาพ "Full (ROI)" ด้วย SVG overlay ตรงตามพิกัดจริง มี banner เตือนถ้าฟอร์มยังไม่มีผล IWGDF ทั้งสองข้าง (นโยบาย: ต้องมีอย่างน้อยข้างเดียวถึงจะใช้เทรนได้) และโชว์สถานะ ROI แยกราย ข้าง มีปุ่ม "ลบ ROI" (โชว์เมื่อมีข้างใดข้างหนึ่งมาร์กแล้ว) ยืนยันด้วยการพิมพ์รหัสวิจัยผ่าน [[components-DeleteConfirmDialog]] ก่อนลบจริง

**Functions/Variables (global scope)**:
- `SIDES`, `MF_SITES`, `ABIT`, `TBIT` — ค่าคงที่แสดงผล (ซ้ำกับ [[lib-crfScoring]] บางส่วน แต่ประกาศแยกในไฟล์นี้)
- `DRow`, `Yn`, `DGroup` — component ช่วยแสดงผลแถวข้อมูล
- `ImageThumb` — thumbnail รูปภาพ ซ่อนตัวเองถ้าโหลดไม่ได้ (404)
- `ViaShape`, `ViaRegion` (interfaces) — รูปร่าง region จาก VIA project JSON
- `RoiShape` — วาด SVG shape เดียวตาม `shape_attributes.name` (rect/circle/ellipse/polygon/polyline/point)
- `RoiImageThumb` — เหมือน `ImageThumb` แต่ overlay กรอบ ROI ทับด้วย (ใช้ `naturalWidth/naturalHeight` ทำ SVG viewBox ให้พิกัดตรง)
- `CrfDetail()` — component หลัก, state: `rec, notFound, manifestRow, roiRegions, roiDeleteOpen`; คำนวณ `bothLabelsMissing, statusL, statusR, anyRoiNeeded, anyRoiDone` จาก [[lib-roiStatus]]
- `onDeleteRoi()` — เรียก `DELETE /api/roi/{pid}` แล้วล้าง `roiRegions` ในหน่วยความจำทันที (สถานะ/overlay กลับเป็น pending โดยไม่ต้อง reload หน้า)

**Called by**: [[main-crf-detail]]

**Depends on**: [[lib-api]], [[lib-crfTypes]] (`CrfRecord, DerivedSide, ManifestRow`), [[lib-roiStatus]] (`roiSideStatus, ROI_STATUS_TEXT`), [[components-DeleteConfirmDialog]], shadcn `Badge`/`Button`/`Card` ([[components-ui-shadcn]]), [[api-delete-roi-rid]] (ผ่าน `onDeleteRoi()`)
