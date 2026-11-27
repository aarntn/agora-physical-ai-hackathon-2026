# Firmware (NasoCheck)

Start with [docs/HARDWARE.md](../docs/HARDWARE.md) and the organizer BotStation reference. Confirm the kit revision and available modules before flashing or choosing a framework.

## `nasocheck_dsp/`: per-trial analysis, ready to drop in
Plain C99 with no heap and no threads, ~4 KB of state. It is an ESP-IDF component: copy the folder into `components/`. It is a streaming port of [backend/nasocheck/dsp.py](../backend/nasocheck/dsp.py), which is the specification. Parity is checked on SIMULATED vectors in CI. Locally the build was tested with zig cc 0.17.1; ESP32 has not been tested.

```c
static nc_state_t st;                       // keep off the stack
nc_init(&st, NULL, imu_hz_measured, 16000.0f);
// for the whole capture window (including ~0.3 s silence before speech):
nc_push_accel(&st, ax, ay, az);             // each IMU sample, any linear unit
nc_push_mic_i16(&st, pcm);                  // each mic sample, AGC OFF
nc_result_t r; nc_finish(&st, &r);          // -> trial JSON
```

Host test: `cc -std=c99 -I. nasocheck_dsp.c test/test_vectors.c -lm -o t && ./t ../../fixtures/dsp_vectors/*.txt`

## Capture sequence (proposal §8)
1. Before the session, `POST /session` (header `X-Device-Key`) with `{"lang":"ms","start_agent":true}`. The response gives `channel`, `device_token` and `device_uid` for joining Agora RTC.
2. On tap: show a 1 s countdown and **mute agent playback**, because the speaker vibrates the IMU.
3. Capture ~2.3 s. Begin with ~0.3 s of silence, which is the accelerometer noise reference for `accel_snr_db`. Don't touch the screen.
4. Run `nc_finish` and `POST /trials`:
   ```json
   {"trial_id":"<session>-004","session_id":"<session>","start_ms":0,"end_ms":2300,
    "ratio_db":-18.4,"spread_db":1.9,"voiced_frames":41,"mic_clipped":false,
    "accel_snr_db":14.2,"imu_hz":1594}
   ```
   - Omit `type` and the backend assigns the current protocol step.
   - Send `null` for `ratio_db` or `accel_snr_db` when `ratio_valid` or `snr_valid` is 0.
   - Retry the same `trial_id` on a network error; it is idempotent.
5. Unmute the agent. Show `status` and `score_db` from the response as a bar. `GET /session/{id}/next` gives the next instruction for the screen.

## Fallbacks if on-device DSP or Wi-Fi is a problem
- **No DSP on device:** send raw samples to `POST /trials/raw` (format in [backend/README.md](../backend/README.md)) and the backend runs the reference DSP.
- **No Wi-Fi:** print `NC_TRIAL <json>` or `NC_RAW <json>` lines over USB serial and run `python backend/scripts/relay.py --port COMx`. Responses come back as `NC_RESP <json>`. Disclose the relay in the demo.

## Measure, don't assume
- **IMU rate**: BMI270 accel ODR up to 1600 Hz. Compute `imu_hz` from timestamps and send that, not the configured ODR. Use the smallest range (±2 g) for resolution.
- **Mic**: disable AGC/ALC in the codec or I2S pipeline. If you can't, say so and calibrate per session.
- **Rejection thresholds** are set with the backend's `NC_*` environment variables (see `GET /config`). Tune them on the day from the go/no-go data, then freeze them.
- Log raw captures for go/no-go: `<person>_<a|m|control>_<n>.accel.csv` (`t_s,ax,ay,az`) plus a 16-bit `.wav`, then run `python backend/scripts/gonogo.py --raw captures/ --plot accel.png`.
