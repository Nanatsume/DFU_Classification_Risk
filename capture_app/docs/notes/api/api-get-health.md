---
name: api-get-health
description: "GET /api/health — unauthenticated liveness probe + next research id + counts"
metadata:
  type: reference
---

# GET /api/health

**Method**: GET — **ไม่ต้อง auth** (endpoint เดียวที่ไม่มี `require_session`, นอกจาก `/api/session`)

**เรียกใช้จากไฟล์ไหนบ้าง**: [[lib-api]] (`probeMode()`), [[components-Navbar]] (badge LIVE/DEMO), [[pages-Capture]] (เช็คโหมด LIVE/DEMO ตอนเปิดหน้า), [[pages-Login]] (ทางอ้อมผ่าน probe ของ Navbar หลัง login)

**ส่งข้อมูลอะไรไป (payload)**: ไม่มี (ไม่มี body/query)

**รับข้อมูลอะไรกลับมา (response)**: `{ ok: bool, source: string (ชื่อ class เช่น "SimulatedSource"), next_id: string (เช่น "P0015"), count: int (จำนวนเคสที่ commit แล้ว), crf_count: int (จำนวนฟอร์มที่บันทึกแล้ว) }`

**ไฟล์ backend ที่ handle**: [[server]] (`health()`)
