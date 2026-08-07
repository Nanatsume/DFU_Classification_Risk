---
name: via-global-state
description: VIA 2's in-memory global JS state (_via_img_metadata, _via_settings, etc.) that _via_dfu.js reads and mutates
metadata:
  type: reference
---

# State: VIA 2 global JS variables (`_via_img_metadata`, `_via_settings`, `_via_attributes`, `_via_image_id_list`, `_via_current_image`, `_via_current_image_loaded`)

**คืออะไร**: ตัวแปร global ที่ประกาศอยู่ใน [[via-vendored]] (`via.js`) เก็บ state ของ annotation session ปัจจุบันทั้งหมดในหน่วยความจำของ browser tab — ไม่ persist เอง (persist ได้ก็ต่อเมื่อกดปุ่ม "บันทึก ROI" ซึ่งจะ serialize ตัวแปรเหล่านี้ส่งไป [[api-post-roi-rid]]) เนื่องจากเป็นไฟล์ third-party จึงไม่มี export/import แบบโมดูล เข้าถึงเป็น global ธรรมดา

**ถูกสร้าง/แก้ไขที่ไฟล์ไหนบ้าง**: [[via-vendored]] (`via.js` เป็นเจ้าของหลัก, สร้าง/แก้ผ่านฟังก์ชันของมันเอง เช่น `_via_show_img()`, `project_open_parse_json_file()`, `project_file_add_url()`), [[_via_dfu]] (`dfu_add_case_images()` เขียน `_via_img_metadata[img_id].file_attributes['foot_side']`)

**ถูกอ่านไปใช้ที่ไฟล์ไหนบ้าง**: [[_via_dfu]] (`dfu_existing_sides_in_project()`, `dfu_project_json()`, `dfu_summary()`, `dfu_wait_for_image_then()` เช็ค `_via_current_image_loaded`) — ข้อมูลสุดท้ายถูกส่งออกนอก browser ผ่าน `dfu_save_roi()` ไปยัง [[api-post-roi-rid]]
