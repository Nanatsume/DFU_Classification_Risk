---
name: api-hn
description: "GET/DELETE /api/hn — how many hospital numbers remain, and the one-shot de-identification"
metadata:
  type: reference
---

# GET /api/hn · DELETE /api/hn

**Method**: GET / DELETE — ต้อง auth ทั้งคู่

**รับข้อมูลอะไรกลับมา (response)**: GET → `{ remaining: number }` · DELETE → `{ cleared: number }`

**DELETE ทำอะไร**: ล้าง `cases.hn` ทุกแถวในคราวเดียว ทำให้ชุดข้อมูลไม่เหลือตัวระบุตัวบุคคลโดยตรง ใช้ตอน**ปิดการเก็บข้อมูล**

**ย้อนกลับไม่ได้ และนั่นคือเจตนา** — หลังกดแล้วจะไม่สามารถเอาค่าที่คัดลอกมาไปตรวจสอบกับต้นฉบับของโรงพยาบาลได้อีก ซึ่งเป็นเหตุผลที่ HN ถูก*เก็บไว้*ระหว่างเก็บข้อมูล แทนที่จะลบทิ้งทันทีที่จับคู่เสร็จ (การคัดลอกด้วยมือมีโอกาสผิด)

**ดูเพิ่ม**: [[db-cases-table]] — HN ถูกกันไม่ให้ออกไปที่ CSV, `meta/*.json`, `fields_json` และ cloud backup (`tools/backup.py` ล้างทิ้งก่อนอัปโหลด)

**ไฟล์ backend ที่ handle**: [[server]] (`hn_status()`, `clear_hn()`) → [[db]] (`count_cases_with_hn()`, `clear_all_hn()`)
