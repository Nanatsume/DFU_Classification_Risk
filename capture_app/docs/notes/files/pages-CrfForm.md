---
name: pages-CrfForm
description: The CRF-07 case record form — sections ก(LOPS)/ข(PAD)/ค(deformity)/ง(history)/จ(notes), live IWGDF scoring via crfScoring.ts
metadata:
  type: reference
---

# frontend/src/pages/CrfForm.tsx

**หน้าที่**: หน้ากรอกแบบฟอร์ม CRF-07 เต็มรูปแบบ แบ่งเป็น 5 ส่วนตามแบบฟอร์มกระดาษ (ก การตรวจ LOPS, ข การตรวจ PAD, ค deformity, ง ประวัติแผล/ตัดรยางค์/CKD, จ หมายเหตุ+ผู้บันทึก) มี sticky summary dock ด้านล่างโชว์ IWGDF category ของทั้งสองข้างแบบ real-time ระหว่างกรอก รองรับทั้งโหมดสร้างเคสใหม่ (ขอรหัสวิจัยจาก `POST /api/session/new`) และแก้ไขเคสเดิม (query param `?edit=`) ส่วนผู้ตรวจมีลิงก์ "+ เพิ่มชื่อพยาบาลใหม่" เปิด input ชื่อแล้วเพิ่มเข้ารายชื่อ dropdown ได้ทันทีโดยไม่ต้องออกจากฟอร์ม

**Functions/Variables (global scope)**:
- `Seg` — component ปุ่มเลือกแบบ segmented control (ใช้กับ ใช่/ไม่ใช่, รู้สึก/ไม่รู้สึก)
- `Verdict` — component ป้ายผลสรุป (สี ok/bad/warn)
- `Panel` — กรอบข้อมูลต่อข้าง (ซ้าย/ขวา, สีต่างกัน)
- `ABI_OPTS`, `TBI_OPTS` — ตัวเลือกช่วงค่า ABI/TBI
- `CrfForm()` — component หลัก, state: `pid, pidNote, nurses, fields, nurse, nurse2, note, saving, addingNurse, newNurseName, savingNurse`; ใช้ `evalSide()` จาก [[lib-crfScoring]] ผ่าน `useMemo`
- `onSave()`, `onClear()`, `onAddNurse()` — เพิ่มชื่อพยาบาลใหม่แล้ว refresh dropdown จาก response ตรงๆ

**Called by**: [[main-crf-form]]

**Depends on**: [[lib-api]], [[lib-crfScoring]] (`DEFORM, MF_SITES, SIDES, evalSide, overallMissing, toDerived`), [[lib-crfTypes]] (`CrfRecord`), shadcn `Button`/`Card`/`Input`/`Textarea`/`Select` ([[components-ui-shadcn]]), [[api-post-nurses]] (ผ่าน `onAddNurse()`)
