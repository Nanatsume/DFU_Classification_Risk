---
name: pages-CrfForm
description: The CRF-07 case record form — sections ก(LOPS)/ข(PAD)/ค(deformity)/ง(history)/จ(notes), live IWGDF scoring via crfScoring.ts
metadata:
  type: reference
---

# frontend/src/pages/CrfForm.tsx

**หน้าที่**: หน้ากรอกแบบฟอร์ม CRF-07 เต็มรูปแบบ แบ่งเป็น 5 ส่วนตามแบบฟอร์มกระดาษ (ก การตรวจ LOPS, ข การตรวจ PAD, ค deformity, ง ประวัติแผล/ตัดรยางค์/CKD, จ หมายเหตุ+ผู้บันทึก) มี sticky summary dock ด้านล่างโชว์ IWGDF category ของทั้งสองข้างแบบ real-time ระหว่างกรอก รองรับทั้งโหมดสร้างเคสใหม่ (ขอรหัสวิจัยจาก `POST /api/session/new`) และแก้ไขเคสเดิม (query param `?edit=`) รายชื่อ dropdown ผู้ตรวจ (`nurses`) เป็นรายชื่อคงที่ที่ seed ไว้ในฐานข้อมูลตรงๆ — จงใจ**ไม่มี**ปุ่ม "เพิ่มชื่อ" ในหน้านี้ (เคยมีแล้วเอาออก) เพราะรายชื่อพยาบาลเปลี่ยนไม่บ่อยและควรแก้ที่ backend ตรงๆ แทนที่จะเปิดให้แก้ผ่านฟอร์มได้ง่ายจนพลาดพิมพ์ผิด/เพิ่มซ้ำ

**Functions/Variables (global scope)**:
- `Seg` — component ปุ่มเลือกแบบ segmented control (ใช้กับ ใช่/ไม่ใช่, รู้สึก/ไม่รู้สึก)
- `Verdict` — component ป้ายผลสรุป (สี ok/bad/warn)
- `Panel` — กรอบข้อมูลต่อข้าง (ซ้าย/ขวา, สีต่างกัน)
- `ABI_OPTS`, `TBI_OPTS` — ตัวเลือกช่วงค่า ABI/TBI
- `CrfForm()` — component หลัก, state: `pid, pidNote, nurses, fields, nurse, nurse2, note, saving`; ใช้ `evalSide()` จาก [[lib-crfScoring]] ผ่าน `useMemo`
- `onSave()`, `onClear()`

**Called by**: [[main-crf-form]]

**Depends on**: [[lib-api]], [[lib-crfScoring]] (`DEFORM, MF_SITES, SIDES, evalSide, overallMissing, toDerived`), [[lib-crfTypes]] (`CrfRecord`), shadcn `Button`/`Card`/`Textarea`/`Select` ([[components-ui-shadcn]])
