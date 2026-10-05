#pragma once

#include "esphome/core/component.h"
#include "esphome/core/automation.h"
#include "esphome/core/helpers.h"

#include <string>

namespace esphome {
namespace tokentide_poller {

// Polls Anthropic's unified rate-limit headers with a minimal probe
// request, from a dedicated FreeRTOS task so the main loop (LVGL, BLE,
// everything) never blocks on TLS + HTTP. Results are handed back to the
// main loop via a done flag polled in loop(), where the on_result
// automation fires.
class TokentidePoller : public Component {
 public:
  void set_token(const std::string &token) { this->token_ = token; }
  void set_probe_model(const std::string &model) { this->model_ = model; }

  void add_on_result_callback(
      std::function<void(float, float, int64_t, int64_t, std::string, int)> &&cb) {
    this->callbacks_.add(std::move(cb));
  }

  void add_on_status_callback(std::function<void(std::string)> &&cb) {
    this->status_callbacks_.add(std::move(cb));
  }

  // Spawn a poll task; no-op while a poll is already in flight.
  void poll();

  // Spawn an Anthropic status-page check task; no-op while one runs.
  // Reports the statuspage indicator (none/minor/major/critical, or
  // "unknown" when the request fails).
  void check_status();

  void loop() override;
  float get_setup_priority() const override { return setup_priority::LATE; }

 protected:
  static void poll_task(void *param);
  void run_probe_();
  static void status_task(void *param);
  void run_status_probe_();
  // Spawns the poll task; the caller must hold the TLS gate.
  void start_poll_task_();

  std::string token_;
  std::string model_;

  // Poll requested while the TLS gate was busy; loop() retries it. The
  // YAML side flags poll_in_flight before calling poll, so a declined
  // poll must still happen or the UI sticks on the refreshing label.
  bool poll_pending_{false};

  // Written by the task, consumed by loop(). done_ is the release fence:
  // the task writes it last, loop() reads it first.
  volatile bool done_{false};
  bool running_{false};
  float result_u5_{-1.0f};
  float result_u7_{-1.0f};
  int64_t result_r5_{0};
  int64_t result_r7_{0};
  std::string result_status_;
  int result_code_{0};

  volatile bool status_done_{false};
  bool status_running_{false};
  std::string status_result_;

  CallbackManager<void(float, float, int64_t, int64_t, std::string, int)> callbacks_;
  CallbackManager<void(std::string)> status_callbacks_;
};

class PollResultTrigger
    : public Trigger<float, float, int64_t, int64_t, std::string, int> {
 public:
  explicit PollResultTrigger(TokentidePoller *parent) {
    parent->add_on_result_callback(
        [this](float u5, float u7, int64_t r5, int64_t r7, std::string status, int code) {
          this->trigger(u5, u7, r5, r7, status, code);
        });
  }
};

class StatusResultTrigger : public Trigger<std::string> {
 public:
  explicit StatusResultTrigger(TokentidePoller *parent) {
    parent->add_on_status_callback(
        [this](std::string indicator) { this->trigger(indicator); });
  }
};

template<typename... Ts> class PollAction : public Action<Ts...>, public Parented<TokentidePoller> {
 public:
  void play(const Ts &...x) override { this->parent_->poll(); }
};

template<typename... Ts> class CheckStatusAction : public Action<Ts...>, public Parented<TokentidePoller> {
 public:
  void play(const Ts &...x) override { this->parent_->check_status(); }
};

}  // namespace tokentide_poller
}  // namespace esphome
