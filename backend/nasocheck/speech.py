"""Tool responses for the agent. Every number the agent speaks comes from here.

Each response carries `say`: a ready sentence in the session language that the
system prompt tells the agent to read without changing any number.
"""
from __future__ import annotations

from . import protocol
from .store import MEANINGFUL_CHANGE_DB, MIN_TRIALS_FOR_COMPARISON, Session, Store, TrialRecord

UNIT = {"en": "decibels", "ms": "desibel"}
MINUS = {"en": "minus", "ms": "negatif"}


def spoken_db(x: float, lang: str) -> str:
    v = round(x, 1)
    if v == 0:
        v = 0.0  # avoid "-0.0"
    num = f"{abs(v):.1f}"
    if lang == "ms":
        num = num.replace(".", " perpuluhan ")
    return f"{MINUS[lang] + ' ' if v < 0 else ''}{num} {UNIT[lang]}"


def _valid_text(s: Session, rec: TrialRecord, score: float) -> str:
    L, d = s.lang, spoken_db(score, s.lang)
    if rec.type == "hum":
        return {"en": f"Calibrated. Your hum is the reference point, {d}.",
                "ms": f"Kalibrasi selesai. Dengungan anda ialah titik rujukan, {d}."}[L]
    if rec.type == "oral":
        return {"en": f"Got it. Your score for that phrase is {d}. Closer to zero means more sound through the nose.",
                "ms": f"Baik. Skor untuk ayat itu ialah {d}. Lebih dekat kepada sifar bermakna lebih banyak bunyi melalui hidung."}[L]
    if rec.type == "nasal":
        oral = next((s.score(r) for r in reversed(s.trials[:rec.seq])
                     if r.type == "oral" and s.score(r) is not None
                     and r.expected_phrase == rec.expected_phrase), None)
        if oral is None:
            return {"en": f"Your nasal score is {d}.", "ms": f"Skor sengau anda ialah {d}."}[L]
        # difference of the *spoken* (rounded) values, so the numbers the
        # user hears always add up and match the summary
        diff = spoken_db(round(score, 1) - round(oral, 1), L)
        return {"en": f"Your nasal score is {d}. That is {diff} above your normal version.",
                "ms": f"Skor sengau anda ialah {d}. Itu {diff} lebih tinggi daripada sebutan biasa."}[L]
    return {"en": f"Control reading recorded: {d}.", "ms": f"Bacaan kawalan direkodkan: {d}."}[L]


def latest_trial_response(s: Session, rec: TrialRecord) -> dict:
    view = s.trial_view(rec)
    status, L = view["status"], s.lang
    if status == "valid":
        say = _valid_text(s, rec, s.score(rec))  # type: ignore[arg-type]
    elif status == "needs_calibration":
        say = {"en": "Before that counts, I need a calibration hum.",
               "ms": "Sebelum itu dikira, saya perlukan dengungan kalibrasi."}[L]
    else:
        say = " ".join(protocol.reason_text(c, L, rec.expected_phrase) for c in view["reasons"])
    nxt = s.next_step_dict()
    say = f"{say} {nxt['instruction']}"
    if rec.trial.simulated:
        say = "[SIMULATED DATA] " + say
    return {**view, "say": say, "next_step": nxt}


def pending_response(s: Session) -> dict:
    nxt = s.next_step_dict()
    say = {"en": "No new measurement yet.", "ms": "Belum ada ukuran baharu."}[s.lang]
    return {"status": "pending", "say": f"{say} {nxt['instruction']}", "next_step": nxt}


