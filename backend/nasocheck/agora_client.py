"""Agora Conversational AI agent: join body, start and stop.

Schema checked against docs.agora.io on 28 Nov 2026 (join + custom tools):
  POST https://api.agora.io/api/conversational-ai-agent/v2/projects/{appid}/join
  POST .../projects/{appid}/agents/{agentId}/leave
Tools live in properties.llm.tools[] with a `server` block; Agora renders
{{args.x}}, {{template_variables.x}} and {{tool_call_id}} into the request and
fails the call on any unresolved placeholder, so every tool argument is required.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import time
from pathlib import Path

import httpx

from .config import Settings

API = "https://api.agora.io/api/conversational-ai-agent/v2/projects"
PROMPT_PATH = Path(__file__).resolve().parents[2] / "agora" / "system_prompt.md"


def rtc_token(s: Settings, channel: str, uid: str, ttl_s: int = 3600) -> str:
    """RTC token, or "" when the project has no certificate (testing mode)."""
    if not s.app_certificate:
        return ""
    from agora_token_builder import RtcTokenBuilder  # optional dependency
    return RtcTokenBuilder.buildTokenWithUid(s.app_id, s.app_certificate, channel,
                                             int(uid), 1, int(time.time()) + ttl_s)


def session_tool_token(tool_secret: str, session_id: str) -> str:
    """Per-session tool credential: a token for one session can't read another."""
    return hmac.new(tool_secret.encode(), session_id.encode(), hashlib.sha256).hexdigest()


def system_prompt(lang: str) -> str:
    text = PROMPT_PATH.read_text(encoding="utf-8")
    language = {"en": "English", "ms": "Bahasa Melayu"}[lang]
    return text.replace("{{LANGUAGE}}", language)


def _tool(name: str, description: str, base: str, path: str, args: dict[str, str]) -> dict:
    body = {"session_id": "{{template_variables.session_id}}", "tool_call_id": "{{tool_call_id}}"}
    body.update({a: "{{args.%s}}" % a for a in args})
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object",
                           "properties": {a: {"type": "string", "description": d} for a, d in args.items()},
                           "required": list(args), "additionalProperties": False},
        },
        "server": {"method": "POST", "url": base.rstrip("/") + path,
                   "headers": {"Content-Type": "application/json",
                               "X-Tool-Secret": "{{template_variables.tool_secret}}"},
                   "body": body, "timeout_ms": 6000},
    }


def tools(base: str) -> list[dict]:
    return [
        _tool("getNextStep", "Get the next protocol step and the exact instruction to give. Call at the start.",
              base, "/tools/getNextStep", {}),
        _tool("getLatestTrial",
              "Get the result of the newest measurement after the user has hummed or spoken. "
              "Pass the exact words you heard the user say during the measurement, or an empty string.",
              base, "/tools/getLatestTrial",
              {"heard_text": "Exact words the user said for this measurement; empty string if none or a hum."}),
        _tool("getSummary", "Get session averages and change versus the previous session.",
              base, "/tools/getSummary", {}),
    ]


def join_body(s: Settings, *, session_id: str, channel: str, lang: str,
              device_uid: str, agent_token: str) -> dict:
    greeting = {"en": "Hi, I'm your NasoCheck coach. Let's start with a short hum.",
                "ms": "Hai, saya jurulatih NasoCheck anda. Mari mula dengan dengungan pendek."}[lang]
    return {
        "name": f"nasocheck-{session_id}-{int(time.time())}",
        "properties": {
            "channel": channel,
            "token": agent_token,
            "agent_rtc_uid": s.agent_rtc_uid,
            "remote_rtc_uids": [device_uid],
            "idle_timeout": 120,
            "advanced_features": {"enable_tools": True},
            "asr": {"language": s.asr_lang[lang]},
            "llm": {
                "url": s.llm_url,
                "api_key": s.llm_api_key,
                "system_messages": [{"role": "system", "content": system_prompt(lang)}],
                "greeting_message": greeting,
                "failure_message": {"en": "Sorry, something went wrong. Let's try again.",
                                    "ms": "Maaf, ada masalah. Mari cuba lagi."}[lang],
                "max_history": 32,
                "params": {"model": s.llm_model},
                "template_variables": {"session_id": session_id, "tool_secret": session_tool_token(s.tool_secret, session_id)},
                "tools": tools(s.public_base_url),
            },
            "tts": {"vendor": s.tts_vendor, "params": s.tts_params},
        },
    }


def _auth(s: Settings) -> dict:
    cred = base64.b64encode(f"{s.customer_id}:{s.customer_secret}".encode()).decode()
    return {"Authorization": f"Basic {cred}", "Content-Type": "application/json"}


def start_agent(s: Settings, body: dict) -> str:
    r = httpx.post(f"{API}/{s.app_id}/join", json=body, headers=_auth(s), timeout=15)
    r.raise_for_status()
    return r.json()["agent_id"]


def stop_agent(s: Settings, agent_id: str) -> None:
    r = httpx.post(f"{API}/{s.app_id}/agents/{agent_id}/leave", headers=_auth(s), timeout=15)
    r.raise_for_status()
