# Agora integration
Product and stack TBD. Prefer organizer starter if permitted and compatible.
Official quickstart: https://docs.agora.io/en/ai/platform/get-started/quickstart
Organizer Node/TS commands (Bash; verify script before executing):
```sh
curl -fsSL https://raw.githubusercontent.com/AgoraIO/cli/main/install.sh | sh
agora login
agora init my-test --template nextjs
cd my-test
npm install
agora project env write server/.env.local
npm install agora-agents
npm run dev
```
Choose new project when prompted; scaffold in scratch directory then integrate into repo after agreement. Never commit server/.env.local. Windows users use Git Bash/WSL where supported. Python alternative: https://github.com/AgoraIO/agora-agents-python.
## Smoke test
- [ ] Start/stop agent; real device joins channel
- [ ] Speak and receive audible response
- [ ] Interrupt agent; verify session remains consistent
- [ ] If using tools, test authorized validated HTTP call and error response: https://docs.agora.io/en/ai/build/tools/custom-tools
- [ ] If using images, check prerequisites and receipt: https://docs.agora.io/en/ai/platform/build/send-multimodal-messages
- [ ] Test network loss and reconnection, record latency
## Submission explanation
Exact Agora products and SDK versions: TBD. Where they run: TBD. Why real-time interaction matters: TBD. Show working event in demo. Keep tokens/credentials server-side; validate tool actions, apply idempotency and human confirmation for consequential operations. MCP optional, not mandatory.
