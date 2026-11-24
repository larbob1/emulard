/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Synthetic, import-free x86-64 calling convention smoke fixture. */
typedef unsigned long long u64;
#if defined(_MSC_VER)
#define NOINLINE __declspec(noinline)
#else
#define NOINLINE __attribute__((noinline))
#endif
static NOINLINE u64 mix(u64 a, u64 b, u64 c, u64 d, u64 e, u64 f) {
    return a + 3*b + 5*c + 7*d + 11*e + 13*f;
}
static volatile u64 values[6] = {1, 2, 3, 4, 5, 6};
static int run(void) {
    u64 (*volatile fn)(u64,u64,u64,u64,u64,u64) = mix;
    u64 got = fn(values[0], values[1], values[2], values[3], values[4], values[5]);
    return got == 183 ? 0 : 1;
}
#if defined(_WIN32)
int mainCRTStartup(void) { return run(); }
#else
int main(void) { return run(); }
#endif