def summary_response(store: Store, s: Session) -> dict:
    st = store.stats(s)
    L, m = s.lang, st["mean_score_db"]
    parts = []
    if m["oral"] is None:
        parts.append({"en": "There are no valid phrase measurements yet.",
                      "ms": "Belum ada ukuran ayat yang sah."}[L])
    else:
        parts.append({"en": f"Average score for normal speech: {spoken_db(m['oral'], L)}.",
                      "ms": f"Purata skor untuk sebutan biasa: {spoken_db(m['oral'], L)}."}[L])
    if st["nasal_minus_oral_db"] is not None:
        parts.append({"en": f"Speaking through the nose was {spoken_db(st['nasal_minus_oral_db'], L)} higher.",
                      "ms": f"Sebutan melalui hidung {spoken_db(st['nasal_minus_oral_db'], L)} lebih tinggi."}[L])
    parts.append({"en": f"{st['rejected']} attempts were repeated.",
                  "ms": f"{st['rejected']} percubaan diulang."}[L])

    prev = store.previous_session(s)
    change = None
    enough = st["valid_counts"]["oral"] >= MIN_TRIALS_FOR_COMPARISON
    if prev and m["oral"] is not None and not enough:
        parts.append({"en": "I need at least two good phrase readings to compare with last session.",
                      "ms": "Saya perlukan sekurang-kurangnya dua bacaan ayat yang baik untuk dibandingkan dengan sesi lepas."}[L])
    if prev and m["oral"] is not None and enough:
        prev_oral = store.stats(prev)["mean_score_db"]["oral"]
        change = round(m["oral"] - prev_oral, 1)
        if abs(change) < MEANINGFUL_CHANGE_DB:
            parts.append({"en": "That is about the same as last session.",
                          "ms": "Itu lebih kurang sama dengan sesi lepas."}[L])
        elif change < 0:
            parts.append({"en": f"That is {spoken_db(-change, L)} lower than last session, so less sound escaped through the nose.",
                          "ms": f"Itu {spoken_db(-change, L)} lebih rendah daripada sesi lepas, jadi kurang bunyi keluar melalui hidung."}[L])
        else:
            parts.append({"en": f"That is {spoken_db(change, L)} higher than last session. Your therapist can help interpret this.",
                          "ms": f"Itu {spoken_db(change, L)} lebih tinggi daripada sesi lepas. Ahli terapi anda boleh membantu mentafsir."}[L])
    say = " ".join(parts)
    if st["simulated_trials"]:
        say = "[SIMULATED DATA] " + say
    return {**st, "change_vs_previous_oral_db": change,
            "previous_session_id": prev.session_id if prev else None, "say": say}


def therapist_report(store: Store, s: Session) -> str:
    """Plain-text session report for the supervising therapist (English, clinical tone).

    Parent-delivered practice works best under therapist supervision
    (ASHA Perspectives 2023), so every session is reviewable.
    """
    st = store.stats(s)
    m = st["mean_score_db"]
    lines = [f"NasoCheck session report: {s.session_id}",
             f"Client ref: {s.user_ref}   Language: {s.lang}   Trials: {len(s.trials)}",
             "", f"{'#':>2}  {'type':7} {'status':18} {'score dB':>8} {'spread':>6}  phrase / reasons"]
    for r in s.trials:
        v = s.trial_view(r)
        sc = "-" if v["score_db"] is None else f"{v['score_db']:.1f}"
        sp = "-" if v["spread_db"] is None else f"{v['spread_db']:.1f}"
        detail = ", ".join(v["reasons"]) or (v["phrase"] or "")
        lines.append(f"{r.seq + 1:>2}  {v['type']:7} {v['status']:18} {sc:>8} {sp:>6}  {detail}")
    lines += ["", f"Mean score (valid): oral {m['oral']}, nasal {m['nasal']}, control {m['control']} dB",
              f"Nasal minus oral: {st['nasal_minus_oral_db']} dB   Repeated (rejected) attempts: {st['rejected']}"]
    prev = store.previous_session(s)
    if prev:
        lines.append(f"Previous session: {prev.session_id}, mean oral "
                     f"{store.stats(prev)['mean_score_db']['oral']} dB")
    if st["simulated_trials"]:
        lines.append(f"WARNING: {st['simulated_trials']} trials are SIMULATED test data.")
    lines += ["", "Interpretation: score = nasal skin vibration relative to voice level, 0 dB = the client's own hum.",
              "Higher (closer to 0) means more nasal coupling. This is a physical measure that correlates with",
              "airflow more than with perceptual ratings; it tracks change and is not a diagnosis.",
              f"Changes under {MEANINGFUL_CHANGE_DB:.0f} dB, or with fewer than {MIN_TRIALS_FOR_COMPARISON} valid trials, are not interpreted."]
    return "\n".join(lines) + "\n"
