#pragma once

#include <cstdint>

namespace esphome {
namespace tokentide_poller {

// Nominal window lengths for providers whose API names the window but
// does not report its length (Claude headers, Gemini buckets).
static constexpr int64_t WINDOW_5H_S = 5 * 3600;
static constexpr int64_t WINDOW_7D_S = 7 * 86400;

// Fraction (0..1) of a usage window already elapsed at `now`, derived from
// the window's reset epoch and length; -1 when any input is unknown (0).
// A reset already in the past reads as a full window until the next poll.
inline float window_elapsed(int64_t reset_epoch, int64_t window_s, int64_t now) {
  if (reset_epoch <= 0 || window_s <= 0 || now <= 0)
    return -1.0f;
  int64_t left = reset_epoch - now;
  if (left <= 0)
    return 1.0f;
  if (left >= window_s)
    return 0.0f;
  return 1.0f - (float) left / (float) window_s;
}

}  // namespace tokentide_poller
}  // namespace esphome
