#pragma once

namespace esphome {
namespace tokentide_poller {

// Single-slot gate serializing the TLS poll tasks across providers (usage
// probe, status check, ChatGPT poll): a TLS handshake transiently costs
// tens of KB of heap and the no-PSRAM boards cannot afford two at once.
// Main-loop use only: take before spawning a task, give from loop() when
// the task reports done.
bool tls_gate_take();
void tls_gate_give();

}  // namespace tokentide_poller
}  // namespace esphome
