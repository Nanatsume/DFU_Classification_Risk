---
name: test_api
description: End-to-end API tests via FastAPI TestClient — auth gates, CRF CRUD, capture/preprocess/commit flow, ROI CRUD
metadata:
  type: reference
---

# tests/test_api.py

**หน้าที่**: เทสต์ระดับ API เต็มรูปแบบผ่าน `TestClient` (fixture `auth_client`/`client` จาก [[conftest]]) ครอบคลุม endpoint แทบทุกตัวใน [[server]], [[crf_store]], [[roi_store]] — รวมถึง regression test `test_preprocess_full_and_original_images_share_dimensions` ที่เพิ่มขึ้นหลังพบบั๊กจริง (ยืนยันว่า `_full.png`/`_original.png` มี (H,W) เท่ากันเสมอ)

**Functions/Variables (global scope)**: (ทดสอบทั้งหมด 23 ฟังก์ชัน ไม่ export อะไรออกไปให้ไฟล์อื่น import) กลุ่มหลัก ๆ:
- health/session ไม่ต้อง auth: `test_health_does_not_require_auth`, `test_session_does_not_require_auth`, `test_protected_routes_401_without_a_session`
- login/logout: `test_login_wrong_password_401`, `test_login_correct_password_sets_cookie_and_session_true`, `test_logout_clears_session`
- id minting: `test_session_new_mints_p0001_first`, `test_session_new_advances_each_call`
- CRF CRUD: `test_crf_save_and_get`, `test_crf_get_missing_pid_404`, `test_crf_save_rejects_bad_pid_format`, `test_crf_list_newest_first`, `test_crf_delete_without_photos_succeeds`, `test_crf_delete_missing_404`
- nurses: `test_nurses_seeded_and_addable`
- capture/preprocess/commit: `test_capture_without_crf_form_is_409`, `test_capture_bad_modality_400`, `test_full_capture_flow`, `test_preprocess_full_and_original_images_share_dimensions`, `test_commit_without_any_capture_is_404`, `test_commit_partial_status_when_only_one_modality_captured`
- ROI: `test_roi_save_get_list_delete`, `test_roi_save_rejects_mismatched_rid`

**Called by**: รันผ่าน `pytest tests/` (ไม่มีไฟล์อื่น import)

**Depends on**: [[conftest]] (fixtures `client`, `auth_client`), ทดสอบพฤติกรรมของ [[server]], [[crf_store]], [[roi_store]], [[preprocessing]] ผ่าน HTTP
