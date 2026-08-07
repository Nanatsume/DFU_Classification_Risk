---
name: _via_dfu
description: Non-invasive VIA 2 connector script — auto-loads case images by ROI-marking policy, adds a save toolbar, posts results to /api/roi
metadata:
  type: reference
---

# via_static/_via_dfu.js

**หน้าที่**: สคริปต์เชื่อม VIA 2 (เครื่องมือ annotation ของ Oxford VGG, vendored ไว้ที่ [[via-vendored]]) เข้ากับ `capture_app` โดยไม่แก้ไฟล์ต้นฉบับของ VIA เลย (ฉีด CSS + ผูก event ผ่าน global function ที่ VIA เรียกเองตอน init เสร็จ คือ `_via_load_submodules()`) หน้าที่หลัก: โหลดภาพของเคสตามรหัสวิจัยใน URL (`?rid=`), ใช้นโยบาย "ข้างไหนต้องมาร์ก ROI" แบบเดียวกับ [[lib-roiStatus]] (เขียนแยกด้วยมือเพราะเป็นไฟล์ JS ล้วน import TS ไม่ได้), ซ่อนปุ่ม/เมนูของ VIA ที่ไม่จำเป็น, เพิ่ม toolbar ของตัวเอง (บันทึก ROI + กลับไปหน้าเคส), ซูมอัตโนมัติ 3x, และ POST ผลไปที่ `/api/roi/{rid}`

**Functions/Variables (global scope)**:
- `DFU_RID` — รหัสวิจัยจาก query param `?rid=`
- `DFU_ATTRIBUTES` — schema ของ attribute ที่จะมาร์ก (roi_type, note, foot_side, has_risk_area)
- `dfu_wait_for_image_then(fn, attemptsLeft)` — poll รอ VIA โหลดภาพเสร็จจริงก่อนเรียก `fn` (แก้บั๊ก `set_zoom()` เรียกเร็วเกินไป)
- `dfu_needed_sides()` — async, ดึง `/api/crf/{rid}` แล้วคืนรายการข้างที่ label ≠ `'Negative'` (นโยบาย ROI)
- `dfu_existing_sides_in_project()` — สแกน `_via_img_metadata` หาข้างที่มีภาพอยู่ใน project แล้ว
- `_via_load_submodules()` — **entry point ที่ VIA เรียกเองอัตโนมัติ** หลัง init เสร็จ, รวม flow ทั้งหมด
- `dfu_add_case_images(sides)` — โหลดภาพ `_full.png` ของข้างที่ระบุเข้า VIA project
- `dfu_simplify_ui()` — ฉีด CSS ซ่อนปุ่ม/เมนูของ VIA ที่ไม่ใช้
- `dfu_add_toolbar()` — สร้างแถบเครื่องมือมุมขวาบน (รหัสเคส + ปุ่มบันทึก + ปุ่มกลับ)
- `dfu_project_json()` — ประกอบ VIA project JSON แบบเดียวกับที่ VIA ใช้ตอน "Save Project"
- `dfu_summary()` — สรุปย่อ region count ต่อข้าง ส่งเก็บคู่กับ project เต็ม
- `dfu_show_save_complete_dialog()` — dialog "ทำต่อ / กลับไปหน้าหลัก" หลังบันทึกสำเร็จ
- `dfu_save_roi()` — POST ไปยัง `/api/roi/{rid}`

**Called by**: [[via-vendored]] (`index.html` ของ VIA เรียก `<script src="_via_dfu.js">` ต่อจาก `via.js`, และ `via.js` เรียก `_via_load_submodules()` เองหลัง init), เปิดจาก [[pages-Roi]]/[[pages-CrfDetail]]/[[pages-Capture]] ผ่านลิงก์ `via/index.html?rid=`

**Depends on**: `/api/crf/{rid}` ([[api-get-crf-pid]]), `/api/roi/{rid}` ([[api-get-roi-rid]], [[api-post-roi-rid]]) — และ global function/variable ของ VIA เอง (`_via_img_metadata`, `_via_settings`, `_via_show_img`, `project_open_parse_json_file`, `set_zoom`, ฯลฯ ดู [[via-global-state]])
