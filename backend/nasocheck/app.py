"""NasoCheck backend: device endpoints + Agora agent tool endpoints.

Run:  uvicorn nasocheck.app:app --host 0.0.0.0 --port 8000   (from backend/)
"""
from __future__ import annotations

import asyncio
import csv
import io
import logging
from dataclasses import asdict
import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import PlainTextResponse

from . import agora_client, dsp, protocol, raw, speech
from .config import Settings, load_dotenv
from .contracts import SessionIn, ToolLatestIn, ToolSessionIn, TrialIn
from .store import Store

log = logging.getLogger("nasocheck")


def create_app(settings: Settings | None = None, store: Store | None = None) -> FastAPI:
    if settings is None:
        load_dotenv(Path(".env"))
        settings = Settings()
    s = settings
    st = store if store is not None else Store(s.log_path, s.thresholds)
    app = FastAPI(title="NasoCheck", version="0.1.0")
    app.state.settings, app.state.store = s, st
    raw_dir = s.log_path.parent / "raw"

    for name, val in (("DEVICE_KEY", s.device_key), ("TOOL_SECRET", s.tool_secret)):
        if not val:
            log.warning("%s not set: endpoints are open (dev mode only)", name)

    def _check(expected: str, got: str | None) -> None:
        if expected and not secrets.compare_digest(expected, got or ""):
            raise HTTPException(401, "bad credentials")

    def device_auth(x_device_key: str | None = Header(default=None)) -> None:
        _check(s.device_key, x_device_key)

    def tool_auth(x_tool_secret: str | None = Header(default=None)) -> None:
        _check(s.tool_secret, x_tool_secret)

    def session_or_404(sid: str):
        sess = st.sessions.get(sid)
        if sess is None:
            raise HTTPException(404, "unknown session")
        return sess

    # ---- device ---------------------------------------------------------
    @app.get("/health")
    def health() -> dict:
        return {"ok": True, "agora_ready": s.agora_ready, "active_session": st.active_session_id}

    @app.post("/session", dependencies=[Depends(device_auth)])
    def create_session(spec: SessionIn) -> dict:
        sess = st.create_session(spec)
        channel = f"naso-{sess.session_id}"
        out = {"session_id": sess.session_id, "channel": channel, "app_id": s.app_id,
               "device_uid": spec.device_rtc_uid, "next_step": sess.next_step_dict(),
               "agent_started": False, "agent_error": None}
        try:
            out["device_token"] = agora_client.rtc_token(s, channel, spec.device_rtc_uid)
        except Exception as e:  # missing optional dependency etc.
            out["device_token"], out["agent_error"] = None, f"token: {e}"
        if spec.start_agent:
            if not s.agora_ready:
                out["agent_error"] = "Agora not configured (see .env.example)"
            else:
                try:
                    body = agora_client.join_body(
                        s, session_id=sess.session_id, channel=channel, lang=spec.lang,
                        device_uid=spec.device_rtc_uid,
                        agent_token=agora_client.rtc_token(s, channel, s.agent_rtc_uid))
                    st.set_agent(sess.session_id, agora_client.start_agent(s, body))
                    out["agent_started"] = True
                except Exception as e:
                    log.exception("agent start failed")
                    out["agent_error"] = str(e)
        return out

    @app.post("/session/{sid}/stop", dependencies=[Depends(device_auth)])
    def stop_session(sid: str) -> dict:
        sess = session_or_404(sid)
        if not (sess.agent_id and s.agora_ready):
            return {"stopped": False, "reason": "no agent running"}
        try:
            agora_client.stop_agent(s, sess.agent_id)
        except Exception as e:  # agent may already have left (idle timeout)
            log.warning("agent stop failed: %s", e)
            return {"stopped": False, "reason": str(e)}
        return {"stopped": True}

    @app.get("/session/{sid}/next", dependencies=[Depends(device_auth)])
    def next_step(sid: str) -> dict:
        return session_or_404(sid).next_step_dict()

    @app.get("/session/{sid}", dependencies=[Depends(device_auth)])
    def session_state(sid: str) -> dict:
        sess = session_or_404(sid)
        return {"session_id": sid, "user_ref": sess.user_ref, "lang": sess.lang,
                "next_step": sess.next_step_dict(),
                "trials": [sess.trial_view(r) for r in sess.trials],
                "summary": speech.summary_response(st, sess)}

    @app.post("/trials", dependencies=[Depends(device_auth)])
    def post_trial(t: TrialIn) -> dict:
        try:
            rec, dup = st.add_trial(t)
        except KeyError:
            raise HTTPException(404, "unknown session")
        except ValueError as e:
            raise HTTPException(409, str(e))
        sess = st.sessions[t.session_id]
        return {**sess.trial_view(rec), "duplicate": dup, "next_step": sess.next_step_dict()}

    @app.post("/trials/raw", dependencies=[Depends(device_auth)])
    def post_raw_trial(r: raw.RawTrialIn) -> dict:
        """Fallback: device uploads raw samples and the backend runs the reference DSP."""
        session_or_404(r.session_id)
        try:
            t, acc, mic = raw.to_trial(r)
        except raw.RawError as e:
            raise HTTPException(422, str(e))
        out = post_trial(t)
        if not out["duplicate"]:
            raw.save(raw_dir, t, acc, mic)
        return out

    # ---- evidence and config (laptop) -------------------------------------
    @app.get("/evidence", dependencies=[Depends(device_auth)])
    def evidence(include_simulated: bool = True) -> dict:
        return st.evidence_summary(include_simulated)

    @app.get("/evidence.csv", dependencies=[Depends(device_auth)], response_class=PlainTextResponse)
    def evidence_csv(include_simulated: bool = True) -> str:
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=Store.EVIDENCE_FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(st.evidence_rows(include_simulated))
        return buf.getvalue()

    @app.get("/config", dependencies=[Depends(device_auth)])
    def config() -> dict:
        return {"thresholds": asdict(st.th), "dsp": asdict(dsp.DspConfig()),
                "phrases": protocol.PHRASES, "tool_wait_s": s.tool_wait_s,
                "agora_ready": s.agora_ready}

    # ---- agent tools (called by Agora) -----------------------------------
    def _no_session() -> dict:
        return {"status": "no_session", "say": "No measurement session is running. Ask the user to start one on the device."}

    @app.post("/tools/getNextStep", dependencies=[Depends(tool_auth)])
    def tool_next(body: ToolSessionIn) -> dict:
        sess = st.resolve(body.session_id)
        if sess is None:
            return _no_session()
        nxt = sess.next_step_dict()
        return {"status": "ok", "next_step": nxt, "say": nxt["instruction"]}

    @app.post("/tools/getLatestTrial", dependencies=[Depends(tool_auth)])
    async def tool_latest(body: ToolLatestIn) -> dict:
        sess = st.resolve(body.session_id)
        if sess is None:
            return _no_session()
        loop = asyncio.get_running_loop()
        deadline = loop.time() + s.tool_wait_s
        rec = st.latest_unreported(sess)
        while rec is None and loop.time() < deadline:
            await asyncio.sleep(0.1)
            rec = st.latest_unreported(sess)
        if rec is None:
            return speech.pending_response(sess)
        st.check_phrase(sess, rec, body.heard_text)
        st.mark_reported(sess, rec)
        return speech.latest_trial_response(sess, rec)

    @app.post("/tools/getSummary", dependencies=[Depends(tool_auth)])
    def tool_summary(body: ToolSessionIn) -> dict:
        sess = st.resolve(body.session_id)
        if sess is None:
            return _no_session()
        return {"status": "ok", **speech.summary_response(st, sess)}

    return app


app = create_app()
