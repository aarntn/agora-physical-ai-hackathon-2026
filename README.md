# Agora Physical AI Hackathon Malaysia 2026

**28 November 2026 | Public team workspace | Product and track: UNDECIDED**

Team: @aarntn, @abqaryne, @mpip0505 (write access to be confirmed).

## Start here tomorrow
1. [Rules and official resources](docs/RULES.md) — confirm pre-event code permission, deadline, hardware and track eligibility.
2. [Kickoff and team workflow](docs/WORKFLOW.md) — assign roles and synchronize branches.
3. [Hardware bring-up](docs/HARDWARE.md) and [Agora integration](docs/AGORA_INTEGRATION.md) — prove real device and voice connectivity.
4. [Research](docs/RESEARCH.md), [competitors](docs/COMPETITORS.md) and [decision gate](docs/PRODUCT_DECISION.md) — choose one concept only after feasibility checks.
5. [Rubric](docs/RUBRIC.md), [architecture](docs/ARCHITECTURE.md) and [test results](docs/TEST_RESULTS.md) — build and collect evidence.
6. [Demo](docs/DEMO.md) and [submission](docs/SUBMISSION.md) — complete before deadline.

## Official judging
Physical AI/technical 25%; Agora 15%; reliability 15%; innovation 15%; impact 15%; presentation 15%. Same rubric for all tracks. Round 1 is submission-only; code is not run. Video maximum 2 minutes.

## Status
Leading proposal: **[NasoCheck, a pocket nasality meter](docs/NASOCHECK.md)** (Social Impact), pending the hardware go/no-go (§10). Software is implemented and tested on SIMULATED data only:
- [backend/](backend/README.md): FastAPI sessions, calibration, rejection rules and Agora tool endpoints, plus go/no-go and fake-device scripts.
- [firmware/nasocheck_dsp/](firmware/README.md): C99 per-trial analysis with Python parity tests.
- [agora/](agora/README.md): agent prompt and tool declarations.

There are no hardware results yet. Do not claim working hardware, a selected track or novelty without evidence.

## Components
firmware/ — device; agora/ — voice/RTC; backend/ — application logic; web/ — optional UI. Select stack at kickoff. See Issues for work items.

Never commit secrets, personal records, production inspection data or unapproved assets. Use synthetic demo fixtures.
