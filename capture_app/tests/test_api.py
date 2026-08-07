"""Integration tests against the real FastAPI app (server.app) via TestClient, isolated DB +
data folder per test (see conftest.client / conftest.auth_client). This is the same flow that
was hand-verified with curl during development — codified so it can't silently regress.
"""

CRF_PAYLOAD_TEMPLATE = {
    "nurse": "กรรณิการ์ ทองพูล",
    "nurse2": "ธนกฤต อินทรสุวรรณ",
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
        ("get", "/api/nurses", None),
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

def test_nurses_seeded_and_addable(auth_client):
    names = auth_client.get("/api/nurses").json()
    assert "กรรณิการ์ ทองพูล" in names
    auth_client.post("/api/nurses", json={"name": "พยาบาลทดสอบ"})
    assert "พยาบาลทดสอบ" in auth_client.get("/api/nurses").json()


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
