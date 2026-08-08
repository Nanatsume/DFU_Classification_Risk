---
name: test_auth
description: Unit tests for auth.py — password hashing, session validity, bootstrap_password behavior
metadata:
  type: reference
---

# tests/test_auth.py

**หน้าที่**: เทสต์ unit-level ของ [[auth]] โดยตรง (ไม่ผ่าน HTTP) — ครอบคลุม hash/verify รหัสผ่าน, การสร้างรหัสผ่านตอนสตาร์ทเซิร์ฟเวอร์ (จาก env var หรือสุ่มใหม่), และความถูกต้อง/หมดอายุของ session

**Functions/Variables (global scope)**: (11 ฟังก์ชันเทสต์)
- `test_hash_verify_round_trip`, `test_verify_rejects_wrong_password`, `test_hash_uses_a_random_salt_each_time`, `test_verify_rejects_garbage_stored_value` — hash/verify
- `test_bootstrap_password_from_env_var`, `test_bootstrap_password_env_var_overwrites_existing`, `test_bootstrap_password_generates_once_when_no_env_and_no_existing` — bootstrap
- `test_session_valid_true_for_fresh_session`, `test_session_valid_false_for_unknown_token`, `test_session_valid_false_for_none`, `test_session_valid_false_and_purged_once_expired` — session validity

**Called by**: รันผ่าน `pytest tests/` (ไม่มีไฟล์อื่น import)

**Depends on**: [[auth]] (fixture `authmod` — import โดยตรงไม่ผ่าน `client`), [[conftest]] (ใช้ `monkeypatch`/`capsys` มาตรฐานของ pytest เอง ไม่ได้ใช้ fixture จาก conftest.py โดยตรงในไฟล์นี้)
