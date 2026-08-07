"""Unit tests for db.py — the SQLite data layer. No FastAPI/HTTP involved here, just the
functions directly, against an isolated DB (see conftest.tmp_db)."""


def test_seed_nurses_present_after_init(tmp_db):
    names = tmp_db.list_nurses()
    assert "กรรณิการ์ ทองพูล" in names
    assert len(names) == 4


def test_next_research_id_starts_at_p0001(tmp_db):
    assert tmp_db.next_research_id() == "P0001"


def test_next_research_id_does_not_advance_by_itself(tmp_db):
    # calling it twice without upserting a case in between must return the same id — the counter
    # only moves forward once a case row actually exists, not on every call.
    assert tmp_db.next_research_id() == "P0001"
    assert tmp_db.next_research_id() == "P0001"


def test_next_research_id_advances_after_upsert(tmp_db):
    first = tmp_db.next_research_id()
    tmp_db.upsert_case(first)
    second = tmp_db.next_research_id()
    assert first == "P0001"
    assert second == "P0002"


def test_upsert_case_is_idempotent(tmp_db):
    tmp_db.upsert_case("P0001")
    tmp_db.upsert_case("P0001")  # must not raise, must not create a duplicate
    with tmp_db.tx() as conn:
        n = conn.execute("SELECT COUNT(*) c FROM cases WHERE research_id='P0001'").fetchone()["c"]
    assert n == 1


def test_save_crf_creates_case_row_too(tmp_db):
    """save_crf() must upsert into `cases` even if /api/session/new was never called for this id
    (e.g. a legacy/manually-entered id) — otherwise next_research_id()'s counter never sees it."""
    tmp_db.save_crf("P0007", "nurse A", "nurse B", "2026-01-01T00:00:00+07:00",
                     fields={"ckd": "no"}, derived={"L": {}, "R": {}}, schema_version="1.0")
    assert tmp_db.next_research_id() == "P0008"


def test_save_crf_overwrites_on_conflict(tmp_db):
    tmp_db.save_crf("P0001", "A", "B", "t1", fields={"note": "first"}, derived={}, schema_version="1.0")
    tmp_db.save_crf("P0001", "A", "B", "t2", fields={"note": "second"}, derived={}, schema_version="1.0")
    rec = tmp_db.get_crf("P0001")
    assert rec["data"]["fields"]["note"] == "second"


def test_delete_crf_returns_false_when_absent(tmp_db):
    assert tmp_db.delete_crf("P9999") is False


def test_delete_crf_returns_true_when_present(tmp_db):
    tmp_db.save_crf("P0001", "A", "B", "t", fields={}, derived={}, schema_version="1.0")
    assert tmp_db.delete_crf("P0001") is True
    assert tmp_db.get_crf("P0001") is None


def test_has_capture_false_until_saved(tmp_db):
    assert tmp_db.has_capture("P0001", "podoscope") is False
    tmp_db.save_capture("P0001", "podoscope", "podo/P0001/raw/P0001_podo.png", "t")
    assert tmp_db.has_capture("P0001", "podoscope") is True
    assert tmp_db.has_capture("P0001", "thermal") is False


def test_list_cases_with_status_only_includes_cases_with_a_form(tmp_db):
    """list_cases_with_status() JOINs cases to crf_forms — a case minted via next_research_id()
    but never saved as a CRF must not show up (the capture-station picker only offers cases that
    actually have a form, per the 409 gate on /api/capture)."""
    tmp_db.upsert_case("P0001")  # minted, no form
    tmp_db.save_crf("P0002", "A", "B", "t", fields={}, derived={"L": {"category": 1}, "R": {}}, schema_version="1.0")
    rows = tmp_db.list_cases_with_status()
    ids = [r["research_id"] for r in rows]
    assert "P0002" in ids
    assert "P0001" not in ids


def test_committed_max_vs_crf_max_are_independent_counters(tmp_db):
    tmp_db.save_crf("P0005", "A", "B", "t", fields={}, derived={}, schema_version="1.0")
    assert tmp_db.crf_max() == 5
    assert tmp_db.committed_max() == 0  # no commit yet
    tmp_db.save_commit("P0003", "complete", "t", "op")
    assert tmp_db.committed_max() == 3
    assert tmp_db.crf_max() == 5  # unaffected by the commit


def test_list_commits_reconstructs_manifest_shape(tmp_db):
    tmp_db.save_capture("P0001", "podoscope", "podo/P0001/raw/P0001_podo.png", "t")
    tmp_db.save_capture("P0001", "thermal", "thermal/P0001/image/P0001_thermal.png", "t")
    tmp_db.save_preprocessing("P0001", "L", "podo/P0001/preprocessing/P0001_podo_L.png")
    tmp_db.save_commit("P0001", "complete", "2026-01-01T00:00:00+07:00", "op")
    rows = tmp_db.list_commits()
    assert len(rows) == 1
    row = rows[0]
    assert row["research_id"] == "P0001"
    assert row["podo_prepro"] == "yes"
    assert row["thermal"] == "thermal/P0001/image/P0001_thermal.png"


def test_roi_round_trip(tmp_db):
    assert tmp_db.get_roi("P0001") is None
    tmp_db.save_roi("P0001", "t", summary={"L": {"region_count": 1}}, project={"big": "blob"})
    rec = tmp_db.get_roi("P0001")
    assert rec["summary"]["L"]["region_count"] == 1
    assert rec["project"]["big"] == "blob"
    # list_roi() must NOT include the project blob (kept small for the list page)
    summaries = tmp_db.list_roi()
    assert "project" not in summaries[0]
    assert tmp_db.delete_roi("P0001") is True
    assert tmp_db.get_roi("P0001") is None


def test_sessions_expire(tmp_db):
    from datetime import datetime, timedelta, timezone
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    tmp_db.create_session("tok1", past)
    assert tmp_db.get_session("tok1") is not None  # row exists...
    tmp_db.purge_expired_sessions()
    assert tmp_db.get_session("tok1") is None  # ...but purge removes it


def test_settings_round_trip(tmp_db):
    assert tmp_db.get_setting("password_hash") is None
    tmp_db.set_setting("password_hash", "abc123")
    assert tmp_db.get_setting("password_hash") == "abc123"
    tmp_db.set_setting("password_hash", "def456")  # overwrite, not duplicate
    assert tmp_db.get_setting("password_hash") == "def456"


def test_add_nurse_is_idempotent(tmp_db):
    tmp_db.add_nurse("ทดสอบ คนใหม่")
    tmp_db.add_nurse("ทดสอบ คนใหม่")
    assert tmp_db.list_nurses().count("ทดสอบ คนใหม่") == 1
