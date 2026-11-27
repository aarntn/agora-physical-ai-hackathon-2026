# Hardware bring-up checklist
Reference: https://mosaico.ai/en/guide and https://mosaico.ai/en/faq
Organizer starter: https://github.com/qiuyanli1990/mosaico-BotStation
- [ ] Inventory board revision, supplied modules, cables and power
- [ ] Confirm supported firmware/BSP and flash/recovery instructions with mentor before flashing
- [ ] Test USB power, Wi-Fi/hotspot, screen/touch, microphone and speaker
- [ ] Test IMU readings, orientation baseline and haptic response if accessible
- [ ] Camera module if supplied: capture actual image, confirm transfer and legibility
- [ ] Test connectivity loss/recovery; verify device events have unique IDs and timestamps
- [ ] Record exact firmware version and reproduction steps
Do not assume camera, PIR/IR, second board, battery runtime or custom firmware access. Keep powered via USB where appropriate. Use synthetic props, not real sensitive data. Return kits as instructed.
Fallback: core IMU/touch/audio interaction if camera unavailable; if no device integration, disclose missing rubric evidence rather than simulate it as real.
