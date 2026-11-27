# Agora (NasoCheck)

The agent is started by the backend (`POST /session` with `start_agent: true`) through the Conversational AI REST `join` endpoint. See [backend/nasocheck/agora_client.py](../backend/nasocheck/agora_client.py). No credentials go in Git.

- [system_prompt.md](system_prompt.md): the agent's rules. Numbers only come from tool `say` fields; no diagnosis; say "simulated" when the data is simulated.
- Tools are declared in `properties.llm.tools[]`, and `advanced_features.enable_tools` is true:
  - `getNextStep()`, `getLatestTrial(heard_text)` and `getSummary()`, all `POST {PUBLIC_BASE_URL}/tools/<name>`.
  - Header `X-Tool-Secret: {{template_variables.tool_secret}}`.
  - Body `{"session_id": "{{template_variables.session_id}}", "tool_call_id": "{{tool_call_id}}", ...args}`.
  - Every argument is `required`, because Agora fails a call on any unresolved placeholder.
- `PUBLIC_BASE_URL` must be HTTPS. Agora does not follow redirects and does not retry; `timeout_ms` is 6000 and the backend waits at most 2 s.

## Verify on the day
- [ ] `ms-MY` ASR accuracy with the default ASR vendor (ARES). Docs list Malay for real-time STT but don't confirm it per vendor.
- [ ] A TTS voice for Malay (e.g. Microsoft `ms-MY-YasminNeural`) set in `TTS_PARAMS_JSON`.
- [ ] Whether `asr.params` is required. The schema says yes, but the docs example omits it.
- [ ] Whether the agent's speech can be muted, or the device can ignore playback, during capture.
- [ ] Whether the organizer starter already handles device RTC join and tokens. If so, pass its channel and uid to `POST /session`.
