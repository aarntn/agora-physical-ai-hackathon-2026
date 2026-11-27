/*
 * NasoCheck trial analysis: streaming C99 port of backend/nasocheck/dsp.py.
 * The Python file is the specification; fixtures/dsp_vectors checks parity.
 *
 * Usage per ~2 s capture (both streams must start at the same instant):
 *   nc_state_t st; nc_init(&st, NULL, imu_hz_measured, 16000.0f);
 *   ... nc_push_accel(&st, ax, ay, az);   // every IMU sample
 *   ... nc_push_mic_i16(&st, sample);     // every mic sample (AGC OFF)
 *   nc_result_t r; nc_finish(&st, &r);    // then send r as trial JSON
 *
 * No heap, no threads. sizeof(nc_state_t) is ~4 KB with NC_MAX_FRAMES 256.
 */
#ifndef NASOCHECK_DSP_H
#define NASOCHECK_DSP_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#ifndef NC_MAX_FRAMES
#define NC_MAX_FRAMES 256 /* 10.24 s at 40 ms frames */
#endif

typedef struct {
    float frame_s;           /* 0.040 */
    float hpf_hz;            /* 80 */
    float accel_lpf_hz;      /* 700 */
    int match_bands;         /* 1: low-pass mic at accel_lpf_hz too */
    float voiced_rel_db;     /* 25 */
    float voiced_floor_dbfs; /* -55 */
    float clip_level;        /* 0.98 */
    int clip_min_samples;    /* 3 */
    int skip_frames;         /* 1 */
} nc_config_t;

typedef struct {
    float b0, b1, b2, a1, a2;
    float z1, z2;
    int enabled;
} nc_biquad_t;

typedef struct {
    nc_config_t cfg;
    float fs_imu, fs_mic;
    int la, lm; /* samples per frame */
    nc_biquad_t acc_hp[3], acc_lp[3], mic_hp, mic_lp;
    float acc_sumsq, mic_sumsq;
    int acc_count, mic_count;
    int acc_frames, mic_frames;
    int clip_count;
    float acc_rms[NC_MAX_FRAMES];
    float mic_rms[NC_MAX_FRAMES];
    float scratch[NC_MAX_FRAMES];
    float scratch2[NC_MAX_FRAMES];
} nc_state_t;

typedef struct {
    int ratio_valid;
    float ratio_db;   /* median of 20log10(accel_rms/mic_rms) over voiced frames */
    float spread_db;  /* interquartile range of the same */
    int voiced_frames;
    int mic_clipped;
    int snr_valid;
    float accel_snr_db;
    int frames;       /* frames analysed after skip */
} nc_result_t;

void nc_default_config(nc_config_t *cfg);
void nc_init(nc_state_t *st, const nc_config_t *cfg, float fs_imu, float fs_mic);
void nc_push_accel(nc_state_t *st, float x, float y, float z);
void nc_push_mic(nc_state_t *st, float sample_fullscale);
void nc_push_mic_i16(nc_state_t *st, int16_t sample);
void nc_finish(nc_state_t *st, nc_result_t *out);

/* exposed for tests */
float nc_percentile_sorted(const float *sorted, int n, float p);

#ifdef __cplusplus
}
#endif
#endif
