"""Shared trial contract between firmware and backend (docs/NASOCHECK.md §8)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TrialType = Literal["hum", "oral", "nasal", "control"]
Lang = Literal["en", "ms"]

ID_PATTERN = r"^[A-Za-z0-9_.:-]{1,64}$"


class TrialIn(BaseModel):
    """What the device POSTs after each ~2 s capture."""
    model_config = ConfigDict(extra="forbid")

    trial_id: str = Field(pattern=ID_PATTERN)
    session_id: str = Field(pattern=ID_PATTERN)
    # Optional: if omitted the backend assigns the protocol's current step.
    type: TrialType | None = None
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    # Absolute level depends on accel units (g vs raw counts); only differences
    # from the hum matter, so the range is deliberately wide.
    ratio_db: float | None = Field(default=None, ge=-200, le=200)
    spread_db: float | None = Field(default=None, ge=0, le=120)
    voiced_frames: int = Field(ge=0)
    mic_clipped: bool
    accel_snr_db: float | None = Field(default=None, ge=-120, le=120)
    imu_hz: float = Field(ge=0, le=100000)
    # Touch override when ASR cannot confirm the phrase (proposal §12).
    phrase_confirmed: bool = False
    # Must be true for anything not captured from the real sensor.
    simulated: bool = False


class SessionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Pseudonymous label only (e.g. "P01"); never a real name.
    user_ref: str = Field(default="anon", pattern=ID_PATTERN)
    lang: Lang = "en"
    pairs: int = Field(default=1, ge=1, le=5)
    start_agent: bool = False
    device_rtc_uid: str = Field(default="1002", pattern=r"^[0-9]{1,10}$")


class ToolLatestIn(BaseModel):
    session_id: str = ""
    heard_text: str = Field(default="", max_length=500)
    tool_call_id: str | None = None


class ToolSessionIn(BaseModel):
    session_id: str = ""
