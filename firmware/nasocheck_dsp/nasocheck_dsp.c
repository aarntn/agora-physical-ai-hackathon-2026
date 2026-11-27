#include "nasocheck_dsp.h"

#include <math.h>
#include <stdlib.h>
#include <string.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

void nc_default_config(nc_config_t *c) {
    c->frame_s = 0.040f;
    c->hpf_hz = 80.0f;
    c->accel_lpf_hz = 700.0f;
    c->match_bands = 1;
    c->voiced_rel_db = 25.0f;
    c->voiced_floor_dbfs = -55.0f;
    c->clip_level = 0.98f;
    c->clip_min_samples = 3;
    c->skip_frames = 1;
}

/* RBJ cookbook, Q = 1/sqrt(2); coefficients computed in double like dsp.biquad */
static void biquad_init(nc_biquad_t *f, int highpass, float fc, float fs, int enabled) {
    double w0 = 2.0 * M_PI * fc / fs, c = cos(w0), alpha = sin(w0) / (2.0 * 0.70710678118654752);
    double a0 = 1.0 + alpha;
    double b0 = highpass ? (1.0 + c) / 2.0 : (1.0 - c) / 2.0;
    double b1 = highpass ? -(1.0 + c) : (1.0 - c);
    memset(f, 0, sizeof(*f));
    f->enabled = enabled;
    f->b0 = (float)(b0 / a0);
    f->b1 = (float)(b1 / a0);
    f->b2 = (float)(b0 / a0);
    f->a1 = (float)(-2.0 * c / a0);
    f->a2 = (float)((1.0 - alpha) / a0);
}

static inline float biquad_run(nc_biquad_t *f, float x) {
    if (!f->enabled) return x;
    float y = f->b0 * x + f->z1; /* transposed direct form II, same as scipy lfilter */
    f->z1 = f->b1 * x - f->a1 * y + f->z2;
    f->z2 = f->b2 * x - f->a2 * y;
    return y;
}

static int frame_len(float fs, float frame_s) {
    int n = (int)lround((double)fs * frame_s);
    return n < 1 ? 1 : n;
}

void nc_init(nc_state_t *st, const nc_config_t *cfg, float fs_imu, float fs_mic) {
    memset(st, 0, sizeof(*st));
    if (cfg) st->cfg = *cfg; else nc_default_config(&st->cfg);
    st->fs_imu = fs_imu;
    st->fs_mic = fs_mic;
    st->la = frame_len(fs_imu, st->cfg.frame_s);
    st->lm = frame_len(fs_mic, st->cfg.frame_s);
    float lp = st->cfg.accel_lpf_hz;
    int acc_lp_on = lp < 0.45f * fs_imu;
    int mic_lp_on = st->cfg.match_bands && lp < 0.45f * fs_mic;
    for (int i = 0; i < 3; i++) {
        biquad_init(&st->acc_hp[i], 1, st->cfg.hpf_hz, fs_imu, 1);
        biquad_init(&st->acc_lp[i], 0, lp, fs_imu, acc_lp_on);
    }
    biquad_init(&st->mic_hp, 1, st->cfg.hpf_hz, fs_mic, 1);
    biquad_init(&st->mic_lp, 0, lp, fs_mic, mic_lp_on);
}

void nc_push_accel(nc_state_t *st, float x, float y, float z) {
    float v[3] = {x, y, z};
    for (int i = 0; i < 3; i++) {
        float f = biquad_run(&st->acc_lp[i], biquad_run(&st->acc_hp[i], v[i]));
        st->acc_sumsq += f * f;
    }
    if (++st->acc_count == st->la) {
        if (st->acc_frames < NC_MAX_FRAMES)
            st->acc_rms[st->acc_frames] = sqrtf(st->acc_sumsq / (float)st->la);
        st->acc_frames++;
        st->acc_sumsq = 0.0f;
        st->acc_count = 0;
    }
}

void nc_push_mic(nc_state_t *st, float s) {
    if (fabsf(s) >= st->cfg.clip_level) st->clip_count++;
    float f = biquad_run(&st->mic_lp, biquad_run(&st->mic_hp, s));
    st->mic_sumsq += f * f;
    if (++st->mic_count == st->lm) {
        if (st->mic_frames < NC_MAX_FRAMES)
            st->mic_rms[st->mic_frames] = sqrtf(st->mic_sumsq / (float)st->lm);
        st->mic_frames++;
        st->mic_sumsq = 0.0f;
        st->mic_count = 0;
    }
}

void nc_push_mic_i16(nc_state_t *st, int16_t s) { nc_push_mic(st, (float)s / 32768.0f); }

static float db(float x) { return 20.0f * log10f(x > 1e-12f ? x : 1e-12f); }

static int cmp_float(const void *a, const void *b) {
    float x = *(const float *)a, y = *(const float *)b;
    return (x > y) - (x < y);
}

float nc_percentile_sorted(const float *v, int n, float p) {
    double pos = p / 100.0 * (n - 1);
    int lo = (int)floor(pos);
    int hi = lo + 1 < n ? lo + 1 : n - 1;
    return (float)(v[lo] + (v[hi] - v[lo]) * (pos - lo));
}

static float median_of(float *buf, int n) {
    qsort(buf, (size_t)n, sizeof(float), cmp_float);
    return nc_percentile_sorted(buf, n, 50.0f);
}

void nc_finish(nc_state_t *st, nc_result_t *out) {
    memset(out, 0, sizeof(*out));
    out->mic_clipped = st->clip_count >= st->cfg.clip_min_samples;
    int n = st->acc_frames < st->mic_frames ? st->acc_frames : st->mic_frames;
    if (n > NC_MAX_FRAMES) n = NC_MAX_FRAMES;
    int k0 = st->cfg.skip_frames;
    if (n <= k0) { out->frames = n > 0 ? n : 0; return; }
    out->frames = n - k0;

    float maxdb = -1e30f;
    for (int i = k0; i < n; i++) {
        float d = db(st->mic_rms[i]);
        if (d > maxdb) maxdb = d;
    }
    float thr = maxdb - st->cfg.voiced_rel_db;
    if (thr < st->cfg.voiced_floor_dbfs) thr = st->cfg.voiced_floor_dbfs;

    int nv = 0, nu = 0;
    for (int i = k0; i < n; i++) {
        float md = db(st->mic_rms[i]);
        if (md >= thr) st->scratch[nv++] = db(st->acc_rms[i]) - md; /* ratio */
        else st->scratch2[nu++] = st->acc_rms[i];                   /* noise */
    }
    out->voiced_frames = nv;
    if (nv == 0) return;

    qsort(st->scratch, (size_t)nv, sizeof(float), cmp_float);
    out->ratio_valid = 1;
    out->ratio_db = nc_percentile_sorted(st->scratch, nv, 50.0f);
    out->spread_db = nc_percentile_sorted(st->scratch, nv, 75.0f) -
                     nc_percentile_sorted(st->scratch, nv, 25.0f);

    if (nu >= 2) {
        float noise = median_of(st->scratch2, nu);
        int j = 0;
        for (int i = k0; i < n; i++)
            if (db(st->mic_rms[i]) >= thr) st->scratch[j++] = st->acc_rms[i];
        float sig = median_of(st->scratch, j);
        out->snr_valid = 1;
        out->accel_snr_db = db(sig) - db(noise);
    }
}
