#pragma once

#include "esphome/core/component.h"
#include "esphome/core/automation.h"
#include "esphome/core/helpers.h"

#include <string>

namespace esphome {
namespace tokentide_poller {

// Polls ChatGPT plan usage (chatgpt.com/backend-api/wham/usage) with an
// OAuth access token the device refreshes autonomously from its own
// refresh-token chain (auth.openai.com, public Codex client, no secret).
// Refresh tokens rotate and the old one is single-use, so every rotation
// is committed to NVS before the new token is relied on. Same task
// pattern as TokentidePoller: TLS + HTTP run in a short-lived FreeRTOS
// task, results are consumed from loop().
class OpenAIUsage : public Component {
 public:
  void set_refresh_token(const std::string &t) { this->seed_refresh_token_ = t; }
  void set_account_id(const std::string &a) { this->account_id_ = a; }
  void set_client_id(const std::string &c) { this->client_id_ = c; }

  // u5/u7 are used_percent 0-100 (-1 unknown), r5/r7 reset epochs
  // (0 unknown). code: HTTP status of the usage GET, 0 = network error,
  // 401 also covers a dead refresh chain (re-seed to recover).
  void add_on_result_callback(std::function<void(float, float, int64_t, int64_t, int)> &&cb) {
    this->callbacks_.add(std::move(cb));
  }

  // Spawn a poll task; no-op while one is in flight or after the refresh
  // chain died (only a fresh seed token recovers that).
  void poll();

  void setup() override;
  void loop() override;
  float get_setup_priority() const override { return setup_priority::LATE; }

 protected:
  static void poll_task(void *param);
  // Spawns the poll task; the caller must hold the TLS gate.
  void start_poll_task_();
  void run_poll_();
  bool ensure_access_token_();
  bool refresh_tokens_();
  void fetch_usage_();
  void persist_refresh_token_();

  std::string seed_refresh_token_;
  std::string account_id_;
  std::string client_id_;

  std::string refresh_token_;
  std::string access_token_;
  int64_t access_refresh_due_us_{0};

  // Definitive token-endpoint rejection (expired/reused/revoked chain).
  bool auth_dead_{false};

  // Written by the task, consumed by loop(); done_ is the release fence.
  volatile bool done_{false};
  bool running_{false};
  // Poll requested while the TLS gate was busy; loop() retries it.
  bool poll_pending_{false};
  float result_u5_{-1.0f};
  float result_u7_{-1.0f};
  int64_t result_r5_{0};
  int64_t result_r7_{0};
  int result_code_{0};

  CallbackManager<void(float, float, int64_t, int64_t, int)> callbacks_;
};

class OpenAIResultTrigger : public Trigger<float, float, int64_t, int64_t, int> {
 public:
  explicit OpenAIResultTrigger(OpenAIUsage *parent) {
    parent->add_on_result_callback([this](float u5, float u7, int64_t r5, int64_t r7, int code) {
      this->trigger(u5, u7, r5, r7, code);
    });
  }
};

template<typename... Ts> class OpenAIPollAction : public Action<Ts...>, public Parented<OpenAIUsage> {
 public:
  // const Ts &... matches the Action base; a by-value pack only overrides
  // for the empty instantiation and breaks inside parameterized
  // automations (e.g. on_result).
  void play(const Ts &...x) override { this->parent_->poll(); }
};

}  // namespace tokentide_poller
}  // namespace esphome
