"""The committed C parity vectors must still match the Python reference."""
from pathlib import Path

import numpy as np
import pytest

from nasocheck import dsp

VECTORS = sorted((Path(__file__).resolve().parents[2] / "fixtures" / "dsp_vectors").glob("*.txt"))


@pytest.mark.parametrize("path", VECTORS, ids=lambda p: p.stem)
def test_vector_matches_reference(path):
    lines = path.read_text().splitlines()
    fs_imu, fs_mic, na, nm = lines[0].split()
    na, nm = int(na), int(nm)
    rv, ratio, spread, voiced, clip, sv, snr = lines[1].split()
    accel = np.loadtxt(lines[2:2 + na])
    mic = np.array(lines[2 + na:2 + na + nm], dtype=float) / 32768.0
    f = dsp.analyze(accel, float(fs_imu), mic, float(fs_mic))
    assert f.voiced_frames == int(voiced) and f.mic_clipped == bool(int(clip))
    assert f.ratio_db == pytest.approx(float(ratio), abs=0.01)
    assert f.spread_db == pytest.approx(float(spread), abs=0.01)
    assert f.accel_snr_db == pytest.approx(float(snr), abs=0.01)


def test_vectors_exist():
    assert len(VECTORS) >= 3
