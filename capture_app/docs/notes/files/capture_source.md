---
name: capture_source
description: Camera abstraction layer — SimulatedSource for demo, UsbCameraSource stub for when real hardware arrives
metadata:
  type: reference
---

# capture_source.py

**หน้าที่**: จุดเดียวในระบบที่กล้องจริง (USB podoscope/thermal) จะเข้ามาต่อทีหลัง ตอนนี้มีแค่ `SimulatedSource` ที่คืนภาพตัวอย่างจริง (podoscope) และภาพ placeholder ที่วาดขึ้นเอง (thermal) ส่วน `UsbCameraSource` ยังเป็น stub รอ implement ตอนอุปกรณ์มาถึง ส่วนอื่นของระบบเขียนอิงกับ interface นี้เท่านั้น ไม่ต้องแก้อะไรตอนเปลี่ยนมาใช้กล้องจริง

**Functions/Variables (global scope)**:
- `TZ`, `_stamp()` — helper เวลา
- `CaptureSource` (abstract base class) — `grab(modality, rid) -> bytes`
- `SAMPLE_PODO` — path ไปยังภาพตัวอย่างโพโดสโคป
- `SimulatedSource(CaptureSource)` — คืนภาพจำลอง
- `UsbCameraSource(CaptureSource)` — ยังไม่ implement (`raise NotImplementedError`)
- `get_source()` — อ่าน env var `CAPTURE_SOURCE` (`sim`/`usb`) แล้วคืน instance ที่เหมาะสม

**Called by**: [[server]] (`SOURCE = get_source()`, เรียก `SOURCE.grab()` ใน `POST /api/capture`)

**Depends on**: PIL (เฉพาะใน `SimulatedSource.grab`, import แบบ lazy)
