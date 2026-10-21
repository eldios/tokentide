#pragma once

#include "reset_time.h"

#include <cstdint>
#include <cstring>
#include <string>
#include <vector>

namespace esphome {
namespace tokentide_poller {

// One bucket of a Code Assist v1internal:retrieveUserQuotaSummary response
// (QuotaSummaryBucket). remaining is remainingFraction, or -1 when the
// field is absent.
struct QuotaBucket {
  std::string id;
  std::string window;
  float remaining{-1.0f};
  std::string reset_time;
  bool disabled{false};
};

// Gemini windows as TokenTide shows them: used 0-100 (-1 unknown) and
// reset epochs (0 unknown).
struct GeminiReading {
  float used_5h{-1.0f};
  float used_7d{-1.0f};
  int64_t reset_5h{0};
  int64_t reset_7d{0};
};

// Used percentage of a bucket, -1 when unknown. proto3 JSON omits a zero
// remainingFraction, so a bucket with a reset time and no fraction is
// exhausted rather than unknown.
inline float bucket_used_pct(const QuotaBucket &b) {
  if (b.remaining >= 0.0f) {
    float used = (1.0f - b.remaining) * 100.0f;
    return used < 0.0f ? 0.0f : used;
  }
  return b.reset_time.empty() ? -1.0f : 100.0f;
}

inline bool ends_with(const std::string &s, const char *suffix) {
  size_t n = strlen(suffix);
  return s.size() >= n && s.compare(s.size() - n, n, suffix) == 0;
}

// Maps the summary onto the 5h and 7d slots. Several Gemini buckets share
// a window (gemini-weekly and the Argon weekly bucket), so each slot shows
// the most used one: that is the limit that blocks first. Buckets for the
// third-party models (3p-*) belong to other providers and are skipped.
inline GeminiReading pick_gemini_windows(const std::vector<QuotaBucket> &buckets) {
  GeminiReading r;
  for (const auto &b : buckets) {
    if (b.disabled || b.id.rfind("3p", 0) == 0)
      continue;
    float used = bucket_used_pct(b);
    if (used < 0.0f)
      continue;
    bool is_5h = b.window == "5h" || (b.window.empty() && ends_with(b.id, "-5h"));
    bool is_7d = b.window == "weekly" || (b.window.empty() && ends_with(b.id, "-weekly"));
    if (is_5h && used > r.used_5h) {
      r.used_5h = used;
      r.reset_5h = parse_reset_ts(b.reset_time.c_str());
    } else if (is_7d && used > r.used_7d) {
      r.used_7d = used;
      r.reset_7d = parse_reset_ts(b.reset_time.c_str());
    }
  }
  return r;
}

// application/x-www-form-urlencoded value encoding (Google refresh tokens
// contain '/').
inline std::string form_encode(const std::string &s) {
  static const char *const HEX = "0123456789ABCDEF";
  std::string out;
  out.reserve(s.size() * 3);
  for (unsigned char c : s) {
    if ((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '-' || c == '_' ||
        c == '.' || c == '~') {
      out += (char) c;
    } else {
      out += '%';
      out += HEX[c >> 4];
      out += HEX[c & 0xF];
    }
  }
  return out;
}

// Polls to skip after `failures` consecutive failed polls: 0, 1, 3, 7,
// then 15 at most (half an hour at the default 120 s interval).
inline int backoff_skip_polls(int failures) {
  if (failures <= 1)
    return 0;
  if (failures >= 5)
    return 15;
  return (1 << (failures - 1)) - 1;
}

}  // namespace tokentide_poller
}  // namespace esphome
