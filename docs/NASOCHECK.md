# NasoCheck: a pocket nasality meter

**Physical AI Hackathon Malaysia 2026 · Proposed track: Social Impact**
Status: proposal, 27 Nov 2026. Nothing tested on hardware yet. Every number below is either cited or marked as an assumption or a target.

---

## 1. One-line pitch

> Hold the device to the side of your nose and speak. It feels how much of your voice escapes through the nose, and a voice coach runs a short, standard check in Bahasa Melayu or English and tells you whether you improved since last time.

## 2. The problem

**Who:** people with hypernasal speech (too much sound leaking through the nose), and the speech therapists who treat them. The most common cause is cleft palate. Others include stroke, brain injury and neurological conditions.

**Why it matters in Malaysia**
- 34.7% of 49 Malaysian school-age children with cleft lip/palate had hypernasality; it correlated with speech distress. https://www.sciencedirect.com/science/article/abs/pii/S0165587625000692
- The Ministry of Health had 156 speech-language therapists in the public sector in 2023, about 1 per 209,615 people. https://codeblue.galencentre.org/2023/06/zaliha-only-156-speech-language-therapists-in-moh/
- Penang reported an average waiting time of 205 days for speech therapy at government hospitals (thesun.my, 2026).
- The usual objective instrument, the Nasometer, costs several thousand US dollars; accelerometer equipment costs a few hundred. https://pmc.ncbi.nlm.nih.gov/articles/PMC4165226/

**The gap:** nasality is mostly judged by ear, and only during appointments that are scarce and far apart. Between visits, patients practise with no objective feedback, and therapists have no numbers to see whether home practice is working.

## 3. The science

**Method:** Horii Oral-Nasal Coupling index (HONC), 1980. When the soft palate doesn't close, sound travels through the nose and vibrates the nasal skin. A sensor on the nose measures that vibration; a microphone measures overall voice level. The ratio cancels out how loudly the person speaks.
https://pubmed.ncbi.nlm.nih.gov/6930999/

```
score_dB = 20 * log10( k * A_nose / M_mic )
k = M_mic / A_nose   measured during a hummed /m/  (fully nasal reference)
```

So a hum scores about 0 dB, and normal oral speech scores well below it. Hypernasal oral speech scores closer to 0.

**Evidence**
- Typically developing children: nasal vs non-nasal speech differed by about 10–13 dB; AUC 0.89–0.94 (Varghese et al., 2014). Same paper: test-retest only moderate; no single cutoff worked for everyone; disordered speakers weren't tested.
- Adults: Horii's index differentiated normal from hypernasal speech (Cleft Palate Journal, distributional analysis).
- A 2017 case series used the accelerometer method in a video game for home practice. https://pmc.ncbi.nlm.nih.gov/articles/PMC5544406/

**Our hardware vs. the studies**
| | Published work | ESP-Mosaico |
|---|---|---|
| Nose sensor | Miniature accelerometer taped to nose | BMI270 inside the whole board |
| Bandwidth | 80–9000 Hz or 400–1000 Hz | ~740 Hz max (1.6 kHz sampling) |
| Microphone | Separate, 6–10 cm from mouth | Onboard mic, same unit |

This is not a replication. It's a test of whether the principle survives on a dev board.

## 4. What exists already (be honest about this)
| Product / project | What it does | Our difference |
|---|---|---|
| Nasometer (commercial) | Clinical gold standard, two mics and a separation plate | We're cheaper and portable, but not equivalent |
| mNasometer (2026), Nosey (2025) | Low-cost open-source acoustic nasometers | They need a plate between nose and mouth; ours is one handheld unit |
| Accelerometer video game (2017) | Home practice biofeedback | Ours adds a guided, spoken protocol with trial checking |
| ASR-only hypernasality estimation | Rates audio with ML | Ours measures a physical signal, not just sound |

**Claim:** a guided, single-device measurement session. **Not claimed:** new physics, diagnosis, or Nasometer equivalence.

