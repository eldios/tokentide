// Host test for the usage-window math: `just test`.
#include "../components/tokentide_poller/usage_window.h"

#include <cmath>
#include <cstdio>

using esphome::tokentide_poller::window_elapsed;
using esphome::tokentide_poller::WINDOW_5H_S;
using esphome::tokentide_poller::WINDOW_7D_S;

static int failures = 0;

static void expect(const char *name, float got, float want) {
  if (std::fabs(got - want) > 1e-4f) {
    std::printf("FAIL %s: got %f, want %f\n", name, got, want);
    failures++;
  }
}

int main() {
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
