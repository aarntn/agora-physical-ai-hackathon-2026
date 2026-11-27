"""Suggest rejection thresholds from logged trials (run after go/no-go).

Reads GET /evidence.csv output (or any CSV with the same columns) and prints
NC_* values for .env. Rules (simple, transparent, review before use):
  max_spread_db       = 95th percentile of spread on hum/oral/nasal trials, +1 dB headroom
  min_accel_snr_db    = max(6, 95th percentile SNR of control trials + 3 dB)
                        so a silent wearer (someone else talking) is rejected
  min_voiced_frames   = min(15, 50% of median voiced frames)  (proposal default caps it)
These are starting points from your own device and people, not clinical cutoffs.

    curl -H "X-Device-Key: $DEVICE_KEY" localhost:8000/evidence.csv > trials.csv
    python scripts/suggest_thresholds.py trials.csv
"""
from __future__ import annotations

import csv
import sys

import numpy as np


def _f(v):
    return float(v) if v not in (None, "", "None") else None


def suggest(rows: list[dict]) -> dict:
    speech = [r for r in rows if r["type"] in ("hum", "oral", "nasal")]
    spreads = [x for x in (_f(r["spread_db"]) for r in speech) if x is not None]
    voiced = [int(r["voiced_frames"]) for r in speech]
    ctl_snr = [x for x in (_f(r["accel_snr_db"]) for r in rows if r["type"] == "control") if x is not None]
    out, notes = {}, []
    if len(spreads) >= 5:
        out["NC_MAX_SPREAD_DB"] = round(float(np.percentile(spreads, 95)) + 1.0, 1)
    else:
        notes.append("need >=5 speech trials for spread")
    if ctl_snr:
        out["NC_MIN_ACCEL_SNR_DB"] = round(max(6.0, float(np.percentile(ctl_snr, 95)) + 3.0), 1)
    else:
        notes.append("no control trials: keep NC_MIN_ACCEL_SNR_DB=6")
    if voiced:
        out["NC_MIN_VOICED_FRAMES"] = int(min(15, 0.5 * float(np.median(voiced))))
    return {"values": out, "notes": notes, "n_speech": len(speech), "n_control": len(ctl_snr)}


def main(path: str) -> None:
    with open(path, newline="", encoding="utf-8") as f:
        res = suggest(list(csv.DictReader(f)))
    print(f"# from {res['n_speech']} speech and {res['n_control']} control trials")
    for k, v in res["values"].items():
        print(f"{k}={v}")
    for n in res["notes"]:
        print(f"# note: {n}")


if __name__ == "__main__":
    main(sys.argv[1])
