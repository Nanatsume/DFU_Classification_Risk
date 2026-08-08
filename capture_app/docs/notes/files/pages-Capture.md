---
name: pages-Capture
description: Photo-capture station (capture.html) — case picker, podoscope/thermal capture, auto preprocessing QC preview, commit flow
metadata:
  type: reference
---

# frontend/src/pages/Capture.tsx

**หน้าที่**: หน้าถ่ายภาพ รองรับทั้ง LIVE mode (ต่อ backend จริง) และ DEMO mode (จำลองภาพด้วย `<canvas>`, เก็บลง `localStorage` เมื่อเซิร์ฟเวอร์ต่อไม่ได้) เลือกเคสที่กรอกฟอร์มแล้วแต่ยังไม่ครบภาพ → ถ่าย podoscope + thermal → รัน preprocessing อัตโนมัติหลังถ่าย podoscope (โชว์ QC preview ซ้าย/ขวา) → ยืนยันและบันทึก (`POST /api/commit`) หลังบันทึกสำเร็จมี dialog ถามว่าจะกลับหน้าหลักหรือทำ ROI ต่อเลย — ปุ่ม "ทำ ROI ต่อ" จะโชว์ก็ต่อเมื่อเคสนั้นมีข้างใดข้างหนึ่งต้องมาร์กจริง (เช็คจาก IWGDF label ของเคสตอน commit) ถ้าทั้งสองข้าง Negative จะเหลือแค่ปุ่ม "กลับหน้าหลัก" ช่อง "ผู้ถ่ายภาพ" เป็น dropdown เลือกจากรายชื่อ (`GET /api/operators`) ไม่ใช่พิมพ์เอง

**Functions/Variables (global scope)**:
- `RECORDS_KEY` — key ของ `localStorage` (`'capture_records'`)
- `DEMO_CASES` — ข้อมูลจำลองตอน DEMO mode
- `pad()`, `nowISO()`, `timeTH()` — helper เวลา
- `drawSim(modality, rid)` — วาดภาพจำลองด้วย canvas (DEMO mode)
- `loadRecords()`, `saveRecords()` — อ่าน/เขียน `localStorage`
- `DisplayRow` (interface), `toDisplay(x)` — รวม `CommitRecord`/`ManifestRow` เป็นรูปแบบแถวเดียวกันสำหรับตาราง
- `Capture()` — component หลัก, state จำนวนมาก: `mode, cases, session, shots, previews, operator, operators, qc, saved, modalRec, justCommittedRid, justCommittedNeedsRoi`
- `iwgdfText()`, `findCase()`, `pendingCases()`, `refreshSaved()`, `refreshCasesAndPicker()`, `startSession()`, `capture(m)`, `retake(m)`, `runPreprocess(rid)`, `commit()` (คำนวณ `needsRoi` จาก `categoryToLabel` ของทั้งสองข้างก่อน `setSession(null)`), `showModalFor(row)`

**Called by**: [[main-capture]]

**Depends on**: [[lib-api]] (`api`, `ApiError`), [[lib-captureTypes]] (`CaseRow, CommitRecord, ManifestRow, Modality`), [[lib-roiStatus]] (`categoryToLabel`), shadcn `Button`/`Badge`/`Card`/`Select`/`Dialog` ([[components-ui-shadcn]]), [[api-get-operators]] — ลิงก์ไปเปิด `via/index.html?rid=` ([[_via_dfu]]) ในแท็บใหม่หลัง commit
