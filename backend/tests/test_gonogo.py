import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import gonogo  # noqa: E402

from nasocheck import synth  # noqa: E402


def write_capture(folder: Path, stem: str, coupling_db: float, seed: int, silent=False):
    c = synth.capture(coupling_db=coupling_db, seed=seed, silent=silent)
    t = np.arange(len(c["accel"])) / c["fs_imu"]
    np.savetxt(folder / f"{stem}.accel.csv", np.column_stack([t, c["accel"]]),
               delimiter=",", header="t_s,ax,ay,az", comments="")
    with wave.open(str(folder / f"{stem}.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(c["fs_mic"]))
        w.writeframes((np.clip(c["mic"], -1, 1) * 32767).astype("<i2").tobytes())


def test_raw_go(tmp_path):
    for p in ("P1", "P2"):
        for i in range(3):
            write_capture(tmp_path, f"{p}_a_{i}", -22 + i, seed=i)
            write_capture(tmp_path, f"{p}_m_{i}", -2 - i, seed=10 + i)
    rows, raw = gonogo.load_raw(tmp_path)
    assert len(rows) == 12 and all(abs(r["imu_hz"] - 1600) < 1 for r in rows)
    assert gonogo.verdict(rows, 6.0) is True


def test_table_nogo_when_overlap(tmp_path):
    csv = tmp_path / "r.csv"
    csv.write_text("person,label,ratio_db\nP1,a,-10\nP1,m,-6\nP2,a,-20\nP2,m,-2\n")
    assert gonogo.verdict(gonogo.load_table(csv), 6.0) is False


def test_table_control_too_close(tmp_path):
    csv = tmp_path / "r.csv"
    csv.write_text("person,label,ratio_db\nP1,a,-20\nP1,m,-2\nP1,control,-5\n")
    assert gonogo.verdict(gonogo.load_table(csv), 6.0) is False


def test_suggest_thresholds():
    import suggest_thresholds as sug
    rows = [{"type": "oral", "spread_db": str(s), "voiced_frames": "40", "accel_snr_db": "15"}
            for s in (0.5, 1.0, 1.5, 2.0, 2.5, 3.0)]
    rows.append({"type": "control", "spread_db": "", "voiced_frames": "30", "accel_snr_db": "5"})
    v = sug.suggest(rows)["values"]
    assert v["NC_MAX_SPREAD_DB"] == 3.9 and v["NC_MIN_ACCEL_SNR_DB"] == 8.0
    assert v["NC_MIN_VOICED_FRAMES"] == 15
    assert "spread" in sug.suggest(rows[:2])["notes"][0]
