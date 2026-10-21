#pragma once

#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <ctime>

namespace esphome {
namespace tokentide_poller {

// Reset timestamps arrive either as a unix epoch or as RFC3339 UTC;
// normalize to epoch without timegm (absent from newlib) via
// days-from-civil. Fractional seconds and the zone suffix are ignored.
inline int64_t parse_reset_ts(const char *v) {
  if (v == nullptr || v[0] == '\0')
    return 0;
  if (strchr(v, 'T') == nullptr)
    return atoll(v);
  struct tm tm {};
  if (strptime(v, "%Y-%m-%dT%H:%M:%S", &tm) == nullptr)
    return 0;
  int y = tm.tm_year + 1900, m = tm.tm_mon + 1, d = tm.tm_mday;
  y -= m <= 2;
  int64_t era = (y >= 0 ? y : y - 399) / 400;
  unsigned yoe = (unsigned) (y - era * 400);
  unsigned doy = (153u * (unsigned) (m + (m > 2 ? -3 : 9)) + 2u) / 5u + (unsigned) d - 1u;
  unsigned doe = yoe * 365u + yoe / 4u - yoe / 100u + doy;
  int64_t days = era * 146097LL + (int64_t) doe - 719468LL;
  return days * 86400LL + tm.tm_hour * 3600LL + tm.tm_min * 60LL + tm.tm_sec;
}

}  // namespace tokentide_poller
}  // namespace esphome
