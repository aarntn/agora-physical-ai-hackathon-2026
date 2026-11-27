"""Fake device: posts SIMULATED trials and plays the agent's tool calls.

Use before the real board works, to exercise backend + agent end to end.
Every trial is sent with "simulated": true and the agent says so out loud.

    python scripts/fake_device.py --base http://localhost:8000 --lang ms \
        --steps hum,oral,oral:wrong,nasal --agent
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nasocheck import dsp, protocol, synth  # noqa: E402

COUPLING = {"hum": 0.0, "oral": -20.0, "nasal": -8.0, "control": -30.0}


def features(kind: str, seed: int) -> dict:
    variant = kind.split(":")[1] if ":" in kind else ""
    base = kind.split(":")[0]
    kw = dict(coupling_db=COUPLING[base], seed=seed)
    if variant == "moved":
        kw["jitter_db"] = 5
    if variant == "loud":
        kw["clip"] = True
    c = synth.capture(**kw, silent=(base == "control"))
    f = dsp.analyze(c["accel"], c["fs_imu"], c["mic"], c["fs_mic"])
    return f.to_dict()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--device-key", default=os.environ.get("DEVICE_KEY", ""))
    ap.add_argument("--tool-secret", default=os.environ.get("TOOL_SECRET", ""))
    ap.add_argument("--lang", default="en", choices=["en", "ms"])
    ap.add_argument("--user", default="anon")
    ap.add_argument("--steps", default="hum,oral,nasal",
                    help="comma list of hum|oral|nasal|control, optional :wrong|:moved|:loud")
    ap.add_argument("--agent", action="store_true", help="also call the agent tools")
    ap.add_argument("--start-agent", action="store_true", help="ask backend to start the real Agora agent")
    a = ap.parse_args()

    dev = {"X-Device-Key": a.device_key}
    tool = {"X-Tool-Secret": a.tool_secret}
    c = httpx.Client(base_url=a.base, timeout=10)
    sess = c.post("/session", headers=dev, json={"lang": a.lang, "user_ref": a.user,
                                                  "start_agent": a.start_agent}).raise_for_status().json()
    sid = sess["session_id"]
    print(f"session {sid}  agent_started={sess['agent_started']}  {sess.get('agent_error') or ''}")
    if a.agent:
        print("AGENT>", c.post("/tools/getNextStep", headers=tool, json={"session_id": sid}).json()["say"])

    for i, kind in enumerate(a.steps.split(",")):
        nxt = c.get(f"/session/{sid}/next", headers=dev).json()
        base = kind.split(":")[0]
        f = features(kind, seed=i)
        body = {"trial_id": f"{sid}-{i:03d}", "session_id": sid, "type": base,
                "start_ms": 0, "end_ms": 2000, "ratio_db": f["ratio_db"], "spread_db": f["spread_db"],
                "voiced_frames": f["voiced_frames"], "mic_clipped": f["mic_clipped"],
                "accel_snr_db": f["accel_snr_db"], "imu_hz": f["imu_hz"], "simulated": True}
        r = c.post("/trials", headers=dev, json=body).raise_for_status().json()
        print(f"\nDEVICE [{kind}] expected={nxt['type']} -> status={r['status']} score={r['score_db']} reasons={r['reasons']}")
        if a.agent:
            phrase = nxt.get("phrase") or ""
            heard = "" if base in ("hum", "control") else (
                protocol.PHRASES[a.lang][-1] if kind.endswith(":wrong") else phrase)
            out = c.post("/tools/getLatestTrial", headers=tool,
                         json={"session_id": sid, "heard_text": heard, "tool_call_id": f"fake-{i}"}).json()
            print(f"USER  > {heard or '(hum)'}\nAGENT > {out['say']}")
        time.sleep(0.1)

    if a.agent:
        print("\nAGENT (summary) >", c.post("/tools/getSummary", headers=tool,
                                            json={"session_id": sid}).json()["say"])


if __name__ == "__main__":
    main()
