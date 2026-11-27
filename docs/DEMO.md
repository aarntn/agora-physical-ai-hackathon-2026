# Demo video script: NasoCheck (≤120 s)

The judges don't run code; they rate what they see. Show the real board, real audio and the live page (`/live`) side by side. No mockups. If any part is simulated, the on-screen SIMULATED badge and the agent's spoken "simulated" must be visible.

| Time | Picture | Audio / caption |
|---|---|---|
| 0–10 s | Title card, then a statistic | "1 in 3 Malaysian school children with cleft palate still had hypernasal speech. There is one public speech therapist per 200,000 people." (cited in README) |
| 10–20 s | The board in hand, held to the side of the nose | "NasoCheck feels how much of your voice escapes through your nose, and a voice coach runs the check." |
| 20–40 s | Hum → `/live` bar fills to 0 dB | Agent (BM): "Dengung 'mmmm'…" → "Kalibrasi selesai." |
| 40–55 s | "Papa pakai topi" → low bar | Agent reads the score from the tool |
| 55–70 s | **Wrong phrase → rejection → retry** | Agent: "Itu bukan ayat yang saya minta…". This shows phrase checking and recovery. |
| 70–85 s | Nasal version → bar jumps | Agent: score plus difference ("12 dB higher") |
| 85–100 s | Evidence table (10+ trials, 2 people, control) and the accel plot /a/ vs /m/ | "Every /m/ was at least X dB above every /a/" (**only real numbers**) |
| 100–120 s | Architecture diagram, then the limitations line | "Agora runs the session and never invents a number. Not a diagnosis; next step is a pilot with a speech clinic." |

## Recording checklist
- [ ] Two takes: a backup early (after the 3:15 milestone), the final after the feature freeze
- [ ] Clear agent audio (record the line-out, or quiet the room); captions on
- [ ] No faces of non-consenting people, no keys on screen, no copyrighted music
- [ ] The video is reachable without login; link added to the README
