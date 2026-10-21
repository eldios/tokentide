// Host test for the usage-window math and the Gemini quota mapping:
// `just test`.
#include "../components/tokentide_poller/gemini_quota.h"
#include "../components/tokentide_poller/usage_window.h"

#include <cmath>
#include <cstdio>

using namespace esphome::tokentide_poller;

static int failures = 0;

static void expect(const char *name, float got, float want) {
  if (std::fabs(got - want) > 1e-4f) {
    std::printf("FAIL %s: got %f, want %f\n", name, got, want);
    failures++;
  }
}

static void expect_i(const char *name, long long got, long long want) {
  if (got != want) {
    std::printf("FAIL %s: got %lld, want %lld\n", name, got, want);
    failures++;
  }
}

static void expect_s(const char *name, const std::string &got, const char *want) {
  if (got != want) {
    std::printf("FAIL %s: got %s, want %s\n", name, got.c_str(), want);
    failures++;
  }
}

static QuotaBucket bucket(const char *id, const char *window, float remaining, const char *reset,
                          bool disabled = false) {
  QuotaBucket b;
  b.id = id;
  b.window = window;
  b.remaining = remaining;
  b.reset_time = reset;
  b.disabled = disabled;
  return b;
}

static void test_gemini_quota() {
  // 2026-10-27T12:00:00Z and 2026-10-21T15:30:00Z as unix epochs.
  const int64_t wk = 1793102400;
  const int64_t h5 = 1792596600;
  expect_i("rfc3339", parse_reset_ts("2026-10-27T12:00:00Z"), wk);
  expect_i("rfc3339 fraction", parse_reset_ts("2026-10-21T15:30:00.123456Z"), h5);
  expect_i("epoch", parse_reset_ts("1792596600"), h5);
  expect_i("empty reset", parse_reset_ts(""), 0);

  expect("used from fraction", bucket_used_pct(bucket("gemini-5h", "5h", 0.25f, "")), 75.0f);
  expect("full bucket", bucket_used_pct(bucket("gemini-5h", "5h", 1.0f, "")), 0.0f);
  expect("omitted zero fraction", bucket_used_pct(bucket("gemini-weekly", "weekly", -1.0f, "2026-10-27T12:00:00Z")),
         100.0f);
  expect("no fraction, no reset", bucket_used_pct(bucket("gemini-5h", "5h", -1.0f, "")), -1.0f);

  GeminiReading r = pick_gemini_windows({
      bucket("gemini-5h", "5h", 0.9f, "2026-10-21T15:30:00Z"),
      bucket("gemini-weekly", "weekly", 0.6f, "2026-10-30T00:00:00Z"),
      bucket("gemini-argon-wtu-weekly", "weekly", -1.0f, "2026-10-27T12:00:00Z"),
      bucket("3p-5h", "5h", 0.0f, "2026-10-21T16:00:00Z"),
      bucket("3p-weekly", "weekly", 0.0f, "2026-10-28T00:00:00Z"),
  });
  expect("5h used", r.used_5h, 10.0f);
  expect_i("5h reset", r.reset_5h, h5);
  expect("weekly picks exhausted Argon", r.used_7d, 100.0f);
  expect_i("weekly reset from Argon", r.reset_7d, wk);

  r = pick_gemini_windows({
      bucket("gemini-5h", "", 0.5f, "2026-10-21T15:30:00Z"),
      bucket("gemini-weekly", "", 0.8f, "2026-10-27T12:00:00Z"),
      bucket("gemini-argon-weekly", "weekly", 0.1f, "2026-10-27T12:00:00Z", true),
  });
  expect("5h from id suffix", r.used_5h, 50.0f);
  expect("weekly from id suffix, disabled skipped", r.used_7d, 20.0f);

  r = pick_gemini_windows({bucket("3p-weekly", "weekly", 0.2f, "2026-10-28T00:00:00Z")});
  expect("only 3p: 5h unknown", r.used_5h, -1.0f);
  expect("only 3p: 7d unknown", r.used_7d, -1.0f);
  expect_i("only 3p: no reset", r.reset_7d, 0);

  expect_s("form encode", form_encode("1//0gAb-c_d.e~f+g=h i"), "1%2F%2F0gAb-c_d.e~f%2Bg%3Dh%20i");

  expect_i("backoff first failure", backoff_skip_polls(1), 0);
  expect_i("backoff second", backoff_skip_polls(2), 1);
  expect_i("backoff fourth", backoff_skip_polls(4), 7);
  expect_i("backoff capped", backoff_skip_polls(40), 15);
}

int main() {
  test_gemini_quota();
  const int64_t now = 1800000000;
  expect("unknown reset", window_elapsed(0, WINDOW_5H_S, now), -1.0f);
  expect("unknown clock", window_elapsed(now + 60, WINDOW_5H_S, 0), -1.0f);
  expect("unknown window", window_elapsed(now + 60, 0, now), -1.0f);
  expect("just started", window_elapsed(now + WINDOW_5H_S, WINDOW_5H_S, now), 0.0f);
  expect("reset beyond window", window_elapsed(now + 2 * WINDOW_5H_S, WINDOW_5H_S, now), 0.0f);
  expect("5% gone", window_elapsed(now + WINDOW_5H_S * 95 / 100, WINDOW_5H_S, now), 0.05f);
  expect("half gone", window_elapsed(now + WINDOW_7D_S / 2, WINDOW_7D_S, now), 0.5f);
  expect("95% gone", window_elapsed(now + WINDOW_7D_S * 5 / 100, WINDOW_7D_S, now), 0.95f);
  expect("reset now", window_elapsed(now, WINDOW_5H_S, now), 1.0f);
  expect("reset passed", window_elapsed(now - 10, WINDOW_5H_S, now), 1.0f);
  if (failures == 0)
    std::puts("usage_window_test: ok");
  return failures == 0 ? 0 : 1;
}
