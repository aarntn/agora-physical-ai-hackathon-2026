"""Reference implementation of the NasoCheck trial analysis (HONC-style ratio).

This is the *specification* for the firmware port in firmware/nasocheck_dsp/.
Keep the two in lock-step: same filters (RBJ biquads), same framing, same
voicing rule, same percentile definition. Cross-checked by
fixtures/dsp_vectors (see backend/scripts/make_dsp_vectors.py).

Units: accelerometer in any linear unit (g or raw counts), mic in float
full-scale [-1, 1]. Absolute units cancel out after hum calibration.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict

import numpy as np
from scipy.signal import lfilter


@dataclass(frozen=True)
class DspConfig:
    frame_s: float = 0.040
    hpf_hz: float = 80.0
    accel_lpf_hz: float = 700.0
    # Low-pass the mic to the same band as the accelerometer so both signals
    # describe the same frequencies. Deviation from the proposal text (which
    # only low-passes the accelerometer); toggle to compare on the day.
    match_bands: bool = True
    voiced_rel_db: float = 25.0     # frame voiced if within this many dB of the loudest frame
    voiced_floor_dbfs: float = -55.0  # ...and above this absolute mic level
    clip_level: float = 0.98
    clip_min_samples: int = 3
    skip_frames: int = 1            # discard filter-settling frames at the start


@dataclass
class TrialFeatures:
    ratio_db: float | None
    spread_db: float | None
    voiced_frames: int
    mic_clipped: bool
    accel_snr_db: float | None
    imu_hz: float
    frames: int

    def to_dict(self) -> dict:
        return asdict(self)


def biquad(kind: str, fc: float, fs: float, q: float = 1 / math.sqrt(2)) -> tuple[np.ndarray, np.ndarray]:
    """RBJ audio-EQ-cookbook 2nd-order Butterworth (q=1/sqrt2) coefficients, a0-normalised."""
    w0 = 2 * math.pi * fc / fs
    alpha = math.sin(w0) / (2 * q)
    c = math.cos(w0)
    if kind == "lp":
        b = [(1 - c) / 2, 1 - c, (1 - c) / 2]
    elif kind == "hp":
        b = [(1 + c) / 2, -(1 + c), (1 + c) / 2]
    else:
        raise ValueError(kind)
    a = [1 + alpha, -2 * c, 1 - alpha]
    return np.array(b) / a[0], np.array(a) / a[0]


def lpf_usable(fc: float, fs: float) -> bool:
    """Skip a low-pass whose cutoff is too close to Nyquist to be meaningful."""
    return fc < 0.45 * fs


def bandlimit(x: np.ndarray, fs: float, hpf_hz: float, lpf_hz: float | None) -> np.ndarray:
    b, a = biquad("hp", hpf_hz, fs)
    y = lfilter(b, a, x, axis=0)
    if lpf_hz is not None and lpf_usable(lpf_hz, fs):
        b, a = biquad("lp", lpf_hz, fs)
        y = lfilter(b, a, y, axis=0)
    return y


def frame_len(fs: float, frame_s: float) -> int:
    return max(1, int(round(fs * frame_s)))


def percentile(values: np.ndarray, p: float) -> float:
    """Linear-interpolation percentile (numpy default); mirrored in C."""
    v = np.sort(np.asarray(values, dtype=float))
    pos = p / 100.0 * (len(v) - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(v) - 1)
    return float(v[lo] + (v[hi] - v[lo]) * (pos - lo))


def _frame_rms(x: np.ndarray, L: int, n: int) -> np.ndarray:
    """RMS per frame; x is (N,) or (N, axes). Vector RMS across axes."""
    x = x[: n * L]
    if x.ndim == 1:
        x = x[:, None]
    sq = (x.astype(float) ** 2).sum(axis=1)
    return np.sqrt(sq.reshape(n, L).mean(axis=1))


def _db(x: float | np.ndarray) -> float | np.ndarray:
    return 20 * np.log10(np.maximum(x, 1e-12))


def analyze(accel: np.ndarray, fs_imu: float, mic: np.ndarray, fs_mic: float,
            cfg: DspConfig = DspConfig()) -> TrialFeatures:
    """Analyse one ~2 s capture. Both streams must start at the same instant.

    accel: (N,) or (N, 3). mic: (M,) float full scale.
    """
    accel = np.asarray(accel, dtype=float)
    mic = np.asarray(mic, dtype=float)

    clipped = int((np.abs(mic) >= cfg.clip_level).sum()) >= cfg.clip_min_samples

    acc_f = bandlimit(accel, fs_imu, cfg.hpf_hz, cfg.accel_lpf_hz)
    mic_f = bandlimit(mic, fs_mic, cfg.hpf_hz, cfg.accel_lpf_hz if cfg.match_bands else None)

    La, Lm = frame_len(fs_imu, cfg.frame_s), frame_len(fs_mic, cfg.frame_s)
    n = min(len(acc_f) // La, len(mic_f) // Lm)
    if n <= cfg.skip_frames:
        return TrialFeatures(None, None, 0, clipped, None, fs_imu, max(n, 0))

    a_rms = _frame_rms(acc_f, La, n)[cfg.skip_frames:]
    m_rms = _frame_rms(mic_f, Lm, n)[cfg.skip_frames:]
    m_db = _db(m_rms)

    thr = max(float(m_db.max()) - cfg.voiced_rel_db, cfg.voiced_floor_dbfs)
    voiced = m_db >= thr
    nv = int(voiced.sum())

    ratio = spread = snr = None
    if nv > 0:
        r = _db(a_rms[voiced]) - m_db[voiced]
        ratio = percentile(r, 50)
        spread = percentile(r, 75) - percentile(r, 25)
    unv = ~voiced
    if nv > 0 and unv.sum() >= 2:
        noise = percentile(a_rms[unv], 50)
        sig = percentile(a_rms[voiced], 50)
        snr = float(_db(sig) - _db(noise))

    return TrialFeatures(ratio, spread, nv, clipped, snr, fs_imu, len(a_rms))


def measured_rate(timestamps_s: np.ndarray) -> float:
    """Actual sample rate from timestamps (go/no-go step 1)."""
    t = np.asarray(timestamps_s, dtype=float)
    if len(t) < 2 or t[-1] <= t[0]:
        return 0.0
    return (len(t) - 1) / (t[-1] - t[0])
