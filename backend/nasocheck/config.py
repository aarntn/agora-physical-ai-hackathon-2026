"""Settings from environment (or a local, git-ignored .env file)."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from .scoring import Thresholds


def load_dotenv(path: Path) -> None:
    """Minimal KEY=VALUE loader; existing environment variables win."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


@dataclass
class Settings:
    app_id: str = field(default_factory=lambda: _env("AGORA_APP_ID"))
    app_certificate: str = field(default_factory=lambda: _env("AGORA_APP_CERTIFICATE"))
    customer_id: str = field(default_factory=lambda: _env("AGORA_CUSTOMER_ID"))
    customer_secret: str = field(default_factory=lambda: _env("AGORA_CUSTOMER_SECRET"))
    llm_api_key: str = field(default_factory=lambda: _env("AI_API_KEY"))
    llm_url: str = field(default_factory=lambda: _env("LLM_URL", "https://api.openai.com/v1/chat/completions"))
    llm_model: str = field(default_factory=lambda: _env("LLM_MODEL", "gpt-4o-mini"))
    tts_vendor: str = field(default_factory=lambda: _env("TTS_VENDOR", "microsoft"))
    tts_params: dict = field(default_factory=lambda: json.loads(_env("TTS_PARAMS_JSON", "{}")))
    asr_lang: dict = field(default_factory=lambda: {"en": _env("ASR_LANG_EN", "en-US"),
                                                    "ms": _env("ASR_LANG_MS", "ms-MY")})
    # Public HTTPS base URL of this backend (tunnel or host) for agent tool calls.
    public_base_url: str = field(default_factory=lambda: _env("PUBLIC_BASE_URL"))
    tool_secret: str = field(default_factory=lambda: _env("TOOL_SECRET"))
    device_key: str = field(default_factory=lambda: _env("DEVICE_KEY"))
    agent_rtc_uid: str = field(default_factory=lambda: _env("AGENT_RTC_UID", "1001"))
    log_path: Path = field(default_factory=lambda: Path(_env("NASOCHECK_LOG", "data/events.jsonl")))
    tool_wait_s: float = field(default_factory=lambda: float(_env("TOOL_WAIT_S", "2.0")))
    # Rejection thresholds: tune on the day from go/no-go data, then freeze.
    thresholds: Thresholds = field(default_factory=lambda: thresholds_from_env())

    @property
    def agora_ready(self) -> bool:
        return all([self.app_id, self.customer_id, self.customer_secret,
                    self.llm_api_key, self.public_base_url.startswith("https://")])


def thresholds_from_env() -> Thresholds:
    d = Thresholds()
    return Thresholds(
        min_voiced_frames=int(_env("NC_MIN_VOICED_FRAMES", str(d.min_voiced_frames))),
        min_accel_snr_db=float(_env("NC_MIN_ACCEL_SNR_DB", str(d.min_accel_snr_db))),
        max_spread_db=float(_env("NC_MAX_SPREAD_DB", str(d.max_spread_db))),
        min_imu_hz=float(_env("NC_MIN_IMU_HZ", str(d.min_imu_hz))),
    )
