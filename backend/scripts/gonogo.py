"""Go/no-go analysis (docs/NASOCHECK.md §10).

Mode A, trial table (what the device computed):
    python scripts/gonogo.py results.csv
    columns: person,label,ratio_db[,voiced_frames,accel_snr_db,spread_db,position]
    label: a | m | control

Mode B, raw captures logged to the laptop:
    python scripts/gonogo.py --raw captures/ [--plot evidence.png]
    files: <person>_<label>_<n>.accel.csv  (t_s,ax,ay,az)  +  <person>_<label>_<n>.wav (mono)

GO if, for every person, every /m/ is >= --margin dB above every /a/ and
every /m/ is >= --margin dB above every control trial.
"""
from __future__ import annotations

import argparse
import csv
import sys
import wave
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nasocheck import dsp  # noqa: E402


def read_wav(path: Path) -> tuple[np.ndarray, float]:
    with wave.open(str(path), "rb") as w:
        if w.getsampwidth() != 2:
            raise ValueError(f"{path}: need 16-bit PCM")
        x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(float) / 32768.0
        if w.getnchannels() > 1:
            x = x.reshape(-1, w.getnchannels())[:, 0]
        return x, float(w.getframerate())


def load_raw(folder: Path) -> tuple[list[dict], dict]:
    rows, raw = [], {}
    for acc in sorted(folder.glob("*.accel.csv")):
        stem = acc.name[: -len(".accel.csv")]
        person, label = stem.split("_")[:2]
        d = np.loadtxt(acc, delimiter=",", skiprows=1)
        t, xyz = d[:, 0], d[:, 1:4]
        fs_imu = dsp.measured_rate(t)
        mic, fs_mic = read_wav(folder / f"{stem}.wav")
        f = dsp.analyze(xyz, fs_imu, mic, fs_mic)
        rows.append({"person": person, "label": label, "ratio_db": f.ratio_db,
                     "voiced_frames": f.voiced_frames, "accel_snr_db": f.accel_snr_db,
                     "spread_db": f.spread_db, "imu_hz": round(fs_imu, 1), "file": stem})
        raw[stem] = (t, xyz)
    return rows, raw


def load_table(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["ratio_db"] = float(r["ratio_db"]) if r.get("ratio_db") not in (None, "") else None
    return rows


def verdict(rows: list[dict], margin: float) -> bool:
    by = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if r["ratio_db"] is not None:
            by[r["person"]][r["label"]].append(r["ratio_db"])
    if len(by) < 2:
        print(f"WARNING: protocol asks for two people; got {len(by)}")
    ok_all = True
    print(f"\n{'person':8} {'n_a':>4} {'n_m':>4} {'max a':>8} {'min m':>8} {'max ctl':>8} {'m-a gap':>8} {'m-ctl':>8}  result")
    for person, d in sorted(by.items()):
        a, m, ctl = d.get("a", []), d.get("m", []), d.get("control", [])
        if not a or not m:
            print(f"{person:8} missing /a/ or /m/ trials -> NO-GO")
            ok_all = False
            continue
        gap = min(m) - max(a)
        cgap = (min(m) - max(ctl)) if ctl else None
        ok = gap >= margin and (cgap is None or cgap >= margin)
        if cgap is None:
            print(f"  note: {person} has no control trial; control check skipped")
        ok_all &= ok
        print(f"{person:8} {len(a):4d} {len(m):4d} {max(a):8.1f} {min(m):8.1f} "
              f"{(max(ctl) if ctl else float('nan')):8.1f} {gap:8.1f} "
              f"{(cgap if cgap is not None else float('nan')):8.1f}  {'GO' if ok else 'NO-GO'}")
    print(f"\nOVERALL: {'GO' if ok_all else 'NO-GO'} (margin {margin} dB)")
    return ok_all


def plot(raw: dict, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    pick = {lab: next((k for k in raw if f"_{lab}_" in k), None) for lab in ("a", "m")}
    fig, axes = plt.subplots(2, 1, figsize=(9, 5), sharex=True, sharey=True)
    for ax, (lab, key) in zip(axes, pick.items()):
        if key is None:
            continue
        t, xyz = raw[key]
        ax.plot(t - t[0], np.linalg.norm(xyz - xyz.mean(axis=0), axis=1), lw=0.5)
        ax.set_title(f"{key}: /{'a' if lab == 'a' else 'm'}/  (accelerometer magnitude, DC removed)")
    axes[-1].set_xlabel("time (s)")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    print(f"plot written to {out}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("table", nargs="?")
    ap.add_argument("--raw")
    ap.add_argument("--margin", type=float, default=6.0)
    ap.add_argument("--plot")
    ap.add_argument("--out-csv", help="write per-trial table (evidence)")
    a = ap.parse_args()
    if a.raw:
        rows, raw = load_raw(Path(a.raw))
    elif a.table:
        rows, raw = load_table(Path(a.table)), {}
    else:
        ap.error("give a results CSV or --raw folder")
    for r in rows:
        print({k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items()})
    ok = verdict(rows, a.margin)
    if a.out_csv and rows:
        with open(a.out_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    if a.plot and raw:
        plot(raw, Path(a.plot))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
