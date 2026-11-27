# Backend (NasoCheck)

Python 3.12 + FastAPI. Owns sessions, calibration, scoring, rejection rules and the
Agora agent's tool endpoints. The agent never computes a number; it reads `say`
from these tools. Spec: [docs/NASOCHECK.md](../docs/NASOCHECK.md).

```sh
cd backend
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q                       # SIMULATED data only
cp ../.env.example .env                   # fill in; never commit
uvicorn nasocheck.app:app --host 0.0.0.0 --port 8000
```

No board yet? Exercise everything with SIMULATED trials (the agent says "simulated" aloud):
```sh
python scripts/fake_device.py --base http://localhost:8000 --lang ms \
    --steps hum,oral:wrong,oral,nasal:moved,nasal --agent
```
`--start-agent` additionally asks the backend to start the real Agora agent (needs `.env` + `PUBLIC_BASE_URL`).

## Endpoints
| Endpoint | Auth header | Caller | Job |
|---|---|---|---|
| `GET /health` | – | anyone | config status |
| `POST /session` | `X-Device-Key` | device | new session, RTC token, optionally start agent |
| `POST /session/{id}/stop` | `X-Device-Key` | device | stop agent |
| `GET /session/{id}/next` | `X-Device-Key` | device | what to show on screen next |
| `GET /session/{id}` | `X-Device-Key` | laptop | full trial table + summary (evidence) |
| `POST /trials` | `X-Device-Key` | device | validate, dedupe by `trial_id` (409 on conflicting reuse), score |
| `POST /trials/raw` | `X-Device-Key` | device | **fallback:** raw int16 samples (base64), backend runs the Python DSP and saves `.npz` under `<log dir>/raw/` |
| `GET /evidence`, `GET /evidence.csv` | `X-Device-Key` | laptop | §11 trial table across sessions; per person and type: n, mean, SD, range; `?include_simulated=false` |
| `GET /config` | `X-Device-Key` | laptop | active thresholds, DSP settings, phrases |
| `POST /tools/getNextStep` | `X-Tool-Secret` | agent | first instruction |
| `POST /tools/getLatestTrial` | `X-Tool-Secret` | agent | waits ≤2 s, phrase check on `heard_text`, result + next step, or `pending` |
| `POST /tools/getSummary` | `X-Tool-Secret` | agent | averages, nasal−oral, change vs previous session of same `user_ref` |

**Auth fails closed.** Without `DEVICE_KEY` / `TOOL_SECRET`, requests get 503 unless `NASOCHECK_DEV_MODE=1`.
- Tool calls carry a **per-session token**, `HMAC-SHA256(TOOL_SECRET, session_id)`, which the backend passes to Agora as a template variable. A token can only read its own session.
- `/evidence.csv` neutralises spreadsheet formulas, because `heard_text` comes from ASR.
- Raw payloads are size-capped before decoding.
- `GET /live` is the live evidence page for the demo video; its data still needs the device key.
- `scripts/suggest_thresholds.py trials.csv` proposes `NC_*` values from go/no-go trials.

## Design decisions (filling gaps in the proposal)
- **Score** = `ratio_db − median(valid hum ratio_db before this trial)`, equal to the HONC `20·log10(k·A/M)` with `k` from the hum.
- **Trial `type` is optional**: if omitted, the backend assigns the current protocol step. The device only needs to tap and capture.
- **State is derived** from the ordered trial log. A rejected trial never advances the protocol, and a late phrase-check rejection rolls it back consistently. Events go to an append-only JSONL file (`NASOCHECK_LOG`), which is replayed on restart.
- **Phrase check**: the agent passes the words it heard (`heard_text`) and the backend fuzzy-matches them against the expected phrase. Empty text means "not checked", which is never a rejection. `phrase_confirmed: true` from the device (touch override) skips the check. This replaces "agent history timestamps" from the proposal, which need no extra Agora API.
- **Stale trials**: `getLatestTrial` reports the newest unseen trial and marks older ones as seen, so heard text always pairs with the latest utterance.
- **Spoken numbers** are the rounded values; differences and averages are computed from the rounded values so what the user hears always adds up.
- **Changes under 3 dB** between sessions are reported as "about the same" (assumption, because test-retest is only moderate).
- **`simulated: true`** on a trial makes every agent sentence start with `[SIMULATED DATA]`.

## Tuning on the day
Thresholds come from `NC_MIN_VOICED_FRAMES`, `NC_MIN_ACCEL_SNR_DB`, `NC_MAX_SPREAD_DB` and `NC_MIN_IMU_HZ` (defaults are the §8 guesses). Set them from go/no-go data, restart, check `GET /config`, then freeze. Restarting re-evaluates logged trials under the new thresholds, so change them before collecting final evidence.

## Raw upload format (`POST /trials/raw`)
`{"trial_id","session_id","imu_hz","mic_hz":16000,"accel_b64","mic_b64"}`, plus optional `type`, `phrase_confirmed` and `simulated`.
- `accel_b64` holds interleaved x,y,z int16 LE values; `mic_b64` holds mono int16 LE samples.
- Keep the accelerometer range fixed for the whole session.
- Captures must be 0.5–10 s long. About 2.3 s at 1.6 kHz/16 kHz is roughly 130 KB of JSON.

## Scripts
- `scripts/relay.py`: USB serial → backend relay, the cut-order fallback. The device prints `NC_SESSION|NC_TRIAL|NC_RAW|NC_NEXT <json>` lines and reads back `NC_RESP <json>` (`ok`, `http`, plus the backend response). `--stdin` replays a log without a board; a real port needs `pip install pyserial`.
- `scripts/gonogo.py`: go/no-go verdict (§10) from a trial CSV or from raw `*.accel.csv` + `*.wav` captures, with `--plot` for the evidence figure.
- `scripts/fake_device.py`: SIMULATED device plus agent tool calls.
- `scripts/make_dsp_vectors.py`: regenerates the C parity vectors in `fixtures/dsp_vectors/`.
