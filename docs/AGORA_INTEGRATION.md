# Agora integration: NasoCheck

## Submission explanation (paste into the form)
**Products:** Agora Conversational AI Engine (REST `join`/`leave`, ASR → LLM → TTS pipeline, custom HTTP tools) over Agora RTC, with ESP-Mosaico as the RTC endpoint.

**Where it runs:**
- **Agent:** Agora cloud. Our backend starts it per session with `POST /api/conversational-ai-agent/v2/projects/{appid}/join`.
- **Tools:** the agent calls our FastAPI backend over HTTPS.
- **Device:** joins the same RTC channel for voice.

**Why real-time voice is central:** the user is holding a device against their face, so they can't read a screen or tap through a form. The agent is the session operator:
1. **Runs the protocol:** calibration hum, then paired oral/nasal phrases, from `getNextStep`.
2. **Checks the phrase:** passes what ASR heard to `getLatestTrial(heard_text)`; the backend fuzzy-matches it and rejects a wrong phrase.
3. **Explains rejections in plain BM/English:** too loud, device moved, couldn't feel the vibration. Then it asks for a retry.
4. **Never invents a number:** every score and comparison is in the tool's `say` field, and the system prompt forbids changing it.
5. **Summarises progress** against the last session, and only when both sessions have ≥2 valid trials.

Without Agora you have a bar on a screen: no protocol, no phrase checking, no coaching, no Malay explanation for a child or parent.

**Working interaction shown in the video:** hum → calibrated; oral phrase → score; wrong phrase → spoken rejection and retry; nasal phrase → score and difference; spoken summary.

## Configuration (code: `backend/nasocheck/agora_client.py`)
- `advanced_features.enable_tools: true`. Three tools in `llm.tools[]`: `getNextStep`, `getLatestTrial(heard_text)` and `getSummary`.
- Each tool is a `POST {PUBLIC_BASE_URL}/tools/<name>` with a 6 s timeout.
- Tool body: `{"session_id": "{{template_variables.session_id}}", "tool_call_id": "{{tool_call_id}}", ...args}`.
- Header `X-Tool-Secret: {{template_variables.tool_secret}}`, which carries a per-session HMAC token.
- Every argument is required, because Agora fails a call on any unresolved placeholder.
- ASR language `ms-MY` or `en-US`. TTS is configured by env (e.g. Microsoft `ms-MY-YasminNeural`).
- Security: credentials stay on the server only. The device never sees Agora customer secrets; it receives only an RTC token.

## Smoke test (record results in TEST_RESULTS.md)
- [ ] A1: start the agent from `POST /session` with `start_agent: true`; the device joins and the greeting is audible
- [ ] Agent calls `getNextStep` and speaks the hum instruction
- [ ] Real trial, then `getLatestTrial` returns a score and the agent reads it unchanged
- [ ] Wrong phrase is rejected and the agent asks again
- [ ] A2: kill the backend mid-session; the agent says "technical problem" and doesn't make up a number. Restart and continue.
- [ ] Record latency from end of speech to result audio (median and range over 5 trials)
- [ ] `ms-MY` ASR quality on our phrases (5 attempts each, 2 speakers)

## Reference
Docs checked 28 Nov 2026: https://docs.agora.io/en/ai/build/tools/custom-tools and https://docs.agora.io/en/api-reference/api-ref/conversational-ai/join. The organizer quickstart and starter are in RULES.md.
