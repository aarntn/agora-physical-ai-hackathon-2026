"""Deterministic trial validation and scoring. The agent never computes numbers."""
from __future__ import annotations

from dataclasses import dataclass

from .contracts import TrialIn


@dataclass(frozen=True)
class Thresholds:
    """Initial guesses from the proposal (§8); tune on the day, then freeze."""
    min_voiced_frames: int = 15
    min_accel_snr_db: float = 6.0
    max_spread_db: float = 4.0
    min_imu_hz: float = 1000.0


def rejection_reasons(t: TrialIn, th: Thresholds = Thresholds()) -> list[str]:
    """Reason codes (see protocol.REASONS). Empty list = acceptable signal."""
    reasons: list[str] = []
    if t.imu_hz < th.min_imu_hz:
        reasons.append("sensor_rate")
    if t.mic_clipped:
        reasons.append("clipped")
    if t.type == "control":
        # Control = silent wearer, someone else talking. Low SNR is expected.
        return reasons
    if t.voiced_frames < th.min_voiced_frames:
        reasons.append("too_short")
    if t.ratio_db is None:
        reasons.append("no_ratio")
    if t.accel_snr_db is not None and t.accel_snr_db < th.min_accel_snr_db:
        reasons.append("weak_vibration")
    if t.spread_db is not None and t.spread_db > th.max_spread_db:
        reasons.append("unstable")
    return reasons


def median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def score_db(ratio_db: float, calibration_db: float) -> float:
    """HONC score: 20*log10(k*A/M) with k = M/A at the hum  ==  ratio - ratio_hum."""
    return ratio_db - calibration_db
