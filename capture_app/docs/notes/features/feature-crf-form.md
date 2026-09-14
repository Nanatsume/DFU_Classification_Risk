---
name: feature-crf-form
description: "Feature: CRF-07 case record form — sections ก-จ, live IWGDF category scoring, create + edit"
metadata:
  type: reference
---

# Feature: กรอกแบบฟอร์ม CRF-07

**คืออะไร (มุมผู้ใช้)**: พยาบาลกรอกผลตรวจเท้าผู้ป่วยเบาหวานทีละเคสตามแบบฟอร์มกระดาษเดิม (ก การตรวจ LOPS ด้วยโมโนฟิลาเมนต์ → ข การตรวจ PAD ด้วย ABI/TBI → ค deformity → ง ประวัติแผล/ตัดรยางค์/CKD → จ หมายเหตุ+ผู้บันทึก) ระบบคำนวณประเภทความเสี่ยง IWGDF (0-3) และ Binary label (Positive/Negative) ให้อัตโนมัติแบบ real-time ระหว่างกรอก แต่ละเคสได้รหัสวิจัยอัตโนมัติ (`P0001`, `P0002`, ...) **ตอนกดบันทึก** — ระหว่างกรอกช่องรหัสจะขึ้นว่า "ออกให้เมื่อบันทึก" เพราะถ้าจองรหัสตั้งแต่เปิดหน้า การเปิดแล้วปิดทิ้งจะเผารหัสไปหนึ่งตัวทุกครั้ง รองรับทั้งสร้างใหม่และแก้ไขเคสเดิม รายชื่อ dropdown ผู้ตรวจเป็นรายชื่อคงที่ 4 คน ไม่มีปุ่มเพิ่มชื่อในหน้านี้ (จงใจ — แก้รายชื่อที่ backend แทน)

**เกี่ยวข้องกับไฟล์ไหนบ้าง**: [[pages-CrfForm]], [[html-crf-form]], [[main-crf-form]], [[lib-crfScoring]] (ตรรกะคำนวณหลัก), [[lib-crfTypes]], [[crf_store]] (backend)

**เกี่ยวข้องกับ API endpoint ไหนบ้าง**: [[api-get-crf-pid]] (โหมดแก้ไข), [[api-post-crf]] (บันทึก + mint รหัสวิจัย), [[api-get-nurses]] (dropdown ผู้ตรวจ)

**เกี่ยวข้องกับ state ตัวไหนบ้าง**: [[db-crf_forms-table]], [[db-cases-table]] (ตัวนับรหัสวิจัย), [[db-nurses-table]], [[url-query-params]] (`?edit=`)
