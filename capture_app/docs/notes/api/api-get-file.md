---
name: api-get-file
description: "GET /api/file/{path} — serves any file under data/ by relative path, with a path-traversal guard"
metadata:
  type: reference
---

# GET /api/file/{path:path}

**Method**: GET — ต้อง auth

**เรียกใช้จากไฟล์ไหนบ้าง**: ทุกหน้าที่แสดงรูปภาพ — [[pages-CrfDetail]] (ImageThumb/RoiImageThumb), [[pages-Gallery]] (Thumb), [[pages-Capture]] (preview), [[_via_dfu]] (`dfu_add_case_images` โหลด `_full.png` เข้า VIA)

**ส่งข้อมูลอะไรไป (payload)**: path parameter คือ path สัมพัทธ์ใต้ `data/` เช่น `podo/P0001/preprocessing/P0001_podo_L_full.png`

**รับข้อมูลอะไรกลับมา (response)**: ไฟล์ตรงๆ (`FileResponse`) — `404` ถ้าไฟล์ไม่มีจริงหรือ path พยายามหลุดออกนอก `DATA_DIR` (กัน path traversal ด้วยการเช็ค `.resolve()` ต้องอยู่ใต้ `DATA_DIR`)

**ไฟล์ backend ที่ handle**: [[server]] (`get_file()`)
