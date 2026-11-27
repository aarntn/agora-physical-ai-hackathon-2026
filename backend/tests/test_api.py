import pytest
from fastapi.testclient import TestClient

from nasocheck.agora_client import join_body
from nasocheck.app import create_app
from nasocheck.config import Settings
from nasocheck.store import Store

DEV = {"X-Device-Key": "dev"}
TOOL = {"X-Tool-Secret": "tool"}


def settings(tmp_path):
    s = Settings()
    s.device_key, s.tool_secret = "dev", "tool"
    s.app_id = s.app_certificate = s.customer_id = s.customer_secret = s.llm_api_key = ""
    s.public_base_url = ""
    s.log_path = tmp_path / "events.jsonl"
    s.tool_wait_s = 0.2
    return s


@pytest.fixture
def env(tmp_path):
    s = settings(tmp_path)
    store = Store(s.log_path)
    return s, store, TestClient(create_app(s, store))


def new_session(c, **kw):
    r = c.post("/session", json={"lang": "ms", **kw}, headers=DEV)
    assert r.status_code == 200, r.text
    return r.json()


def post(c, sid, tid, ratio, **kw):
    body = dict(trial_id=tid, session_id=sid, start_ms=0, end_ms=2000, ratio_db=ratio,
                spread_db=1.0, voiced_frames=40, mic_clipped=False, accel_snr_db=15.0,
                imu_hz=1600, simulated=True)
    body.update(kw)
    return c.post("/trials", json=body, headers=DEV)


def latest(c, heard=""):
    r = c.post("/tools/getLatestTrial", json={"session_id": "", "heard_text": heard,
                                               "tool_call_id": "x"}, headers=TOOL)
    assert r.status_code == 200
    return r.json()


def test_auth_required(env):
    _, _, c = env
    assert c.post("/session", json={}).status_code == 401
    assert c.post("/tools/getSummary", json={}, headers={"X-Tool-Secret": "nope"}).status_code == 401


def test_full_protocol_flow(env):
    _, _, c = env
    sess = new_session(c)
    sid = sess["session_id"]
    assert sess["next_step"]["type"] == "hum"
    assert sess["agent_started"] is False

    assert latest(c)["status"] == "pending"

    r = post(c, sid, "t1", -2.0).json()
    assert r["type"] == "hum" and r["status"] == "valid" and r["score_db"] == 0.0
    out = latest(c)
    assert out["say"].startswith("[SIMULATED DATA]")
    assert out["next_step"]["type"] == "oral" and out["next_step"]["phrase"] == "Papa pakai topi"

    # wrong phrase -> rejected by the agent-side check, step does not advance
    post(c, sid, "t2", -20.0)
    out = latest(c, "kakak beli kuih")
    assert out["status"] == "rejected" and out["reasons"] == ["wrong_phrase"]
    assert out["next_step"]["type"] == "oral"

    post(c, sid, "t3", -20.0)
    out = latest(c, "papa pakai topi")
    assert out["status"] == "valid" and out["score_db"] == -18.0
    assert "negatif 18 perpuluhan 0 desibel" in out["say"]
    assert out["next_step"]["type"] == "nasal"

    # signal-quality rejection
    post(c, sid, "t4", -8.0, spread_db=6.0)
    out = latest(c, "papa pakai topi")
    assert out["reasons"] == ["unstable"]

    post(c, sid, "t5", -8.0)
    out = latest(c, "papa pakai topi")
    assert out["score_db"] == -6.0 and out["next_step"]["type"] == "done"
    assert "12 perpuluhan 0 desibel" in out["say"]

    summ = c.post("/tools/getSummary", json={"session_id": sid}, headers=TOOL).json()
    assert summ["mean_score_db"]["oral"] == -18.0
    assert summ["nasal_minus_oral_db"] == 12.0
    assert summ["rejected"] == 2


def test_spoken_numbers_are_consistent(env):
    _, _, c = env
    sid = new_session(c)["session_id"]
    post(c, sid, "h", 0.0)
    latest(c)
    post(c, sid, "o", -19.84)
    latest(c, "papa pakai topi")
    post(c, sid, "n", -8.04)
    out = latest(c, "papa pakai topi")
    assert "11 perpuluhan 8 desibel" in out["say"]           # -8.0 - (-19.8)
    summ = c.post("/tools/getSummary", json={"session_id": sid}, headers=TOOL).json()
    assert summ["nasal_minus_oral_db"] == 11.8


