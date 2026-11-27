# Technical feasibility: NasoCheck

The question this page answers: can a dev board held against the nose measure nasal vibration well enough, fast enough, through a voice agent? Each budget below says what is **known** (datasheet, docs, code), what is **assumed**, and **what test decides it**.

## 1. Signal budget (the core risk)
| Quantity | Value | Source |
|---|---|---|
| BMI270 accel noise density | 160 µg/√Hz | Datasheet (proposal §12) |
| Analysis band | 80–700 Hz (620 Hz wide) | Our filters (`dsp.py`) |
| Noise RMS in band | 160 µg × √620 ≈ **4.0 mg** | Calculation |
| Rejection rule | accel SNR ≥ 6 dB, i.e. voiced vibration ≥ 2× the noise floor | `scoring.py` (proposal §8) |
| Vibration needed at the board for a valid trial | ≈ **8 mg RMS** over 80–700 Hz | Calculation |
| Vibration actually reaching the board | **Unknown.** Published sensors are miniature and taped to the skin; ours is a whole board held by hand, so mass loading reduces the coupling. | Go/no-go §10 decides |
| Required separation | /m/ ≥ 6 dB above /a/ for every trial, two people | Go/no-go bar |
| Published separation | 10–13 dB nasal vs non-nasal (children, miniature accelerometer) | Varghese et al. 2014 |

**Reading:** the method has 4–7 dB of margin over our 6 dB bar on ideal hardware. Board mass may use some or all of it, which is why the first 30 minutes are a go/no-go test, not a build.

**Why the ratio survives loudness:** score = accel level − mic level, so a louder voice moves both. The simulated test `test_ratio_is_loudness_invariant` holds to ±0.5 dB over a 14 dB loudness change. On hardware, this holds only if mic automatic gain control (AGC) is **off**, which is a firmware checklist item.

**Bandwidth caveat:** at a 1.6 kHz sample rate the usable accelerometer band ends near 700–800 Hz. Published work used 80–9000 Hz or 400–1000 Hz. The low band carries voicing fundamentals and the nasal murmur (low-frequency energy), so a ratio is still expected, but its absolute values won't match published norms. That is one reason we only track change, never compare to norms.

## 2. Latency budget (one trial, user hears the result)
| Step | Budget | Basis |
|---|---|---|
| Capture | 2.3 s (0.3 s silence + 2 s speech) | Protocol |
| On-device DSP | < 50 ms (streaming, ~4 KB state; 1 biquad pair per sample) | Design; **measure on ESP32** |
| POST /trials over Wi-Fi | ~0.1–0.5 s | Assumption; measure |
| Agent → `getLatestTrial` | waits ≤ 2 s; returns as soon as the trial lands | `app.py` |
| LLM turn + TTS first audio | ~1–2 s | Assumption; **measure in A1** |
| **Result spoken after speech ends** | **~1.5–3 s** | Target |

## 3. Compute and memory on the board
- DSP state: 2 × 256 frame buffers + 2 scratch buffers ≈ 4 KB, no heap. This is `sizeof(nc_state_t)` and verifiable.
- Per sample: 2 biquads (accel ×3 axes, mic ×1), one multiply-add, an integer frame counter. At 16 kHz + 1.6 kHz × 3 that is ~21k biquad pairs/s, trivial for an ESP32-S3 with a single-precision FPU.
- Fallback if the board can't keep up while Agora streams: upload raw samples (`/trials/raw`) and the backend runs the same DSP.

## 4. Failure modes and handling
| Failure | Detection | Handling | Tested |
|---|---|---|---|
| Too loud | ≥3 samples ≥ 0.98 FS | Reject "too loud" | Yes (sim) |
| Device moved | Frame-ratio spread (IQR) > 4 dB | Reject "unsteady" | Yes (sim) |
| Not pressed on the nose / weak coupling | Accel SNR < 6 dB | Reject "couldn't feel the vibration" | Yes (sim) |
| Too short / quiet | < 15 voiced frames | Reject | Yes (sim) |
| IMU rate dropped | measured < 1000 Hz | Reject | Yes |
| Wrong phrase | ASR text fuzzy-match | Reject, ask again | Yes |
| ASR fails on hypernasal speech | Touch override `phrase_confirmed` | Skip check | Yes |
| Duplicate upload | Same `trial_id` | Idempotent | Yes |
| Backend restart | Event log replay | State identical | Yes |
| Agent speaker vibrates the IMU | Mute playback during capture | Firmware | **No: hardware** |
| No Wi-Fi | USB serial relay | Disclosed | Yes (relay logic) |

## 5. What would make us stop (no-go)
- /m/ − /a/ < 6 dB for either tester in both nose positions, or control trials not clearly below /m/.
- AGC can't be disabled **and** per-session calibration doesn't stabilise repeated hums (spread > 4 dB).
- Fallback: same code on the neck (SwallowCheck, proposal §10), or an honest pivot.
