#pragma once

namespace esphome {
namespace tokentide_poller {

// Provider states, as the engine globals hold them.
static constexpr int STATE_OFF = 0;
static constexpr int STATE_OK = 1;
static constexpr int STATE_AUTH_ERROR = 2;
static constexpr int STATE_NET_ERROR = 3;
static constexpr int STATE_NO_DATA = 4;

// Limit levels: 0 = ok, 1 = near the limit, 2 = limit reached.
static constexpr int LIMIT_OK = 0;
static constexpr int LIMIT_NEAR = 1;
static constexpr int LIMIT_REACHED = 2;

// Providers without a server-side limit status (Codex, Gemini) are near
// their limit from this used percentage on.
static constexpr float NEAR_LIMIT_PCT = 90.0f;

// Device status, ordered by severity: the worst provider wins.
enum Status {
  STATUS_WAITING = 0,
  STATUS_NO_DATA,
  STATUS_OK,
  STATUS_OFF_PACE,
  STATUS_NEAR_LIMIT,
  STATUS_NET_ERROR,
  STATUS_TOKEN_ERROR,
  STATUS_LIMIT,
};

// One provider as the engine sees it. used_* are 0-100 (-1 unknown),
// elapsed_* 0..1 (-1 unknown), server_limit is a LIMIT_* level reported by
// the provider itself (-1 when it reports none).
struct ProviderReading {
  bool present{false};
  int state{STATE_OFF};
  int server_limit{-1};
  float used_5h{-1.0f};
  float used_7d{-1.0f};
  float elapsed_5h{-1.0f};
  float elapsed_7d{-1.0f};
};

struct StatusSummary {
  Status status{STATUS_WAITING};
  // Index of the provider that set the status, -1 when none did.
  int provider{-1};
  int limit_level{LIMIT_OK};
  // Highest known used percentage per window across present providers.
  float worst_5h{-1.0f};
  float worst_7d{-1.0f};
};

// A window is off pace when at least half of it is used and usage runs 15
// points or more ahead of the time elapsed.
inline bool window_off_pace(bool known, float used, float elapsed) {
  if (!known || used < 0.0f || elapsed < 0.0f)
    return false;
  float u = used > 100.0f ? 100.0f : used;
  return u >= 50.0f && u - elapsed * 100.0f >= 15.0f;
}

inline int pct_limit_level(float used) {
  if (used >= 100.0f)
    return LIMIT_REACHED;
  if (used >= NEAR_LIMIT_PCT)
    return LIMIT_NEAR;
  return LIMIT_OK;
}

// Limit level of one provider: the stricter of its own report (trusted only
// while its last poll succeeded) and its used percentages.
inline int provider_limit_level(const ProviderReading &p) {
  int lvl = p.state == STATE_OK && p.server_limit > LIMIT_OK ? p.server_limit : LIMIT_OK;
  int l5 = pct_limit_level(p.used_5h), l7 = pct_limit_level(p.used_7d);
  if (l5 > lvl)
    lvl = l5;
  if (l7 > lvl)
    lvl = l7;
  return lvl;
}

inline Status provider_status(const ProviderReading &p) {
  int lvl = provider_limit_level(p);
  if (lvl == LIMIT_REACHED)
    return STATUS_LIMIT;
  if (p.state == STATE_AUTH_ERROR)
    return STATUS_TOKEN_ERROR;
  if (p.state == STATE_NET_ERROR)
    return STATUS_NET_ERROR;
  if (lvl == LIMIT_NEAR)
    return STATUS_NEAR_LIMIT;
  bool k5 = p.used_5h >= 0.0f, k7 = p.used_7d >= 0.0f;
  if (window_off_pace(k5, p.used_5h, p.elapsed_5h) || window_off_pace(k7, p.used_7d, p.elapsed_7d))
    return STATUS_OFF_PACE;
  if (p.state == STATE_OK || k5 || k7)
    return STATUS_OK;
  if (p.state == STATE_NO_DATA)
    return STATUS_NO_DATA;
  return STATUS_WAITING;
}

// Folds every present provider into one device status. With several
// providers, "no data" from one of them never hides a healthy other: it
// only shows when no provider has anything better to report.
inline StatusSummary summarize_providers(const ProviderReading *providers, int count) {
  StatusSummary s;
  for (int i = 0; i < count; i++) {
    const ProviderReading &p = providers[i];
    if (!p.present)
      continue;
    Status st = provider_status(p);
    if (s.provider < 0 || st > s.status) {
      s.status = st;
      s.provider = i;
    }
    int lvl = provider_limit_level(p);
    if (lvl > s.limit_level)
      s.limit_level = lvl;
    if (p.used_5h > s.worst_5h)
      s.worst_5h = p.used_5h;
    if (p.used_7d > s.worst_7d)
      s.worst_7d = p.used_7d;
  }
  return s;
}

}  // namespace tokentide_poller
}  // namespace esphome
