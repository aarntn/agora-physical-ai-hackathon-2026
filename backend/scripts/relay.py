"""USB serial relay: device -> laptop -> backend (cut-order fallback, proposal §9).

Use when the board can't reach the backend over Wi-Fi. Disclose it in the demo.
The device prints one tagged line per message; the relay answers each with
`NC_RESP <json>` on the same serial port so the device can read session ids,
scores and the next instruction. Any other line is shown as device log.

  NC_SESSION {"lang":"ms","user_ref":"P01","start_agent":true}   -> POST /session
  NC_TRIAL   {...trial JSON...}                                  -> POST /trials
  NC_RAW     {...raw trial JSON, base64 int16...}                -> POST /trials/raw
  NC_NEXT    {"session_id":"s1234abcd"}                          -> GET  /session/{id}/next

    pip install pyserial
    python scripts/relay.py --port COM5 --baud 921600 --base http://localhost:8000
    python scripts/relay.py --stdin < device_log.txt      # replay / test without a board
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Callable

import httpx

ROUTES = {"NC_SESSION": ("POST", "/session"), "NC_TRIAL": ("POST", "/trials"),
          "NC_RAW": ("POST", "/trials/raw"), "NC_NEXT": ("GET", "/session/{session_id}/next")}


class Relay:
    def __init__(self, client: httpx.Client, device_key: str = "",
                 write: Callable[[str], None] = lambda s: None,
                 log: Callable[[str], None] = print, retries: int = 3):
        self.c, self.write, self.log, self.retries = client, write, log, retries
        self.headers = {"X-Device-Key": device_key}

    def handle_line(self, line: str) -> dict | None:
        line = line.strip()
        tag, _, payload = line.partition(" ")
        if tag not in ROUTES:
            if line:
                self.log(f"device: {line}")
            return None
        try:
            body = json.loads(payload or "{}")
        except json.JSONDecodeError as e:
            return self._reply({"ok": False, "error": f"bad json: {e}"})
        method, path = ROUTES[tag]
        try:
            path = path.format(**body)
        except KeyError as e:
            return self._reply({"ok": False, "error": f"missing {e}"})
        for attempt in range(self.retries):
            try:
                r = (self.c.get(path, headers=self.headers) if method == "GET"
                     else self.c.post(path, json=body, headers=self.headers))
                out = {**_json(r), "ok": r.is_success, "http": r.status_code, "tag": tag}
                self.log(f"{tag} -> {r.status_code}")
                return self._reply(out)
            except httpx.TransportError as e:  # trials are idempotent by trial_id: safe to retry
                self.log(f"{tag} network error ({e}); retry {attempt + 1}/{self.retries}")
                time.sleep(0.5 * (attempt + 1))
        return self._reply({"ok": False, "tag": tag, "error": "backend unreachable"})

    def _reply(self, out: dict) -> dict:
        self.write("NC_RESP " + json.dumps(out, separators=(",", ":")) + "\n")
        return out


def _json(r: httpx.Response) -> dict:
    try:
        j = r.json()
        return j if isinstance(j, dict) else {"body": j}
    except ValueError:
        return {"body": r.text[:200]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port")
    ap.add_argument("--baud", type=int, default=921600)
    ap.add_argument("--stdin", action="store_true")
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--device-key", default=os.environ.get("DEVICE_KEY", ""))
    a = ap.parse_args()
    client = httpx.Client(base_url=a.base, timeout=15)

    if a.stdin:
        relay = Relay(client, a.device_key, write=sys.stdout.write)
        for line in sys.stdin:
            relay.handle_line(line)
        return
    if not a.port:
        ap.error("give --port COMx (or --stdin)")
    import serial  # pyserial, only needed for a real board

    with serial.Serial(a.port, a.baud, timeout=0.2) as ser:
        relay = Relay(client, a.device_key, write=lambda s: ser.write(s.encode()))
        print(f"relaying {a.port} @ {a.baud} -> {a.base}  (Ctrl+C to stop)")
        buf = b""
        while True:
            buf += ser.read(4096)
            while b"\n" in buf:
                raw_line, buf = buf.split(b"\n", 1)
                relay.handle_line(raw_line.decode("utf-8", "replace"))


if __name__ == "__main__":
    main()
