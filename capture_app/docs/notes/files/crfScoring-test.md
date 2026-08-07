---
name: crfScoring-test
description: Vitest unit tests for evalSide()/overallMissing() — LOPS/PAD/deformity/history branch coverage, IWGDF category correctness
metadata:
  type: reference
---

# frontend/src/lib/crfScoring.test.ts

**หน้าที่**: เทสต์ unit ของ [[lib-crfScoring]] (`evalSide`, `overallMissing`, `toDerived`) ด้วย Vitest — ตรวจทุกแขนงของตรรกะคำนวณ LOPS (จากผล monofilament 3 จุด), PAD (จาก ABI/TBI), deformity, history, และผลรวมเป็น IWGDF category สำคัญเพราะเป็นจุดที่พลาดแล้วจะจัดประเภทความเสี่ยงผู้ป่วยผิด

**Functions/Variables (global scope)**: `BASE` (Fields object ตั้งต้น: ครบทุกฟิลด์, LOPS-negative, PAD-negative, ไม่มี deformity/history → category คาดหวัง 0) — ตัวเทสต์เองจัดกลุ่มด้วย `describe`/`it` ของ Vitest ไม่ export อะไรออกไป

**Called by**: รันผ่าน `npx vitest run` (ไม่มีไฟล์อื่น import)

**Depends on**: [[lib-crfScoring]] (`evalSide, overallMissing, toDerived, Fields`)
