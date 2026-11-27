# Test evidence (all pending)
Never present targets or simulations as actual results.
| ID | Test | Suggested success condition | Actual result | Evidence link |
|---|---|---|---|---|
| H1 | Real sensor input | changes match controlled action | Not run | |
| A1 | Agora round trip | audible contextual response | Not run | |
| A2 | Interruption/tool error | state preserved; useful recovery | Not run | |
| E1 | Full physical flow | five consecutive successful trials | Not run | |
| E2 | Wrong/ambiguous input | safe correction or explicit uncertainty | Not run | |
| E3 | Network loss/retry | no silent failure or duplicate state | Not run | |
| N1 | Novelty mechanism | measurable difference vs baseline | Not run | |
| V1 | User benefit | record task time/error or other domain metric | Not run | |
| S1 | Software only (SIMULATED data): backend unit/API tests, C DSP vs Python parity | all pass | 48 pytest tests pass (incl. raw upload, evidence export, relay); C parity 3/3 within 0.001 dB (28 Nov, Windows, zig cc 0.17.1). **Not hardware evidence.** | `backend/tests`, `fixtures/dsp_vectors` |
| G1 | NasoCheck go/no-go (NASOCHECK.md §10) | every /m/ ≥6 dB above every /a/ and control, 2 people | Not run | `backend/scripts/gonogo.py` |
Record sample size, setup, device revision, latency (median/range), failures and limitations. Use only synthetic fixtures and consenting participants. If unavailable, mark not tested.
