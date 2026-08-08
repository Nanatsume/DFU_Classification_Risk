---
name: test_db
description: Unit tests for db.py — id minting, CRF/capture/preprocessing/commit/ROI CRUD, session expiry, settings round-trip
metadata:
  type: reference
---

# tests/test_db.py

**หน้าที่**: เทสต์ unit-level ของ [[db]] โดยตรงผ่าน fixture `tmp_db` (ไม่ผ่าน HTTP/`TestClient`) ครอบคลุมทุกฟังก์ชันสำคัญของเลเยอร์ข้อมูล — เป็นชุดเทสต์ที่จับบั๊ก FK constraint จริงได้ (`save_capture`/`save_preprocessing` เดิมไม่ upsert `cases` ก่อน ทำให้ FOREIGN KEY constraint failed)

**Functions/Variables (global scope)**: (17 ฟังก์ชันเทสต์)
- `test_seed_nurses_present_after_init`
- id minting: `test_next_research_id_starts_at_p0001`, `test_next_research_id_does_not_advance_by_itself`, `test_next_research_id_advances_after_upsert`, `test_upsert_case_is_idempotent`
- CRF: `test_save_crf_creates_case_row_too`, `test_save_crf_overwrites_on_conflict`, `test_delete_crf_returns_false_when_absent`, `test_delete_crf_returns_true_when_present`
- captures/commits: `test_has_capture_false_until_saved`, `test_list_cases_with_status_only_includes_cases_with_a_form`, `test_committed_max_vs_crf_max_are_independent_counters`, `test_list_commits_reconstructs_manifest_shape`
- ROI: `test_roi_round_trip`
- sessions/settings/nurses: `test_sessions_expire`, `test_settings_round_trip`, `test_add_nurse_is_idempotent`

**Called by**: รันผ่าน `pytest tests/` (ไม่มีไฟล์อื่น import)

**Depends on**: [[conftest]] (fixture `tmp_db`), ทดสอบ [[db]] โดยตรง
