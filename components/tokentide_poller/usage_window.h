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

// Claude's 5h window: known (the response carries its utilization), unknown
// (no response with data yet), or no limit (verified Ultra accounts report
// only the weekly window).
enum Window5hState {
  WINDOW_5H_UNKNOWN = 0,
  WINDOW_5H_KNOWN,
  WINDOW_5H_NO_LIMIT,
};

// State after one response. A weekly utilization without a 5h one means the
// account has no 5h limit; a response with neither carries no data and keeps
// the previous state.
inline Window5hState next_5h_state(Window5hState prev, bool has_5h, bool has_7d) {
  if (has_5h)
    return WINDOW_5H_KNOWN;
  if (has_7d)
    return WINDOW_5H_NO_LIMIT;
  return prev;
}

}  // namespace tokentide_poller
}  // namespace esphome
