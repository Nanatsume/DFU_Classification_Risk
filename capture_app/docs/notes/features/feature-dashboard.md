---
name: feature-dashboard
description: "Feature: home dashboard — 5 cards linking to every feature, entry point after login"
metadata:
  type: reference
---

# Feature: หน้าแรก (Dashboard)

**คืออะไร (มุมผู้ใช้)**: หน้าแรกหลัง login — การ์ด 01-05 ลิงก์ไปยังฟีเจอร์หลักทั้งหมด (กรอกฟอร์มใหม่ → ถ่ายภาพ → ทำ ROI → ประวัติการบันทึก → คลังภาพ) เป็นจุดกลับหลักที่หลายหน้าลิงก์กลับมา (เช่นปุ่ม "กลับไปหน้าหลัก" หลัง commit เคส หรือหลังบันทึก ROI)

**เกี่ยวข้องกับไฟล์ไหนบ้าง**: [[pages-Home]], [[html-index]], [[main-home]], [[components-Navbar]] (ลิงก์ "หน้าแรก")

**เกี่ยวข้องกับ API endpoint ไหนบ้าง**: [[api-get-crf-list]] (นับจำนวนเคสโชว์ในปุ่ม)

**เกี่ยวข้องกับ state ตัวไหนบ้าง**: [[db-crf_forms-table]] (ทางอ้อม, ผ่านการนับจำนวน)
