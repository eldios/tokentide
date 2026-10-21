// Host test for the usage-window math, the Gemini quota mapping and the
// device status summary: `just test`.
#include "../components/tokentide_poller/gemini_quota.h"
#include "../components/tokentide_poller/status_summary.h"
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

static ProviderReading reading(int state, float u5, float u7, float e5 = -1.0f, float e7 = -1.0f,
                               int server_limit = -1) {
  ProviderReading p;
  p.present = true;
  p.state = state;
  p.server_limit = server_limit;
  p.used_5h = u5;
  p.used_7d = u7;
  p.elapsed_5h = e5;
  p.elapsed_7d = e7;
  return p;
}

static void test_status_summary() {
  expect_i("on pace", window_off_pace(true, 60.0f, 0.5f), 0);
  expect_i("off pace", window_off_pace(true, 65.0f, 0.5f), 1);
  expect_i("low usage never off pace", window_off_pace(true, 40.0f, 0.0f), 0);
  expect_i("unknown elapsed", window_off_pace(true, 90.0f, -1.0f), 0);
  expect_i("unknown usage", window_off_pace(false, 90.0f, 0.1f), 0);
  expect_i("over 100 stays off pace", window_off_pace(true, 120.0f, 0.86f), 1);
  expect_i("whole percent, rounded up", window_off_pace(true, 64.6f, 0.5f), 1);
  expect_i("whole percent, rounded down", window_off_pace(true, 64.4f, 0.5f), 0);

  expect_i("pct ok", pct_limit_level(89.0f), LIMIT_OK);
  expect_i("pct near", pct_limit_level(90.0f), LIMIT_NEAR);
  expect_i("pct reached", pct_limit_level(100.0f), LIMIT_REACHED);
  expect_i("pct unknown", pct_limit_level(-1.0f), LIMIT_OK);

  // Claude ok, Codex at 100%: the limit comes from Codex.
  ProviderReading p[3] = {reading(STATE_OK, 20.0f, 10.0f, 0.5f, 0.5f, LIMIT_OK),
                          reading(STATE_OK, 100.0f, 40.0f, 0.6f, 0.5f), ProviderReading{}};
  StatusSummary s = summarize_providers(p, 3);
  expect_i("codex limit status", s.status, STATUS_LIMIT);
  expect_i("codex limit level", s.limit_level, LIMIT_REACHED);
  expect("worst 5h", s.worst_5h, 100.0f);
  expect("worst 7d", s.worst_7d, 40.0f);

  // Claude's own warning header counts while its poll succeeds.
  p[1] = reading(STATE_OK, 10.0f, 10.0f, 0.5f, 0.5f);
  p[0] = reading(STATE_OK, 70.0f, 30.0f, 0.9f, 0.5f, LIMIT_NEAR);
  s = summarize_providers(p, 3);
  expect_i("claude near", s.status, STATUS_NEAR_LIMIT);
  expect_i("claude near level", s.limit_level, LIMIT_NEAR);

  // A token error wins over stale data that still reads fine.
  p[0] = reading(STATE_AUTH_ERROR, 30.0f, 20.0f, 0.5f, 0.5f, LIMIT_NEAR);
  s = summarize_providers(p, 3);
  expect_i("stale data, token error", s.status, STATUS_TOKEN_ERROR);
  expect_i("stale server level ignored", s.limit_level, LIMIT_OK);

  p[0] = reading(STATE_NET_ERROR, -1.0f, -1.0f);
  s = summarize_providers(p, 3);
  expect_i("network error", s.status, STATUS_NET_ERROR);

  // Off pace and healthy.
  p[0] = reading(STATE_OK, 80.0f, 20.0f, 0.4f, 0.5f, LIMIT_OK);
  s = summarize_providers(p, 3);
  expect_i("off pace", s.status, STATUS_OFF_PACE);
  p[0] = reading(STATE_OK, 20.0f, 20.0f, 0.4f, 0.5f, LIMIT_OK);
  s = summarize_providers(p, 3);
  expect_i("all ok", s.status, STATUS_OK);

  // Gemini without data next to a healthy provider stays ok; alone it
  // shows as no data, not as waiting.
  p[2] = reading(STATE_NO_DATA, -1.0f, -1.0f);
  s = summarize_providers(p, 3);
  expect_i("no data hidden by ok", s.status, STATUS_OK);
  ProviderReading only_gemini[3] = {ProviderReading{}, ProviderReading{}, reading(STATE_NO_DATA, -1.0f, -1.0f)};
  s = summarize_providers(only_gemini, 3);
  expect_i("only no data", s.status, STATUS_NO_DATA);

  ProviderReading booting[3] = {reading(STATE_OFF, -1.0f, -1.0f), ProviderReading{}, ProviderReading{}};
  s = summarize_providers(booting, 3);
  expect_i("waiting", s.status, STATUS_WAITING);
  expect("waiting worst 5h", s.worst_5h, -1.0f);

  ProviderReading none[3] = {};
  s = summarize_providers(none, 3);
  expect_i("no provider", s.status, STATUS_WAITING);
}

