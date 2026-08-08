---
name: feature-gallery
description: "Feature: cross-case image browser — 4 thumbnails per case, a quick QC sweep before training"
metadata:
  type: reference
---

# Feature: คลังภาพ (Gallery)

**คืออะไร (มุมผู้ใช้)**: ไล่ดูรูปทุกเคสที่บันทึกแล้วในหน้าเดียว (Podoscope, Thermal, เท้าซ้าย-full, เท้าขวา-full ต่อเคส) ใช้สแกนหาภาพคุณภาพแย่ก่อนเอาไปเทรนโมเดล — level-2 follow-up ของส่วน "รูปภาพ" ใน [[feature-crf-detail]] ซึ่งดูได้ทีละเคสเท่านั้น คลิกรูปเพื่อดูเต็มขนาด หรือคลิกรหัสวิจัยเพื่อไปหน้ารายละเอียดเต็ม

**เกี่ยวข้องกับไฟล์ไหนบ้าง**: [[pages-Gallery]], [[html-gallery]], [[main-gallery]]

**เกี่ยวข้องกับ API endpoint ไหนบ้าง**: [[api-get-manifest]] (แหล่งข้อมูลเดียว)

**เกี่ยวข้องกับ state ตัวไหนบ้าง**: [[db-commits-table]], [[db-captures-preprocessing-tables]]
