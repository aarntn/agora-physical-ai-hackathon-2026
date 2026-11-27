# User research: NasoCheck

Status: plan only, 28 Nov 2026. No interviews have been run yet. Record findings in the synthesis table below, with dates; never paraphrase someone into agreement.

## 1. Objectives
1. **Workflow:** how hypernasality is judged today in Malaysia (perceptual rating, Nasometer access), and what happens between appointments.
2. **Trust:** whether a handheld, single-number reading would be trusted, and what would make a clinician doubt it.
3. **Holder:** who should hold the device (therapist in clinic, parent at home, NGO outreach worker).
4. **Language:** whether the BM and English phrase lists and the coaching wording are appropriate (the phrases are a draft; see `backend/nasocheck/protocol.py`).
5. **Kill signals** (proposal §14): "ear judgement is enough", "home numbers would mislead families", "the Nasometer is easy to access."

## 1b. Secondary research (web search, 28 Nov 2026; abstracts only, verify the full text)
| Finding | Implication for NasoCheck | Source |
|---|---|---|
| Malay nasalance norms exist: 150 children aged 6–12; oral passage ≈13.9%, nasal ≈60.3%; age and sex effects clinically minor | Our phrases should come from these **validated Malay stimuli** after review; we don't create norms | [Ibrahim, Reilly & Kilpatrick 2012](https://research-repository.griffith.edu.au/items/f66cb5f7-1503-567a-aead-20be4f278afd); [Kelantan dialect study](https://search.bvsalud.org/gim/resource/en/wpr-628040) |
| Parents rated biofeedback positively; children found repetitive articulation practice "boring" | Keep sessions short; the coach should encourage, never criticise (already in the prompt) | [Pilot RCT, PMC11626862](https://pmc.ncbi.nlm.nih.gov/articles/PMC11626862/) |
| Trained parents can deliver cleft speech practice under therapist supervision | The holder is the parent, supervised by the therapist; the therapist needs a **reviewable session report** (built: `GET /session/{id}/report`) | [ASHA Perspectives 2023](https://pubs.asha.org/doi/10.1044/2023_PERSP-22-00253) |
| Clinician acceptance of biofeedback tech is under-studied; SLPs report training gaps in cleft care | Interviews must probe trust and training burden; the report should be self-explanatory | [Cleland et al. 2025](https://strathprints.strath.ac.uk/id/eprint/91974); [LSHSS 2021](https://pubs.asha.org/doi/10.1044/2021_LSHSS-21-00071) |
| Accelerometry correlates with airflow (r = .87) more than with perceptual ratings (r = .49) | Position the device as "track change", not "diagnose" | [JSLHR 2016](https://pubs.asha.org/doi/10.1044/2016_JSLHR-S-15-0407) |

## 2. Method and participants
The hackathon day only allows short interviews. These are hypothesis checks, not validation; the sample is too small to generalise.

| Who | Method | Target n | When |
|---|---|---|---|
| Event mentors (technical, health or business) | 10-minute semi-structured interview, plus a 30 s demo reaction | 3–5 | Day, 0:50–2:00 slot |
| Speech-language therapists (MOH, university clinics, private) | 30–45 min remote interview | 5–8 (typical for qualitative saturation of core themes) | After the event |
| Parents of children with cleft palate (via a cleft NGO or clinic) | 30 min interview, consent required, no recording of the child | 3–5 | After ethics guidance |

**Ethics:** no health data and no recordings of minors on the hackathon day. Use pseudonymous codes (M1, T1, P1). Before any patient use, get ethics approval (proposal §15).

## 3. Interview guide (therapist version; shorten for mentors)
**Warm-up (2–5 min).** Explain who we are and that this is a prototype, not a medical device. Ask for consent to take notes.

**Context (5–10 min)**
- Walk me through how you assess nasality in a session. Probe: rating scale used, instrumentation, time spent.
- When did you last use a Nasometer or similar? Probe: availability, cost, who has one.
- What happens between appointments? Probe: home practice, how you know whether it happened.

**Deep dive (10–20 min)**
- Tell me about the last time you couldn't tell whether a patient had improved.
- What would a number have to look like for you to trust it? What would make you distrust it?
- Who should hold this device: you, the parent, the child? Why?
- What would go wrong if families saw a number at home?

**Reaction (5–10 min).** Run the 30-second demo (hum, oral phrase, nasal phrase).
- What did you expect to happen? What surprised you?
- Are "Papa pakai topi" and "Buy Bobby a puppy" suitable? Suggest alternatives.
- What should the coach never say?

**Wrap-up (2–5 min).** Who pays, and from which budget? Who else should we talk to? Thank them.

Avoid leading questions such as "Would this help you?". Ask about past behaviour, not hypothetical future use.

## 4. Synthesis
Afterwards, affinity-map the notes into themes and score each theme for impact and evidence count.

| ID | Date | Role | Quote / observation (verbatim where possible) | Theme | Kill signal? |
|---|---|---|---|---|---|
| | | | | | |

**Decision rule:** if two or more therapists independently raise the same kill signal, record it in PRODUCT_DECISION.md and change the pitch or the positioning.

## 5. Deliverables
This plan; the filled synthesis table; 3–5 anonymised quotes for the pitch, only with permission; changes made because of the findings, logged in git.
