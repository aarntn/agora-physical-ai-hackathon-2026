"""Generate SIMULATED parity vectors for the C port (firmware/nasocheck_dsp).

Each file: line 1 "fs_imu fs_mic n_accel n_mic", line 2 the Python reference
result "ratio_valid ratio_db spread_db voiced_frames mic_clipped snr_valid snr_db",
then n_accel lines "x y z", then n_mic lines of int16 mic samples.

    python scripts/make_dsp_vectors.py ../fixtures/dsp_vectors
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nasocheck import dsp, synth  # noqa: E402

CASES = {
    "oral": dict(coupling_db=-20, seed=1),
    "nasal_jitter": dict(coupling_db=-8, jitter_db=3, seed=2),
    "clipped_odd_rate": dict(coupling_db=-14, clip=True, fs_imu=1594.0, seed=3),
}
SHORT = dict(lead_in_s=0.3, voiced_s=0.8, tail_s=0.1)


def main(out_dir: str) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, kw in CASES.items():
        c = synth.capture(**SHORT, **kw)
        mic_i16 = np.clip(np.round(c["mic"] * 32768), -32768, 32767).astype(np.int16)
        accel = c["accel"].astype(np.float32)
        f = dsp.analyze(accel.astype(float), c["fs_imu"], mic_i16 / 32768.0, c["fs_mic"])
        lines = [f"{c['fs_imu']} {c['fs_mic']} {len(accel)} {len(mic_i16)}",
                 f"{int(f.ratio_db is not None)} {f.ratio_db or 0:.6f} {f.spread_db or 0:.6f} "
                 f"{f.voiced_frames} {int(f.mic_clipped)} {int(f.accel_snr_db is not None)} "
                 f"{f.accel_snr_db or 0:.6f}"]
        lines += [f"{x:.9g} {y:.9g} {z:.9g}" for x, y, z in accel]
        lines += [str(int(s)) for s in mic_i16]
        (out / f"{name}.txt").write_text("\n".join(lines) + "\n", encoding="ascii")
        print(name, f)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "../fixtures/dsp_vectors")
