---
name: lib-crfScoring
description: IWGDF risk-scoring engine — evalSide()/toDerived()/overallMissing(), the core clinical logic ported field-for-field from the original vanilla-JS form
metadata:
  type: reference
---

# frontend/src/lib/crfScoring.ts

**หน้าที่**: หัวใจของการคำนวณ IWGDF risk category จากคำตอบในฟอร์ม CRF-07 — pure function ไม่แตะ DOM (แต่เดิมเป็นฟังก์ชันที่อ่าน DOM ตรงๆ ใน `crf-form.html` แบบ vanilla) เพื่อให้ state เดียวกันขับ UI ของ React ได้ ⚠️ ตามคอมเมนต์ในไฟล์ ห้ามแก้ลำดับเงื่อนไข/branch โดยไม่รัน regression case P0003 ซ้ำ (L: ครบทุกเกณฑ์ปกติ → category 0; R: LOPS ทุกจุด + PAD → category 2)

**Functions/Variables (global scope)**:
- `SIDES`, `Side` (type), `MF_SITES`, `DEFORM` — ค่าคงที่รายการฟิลด์ (จุดตรวจ monofilament, กลุ่ม deformity)
- `FieldValue`, `Fields` (types)
- `SideEval` (interface) — ผลประเมินข้างเดียว (`lops, pad, deform, deformList, ulcer, amp, ckd, history, autoCat, historyOnly, missing, needTbi`)
- `evalSide(fields, k)` — ฟังก์ชันคำนวณหลัก คืน `SideEval` รวมตรรกะ IWGDF category (0-3)
- `DerivedSide` (interface), `toDerived(r)` — แปลง `SideEval` → รูปแบบที่บันทึกลง DB (`data.derived.L/R`)
- `overallMissing(pid, fields, nurse, nurse2, evals)` — เช็คว่าฟอร์มยังขาดอะไรบ้างก่อนบันทึก

**Called by**: [[pages-CrfForm]] (ใช้คำนวณ real-time ตอนกรอกฟอร์ม), [[pages-CrfList]] (`patientLevelIwgdf` ใช้ `SIDES`, `MF_SITES` ประกอบ CSV), [[crfScoring-test]] (unit test)

**Depends on**: ไม่มี (pure logic, ไม่ import โมดูลอื่น)