static void test_status_edges() {
  // Claude's "rejected" header is a limit even with low percentages.
  ProviderReading p[3] = {reading(STATE_OK, 10.0f, 5.0f, 0.5f, 0.5f, LIMIT_REACHED), ProviderReading{},
                          ProviderReading{}};
  StatusSummary s = summarize_providers(p, 3);
  expect_i("rejected header", s.status, STATUS_LIMIT);
  expect_i("rejected header level", s.limit_level, LIMIT_REACHED);

  // After a network error the last header no longer counts.
  p[0] = reading(STATE_NET_ERROR, 30.0f, 20.0f, 0.5f, 0.5f, LIMIT_REACHED);
  s = summarize_providers(p, 3);
  expect_i("stale header on network error", s.status, STATUS_NET_ERROR);
  expect_i("stale header level", s.limit_level, LIMIT_OK);

  // The 7d window alone can set the limit.
  p[0] = reading(STATE_OK, 20.0f, 100.0f, 0.5f, 0.5f, LIMIT_OK);
  s = summarize_providers(p, 3);
  expect_i("limit from 7d", s.status, STATUS_LIMIT);
  expect_i("limit from 7d level", s.limit_level, LIMIT_REACHED);

  // Precedence across providers: limit > token error > network error >
  // near limit > off pace > ok.
  ProviderReading mix[3] = {reading(STATE_AUTH_ERROR, -1.0f, -1.0f), reading(STATE_OK, 92.0f, 10.0f, 0.95f, 0.1f),
                            reading(STATE_NET_ERROR, 20.0f, 20.0f, 0.5f, 0.5f)};
  s = summarize_providers(mix, 3);
  expect_i("token error over network and near", s.status, STATUS_TOKEN_ERROR);
  expect_i("near level kept under token error", s.limit_level, LIMIT_NEAR);
  mix[1] = reading(STATE_OK, 100.0f, 10.0f, 0.95f, 0.1f);
  s = summarize_providers(mix, 3);
  expect_i("limit over token error", s.status, STATUS_LIMIT);
  mix[0] = reading(STATE_OK, 80.0f, 20.0f, 0.4f, 0.5f);
  mix[1] = reading(STATE_OK, 92.0f, 10.0f, 0.95f, 0.1f);
  s = summarize_providers(mix, 3);
  expect_i("network error over near and off pace", s.status, STATUS_NET_ERROR);
  mix[2] = reading(STATE_OK, 20.0f, 20.0f, 0.5f, 0.5f);
  s = summarize_providers(mix, 3);
  expect_i("near over off pace", s.status, STATUS_NEAR_LIMIT);
  mix[1] = reading(STATE_OK, 10.0f, 10.0f, 0.5f, 0.5f);
  s = summarize_providers(mix, 3);
  expect_i("off pace over ok", s.status, STATUS_OFF_PACE);

  // Network error with a stale 100%: the window that has reset counts as
  // unknown, one still running keeps the limit.
  ProviderReading net[3] = {ProviderReading{}, reading(STATE_NET_ERROR, 100.0f, 40.0f, 1.0f, 0.5f),
                            ProviderReading{}};
  s = summarize_providers(net, 3);
  expect_i("reset window dropped", s.status, STATUS_NET_ERROR);
  expect_i("reset window level", s.limit_level, LIMIT_OK);
  expect("reset window worst 5h", s.worst_5h, -1.0f);
  expect("running window worst 7d", s.worst_7d, 40.0f);
  net[1] = reading(STATE_NET_ERROR, 40.0f, 100.0f, 0.5f, 1.0f);
  s = summarize_providers(net, 3);
  expect_i("reset 7d window dropped", s.status, STATUS_NET_ERROR);
  expect_i("reset 7d window level", s.limit_level, LIMIT_OK);
  expect("running window worst 5h", s.worst_5h, 40.0f);
  expect("reset window worst 7d", s.worst_7d, -1.0f);
  net[1] = reading(STATE_NET_ERROR, 100.0f, 40.0f, 0.7f, 0.5f);
  s = summarize_providers(net, 3);
  expect_i("running window keeps limit", s.status, STATUS_LIMIT);
  net[1] = reading(STATE_NET_ERROR, 100.0f, 40.0f, -1.0f, -1.0f);
  s = summarize_providers(net, 3);
  expect_i("unknown reset keeps limit", s.status, STATUS_LIMIT);
  net[1] = reading(STATE_OK, 100.0f, 40.0f, 1.0f, 0.5f);
  s = summarize_providers(net, 3);
  expect_i("successful poll keeps limit", s.status, STATUS_LIMIT);
}

int main() {
  test_gemini_quota();
  test_status_summary();
  test_status_edges();
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
