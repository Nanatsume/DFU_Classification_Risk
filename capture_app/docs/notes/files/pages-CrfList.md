---
name: pages-CrfList
description: History table (crf-list.html) — every saved case, CSV exports (raw form + training data), ROI status per side, delete flow
metadata:
  type: reference
---

# frontend/src/pages/CrfList.tsx

**หน้าที่**: ตาราง "ประวัติการบันทึก" รวมทุกเคส แสดงผล IWGDF ทั้งสองข้าง, สถานะถ่ายภาพ, สถานะ ROI แยกราย ข้าง, และปุ่มดูรายละเอียด/ลบ มีปุ่ม export 2 แบบ: CSV ทั้งหมด (ทุกฟิลด์ตามลำดับแบบฟอร์มกระดาษ + ผล IWGDF ระดับข้าง/ผู้ป่วย) กับ CSV สำหรับเทรนโมเดล (long format แถวละข้าง) การลบใช้ [[components-DeleteConfirmDialog]] และถูก backend บล็อกด้วย 409 ถ้าเคสมีภาพถ่ายผูกอยู่แล้ว

**Functions/Variables (global scope)**:
- `today()`, `download(text, name, mime)` — helper ทั่วไป
- `patientLevelIwgdf(rec)` — IWGDF ระดับผู้ป่วย = ค่าสูงสุด (แย่ที่สุด) ของสองข้าง
- `RAW_FORM_COLUMNS` — ลำดับคอลัมน์ CSV ตามแบบฟอร์มกระดาษ (ก→ข→ค→ง→จ)
- `flattenRawForm(rec)`, `flattenTrainingRows(rec)` — แปลง record เป็นแถว CSV แต่ละแบบ
- `StatusPill` — ป้ายสถานะคลิกได้ (ใช้กับคอลัมน์ "ภาพ")
- `CellCat` — ป้ายแสดงผล Positive/Negative + category ต่อข้าง
- `CrfList()` — component หลัก, state: `records, captured, roiCounts, toast, deleteTarget`
- `loadAll()`, `rowsToCsv()`, `exportRawFormCsv()`, `exportTrainingCsv()`, `doDelete(pid)`, `onRoi(pid)`

**Called by**: [[main-crf-list]]

**Depends on**: [[lib-api]] (`api`, `ApiError`), [[lib-crfTypes]] (`CrfRecord, DerivedSide, ManifestRow, RoiSummaryRow`), [[lib-crfScoring]] (`MF_SITES, SIDES`), [[lib-roiStatus]] (`roiSideStatus, ROI_STATUS_TEXT`), [[components-DeleteConfirmDialog]], shadcn `Button`/`Badge`/`Table` ([[components-ui-shadcn]])
