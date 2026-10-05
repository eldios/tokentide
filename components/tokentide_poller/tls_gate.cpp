#include "tls_gate.h"

namespace esphome {
namespace tokentide_poller {

// Plain bool, no atomics: taken and given only from the main loop.
static bool tls_gate_busy = false;

bool tls_gate_take() {
  if (tls_gate_busy)
    return false;
  tls_gate_busy = true;
  return true;
}

void tls_gate_give() { tls_gate_busy = false; }

}  // namespace tokentide_poller
}  // namespace esphome
