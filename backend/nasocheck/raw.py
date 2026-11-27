"""Server-side analysis of raw captures (fallback when the device can't run the DSP).

The device sends int16 little-endian samples, base64-encoded:
  accel_b64: interleaved x,y,z (any linear unit; scale cancels after calibration)
  mic_b64:   mono PCM, AGC off
The backend runs the Python reference DSP, and keeps the raw capture as .npz
under <log dir>/raw/ for evidence plots.
"""
from __future__ import annotations

import base64
import binascii
from pathlib import Path

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from . import dsp
from .contracts import ID_PATTERN, TrialIn, TrialType

MAX_CAPTURE_S = 10.0


class RawTrialIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trial_id: str = Field(pattern=ID_PATTERN)
    session_id: str = Field(pattern=ID_PATTERN)
    type: TrialType | None = None
    start_ms: int = Field(default=0, ge=0)
    imu_hz: float = Field(gt=0, le=10000, description="measured from timestamps, not configured ODR")
    mic_hz: float = Field(default=16000, gt=0, le=96000)
    # Bounded before decoding: 10 s of 3-axis int16 at 10 kHz, 10 s of int16 at 48 kHz.
    accel_b64: str = Field(max_length=1_000_000)
    mic_b64: str = Field(max_length=1_300_000)
    phrase_confirmed: bool = False
    simulated: bool = False


class RawError(ValueError):
    pass


def _decode_i16(b64: str, name: str) -> np.ndarray:
    try:
        buf = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError) as e:
        raise RawError(f"{name}: invalid base64") from e
    if len(buf) % 2:
        raise RawError(f"{name}: odd byte count")
    return np.frombuffer(buf, dtype="<i2")


def decode(r: RawTrialIn) -> tuple[np.ndarray, np.ndarray]:
    acc = _decode_i16(r.accel_b64, "accel_b64")
    if len(acc) % 3:
        raise RawError("accel_b64: sample count not a multiple of 3 (x,y,z)")
    acc = acc.reshape(-1, 3).astype(float)
    mic = _decode_i16(r.mic_b64, "mic_b64").astype(float) / 32768.0
    if len(acc) / r.imu_hz > MAX_CAPTURE_S or len(mic) / r.mic_hz > MAX_CAPTURE_S:
        raise RawError(f"capture longer than {MAX_CAPTURE_S} s")
    if len(acc) / r.imu_hz < 0.5 or len(mic) / r.mic_hz < 0.5:
        raise RawError("capture shorter than 0.5 s")
    return acc, mic


def to_trial(r: RawTrialIn, cfg: dsp.DspConfig = dsp.DspConfig()) -> tuple[TrialIn, np.ndarray, np.ndarray]:
    acc, mic = decode(r)
    f = dsp.analyze(acc, r.imu_hz, mic, r.mic_hz, cfg)
    dur_ms = int(1000 * len(mic) / r.mic_hz)
    try:
        t = _make_trial(r, f, dur_ms)
    except ValidationError as e:
        raise RawError(f"computed features out of range: {e.errors()[0]['loc']}") from e
    return t, acc, mic


def _make_trial(r: RawTrialIn, f: dsp.TrialFeatures, dur_ms: int) -> TrialIn:
    return TrialIn(trial_id=r.trial_id, session_id=r.session_id, type=r.type,
                start_ms=r.start_ms, end_ms=r.start_ms + dur_ms,
                ratio_db=f.ratio_db, spread_db=f.spread_db, voiced_frames=f.voiced_frames,
                mic_clipped=f.mic_clipped, accel_snr_db=f.accel_snr_db, imu_hz=r.imu_hz,
                phrase_confirmed=r.phrase_confirmed, simulated=r.simulated)


def save(raw_dir: Path, t: TrialIn, acc: np.ndarray, mic: np.ndarray) -> Path:
    d = raw_dir / t.session_id
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{t.trial_id}.npz"
    np.savez_compressed(p, accel=acc.astype(np.int16), mic=(mic * 32768).astype(np.int16),
                        imu_hz=t.imu_hz, simulated=t.simulated)
    return p


def encode_capture(accel: np.ndarray, mic: np.ndarray, accel_scale: float = 10000.0) -> tuple[str, str]:
    """Helper for clients/tests: float arrays -> base64 int16.

    accel_scale must be the SAME for every trial in a session (like a fixed
    sensor range); a per-capture scale would break the hum calibration.
    """
    a = np.clip(np.round(np.asarray(accel, dtype=float) * accel_scale), -32768, 32767)
    a16 = a.astype("<i2")
    m16 = np.clip(np.round(np.asarray(mic) * 32768), -32768, 32767).astype("<i2")
    return base64.b64encode(a16.tobytes()).decode(), base64.b64encode(m16.tobytes()).decode()
