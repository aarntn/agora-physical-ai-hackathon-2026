import numpy as np
import pytest

from nasocheck import dsp, synth


def run(**kw):
    c = synth.capture(**kw)
    return dsp.analyze(c["accel"], c["fs_imu"], c["mic"], c["fs_mic"])


def test_ratio_tracks_coupling():
    hum, oral, nasal = run(coupling_db=0), run(coupling_db=-20), run(coupling_db=-8)
    assert oral.ratio_db < nasal.ratio_db < hum.ratio_db
    assert (hum.ratio_db - oral.ratio_db) == pytest.approx(20, abs=1.5)
    assert (nasal.ratio_db - oral.ratio_db) == pytest.approx(12, abs=1.5)


def test_ratio_is_loudness_invariant():
    quiet, loud = run(coupling_db=-15, mic_level=0.1), run(coupling_db=-15, mic_level=0.5)
    assert quiet.ratio_db == pytest.approx(loud.ratio_db, abs=0.5)


def test_voiced_frames_and_snr():
    f = run(coupling_db=-15)
    assert 35 <= f.voiced_frames <= 42          # 1.6 s voiced / 40 ms
    assert f.accel_snr_db is not None and f.accel_snr_db > 6
    assert not f.mic_clipped


def test_silence_gives_no_ratio():
    f = run(coupling_db=0, silent=True)
    assert f.voiced_frames == 0 and f.ratio_db is None


def test_clipping_detected():
    assert run(coupling_db=-15, clip=True).mic_clipped


def test_movement_increases_spread():
    assert run(coupling_db=-15).spread_db < 1
    assert run(coupling_db=-15, jitter_db=4).spread_db > 4


def test_single_axis_input_and_short_input():
    c = synth.capture(coupling_db=-10)
    f = dsp.analyze(c["accel"][:, 0], c["fs_imu"], c["mic"], c["fs_mic"])
    assert f.ratio_db is not None
    f = dsp.analyze(np.zeros(10), 1600, np.zeros(100), 16000)
    assert f.ratio_db is None and f.voiced_frames == 0


def test_percentile_matches_numpy():
    x = np.random.default_rng(1).normal(size=37)
    for p in (25, 50, 75):
        assert dsp.percentile(x, p) == pytest.approx(np.percentile(x, p))


def test_measured_rate():
    t = np.arange(1594) / 1594.0
    assert dsp.measured_rate(t) == pytest.approx(1594, rel=1e-6)
