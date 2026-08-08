---
name: feature-login
description: "Feature: shared-password login/logout and the client-side session gate wrapping every protected page"
metadata:
  type: reference
---

# Feature: เข้าสู่ระบบ (Login / Session)

**คืออะไร (มุมผู้ใช้)**: หน้าจอแรกที่ทุกคนในทีมต้องผ่านก่อนใช้งาน — รหัสผ่านทีมเดียว ไม่มีบัญชีแยกต่อพยาบาล (การระบุตัวคนบันทึกอยู่ในฟอร์ม CRF เอง) หลัง login ค้างไว้ 12 ชั่วโมง ปุ่ม "ออกจากระบบ" อยู่ที่มุมขวาบนของทุกหน้า

**เกี่ยวข้องกับไฟล์ไหนบ้าง**: [[pages-Login]], [[html-login]], [[main-login]], [[lib-auth]] (`AuthGuard`, `logout()`), [[components-Navbar]] (ปุ่มออกจากระบบ), [[auth]] (backend ทั้งหมด)

**เกี่ยวข้องกับ API endpoint ไหนบ้าง**: [[api-post-login]], [[api-post-logout]], [[api-get-session]], [[api-get-health]] (unauth probe ที่ทุกหน้าเรียกคู่กัน)

**เกี่ยวข้องกับ state ตัวไหนบ้าง**: [[session-cookie]], [[db-settings-audit-tables]] (`password_hash`), [[url-query-params]] (`?next=`)
