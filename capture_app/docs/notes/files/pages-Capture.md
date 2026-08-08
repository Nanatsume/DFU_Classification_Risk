---
name: pages-Capture
description: Photo-capture station (capture.html) — case picker, podoscope/thermal capture, auto preprocessing QC preview, commit flow
metadata:
  type: reference
---

# frontend/src/pages/Capture.tsx

**หน้าที่**: หน้าถ่ายภาพ รองรับทั้ง LIVE mode (ต่อ backend จริง) และ DEMO mode (จำลองภาพด้วย `<canvas>`, เก็บลง `localStorage` เมื่อเซิร์ฟเวอร์ต่อไม่ได้) เลือกเคสที่กรอกฟอร์มแล้วแต่ยังไม่ครบภาพ → ถ่าย podoscope + thermal → รัน preprocessing อัตโนมัติหลังถ่าย podoscope (โชว์ QC preview ซ้าย/ขวา) → ยืนยันและบันทึก (`POST /api/commit`) หลังบันทึกสำเร็จมี dialog ถามว่าจะกลับหน้าหลักหรือทำ ROI ต่อเลย

**Functions/Variables (global scope)**:
- `RECORDS_KEY` — key ของ `localStorage` (`'capture_records'`)
- `DEMO_CASES` — ข้อมูลจำลองตอน DEMO mode
- `pad()`, `nowISO()`, `timeTH()` — helper เวลา
- `drawSim(modality, rid)` — วาดภาพจำลองด้วย canvas (DEMO mode)
- `loadRecords()`, `saveRecords()` — อ่าน/เขียน `localStorage`
- `DisplayRow` (interface), `toDisplay(x)` — รวม `CommitRecord`/`ManifestRow` เป็นรูปแบบแถวเดียวกันสำหรับตาราง
- `Capture()` — component หลัก, state จำนวนมาก: `mode, cases, session, shots, previews, operator, qc, saved, modalRec, justCommittedRid`
- `iwgdfText()`, `findCase()`, `pendingCases()`, `refreshSaved()`, `refreshCasesAndPicker()`, `startSession()`, `capture(m)`, `retake(m)`, `runPreprocess(rid)`, `commit()`, `showModalFor(row)`

**Called by**: [[main-capture]]

**Depends on**: [[lib-api]] (`api`, `ApiError`), [[lib-captureTypes]] (`CaseRow, CommitRecord, ManifestRow, Modality`), shadcn `Button`/`Badge`/`Card`/`Input`/`Dialog` ([[components-ui-shadcn]]) — ลิงก์ไปเปิด `via/index.html?rid=` ([[_via_dfu]]) ในแท็บใหม่หลัง commit
