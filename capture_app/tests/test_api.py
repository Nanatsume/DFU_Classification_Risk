"""Integration tests against the real FastAPI app (server.app) via TestClient, isolated DB +
data folder per test (see conftest.client / conftest.auth_client). This is the same flow that
was hand-verified with curl during development — codified so it can't silently regress.
"""

import json

import numpy as np
from PIL import Image

CRF_PAYLOAD_TEMPLATE = {
    "data": {
        "fields": {
            "ckd": "no",
            "mf_L_hallux": "y", "mf_L_mth1": "y", "mf_L_mth5": "y",
            "abi_L": "normal", "ulcer_L": "no", "amp_L": "no",
            "mf_R_hallux": "n", "mf_R_mth1": "n", "mf_R_mth5": "n",
            "abi_R": "pad", "ulcer_R": "no", "amp_R": "no",
        },
        "derived": {
            "L": {"category": 0, "label": "Negative", "lops": False, "pad": False},
            "R": {"category": 2, "label": "Positive", "lops": True, "pad": True},
        },
    },
}


def crf_payload(pid: str) -> dict:
    return {"pid": pid, **CRF_PAYLOAD_TEMPLATE}


# ---------- unauthenticated access ----------

def test_health_does_not_require_auth(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_session_does_not_require_auth(client):
    r = client.get("/api/session")
    assert r.status_code == 200
    assert r.json() == {"authenticated": False}


def test_protected_routes_401_without_a_session(client):
    for method, path, body in [
        ("get", "/api/cases", None),
        ("post", "/api/session/new", {}),
        ("get", "/api/crf", None),
        ("get", "/api/roi", None),
        ("get", "/api/manifest", None),
    ]:
        r = getattr(client, method)(path, json=body) if body is not None else getattr(client, method)(path)
        assert r.status_code == 401, f"{method.upper()} {path} should 401 without a session"


# ---------- login / logout ----------

def test_login_wrong_password_401(client):
    r = client.post("/api/login", json={"password": "wrong"})
    assert r.status_code == 401


def test_login_correct_password_sets_cookie_and_session_true(client):
    r = client.post("/api/login", json={"password": "test-password-123"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert client.get("/api/session").json()["authenticated"] is True


def test_login_locked_out_after_repeated_failures(client):
    """Starlette's TestClient reports its own host as 'testclient' — pre-fill that key's
    failure count directly (avoids five real 2s sleeps just to reach the threshold)."""
    import auth
    key = "testclient"
    auth._failed_attempts.pop(key, None)
    try:
        for _ in range(auth.LOCKOUT_MAX_ATTEMPTS):
            auth._record_failure(key)
        r = client.post("/api/login", json={"password": "test-password-123"})  # correct password, still locked out
        assert r.status_code == 429
    finally:
        auth._failed_attempts.pop(key, None)


def test_logout_clears_session(auth_client):
    assert auth_client.get("/api/session").json()["authenticated"] is True
    r = auth_client.post("/api/logout", json={})
    assert r.status_code == 200
    assert auth_client.get("/api/session").json()["authenticated"] is False


# ---------- id minting ----------

def test_session_new_mints_p0001_first(auth_client):
    r = auth_client.post("/api/session/new", json={})
    assert r.status_code == 200
    assert r.json()["research_id"] == "P0001"


def test_session_new_advances_each_call(auth_client):
    ids = [auth_client.post("/api/session/new", json={}).json()["research_id"] for _ in range(3)]
    assert ids == ["P0001", "P0002", "P0003"]


# ---------- backup status ----------

def test_backup_status_unconfigured_when_no_file(auth_client):
    assert auth_client.get("/api/backup-status").json() == {"configured": False}


def test_backup_status_reports_a_recent_backup_as_fresh(auth_client, tmp_path):
    import json
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone(timedelta(hours=7))).isoformat()
    (tmp_path / "backup_status.json").write_text(
        json.dumps({"updated_at": now, "ok": True, "cases": 12}), encoding="utf-8")
    body = auth_client.get("/api/backup-status").json()
    assert body["configured"] is True and body["ok"] is True
    assert body["stale"] is False
    assert body["cases"] == 12


def test_backup_status_flags_a_backup_that_stopped_running(auth_client, tmp_path):
    """The failure this guards against is silence: a job that died weeks ago while everyone
    assumed the data was safe."""
    import json
    from datetime import datetime, timedelta, timezone
    old = (datetime.now(timezone(timedelta(hours=7))) - timedelta(days=9)).isoformat()
    (tmp_path / "backup_status.json").write_text(
        json.dumps({"updated_at": old, "ok": True}), encoding="utf-8")
    body = auth_client.get("/api/backup-status").json()
    assert body["stale"] is True
    assert body["age_hours"] > 200


def test_backup_status_does_not_cry_wolf_the_morning_after(auth_client, tmp_path):
    """A nightly job that ran late, or a laptop closed at 02:00, is not a problem yet."""
    import json
    from datetime import datetime, timedelta, timezone
    recent = (datetime.now(timezone(timedelta(hours=7))) - timedelta(hours=30)).isoformat()
    (tmp_path / "backup_status.json").write_text(
        json.dumps({"updated_at": recent, "ok": True}), encoding="utf-8")
    assert auth_client.get("/api/backup-status").json()["stale"] is False


def test_backup_status_survives_a_corrupt_status_file(auth_client, tmp_path):
    (tmp_path / "backup_status.json").write_text("{not json", encoding="utf-8")
    body = auth_client.get("/api/backup-status").json()
    assert body["ok"] is False and "unreadable" in body["error"]


def test_backup_status_requires_login(client):
    assert client.get("/api/backup-status").status_code == 401


# ---------- CRF CRUD ----------

def test_crf_save_and_get(auth_client):
    r = auth_client.post("/api/crf", json=crf_payload("P0001"))
    assert r.status_code == 200
    body = r.json()
    assert body["data"]["derived"]["L"]["label"] == "Negative"
    assert body["data"]["derived"]["R"]["label"] == "Positive"

    r = auth_client.get("/api/crf/P0001")
    assert r.status_code == 200
    assert r.json()["pid"] == "P0001"


def test_crf_save_without_pid_mints_the_id(auth_client):
    """The form page sends no pid for a new case — the server mints it and hands it back in the
    saved record, which is the only place the client learns it."""
    payload = {k: v for k, v in crf_payload("P0001").items() if k != "pid"}
    r = auth_client.post("/api/crf", json=payload)
    assert r.status_code == 200
    assert r.json()["pid"] == "P0001"
    assert auth_client.get("/api/crf/P0001").status_code == 200


def test_crf_save_without_pid_advances_each_time(auth_client):
    payload = {k: v for k, v in crf_payload("P0001").items() if k != "pid"}
    ids = [auth_client.post("/api/crf", json=payload).json()["pid"] for _ in range(3)]
    assert ids == ["P0001", "P0002", "P0003"]


def test_opening_a_form_without_saving_burns_no_id(auth_client):
    """Regression: the form page used to reserve an id on mount, so abandoning a half-filled form
    left a case row with no form behind and the next patient got a gap in the sequence."""
    before = auth_client.get("/api/health").json()["next_id"]
    payload = {k: v for k, v in crf_payload("P0001").items() if k != "pid"}
    assert auth_client.get("/api/health").json()["next_id"] == before
    assert auth_client.post("/api/crf", json=payload).json()["pid"] == before


def test_crf_save_with_pid_still_edits_that_case(auth_client):
    """Sending a pid is the edit path and must not mint anything new."""
    auth_client.post("/api/crf", json=crf_payload("P0001"))
    r = auth_client.post("/api/crf", json=crf_payload("P0001"))
    assert r.json()["pid"] == "P0001"
    assert [row["pid"] for row in auth_client.get("/api/crf").json()] == ["P0001"]


def test_crf_get_missing_pid_404(auth_client):
    r = auth_client.get("/api/crf/P9999")
    assert r.status_code == 404


def test_crf_save_rejects_bad_pid_format(auth_client):
    r = auth_client.post("/api/crf", json=crf_payload("not-a-pid"))
    assert r.status_code == 400


def test_crf_list_newest_first(auth_client):
    auth_client.post("/api/crf", json=crf_payload("P0001"))
    auth_client.post("/api/crf", json=crf_payload("P0002"))
    rows = auth_client.get("/api/crf").json()
    assert [r["pid"] for r in rows] == ["P0002", "P0001"]


def test_crf_delete_without_photos_succeeds(auth_client):
    auth_client.post("/api/crf", json=crf_payload("P0001"))
    r = auth_client.delete("/api/crf/P0001")
    assert r.status_code == 200
    assert auth_client.get("/api/crf/P0001").status_code == 404


def test_crf_delete_missing_404(auth_client):
    assert auth_client.delete("/api/crf/P9999").status_code == 404


# ---------- backup status ----------

def test_backup_status_unconfigured_when_no_file(auth_client):
    assert auth_client.get("/api/backup-status").json() == {"configured": False}


def test_backup_status_reports_a_recent_backup_as_fresh(auth_client, tmp_path):
    import json
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone(timedelta(hours=7))).isoformat()
    (tmp_path / "backup_status.json").write_text(
        json.dumps({"updated_at": now, "ok": True, "cases": 12}), encoding="utf-8")
    body = auth_client.get("/api/backup-status").json()
    assert body["configured"] is True and body["ok"] is True
    assert body["stale"] is False
    assert body["cases"] == 12


def test_backup_status_flags_a_backup_that_stopped_running(auth_client, tmp_path):
    """The failure this guards against is silence: a job that died weeks ago while everyone
    assumed the data was safe."""
    import json
    from datetime import datetime, timedelta, timezone
    old = (datetime.now(timezone(timedelta(hours=7))) - timedelta(days=9)).isoformat()
    (tmp_path / "backup_status.json").write_text(
        json.dumps({"updated_at": old, "ok": True}), encoding="utf-8")
    body = auth_client.get("/api/backup-status").json()
    assert body["stale"] is True
    assert body["age_hours"] > 200


def test_backup_status_does_not_cry_wolf_the_morning_after(auth_client, tmp_path):
    """A nightly job that ran late, or a laptop closed at 02:00, is not a problem yet."""
    import json
    from datetime import datetime, timedelta, timezone
    recent = (datetime.now(timezone(timedelta(hours=7))) - timedelta(hours=30)).isoformat()
    (tmp_path / "backup_status.json").write_text(
        json.dumps({"updated_at": recent, "ok": True}), encoding="utf-8")
    assert auth_client.get("/api/backup-status").json()["stale"] is False


def test_backup_status_survives_a_corrupt_status_file(auth_client, tmp_path):
    (tmp_path / "backup_status.json").write_text("{not json", encoding="utf-8")
    body = auth_client.get("/api/backup-status").json()
    assert body["ok"] is False and "unreadable" in body["error"]


def test_backup_status_requires_login(client):
    assert client.get("/api/backup-status").status_code == 401


# ---------- CRF CRUD ----------

def test_crf_save_and_get(auth_client):
    r = auth_client.post("/api/crf", json=crf_payload("P0001"))
    assert r.status_code == 200
    body = r.json()
    assert body["data"]["derived"]["L"]["label"] == "Negative"
    assert body["data"]["derived"]["R"]["label"] == "Positive"

    r = auth_client.get("/api/crf/P0001")
    assert r.status_code == 200
    assert r.json()["pid"] == "P0001"


def test_crf_save_without_pid_mints_the_id(auth_client):
    """The form page sends no pid for a new case — the server mints it and hands it back in the
    saved record, which is the only place the client learns it."""
    payload = {k: v for k, v in crf_payload("P0001").items() if k != "pid"}
    r = auth_client.post("/api/crf", json=payload)
    assert r.status_code == 200
    assert r.json()["pid"] == "P0001"
    assert auth_client.get("/api/crf/P0001").status_code == 200


def test_crf_save_without_pid_advances_each_time(auth_client):
    payload = {k: v for k, v in crf_payload("P0001").items() if k != "pid"}
    ids = [auth_client.post("/api/crf", json=payload).json()["pid"] for _ in range(3)]
    assert ids == ["P0001", "P0002", "P0003"]


def test_opening_a_form_without_saving_burns_no_id(auth_client):
    """Regression: the form page used to reserve an id on mount, so abandoning a half-filled form
    left a case row with no form behind and the next patient got a gap in the sequence."""
    before = auth_client.get("/api/health").json()["next_id"]
    payload = {k: v for k, v in crf_payload("P0001").items() if k != "pid"}
    assert auth_client.get("/api/health").json()["next_id"] == before
    assert auth_client.post("/api/crf", json=payload).json()["pid"] == before


def test_crf_save_with_pid_still_edits_that_case(auth_client):
    """Sending a pid is the edit path and must not mint anything new."""
    auth_client.post("/api/crf", json=crf_payload("P0001"))
    r = auth_client.post("/api/crf", json=crf_payload("P0001"))
    assert r.json()["pid"] == "P0001"
    assert [row["pid"] for row in auth_client.get("/api/crf").json()] == ["P0001"]


def test_crf_get_missing_pid_404(auth_client):
    r = auth_client.get("/api/crf/P9999")
    assert r.status_code == 404


def test_crf_save_rejects_bad_pid_format(auth_client):
    r = auth_client.post("/api/crf", json=crf_payload("not-a-pid"))
    assert r.status_code == 400


def test_crf_list_newest_first(auth_client):
    auth_client.post("/api/crf", json=crf_payload("P0001"))
    auth_client.post("/api/crf", json=crf_payload("P0002"))
    rows = auth_client.get("/api/crf").json()
    assert [r["pid"] for r in rows] == ["P0002", "P0001"]


def test_crf_delete_without_photos_succeeds(auth_client):
    auth_client.post("/api/crf", json=crf_payload("P0001"))
    r = auth_client.delete("/api/crf/P0001")
    assert r.status_code == 200
    assert auth_client.get("/api/crf/P0001").status_code == 404


def test_crf_delete_missing_404(auth_client):
    assert auth_client.delete("/api/crf/P9999").status_code == 404


# ---------- nurses ----------

def test_staff_name_endpoints_are_gone(auth_client):
    """The study site asked that staff names not be stored, so the rosters and the endpoints that
    served them were removed rather than merely hidden from the UI. A 404 here is the point: a
    dropdown that still answers is a dropdown someone will wire back up."""
    assert auth_client.get("/api/nurses").status_code == 404
    assert auth_client.get("/api/operators").status_code == 404


def test_saved_form_stores_no_staff_names(auth_client):
    payload = {k: v for k, v in crf_payload("P0001").items() if k != "pid"}
    payload["nurse"] = "ควรถูกเพิกเฉย"      # a stale client must not be able to smuggle one back in
    payload["nurse2"] = "ควรถูกเพิกเฉย"
    body = auth_client.post("/api/crf", json=payload).json()
    assert "nurse" not in body and "nurse2" not in body
    assert "nurse" not in json.dumps(body, ensure_ascii=False)


# ---------- the capture gate: no CRF form -> 409 ----------

def test_capture_without_crf_form_is_409(auth_client):
    r = auth_client.post("/api/capture", json={"rid": "P0001", "modality": "podoscope"})
    assert r.status_code == 409


def test_capture_bad_modality_400(auth_client):
    auth_client.post("/api/crf", json=crf_payload("P0001"))
    r = auth_client.post("/api/capture", json={"rid": "P0001", "modality": "xray"})
    assert r.status_code == 400


# ---------- full happy path: crf -> capture -> preprocess -> commit -> roi ----------

def test_full_capture_flow(auth_client):
    auth_client.post("/api/crf", json=crf_payload("P0001"))

    r = auth_client.post("/api/capture", json={"rid": "P0001", "modality": "podoscope"})
    assert r.status_code == 200
    assert r.json()["url"].startswith("/api/file/")

    r = auth_client.post("/api/preprocess", json={"rid": "P0001"})
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert "left_url" in r.json() and "right_url" in r.json()

    r = auth_client.post("/api/capture", json={"rid": "P0001", "modality": "thermal"})
    assert r.status_code == 200

    r = auth_client.post("/api/commit", json={"rid": "P0001", "operator": "tester"})
    assert r.status_code == 200
    assert r.json()["status"] == "complete"

    manifest = auth_client.get("/api/manifest").json()
    assert any(m["research_id"] == "P0001" and m["status"] == "complete" for m in manifest)

    # /api/cases now shows this case as fully captured
    cases = auth_client.get("/api/cases").json()
    case = next(c for c in cases if c["research_id"] == "P0001")
    assert case["has_podo"] is True and case["has_thermal"] is True

    # the delete guard: a case with photos must not have its CRF form deletable
    r = auth_client.delete("/api/crf/P0001")
    assert r.status_code == 409


def test_preprocess_full_and_original_images_share_dimensions(auth_client, tmp_path):
    """ROI is marked in VIA on the *_full.png (grayscale+CLAHE). Grad-CAM overlay later needs
    *_original.png (color, pre-grayscale) to be pixel-grid-identical to it, so ROI coordinates
    transfer with zero rescaling. Grayscale/CLAHE/3-channel conversion are pixel-wise ops that
    must never touch (H, W) — this test is the guardrail against a future edit breaking that."""
    auth_client.post("/api/crf", json=crf_payload("P0001"))
    auth_client.post("/api/capture", json={"rid": "P0001", "modality": "podoscope"})
    r = auth_client.post("/api/preprocess", json={"rid": "P0001"})
    assert r.status_code == 200 and r.json()["status"] == "ok"

    prepro_dir = tmp_path / "podo" / "P0001" / "preprocessing"
    for side in ("L", "R"):
        train = np.array(Image.open(prepro_dir / f"P0001_podo_{side}.png"))
        full = np.array(Image.open(prepro_dir / f"P0001_podo_{side}_full.png"))
        original = np.array(Image.open(prepro_dir / f"P0001_podo_{side}_original.png"))

        assert train.shape[:2] == (224, 224)  # training file — fixed CNN input size
        assert full.shape[:2] == original.shape[:2]  # the actual guarantee under test
        assert np.array_equal(full[..., 0], full[..., 1])  # _full is grayscale (R==G==B)
        assert not np.array_equal(original[..., 0], original[..., 1])  # _original has real color


def test_commit_without_any_capture_is_404(auth_client):
    auth_client.post("/api/crf", json=crf_payload("P0001"))
    r = auth_client.post("/api/commit", json={"rid": "P0001", "operator": "tester"})
    assert r.status_code == 404


def test_commit_partial_status_when_only_one_modality_captured(auth_client):
    auth_client.post("/api/crf", json=crf_payload("P0001"))
    auth_client.post("/api/capture", json={"rid": "P0001", "modality": "podoscope"})
    r = auth_client.post("/api/commit", json={"rid": "P0001", "operator": "tester"})
    assert r.status_code == 200
    assert r.json()["status"] == "partial"


# ---------- ROI ----------

def test_roi_save_get_list_delete(auth_client):
    body = {"rid": "P0001", "project": {"demo": True}, "summary": {"L": {"region_count": 1}}}
    r = auth_client.post("/api/roi/P0001", json=body)
    assert r.status_code == 200

    r = auth_client.get("/api/roi/P0001")
    assert r.status_code == 200
    assert r.json()["project"]["demo"] is True

    r = auth_client.get("/api/roi")
    assert any(row["rid"] == "P0001" for row in r.json())

    r = auth_client.delete("/api/roi/P0001")
    assert r.status_code == 200
    assert auth_client.get("/api/roi/P0001").status_code == 404


def test_roi_save_rejects_mismatched_rid(auth_client):
    body = {"rid": "P0002", "project": {}, "summary": {}}
    r = auth_client.post("/api/roi/P0001", json=body)
    assert r.status_code == 400


def test_roi_save_accepts_real_via_filename_shape(auth_client):
    """The exact filename shape _via_dfu.js's dfu_add_case_images() actually writes must keep
    working — this is the regression guard for the security-review fix below."""
    body = {
        "rid": "P0001",
        "project": {
            "_via_img_metadata": {
                "img1": {
                    "filename": "/api/file/podo/P0001/preprocessing/P0001_podo_L_full.png",
                    "regions": [],
                }
            }
        },
        "summary": {},
    }
    r = auth_client.post("/api/roi/P0001", json=body)
    assert r.status_code == 200


def test_roi_save_rejects_html_in_filename(auth_client):
    """Security regression: a filename outside the exact shape _via_dfu.js ever writes (e.g. one
    smuggling an HTML/script payload) must be rejected — closes the stored-XSS path where a saved
    project is later replayed unescaped into VIA's own innerHTML rendering of the image list."""
    body = {
        "rid": "P0001",
        "project": {
            "_via_img_metadata": {
                "img1": {
                    "filename": '"><img src=x onerror=alert(1)>',
                    "regions": [],
                }
            }
        },
        "summary": {},
    }
    r = auth_client.post("/api/roi/P0001", json=body)
    assert r.status_code == 422
