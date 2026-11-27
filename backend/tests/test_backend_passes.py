"""Raw upload fallback, evidence export, tunable thresholds, serial relay."""
import base64
import json
import sys
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from nasocheck import dsp, raw, synth
from nasocheck.app import create_app
from nasocheck.config import Settings, thresholds_from_env
from nasocheck.store import Store

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import relay as relay_mod  # noqa: E402

from test_api import DEV, TOOL, latest, new_session, post, settings, tok  # noqa: E402


@pytest.fixture
def env(tmp_path):
    s = settings(tmp_path)
    store = Store(s.log_path, s.thresholds)
    return s, store, TestClient(create_app(s, store))


def raw_body(sid, tid, coupling_db, **kw):
    c = synth.capture(coupling_db=coupling_db, seed=hash(tid) % 1000)
    a64, m64 = raw.encode_capture(c["accel"], c["mic"])
    return {"trial_id": tid, "session_id": sid, "imu_hz": c["fs_imu"], "mic_hz": c["fs_mic"],
            "accel_b64": a64, "mic_b64": m64, "simulated": True, **kw}


# ---- pass 1: raw upload ---------------------------------------------------
def test_raw_upload_scores_like_reference(env):
    s, _, c = env
    sid = new_session(c)["session_id"]
    hum = c.post("/trials/raw", json=raw_body(sid, "h", 0.0), headers=DEV).json()
    assert hum["status"] == "valid" and hum["type"] == "hum"
    oral = c.post("/trials/raw", json=raw_body(sid, "o", -20.0), headers=DEV).json()
    assert oral["score_db"] == pytest.approx(-20, abs=1.5)
    assert (s.log_path.parent / "raw" / sid / "o.npz").exists()
    again = c.post("/trials/raw", json=raw_body(sid, "o", -20.0), headers=DEV).json()
    assert again["duplicate"] is True


def test_raw_matches_dsp_on_same_samples(env):
    _, _, c = env
    sid = new_session(c)["session_id"]
    body = raw_body(sid, "x", -12.0)
    acc, mic = raw.decode(raw.RawTrialIn(**body))
    f = dsp.analyze(acc, body["imu_hz"], mic, body["mic_hz"])
    out = c.post("/trials/raw", json=body, headers=DEV).json()
    assert out["ratio_db"] == pytest.approx(f.ratio_db)


@pytest.mark.parametrize("patch,code", [
    ({"accel_b64": "!!notbase64"}, 422),
    ({"accel_b64": base64.b64encode(b"\x00\x00" * 4).decode()}, 422),   # not multiple of 3
    ({"mic_b64": base64.b64encode(b"\x00\x00" * 16000 * 11).decode()}, 422),  # > 10 s
    ({"session_id": "nosuch"}, 404),
])
def test_raw_rejects_bad_input(env, patch, code):
    _, _, c = env
    sid = new_session(c)["session_id"]
    assert c.post("/trials/raw", json={**raw_body(sid, "b", -10.0), **patch}, headers=DEV).status_code == code


# ---- pass 3: evidence -----------------------------------------------------
def test_evidence_table_and_summary(env):
    _, _, c = env
    for person in ("P1", "P2"):
        sid = new_session(c, user_ref=person)["session_id"]
        post(c, sid, "h", 0.0)
        post(c, sid, "o1", -20.0, type="oral")
        post(c, sid, "o2", -18.0, type="oral")
        post(c, sid, "n1", -8.0, type="nasal")
        post(c, sid, "bad", -8.0, type="nasal", spread_db=9.0)
    csv_text = c.get("/evidence.csv", headers=DEV).text
    lines = csv_text.strip().split("\n")
    assert lines[0].startswith("session_id,user_ref,lang,seq,trial_id,type,status,score_db")
    assert len(lines) == 1 + 10
    summ = c.get("/evidence", headers=DEV).json()
    p1 = summ["people"]["P1"]
    assert p1["by_type"]["oral"] == {"n": 2, "mean": -19.0, "sd": 1.4, "min": -20.0, "max": -18.0}
    assert p1["rejected"] == 1 and p1["nasal_minus_oral_db"] == 11.0
    assert summ["simulated_trials"] == 10
    assert c.get("/evidence?include_simulated=false", headers=DEV).json()["trials"] == 0


# ---- pass 4: thresholds, stop, practice ----------------------------------
def test_thresholds_from_env(monkeypatch):
    monkeypatch.setenv("NC_MAX_SPREAD_DB", "10")
    monkeypatch.setenv("NC_MIN_VOICED_FRAMES", "5")
    th = thresholds_from_env()
    assert th.max_spread_db == 10.0 and th.min_voiced_frames == 5