def test_oral_before_hum_needs_calibration(env):
    _, _, c = env
    sid = new_session(c)["session_id"]
    r = post(c, sid, "t1", -20.0, type="oral").json()
    assert r["status"] == "needs_calibration" and r["score_db"] is None


def test_idempotent_and_conflict(env):
    _, _, c = env
    sid = new_session(c)["session_id"]
    assert post(c, sid, "t1", -2.0).json()["duplicate"] is False
    assert post(c, sid, "t1", -2.0).json()["duplicate"] is True
    assert post(c, sid, "t1", -3.0).status_code == 409
    assert post(c, "nosuch", "t9", -2.0).status_code == 404


def test_latest_returns_newest_and_skips_stale(env):
    _, _, c = env
    sid = new_session(c)["session_id"]
    post(c, sid, "t1", -2.0)
    post(c, sid, "t2", -20.0)
    out = latest(c, "papa pakai topi")
    assert out["trial_id"] == "t2"
    assert latest(c)["status"] == "pending"


def test_touch_override_skips_phrase_check(env):
    _, _, c = env
    sid = new_session(c)["session_id"]
    post(c, sid, "t1", -2.0)
    post(c, sid, "t2", -20.0, phrase_confirmed=True)
    out = latest(c, "something unrelated")
    assert out["status"] == "valid" and out["phrase_status"] == "override"


def test_replay_and_previous_session_comparison(env):
    s, _, c = env
    for i, oral in enumerate((-12.0, -18.0)):
        sid = new_session(c, user_ref="P01")["session_id"]
        post(c, sid, f"h{i}", 0.0)
        post(c, sid, f"o{i}", oral)
        latest(c, "papa pakai topi")
        post(c, sid, f"p{i}", oral, type="oral")   # second oral trial (min 2 to compare)
    summ = c.post("/tools/getSummary", json={"session_id": sid}, headers=TOOL).json()
    assert summ["change_vs_previous_oral_db"] == -6.0
    assert "lebih rendah" in summ["say"]

    # restart: rebuild from the event log, state must match
    store2 = Store(s.log_path)
    c2 = TestClient(create_app(s, store2))
    st2 = c2.get(f"/session/{sid}", headers=DEV).json()
    assert [t["status"] for t in st2["trials"]] == ["valid", "valid", "valid"]
    assert st2["summary"]["change_vs_previous_oral_db"] == -6.0
    # reported flags survive replay: only the extra (never-polled) trial is unreported
    assert store2.latest_unreported(store2.sessions[sid]).trial.trial_id == "p1"


def test_join_body_shape(tmp_path):
    s = settings(tmp_path)
    s.public_base_url = "https://example.test"
    body = join_body(s, session_id="sabc", channel="naso-sabc", lang="ms",
                     device_uid="1002", agent_token="")
    p = body["properties"]
    assert p["advanced_features"]["enable_tools"] is True
    assert p["remote_rtc_uids"] == ["1002"] and p["asr"]["language"] == "ms-MY"
    assert "Bahasa Melayu" in p["llm"]["system_messages"][0]["content"]
    names = [t["function"]["name"] for t in p["llm"]["tools"]]
    assert names == ["getNextStep", "getLatestTrial", "getSummary"]
    for t in p["llm"]["tools"]:
        assert t["server"]["url"].startswith("https://example.test/tools/")
        assert set(t["function"]["parameters"]["required"]) == set(t["function"]["parameters"]["properties"])
        # every {{args.x}} placeholder must be a required parameter
        for k, v in t["server"]["body"].items():
            if v.startswith("{{args."):
                assert v[7:-2] in t["function"]["parameters"]["required"]
    assert p["llm"]["template_variables"]["session_id"] == "sabc"


def test_no_comparison_from_single_trial(env):
    _, _, c = env
    for i in range(2):
        sid = new_session(c, user_ref="P02")["session_id"]
        post(c, sid, f"h{i}", 0.0)
        post(c, sid, f"o{i}", -12.0 - 6 * i)
        post(c, sid, f"q{i}", -12.0 - 6 * i, type="oral") if i == 0 else None
    summ = c.post("/tools/getSummary", json={"session_id": sid}, headers=TOOL).json()
    assert summ["change_vs_previous_oral_db"] is None
    assert "sekurang-kurangnya dua" in summ["say"]