## 5. Why it needs Agora (15% of score)
The agent is the session operator, not a voice-over.
1. Runs the protocol: calibration hum, then paired oral and nasal phrases.
2. Checks the person said the right phrase, using speech recognition. Wrong phrase = invalid trial.
3. Explains rejected trials in plain language ("too quiet", "the device moved") and asks for a retry.
4. Reads the score from a tool call. It is never allowed to invent a number.
5. Compares with the last session and summarises in the person's language.

Remove Agora and you get a bar with no protocol, no checking and no coaching. That's the argument.

## 6. Users and buyers (hypotheses, not validated)
| Who | Uses it for | Would pay? |
|---|---|---|
| Speech therapist | Quick objective number in clinic; reviewing home practice | Clinic budget |
| Patient / parent | Practice between sessions | Low; likely via clinic or NGO |
| Cleft team / NGO (e.g. hospital cleft centres, charity programmes) | Outreach where Nasometers aren't available | Programme grants |
| Researchers | Cheap field data collection | Research budgets |

Positioning: **"a thermometer for nasality, not a doctor."** Like a home blood-pressure cuff, it tracks change; the clinician decides.

## 7. The 30-second demo
1. Judge holds the device to the side of their nose.
2. Agent: "Hum for me... mmmm." The bar fills: calibrated.
3. Agent: "Now say: Papa pakai topi." Bar stays low.
4. Agent: "Now say it again, through your nose." Bar jumps.
5. Agent reads both scores and the difference.

Arbitrary input: the judge can choose how nasal to sound. Nothing is scripted on the device side.

## 8. Architecture
```
ESP-Mosaico ──audio over Agora RTC─────────▶ Agora agent (ASR → LLM → TTS)
  IMU 1.6 kHz + mic 16 kHz                         │ custom tool (HTTPS)
  compute ratio per trial                          ▼
     └──trial JSON over HTTPS──▶ Backend: sessions, baseline, scoring, log
```

**Device**
- Tap to start → 1 s countdown → capture ~2 s. Don't touch the screen while measuring.
- Mute agent playback during capture (speaker vibrates the IMU).
- High-pass both signals at 80 Hz; low-pass accelerometer ~700 Hz.
- 40 ms frames, voiced frames only, `20*log10(accel_rms/mic_rms)`, median.
- Mic automatic gain OFF.

**Trial message**
```json
{"trial_id":"s1-004","session_id":"s1","type":"oral","start_ms":0,"end_ms":2100,
 "ratio_db":-18.4,"spread_db":1.9,"voiced_frames":41,
 "mic_clipped":false,"accel_snr_db":14.2,"imu_hz":1594}
```

**Backend endpoints**
| Endpoint | Caller | Job |
|---|---|---|
| `POST /session` | device | token, start agent |
| `POST /trials` | device | validate, dedupe by `trial_id`, score vs baseline |
| `POST /tools/getLatestTrial` | agent | score, valid/rejected + reason, next step |
| `POST /tools/getSummary` | agent | session averages, change vs last session |

**Agent config:** `advanced_features.enable_tools: true`; tools in `llm.tools[]`; HTTPS URL (tunnel or hosted); secret header; tool waits ~2 s then returns `pending`. Optional: backend nudges agent via the `think` endpoint. Phrase check via agent history timestamps (confirm fields exist).

**Rejection rules (initial guesses, tune on the day):** clipped; fewer than 15 voiced frames; accel SNR < 6 dB; spread > 4 dB; IMU rate < 1000 Hz.

