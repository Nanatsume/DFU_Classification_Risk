---
name: pages-Roi
description: ROI case picker (roi.html) — lists every captured case with per-side ROI status; fully-Negative cases stay visible, tagged "ไม่ต้องทำ"
metadata:
  type: reference
---

# frontend/src/pages/Roi.tsx

**หน้าที่**: หน้าเลือกเคสสำหรับไปทำ ROI ใน VIA 2 — คล้าย picker ของหน้าถ่ายภาพ แต่โฟกัสที่เคสที่ถ่ายภาพครบแล้ว (`has_podo && has_thermal`) แสดงสถานะ ROI แยกราย ข้าง (ไม่ต้องทำ/ยังไม่ทำ/ทำแล้ว) ตามนโยบายใน [[lib-roiStatus]] — เคสที่ทั้งสองข้าง Negative **ไม่ถูกซ่อน** จากรายการ แค่โชว์ badge "ไม่ต้องทำ" แทนปุ่มลิงก์ (ตามนโยบายที่ผู้ใช้ตัดสินใจไว้ชัดเจน) แต่ละแถวที่มีข้างใดข้างหนึ่งมาร์กแล้วมีปุ่ม "ลบ ROI" เพิ่มขึ้นด้วย ยืนยันด้วยการพิมพ์รหัสวิจัยผ่าน [[components-DeleteConfirmDialog]]

**Functions/Variables (global scope)**:
- `CaseRow`, `RoiSummaryRow` (interfaces, ประกาศเฉพาะไฟล์นี้)
- `Roi()` — component เดียวในไฟล์, state: `loading, error, cases, roiCounts, deleteTarget`
- `onDeleteRoi(rid)` — เรียก `DELETE /api/roi/{rid}` แล้วรีเซ็ต region count ของแถวนั้นในหน่วยความจำเป็น 0 ทันที

**Called by**: [[main-roi]]

**Depends on**: [[lib-api]], [[lib-roiStatus]] (`categoryToLabel, roiSideStatus, ROI_STATUS_TEXT`), [[components-DeleteConfirmDialog]], shadcn `Card`/`Button`/`Badge` ([[components-ui-shadcn]]), [[api-delete-roi-rid]] (ผ่าน `onDeleteRoi()`) — ลิงก์ไปเปิด `via/index.html?rid=` ([[_via_dfu]]) ในแท็บใหม่
