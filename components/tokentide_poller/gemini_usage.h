#pragma once

#include "esphome/core/component.h"
#include "esphome/core/automation.h"
#include "esphome/core/helpers.h"

#include <string>

namespace esphome {
namespace tokentide_poller {

// Polls the Google AI plan quota windows (Code Assist
// v1internal:retrieveUserQuotaSummary, the call Antigravity makes) with an
// access token the device refreshes itself from a long-lived Google refresh
// token. Google refresh tokens do not rotate, so nothing is persisted; the
// Code Assist project id is looked up once per boot via loadCodeAssist.
// Same task pattern as TokentidePoller: TLS + HTTP run in a short-lived
// FreeRTOS task, results are consumed from loop().
class GeminiUsage : public Component {
 public:
  void set_refresh_token(const std::string &t) { this->refresh_token_ = t; }
  void set_client_id(const std::string &c) { this->client_id_ = c; }
  void set_client_secret(const std::string &s) { this->client_secret_ = s; }
  void set_api_host(const std::string &h) { this->api_host_ = h; }
  void set_user_agent(const std::string &ua) { this->user_agent_ = ua; }
  bool is_configured() const { return !this->refresh_token_.empty() && !this->client_secret_.empty(); }

  // u5/u7 are used percentages 0-100 (-1 unknown), r5/r7 reset epochs (0
  // unknown). code: HTTP status of the quota call, 0 = network error, 401
  // also covers a rejected refresh token (re-run the helper to recover),
  // -1 = no credentials configured.
  void add_on_result_callback(std::function<void(float, float, int64_t, int64_t, int)> &&cb) {
    this->callbacks_.add(std::move(cb));
  }

  // Spawn a poll task; no-op while one is in flight, while backing off
  // after failures, or after the refresh token was rejected. Without
  // credentials the result (code -1) is reported on the next loop instead.
  void poll();

  void loop() override;
  float get_setup_priority() const override { return setup_priority::LATE; }

 protected:
  static void poll_task(void *param);
  // Spawns the poll task; the caller must hold the TLS gate.
  void start_poll_task_();
  void run_poll_();
  bool ensure_access_token_();
  bool ensure_project_();
  void fetch_quota_();
  // POSTs a JSON body to v1internal:<method>; returns the HTTP status (0 =
  // network error or truncated body) and fills body.
  int call_api_(const char *method, const std::string &payload, std::string &body);

  std::string refresh_token_;
  std::string client_id_;
  std::string client_secret_;
  std::string api_host_;
  std::string user_agent_;

  std::string access_token_;
  int64_t access_refresh_due_us_{0};
  std::string project_;

  // Definitive token-endpoint rejection (revoked or expired grant).
  bool auth_dead_{false};
  int failures_{0};
  int skip_polls_{0};

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

class GeminiResultTrigger : public Trigger<float, float, int64_t, int64_t, int> {
 public:
  explicit GeminiResultTrigger(GeminiUsage *parent) {
    parent->add_on_result_callback([this](float u5, float u7, int64_t r5, int64_t r7, int code) {
      this->trigger(u5, u7, r5, r7, code);
    });
  }
};

template<typename... Ts> class GeminiPollAction : public Action<Ts...>, public Parented<GeminiUsage> {
 public:
  void play(const Ts &...x) override { this->parent_->poll(); }
};

}  // namespace tokentide_poller
}  // namespace esphome