## 9. Six-hour plan (three people, each with a Claude agent)
| Time | Hardware | Agora/backend | Product |
|---|---|---|---|
| 0:00–0:20 | Flash starter, find IMU/mic access | Starter agent talking | Confirm rules, deadline |
| 0:20–0:50 | Log both sensors to laptop | Fake tool call (labelled) | Run go/no-go trials |
| **0:50** | **Go/no-go decision** | | |
| 0:50–2:00 | Filters, ratio, trial JSON | `/trials`, baseline, rejection | Malay/English phrases, interviews with mentors |
| 2:00–3:15 | Post over Wi-Fi with Agora running | Agent uses real tools | Placement tests, evidence log |
| 3:15–4:00 | Screen bar, trial states | Phrase check (if stable) | Backup video take |
| 4:00 | **Feature freeze** | | |
| 4:00–5:00 | Fix failures | Fix failures | 10 logged trials, 2 people |
| 5:00–6:00 | Tidy, remove secrets | README, architecture, Agora write-up | Final video, submit |

Give each Claude agent its own folder (`firmware/`, `backend/`, `docs/`) and the trial JSON as the shared contract.

**Cut order if behind:** phrase check → session summary → graphics → direct Wi-Fi (relay via laptop USB, disclose it). Never cut: real sensor, baseline, one live tool call.

## 10. Go/no-go test (first 30 minutes)
1. Log accelerometer at ≥800 Hz; check real rate from timestamps.
2. Control: device on nose, user silent, someone talking nearby.
3. Five "aaaa" and five "mmmm", re-placing each time. Two teammates.
4. **GO** if, for both people, every /m/ is ≥6 dB above every /a/ and clearly above control (6 dB is our bar).
5. Try side of nose, then nasal bridge.
6. If both fail → test SwallowCheck (neck) with the same code, or fall back.

## 11. Evidence to show judges ("rated on what is shown")
- Table: 10+ trials, two people, /a/ vs /m/ vs voluntary nasal speech, with spread.
- Control trial (silent) showing the noise floor.
- One rejected trial and the agent's retry, on video.
- A plot of raw accelerometer during "aaaa" vs "mmmm".
- Honest limitations slide.

## 12. Risks
| Risk | Mitigation |
|---|---|
| Board too heavy to move with nose skin | Test two positions; press gently; fall back |
| IMU noise (~4 mg RMS over 700 Hz, from datasheet 160 µg/√Hz) | Band-limit, median over frames |
| Firmware can't read IMU at 1.6 kHz while Agora runs | Ask mentor first; alternate measure/talk |
| Mic AGC breaks the ratio | Disable; else calibrate per session |
| ASR fails on unusual speech | Touch override for phrase confirmation |
| Read as "training" (handbook example) | Pitch as a measuring instrument |
| Hygiene | Wipe between users; cling film if available |
| Medical over-claiming | Never say diagnose; say "track change" |

## 13. Market story for the pitch (2 minutes)
1. **Hook (0:00–0:10):** "1 in 3 Malaysian kids with cleft palate still sounds nasal at school age, and there's one public speech therapist per 200,000 people."
2. **Gap (0:10–0:20):** "Nasality is judged by ear, months apart. The machine that measures it costs thousands."
3. **Reveal (0:20–0:45):** live hum → oral → nasal demo.
4. **How (0:45–1:10):** nose vibration ÷ voice level, a method from 1980, running on a $59 board.
5. **Agora (1:10–1:30):** agent runs the session, checks phrases, rejects bad trials, never invents numbers.
6. **Proof (1:30–1:45):** trial table and control.
7. **Honesty and next step (1:45–2:00):** "Not a diagnosis. Next: test with a speech therapist and patients."

**Lines to avoid:** "diagnoses", "replaces therapists", "clinically validated", "world first".

## 14. Validation questions (mentors tomorrow, therapists later)
1. How is nasality judged today? Walk me through a session.
2. What happens between appointments?
3. Would you trust a handheld number? What would make you doubt it?
4. Who should hold this: therapist, parent, patient?
5. Who would pay, and from what budget?

Kill signals: "ear judgement is enough", "home numbers would mislead families", "the Nasometer is easy to access."

## 15. After the hackathon
Small pilot with a university speech clinic (e.g. UKM or USM speech sciences), compare against a Nasometer, gather Malay norms on this device, ethics approval before any patient use.