def test_custom_thresholds_change_decisions(tmp_path):
    s = settings(tmp_path)
    s.thresholds = thresholds_from_env().__class__(max_spread_db=10.0)
    c = TestClient(create_app(s, Store(s.log_path, s.thresholds)))
    sid = new_session(c)["session_id"]
    assert post(c, sid, "h", 0.0, spread_db=6.0).json()["status"] == "valid"
    assert c.get("/config", headers=DEV).json()["thresholds"]["max_spread_db"] == 10.0


def test_stop_without_agent_does_not_crash(env):
    _, _, c = env
    sid = new_session(c)["session_id"]
    assert c.post(f"/session/{sid}/stop", headers=DEV).json()["stopped"] is False


def test_untyped_trials_after_done_are_practice(env):
    _, _, c = env
    sid = new_session(c)["session_id"]
    post(c, sid, "h", 0.0)
    post(c, sid, "o", -20.0)
    post(c, sid, "n", -8.0)
    assert c.get(f"/session/{sid}/next", headers=DEV).json()["type"] == "done"
    extra = post(c, sid, "x", -15.0).json()
    assert extra["type"] == "oral" and extra["status"] == "valid"


# ---- pass 2: serial relay -------------------------------------------------
def test_relay_round_trip(env):
    _, _, c = env
    sent, logs = [], []
    r = relay_mod.Relay(c, "dev", write=sent.append, log=logs.append)
    out = r.handle_line('NC_SESSION {"lang":"en","user_ref":"P9"}')
    sid = out["session_id"]
    assert out["ok"] and sent[-1].startswith("NC_RESP ")
    body = {"trial_id": "t1", "session_id": sid, "start_ms": 0, "end_ms": 2000, "ratio_db": -2.0,
            "spread_db": 1.0, "voiced_frames": 40, "mic_clipped": False, "accel_snr_db": 15.0,
            "imu_hz": 1600}
    assert r.handle_line("NC_TRIAL " + json.dumps(body))["http"] == 200
    assert r.handle_line("NC_TRIAL " + json.dumps(body))["duplicate"] is True
    nxt = r.handle_line('NC_NEXT {"session_id":"%s"}' % sid)
    assert nxt["type"] == "oral" and nxt["phrase"] == "Buy Bobby a puppy"
    assert r.handle_line("NC_RAW " + json.dumps(raw_body(sid, "r1", -20.0)))["ok"]
    assert r.handle_line("boot: imu ok 1594 Hz") is None and "device: boot" in logs[-1]
    assert r.handle_line("NC_TRIAL {broken")["ok"] is False
    assert r.handle_line("NC_NEXT {}")["error"].startswith("missing")
    # agent still sees relayed trials
    assert latest(c, "buy bobby a puppy")["trial_id"] == "r1"


def test_relay_rejects_wrong_key(env):
    _, _, c = env
    r = relay_mod.Relay(c, "wrong", write=lambda s: None, log=lambda s: None)
    assert r.handle_line('NC_SESSION {}')["http"] == 401


# ---- security fixes ---------------------------------------------------------
def test_tool_token_is_per_session(env):
    _, _, c = env
    a = new_session(c)["session_id"]
    b = new_session(c)["session_id"]
    assert c.post("/tools/getSummary", json={}, headers=TOOL).status_code == 401
    assert c.post("/tools/getSummary", json={"session_id": a}, headers=TOOL).status_code == 401
    assert c.post("/tools/getSummary", json={"session_id": b}, headers=tok(a)).status_code == 401
    assert c.post("/tools/getSummary", json={"session_id": a}, headers=tok(a)).json()["status"] == "ok"


def test_fail_closed_without_keys(tmp_path):
    s = settings(tmp_path)
    s.device_key = s.tool_secret = ""
    s.dev_mode = False
    c = TestClient(create_app(s, Store(s.log_path)))
    assert c.post("/session", json={}).status_code == 503
    assert c.post("/tools/getSummary", json={}).status_code == 503
    s.dev_mode = True
    c = TestClient(create_app(s, Store(s.log_path)))
    assert c.post("/session", json={}).status_code == 200
    assert c.post("/tools/getSummary", json={}).json()["status"] == "ok"   # active-session fallback


def test_csv_formula_injection_neutralised(env):
    _, _, c = env
    sid = new_session(c)["session_id"]
    post(c, sid, "h", 0.0)
    post(c, sid, "o", -20.0)
    latest(c, "=HYPERLINK(\"http://x\")")
    r = c.get("/evidence.csv", headers=DEV)
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    assert "'=HYPERLINK" in r.text and ",=HYPERLINK" not in r.text


def test_raw_payload_size_capped_before_decode(env):
    _, _, c = env
    sid = new_session(c)["session_id"]
    big = {**raw_body(sid, "big", -10.0), "mic_b64": "A" * 1_400_000}
    assert c.post("/trials/raw", json=big, headers=DEV).status_code == 422


def test_live_page_served(env):
    _, _, c = env
    r = c.get("/live")
    assert r.status_code == 200 and "NasoCheck live" in r.text
