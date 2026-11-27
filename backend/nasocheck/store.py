"""Sessions, trials and the append-only event log.

All protocol state (current step, calibration, scores) is *derived* from the
ordered trial list, so a late phrase-check rejection or a retried POST can never
leave the session inconsistent. Events are appended to a JSONL file and
replayed on startup.
"""
from __future__ import annotations

import json
import math
import secrets
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import protocol
from .contracts import SessionIn, TrialIn
from .scoring import Thresholds, median, rejection_reasons, score_db

# Changes smaller than this are reported as "about the same" (proposal ยง3:
# test-retest is only moderate). Assumption; revisit with real data.
MEANINGFUL_CHANGE_DB = 3.0
# Single-trial HONC readings have only moderate test-retest reliability
# (Varghese et al. 2014), so session comparisons need repeated trials.
MIN_TRIALS_FOR_COMPARISON = 2


def now_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class TrialRecord:
    trial: TrialIn
    seq: int
    step_index: int | None
    expected_phrase: str | None
    received_ms: int
    signal_reasons: list[str]
    phrase_status: str = "unchecked"  # unchecked | ok | wrong | override | n/a
    heard_text: str | None = None
    reported: bool = False

    @property
    def type(self) -> str:
        assert self.trial.type is not None
        return self.trial.type


@dataclass
class Session:
    session_id: str
    user_ref: str
    lang: str
    pairs: int
    created_ms: int
    trials: list[TrialRecord] = field(default_factory=list)
    agent_id: str | None = None

    @property
    def steps(self) -> list[protocol.Step]:
        return protocol.steps_for(self.lang, self.pairs)

    # ---- derived state -------------------------------------------------
    def reasons(self, rec: TrialRecord) -> list[str]:
        r = list(rec.signal_reasons)
        if rec.phrase_status == "wrong":
            r.append("wrong_phrase")
        return r

    def calibration_before(self, seq: int) -> float | None:
        hums = [r.trial.ratio_db for r in self.trials
                if r.seq < seq and r.type == "hum" and not self.reasons(r)
                and r.trial.ratio_db is not None]
        return median(hums) if hums else None

    def status(self, rec: TrialRecord) -> str:
        if self.reasons(rec):
            return "rejected"
        if rec.type in ("oral", "nasal") and self.calibration_before(rec.seq) is None:
            return "needs_calibration"
        return "valid"

    def score(self, rec: TrialRecord) -> float | None:
        if self.status(rec) != "valid" or rec.trial.ratio_db is None:
            return None
        if rec.type == "hum":
            cal = self.calibration_before(rec.seq + 1)  # includes itself
        else:
            cal = self.calibration_before(rec.seq)
        return None if cal is None else score_db(rec.trial.ratio_db, cal)

    def position(self) -> int:
        idx, steps = 0, self.steps
        for r in self.trials:
            if idx < len(steps) and r.step_index == idx and self.status(r) == "valid":
                idx += 1
        return idx

    def current_step(self) -> protocol.Step | None:
        i, steps = self.position(), self.steps
        return steps[i] if i < len(steps) else None

    def next_step_dict(self) -> dict:
        st = self.current_step()
        return {"type": st.type if st else "done",
                "phrase": st.phrase if st else None,
                "instruction": protocol.instruction(st, self.lang),
                "step": self.position(), "total_steps": len(self.steps)}

    def trial_view(self, rec: TrialRecord) -> dict:
        sc = self.score(rec)
        return {"trial_id": rec.trial.trial_id, "type": rec.type, "status": self.status(rec),
                "score_db": None if sc is None else round(sc, 1),
                "ratio_db": rec.trial.ratio_db, "spread_db": rec.trial.spread_db,
                "reasons": self.reasons(rec), "phrase": rec.expected_phrase,
                "phrase_status": rec.phrase_status, "simulated": rec.trial.simulated,
                "received_ms": rec.received_ms}


