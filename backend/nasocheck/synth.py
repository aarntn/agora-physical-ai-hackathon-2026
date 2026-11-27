"""SIMULATED captures for tests and the fake device. Never present as real data.

Model: a voiced buzz (harmonics of f0) reaches the mic at `mic_level`; the nose
skin vibrates with the same waveform scaled by `coupling_db` (higher = more
nasal), plus white accelerometer noise. A silent lead-in gives the noise floor.
"""
from __future__ import annotations

import numpy as np


def voice(t: np.ndarray, f0: float = 140.0, n_harm: int = 12) -> np.ndarray:
    y = sum(np.sin(2 * np.pi * f0 * k * t) / k for k in range(1, n_harm + 1))
    return y / np.max(np.abs(y))


def capture(coupling_db: float, *, fs_imu: float = 1600.0, fs_mic: float = 16000.0,
            lead_in_s: float = 0.4, voiced_s: float = 1.6, tail_s: float = 0.2,
            mic_level: float = 0.3, accel_noise: float = 0.002, mic_noise: float = 1e-4,
            jitter_db: float = 0.0, seed: int = 0, silent: bool = False,
            clip: bool = False) -> dict:
    rng = np.random.default_rng(seed)
    total = lead_in_s + voiced_s + tail_s

    def env(t):
        e = ((t >= lead_in_s) & (t < lead_in_s + voiced_s)).astype(float)
        return 0.0 * e if silent else e

    tm = np.arange(int(total * fs_mic)) / fs_mic
    mic = mic_level * env(tm) * voice(tm) + mic_noise * rng.standard_normal(len(tm))
    if clip:
        mic = np.clip(mic * 6, -1, 1)

    ta = np.arange(int(total * fs_imu)) / fs_imu
    # slow wobble in coupling models re-placement / articulation variation
    wobble = 10 ** ((jitter_db * np.sin(2 * np.pi * 1.3 * ta + rng.uniform(0, 6))) / 20)
    amp = mic_level * 10 ** (coupling_db / 20) * wobble
    a1 = amp * env(ta) * voice(ta)
    noise = accel_noise * rng.standard_normal((len(ta), 3))
    accel = noise.copy()
    accel[:, 0] += a1 * 0.8
    accel[:, 1] += a1 * 0.6
    return {"accel": accel, "mic": mic, "fs_imu": fs_imu, "fs_mic": fs_mic,
            "simulated": True}
