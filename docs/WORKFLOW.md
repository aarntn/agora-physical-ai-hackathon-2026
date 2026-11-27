# Tomorrow's operating plan
Three people; agree actual roles at kickoff, not preassigned by username.
| Role | Owns | Shared contract |
|---|---|---|
| Hardware | Board, power, sensors, device feedback | Device event payload and timestamps |
| AI/backend | Agora, tool endpoints, session and application state | Typed event/action contract, errors |
| Product/integration | UX, domain research, end-to-end tests, demo/submission | Acceptance tests and rubric evidence |

## First 45 minutes
0–10: confirm rules/deadline/modules, permissions, tools; assign roles.
10–30: parallel device/Agora smoke test and competitor research.
30–45: product selection gate; agree single end-to-end flow and data contract. If camera unavailable, choose IMU/audio fallback. Do not assume physical device control from agent works until tested.
## Remaining build window (relative to confirmed deadline)
Build first vertical slice before UI polish. Integrate small PRs every 30–45 minutes. Keep one person responsible for main/demo stability. By T-60m record tests and prepare architecture/Agora explanation. By T-45m freeze nonessential features. By T-30m record final video and check links. Submit by T-15m; adjust if organizer deadline requires.
## Git workflow
git clone https://github.com/aarntn/agora-physical-ai-hackathon-2026.git
git switch main
git pull --ff-only
git switch -c feat/<short-task>
# work, commit, push, open PR to main; squash merge after review
Existing feat/firmware, feat/agora, feat/backend, feat/frontend, feat/integration branches are optional; sync from main before use. Avoid long-lived integration branch; no force-push. One owner per file. If conflict, coordinate in person. Track tasks with issue numbers and acceptance criteria.
## Setup
Confirm write permissions for abqaryne and mpip0505; public read does not mean write. Keep API keys in ignored local env files. Confirm permitted starter use before scaffolding.
## Done means
Actual physical input and output tested; voice/RTC central; errors handled; no secrets; reproducible setup; real demo evidence and limitations documented.
