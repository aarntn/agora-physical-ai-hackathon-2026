/* Host parity test: C port vs Python reference on SIMULATED vectors.
 *   cc -O2 -std=c99 -I.. ../nasocheck_dsp.c test_vectors.c -lm -o test_vectors
 *   ./test_vectors ../../../fixtures/dsp_vectors/ * .txt   (all vector files)
 */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>

#include "nasocheck_dsp.h"

static int close_to(float a, float b, float tol) { return fabsf(a - b) <= tol; }

static int run_case(const char *path) {
    FILE *f = fopen(path, "r");
    if (!f) { perror(path); return 1; }
    float fs_imu, fs_mic, e_ratio, e_spread, e_snr;
    int na, nm, e_rv, e_voiced, e_clip, e_sv;
    if (fscanf(f, "%f %f %d %d", &fs_imu, &fs_mic, &na, &nm) != 4 ||
        fscanf(f, "%d %f %f %d %d %d %f", &e_rv, &e_ratio, &e_spread, &e_voiced, &e_clip,
               &e_sv, &e_snr) != 7) {
        fprintf(stderr, "%s: bad header\n", path);
        fclose(f);
        return 1;
    }
    static nc_state_t st;
    nc_init(&st, NULL, fs_imu, fs_mic);
    /* interleave the streams as a device would; framing makes order irrelevant */
    for (int i = 0; i < na; i++) {
        float x, y, z;
        if (fscanf(f, "%f %f %f", &x, &y, &z) != 3) { fclose(f); return 1; }
        nc_push_accel(&st, x, y, z);
    }
    for (int i = 0; i < nm; i++) {
        int s;
        if (fscanf(f, "%d", &s) != 1) { fclose(f); return 1; }
        nc_push_mic_i16(&st, (int16_t)s);
    }
    fclose(f);

    nc_result_t r;
    nc_finish(&st, &r);
    int ok = r.ratio_valid == e_rv && r.voiced_frames == e_voiced && r.mic_clipped == e_clip &&
             r.snr_valid == e_sv && close_to(r.ratio_db, e_ratio, 0.05f) &&
             close_to(r.spread_db, e_spread, 0.05f) && close_to(r.accel_snr_db, e_snr, 0.1f);
    printf("%s %s: ratio %.3f (exp %.3f) spread %.3f (%.3f) voiced %d (%d) clip %d (%d) snr %.3f (%.3f)\n",
           ok ? "PASS" : "FAIL", path, r.ratio_db, e_ratio, r.spread_db, e_spread, r.voiced_frames,
           e_voiced, r.mic_clipped, e_clip, r.accel_snr_db, e_snr);
    return ok ? 0 : 1;
}

int main(int argc, char **argv) {
    float v[5] = {1, 2, 3, 4, 5};
    if (!close_to(nc_percentile_sorted(v, 5, 25.0f), 2.0f, 1e-6f) ||
        !close_to(nc_percentile_sorted(v, 4, 50.0f), 2.5f, 1e-6f)) {
        puts("FAIL percentile");
        return 1;
    }
    if (argc < 2) { fprintf(stderr, "usage: %s vector.txt...\n", argv[0]); return 2; }
    int fails = 0;
    for (int i = 1; i < argc; i++) fails += run_case(argv[i]);
    return fails ? 1 : 0;
}