class Store:
    def __init__(self, log_path: Path | None, thresholds: Thresholds = Thresholds()):
        self.log_path = log_path
        self.th = thresholds
        self.sessions: dict[str, Session] = {}
        self.active_session_id: str | None = None
        self._lock = threading.RLock()
        if log_path and log_path.exists():
            self._replay()

    # ---- persistence ----------------------------------------------------
    def _append(self, event: dict) -> None:
        if not self.log_path:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, separators=(",", ":")) + "\n")

    def _replay(self) -> None:
        assert self.log_path
        for line in self.log_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            e = json.loads(line)
            k = e["kind"]
            if k == "session":
                self._create(e["session_id"], SessionIn(**e["spec"]), e["created_ms"], log=False)
            elif k == "agent":
                self.sessions[e["session_id"]].agent_id = e["agent_id"]
            elif k == "trial":
                self._add_trial(TrialIn(**e["trial"]), e["received_ms"], log=False)
            elif k == "phrase":
                self._set_phrase(e["session_id"], e["trial_id"], e["heard"], e["status"], log=False)
            elif k == "reported":
                rec = self._find(e["session_id"], e["trial_id"])
                if rec:
                    rec.reported = True

    # ---- sessions -------------------------------------------------------
    def create_session(self, spec: SessionIn) -> Session:
        with self._lock:
            sid = "s" + secrets.token_hex(4)
            return self._create(sid, spec, now_ms(), log=True)

    def _create(self, sid: str, spec: SessionIn, created_ms: int, log: bool) -> Session:
        s = Session(sid, spec.user_ref, spec.lang, spec.pairs, created_ms)
        self.sessions[sid] = s
        self.active_session_id = sid
        if log:
            self._append({"kind": "session", "session_id": sid, "created_ms": created_ms,
                          "spec": spec.model_dump()})
        return s

    def set_agent(self, sid: str, agent_id: str) -> None:
        with self._lock:
            self.sessions[sid].agent_id = agent_id
            self._append({"kind": "agent", "session_id": sid, "agent_id": agent_id})

    def resolve(self, sid: str | None) -> Session | None:
        """Agent tools may omit the id; fall back to the active session."""
        sid = sid or self.active_session_id
        return self.sessions.get(sid) if sid else None

    # ---- trials ---------------------------------------------------------
    def _find(self, sid: str, tid: str) -> TrialRecord | None:
        s = self.sessions.get(sid)
        return next((r for r in s.trials if r.trial.trial_id == tid), None) if s else None

    def add_trial(self, t: TrialIn) -> tuple[TrialRecord, bool]:
        """Returns (record, duplicate). Raises KeyError / ValueError."""
        with self._lock:
            return self._add_trial(t, now_ms(), log=True)

    def _add_trial(self, t: TrialIn, received_ms: int, log: bool) -> tuple[TrialRecord, bool]:
        s = self.sessions.get(t.session_id)
        if s is None:
            raise KeyError(t.session_id)
        existing = self._find(t.session_id, t.trial_id)
        if existing:
            if existing.trial.model_dump(exclude={"type"}) != t.model_dump(exclude={"type"}):
                raise ValueError("trial_id reused with different content")
            return existing, True
        step = s.current_step()
        if t.type is None:
            # after the protocol is done, extra untyped trials count as oral practice
            t = t.model_copy(update={"type": step.type if step else "oral"})
        on_step = step is not None and t.type == step.type
        step_index = s.position() if on_step else None
        phrase = step.phrase if on_step and step else None
        rec = TrialRecord(trial=t, seq=len(s.trials), step_index=step_index,
                          expected_phrase=phrase, received_ms=received_ms,
                          signal_reasons=rejection_reasons(t, self.th))
        if phrase is None:
            rec.phrase_status = "n/a"
        elif t.phrase_confirmed:
            rec.phrase_status = "override"
        s.trials.append(rec)
        if log:
            self._append({"kind": "trial", "received_ms": received_ms,
                          "trial": t.model_dump()})
        return rec, False

    def check_phrase(self, s: Session, rec: TrialRecord, heard: str) -> None:
        """Apply the ASR phrase check. Empty text = could not check (left as is)."""
        if rec.phrase_status != "unchecked" or not heard.strip() or not rec.expected_phrase:
            return
        ok = protocol.phrase_matches(heard, rec.expected_phrase)
        with self._lock:
            self._set_phrase(s.session_id, rec.trial.trial_id, heard, "ok" if ok else "wrong", log=True)

    def _set_phrase(self, sid: str, tid: str, heard: str, status: str, log: bool) -> None:
        rec = self._find(sid, tid)
        if rec is None:
            return
        rec.heard_text, rec.phrase_status = heard, status
        if log:
            self._append({"kind": "phrase", "session_id": sid, "trial_id": tid,
                          "heard": heard, "status": status})

    def latest_unreported(self, s: Session) -> TrialRecord | None:
        """Newest trial the agent has not seen. The agent's heard_text refers to
        the user's latest utterance, so older unseen trials are skipped."""
        return next((r for r in reversed(s.trials) if not r.reported), None)

    def mark_reported(self, s: Session, rec: TrialRecord) -> None:
        """Mark `rec` and every earlier trial as seen by the agent."""
        with self._lock:
            for r in s.trials[: rec.seq + 1]:
                if not r.reported:
                    r.reported = True
                    self._append({"kind": "reported", "session_id": s.session_id,
                                  "trial_id": r.trial.trial_id})

    # ---- summaries ------------------------------------------------------
    def stats(self, s: Session) -> dict:
        by: dict[str, list[float]] = {"hum": [], "oral": [], "nasal": [], "control": []}
        rejected = 0
        for r in s.trials:
            sc = s.score(r)
            if s.status(r) == "rejected":
                rejected += 1
            elif sc is not None:
                by[r.type].append(round(sc, 1))  # average what the user heard
        mean = {k: (round(sum(v) / len(v), 1) if v else None) for k, v in by.items()}
        sep = (round(mean["nasal"] - mean["oral"], 1)
               if mean["nasal"] is not None and mean["oral"] is not None else None)
        return {"valid_counts": {k: len(v) for k, v in by.items()}, "rejected": rejected,
                "mean_score_db": mean, "nasal_minus_oral_db": sep,
                "simulated_trials": sum(r.trial.simulated for r in s.trials)}

    def previous_session(self, s: Session) -> Session | None:
        if s.user_ref == "anon":
            return None
        # creation order (dict insertion order, preserved by replay), not
        # timestamps, which can tie within a millisecond
        order = list(self.sessions.values())
        earlier = order[: order.index(s)]
        prev = [p for p in earlier if p.user_ref == s.user_ref
                and self.stats(p)["valid_counts"]["oral"] >= MIN_TRIALS_FOR_COMPARISON]
        return prev[-1] if prev else None

    # ---- evidence (proposal ง11) -----------------------------------------
    EVIDENCE_FIELDS = ["session_id", "user_ref", "lang", "seq", "trial_id", "type", "status",
                       "score_db", "ratio_db", "spread_db", "voiced_frames", "accel_snr_db",
                       "imu_hz", "mic_clipped", "reasons", "phrase", "phrase_status",
                       "heard_text", "simulated", "received_ms"]

    def evidence_rows(self, include_simulated: bool = True) -> list[dict]:
        rows = []
        for s in self.sessions.values():
            for r in s.trials:
                if r.trial.simulated and not include_simulated:
                    continue
                sc = s.score(r)
                rows.append({
                    "session_id": s.session_id, "user_ref": s.user_ref, "lang": s.lang,
                    "seq": r.seq, "trial_id": r.trial.trial_id, "type": r.type,
                    "status": s.status(r), "score_db": None if sc is None else round(sc, 2),
                    "ratio_db": r.trial.ratio_db, "spread_db": r.trial.spread_db,
                    "voiced_frames": r.trial.voiced_frames, "accel_snr_db": r.trial.accel_snr_db,
                    "imu_hz": r.trial.imu_hz, "mic_clipped": r.trial.mic_clipped,
                    "reasons": "|".join(s.reasons(r)), "phrase": r.expected_phrase,
                    "phrase_status": r.phrase_status, "heard_text": r.heard_text,
                    "simulated": r.trial.simulated, "received_ms": r.received_ms})
        return rows

    def evidence_summary(self, include_simulated: bool = True) -> dict:
        """Per person and trial type: n, mean, SD, range of valid scores."""
        rows = self.evidence_rows(include_simulated)
        groups: dict[str, dict[str, list[float]]] = {}
        rejected: dict[str, int] = {}
        for r in rows:
            u = r["user_ref"]
            groups.setdefault(u, {})
            if r["status"] == "rejected":
                rejected[u] = rejected.get(u, 0) + 1
            elif r["score_db"] is not None:
                groups[u].setdefault(r["type"], []).append(r["score_db"])
        out = {}
        for u, by in groups.items():
            stats = {}
            for typ, v in by.items():
                mean = sum(v) / len(v)
                sd = math.sqrt(sum((x - mean) ** 2 for x in v) / (len(v) - 1)) if len(v) > 1 else None
                stats[typ] = {"n": len(v), "mean": round(mean, 1),
                              "sd": None if sd is None else round(sd, 1),
                              "min": round(min(v), 1), "max": round(max(v), 1)}
            sep = (round(stats["nasal"]["mean"] - stats["oral"]["mean"], 1)
                   if "nasal" in stats and "oral" in stats else None)
            out[u] = {"by_type": stats, "rejected": rejected.get(u, 0), "nasal_minus_oral_db": sep}
        return {"people": out, "trials": len(rows),
                "simulated_trials": sum(r["simulated"] for r in rows)}
