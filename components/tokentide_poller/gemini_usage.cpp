#include "gemini_usage.h"
#include "gemini_quota.h"
#include "http_body.h"
#include "tls_gate.h"
#include "esphome/core/log.h"
#include "esphome/components/json/json_util.h"

#include "esp_crt_bundle.h"
#include "esp_http_client.h"
#include "esp_timer.h"

#include <vector>

namespace esphome {
namespace tokentide_poller {

static const char *const TAG = "tokentide_gemini";

// Refresh this long before the access token's expires_in runs out.
static const int64_t REFRESH_MARGIN_S = 300;

void GeminiUsage::poll() {
  if (!this->is_configured()) {
    this->defer([this]() { this->callbacks_.call(-1.0f, -1.0f, 0, 0, -1); });
    return;
  }
  if (this->auth_dead_) {
    ESP_LOGD(TAG, "Refresh token rejected, poll skipped");
    return;
  }
  if (this->running_ || this->poll_pending_) {
    ESP_LOGD(TAG, "Poll already in flight or queued, skipping");
    return;
  }
  if (this->skip_polls_ > 0) {
    this->skip_polls_--;
    ESP_LOGD(TAG, "Backing off after %d failures, %d polls left", this->failures_, this->skip_polls_);
    return;
  }
  if (!tls_gate_take()) {
    this->poll_pending_ = true;
    ESP_LOGD(TAG, "TLS gate busy, poll queued");
    return;
  }
  this->start_poll_task_();
}

void GeminiUsage::start_poll_task_() {
  this->running_ = true;
  // TLS handshake needs generous stack; the task is short-lived.
  if (xTaskCreate(GeminiUsage::poll_task, "tokentide_gem", 12288, this, 1, nullptr) != pdPASS) {
    ESP_LOGW(TAG, "Failed to create poll task");
    this->running_ = false;
    tls_gate_give();
  }
}

void GeminiUsage::poll_task(void *param) {
  auto *self = static_cast<GeminiUsage *>(param);
  self->run_poll_();
  self->done_ = true;
  vTaskDelete(nullptr);
}

void GeminiUsage::run_poll_() {
  this->result_u5_ = -1.0f;
  this->result_u7_ = -1.0f;
  this->result_r5_ = 0;
  this->result_r7_ = 0;
  if (!this->ensure_access_token_() || !this->ensure_project_())
    return;  // result_code_ already describes the failure
  this->fetch_quota_();
  if (this->result_code_ == 401) {
    // Access token no longer accepted: refresh on the next poll.
    this->access_token_.clear();
  }
}

bool GeminiUsage::ensure_access_token_() {
  if (!this->access_token_.empty() && esp_timer_get_time() < this->access_refresh_due_us_)
    return true;

  BodyBuffer body;
  body.cap = 8192;

  esp_http_client_config_t cfg{};
  cfg.url = "https://oauth2.googleapis.com/token";
  cfg.method = HTTP_METHOD_POST;
  cfg.timeout_ms = 15000;
  cfg.crt_bundle_attach = esp_crt_bundle_attach;
  cfg.event_handler = body_event_handler;
  cfg.user_data = &body;
  cfg.buffer_size = 2048;

  esp_http_client_handle_t client = esp_http_client_init(&cfg);
  if (client == nullptr) {
    this->result_code_ = 0;
    return false;
  }

  std::string payload = "grant_type=refresh_token&client_id=" + form_encode(this->client_id_) +
                        "&client_secret=" + form_encode(this->client_secret_) +
                        "&refresh_token=" + form_encode(this->refresh_token_);
  esp_http_client_set_header(client, "Content-Type", "application/x-www-form-urlencoded");
  esp_http_client_set_header(client, "User-Agent", this->user_agent_.c_str());
  esp_http_client_set_post_field(client, payload.c_str(), (int) payload.size());

  esp_err_t err = esp_http_client_perform(client);
  int status = (err == ESP_OK) ? esp_http_client_get_status_code(client) : -1;
  esp_http_client_cleanup(client);

  if (err != ESP_OK) {
    ESP_LOGW(TAG, "Token refresh failed: %s", esp_err_to_name(err));
    this->result_code_ = 0;
    return false;
  }
  if (status == 400 || status == 401) {
    // invalid_grant (revoked, expired or unused for 6 months) or
    // invalid_client: only a new refresh token from the helper recovers.
    this->auth_dead_ = true;
    this->result_code_ = 401;
    ESP_LOGE(TAG, "Refresh token rejected (HTTP %d); run tools/gemini_refresh_token.py again", status);
    return false;
  }
  if (status != 200 || body.truncated) {
    ESP_LOGW(TAG, "Token refresh failed: HTTP %d, retrying later", status);
    this->result_code_ = 0;
    return false;
  }

  std::string access;
  int64_t expires_in = 0;
  json::parse_json(body.data, [&](JsonObject root) -> bool {
    access = root["access_token"] | "";
    expires_in = root["expires_in"] | (int64_t) 0;
    return true;
  });
  if (access.empty()) {
    ESP_LOGW(TAG, "Token refresh response carried no access_token");
    this->result_code_ = 0;
    return false;
  }
  if (expires_in <= REFRESH_MARGIN_S)
    expires_in = REFRESH_MARGIN_S + 60;
  this->access_token_ = std::move(access);
  this->access_refresh_due_us_ = esp_timer_get_time() + (expires_in - REFRESH_MARGIN_S) * 1000000LL;
  ESP_LOGD(TAG, "Access token refreshed");
  return true;
}

int GeminiUsage::call_api_(const char *method, const std::string &payload, std::string &out) {
  BodyBuffer body;
  body.cap = 16384;
  std::string url = "https://" + this->api_host_ + "/v1internal:" + method;

  esp_http_client_config_t cfg{};
  cfg.url = url.c_str();
  cfg.method = HTTP_METHOD_POST;
  cfg.timeout_ms = 15000;
  cfg.crt_bundle_attach = esp_crt_bundle_attach;
  cfg.event_handler = body_event_handler;
  cfg.user_data = &body;
  // The Authorization header carries the access token: size the TX buffer
  // for it instead of relying on the 512-byte default.
  cfg.buffer_size = 4096;
  size_t tx_size = this->access_token_.size() + 1024;
  cfg.buffer_size_tx = (int) (tx_size < 2048 ? 2048 : tx_size);

  esp_http_client_handle_t client = esp_http_client_init(&cfg);
  if (client == nullptr)
    return 0;

  std::string auth = "Bearer " + this->access_token_;
  esp_http_client_set_header(client, "Authorization", auth.c_str());
  esp_http_client_set_header(client, "Content-Type", "application/json");
  esp_http_client_set_header(client, "User-Agent", this->user_agent_.c_str());
  esp_http_client_set_post_field(client, payload.c_str(), (int) payload.size());

  esp_err_t err = esp_http_client_perform(client);
  int status = (err == ESP_OK) ? esp_http_client_get_status_code(client) : 0;
  esp_http_client_cleanup(client);

  if (err != ESP_OK) {
    ESP_LOGW(TAG, "%s failed: %s", method, esp_err_to_name(err));
    return 0;
  }
  if (status == 200 && body.truncated) {
    ESP_LOGW(TAG, "%s response truncated (> %u bytes)", method, (unsigned) body.cap);
    return 0;
  }
  out = std::move(body.data);
  return status;
}

bool GeminiUsage::ensure_project_() {
  if (!this->project_.empty())
    return true;
  std::string body;
  int status = this->call_api_("loadCodeAssist", R"({"metadata":{"ideType":"ANTIGRAVITY"}})", body);
  if (status != 200) {
    ESP_LOGW(TAG, "loadCodeAssist: HTTP %d", status);
    this->result_code_ = status;
    if (status == 401)
      this->access_token_.clear();
    return false;
  }
  json::parse_json(body, [this](JsonObject root) -> bool {
    // A plain id, or an object carrying it.
    JsonVariant p = root["cloudaicompanionProject"];
    this->project_ = p.is<const char *>() ? (p | "") : (p["id"] | "");
    return true;
  });
  if (this->project_.empty()) {
    // The account was never onboarded to Code Assist: no quota to read.
    ESP_LOGW(TAG, "loadCodeAssist returned no project; sign in once with Antigravity");
    this->result_code_ = 200;
    return false;
  }
  return true;
}

static void collect_buckets(JsonArray arr, std::vector<QuotaBucket> &out) {
  for (JsonObject b : arr) {
    QuotaBucket q;
    q.id = b["bucketId"] | "";
    q.window = b["window"] | "";
    JsonVariant rf = b["remainingFraction"];
    q.remaining = rf.isNull() ? -1.0f : rf.as<float>();
    q.reset_time = b["resetTime"] | "";
    q.disabled = b["disabled"] | false;
    out.push_back(std::move(q));
  }
}

void GeminiUsage::fetch_quota_() {
  std::string body;
  std::string payload = json::build_json([this](JsonObject root) { root["project"] = this->project_; });
  this->result_code_ = this->call_api_("retrieveUserQuotaSummary", payload, body);
  if (this->result_code_ != 200)
    return;
  std::vector<QuotaBucket> buckets;
  json::parse_json(body, [&buckets](JsonObject root) -> bool {
    collect_buckets(root["buckets"].as<JsonArray>(), buckets);
    for (JsonObject g : root["groups"].as<JsonArray>())
      collect_buckets(g["buckets"].as<JsonArray>(), buckets);
    return true;
  });
  if (!this->buckets_logged_) {
    // Once per boot, at INFO: the raw buckets show which ids this User-Agent
    // gets and whether exhausted buckets omit remainingFraction.
    this->buckets_logged_ = true;
    ESP_LOGI(TAG, "Quota summary (User-Agent %s): %u buckets", this->user_agent_.c_str(), (unsigned) buckets.size());
    for (const auto &b : buckets) {
      char frac[16] = "absent";
      if (b.remaining >= 0.0f)
        snprintf(frac, sizeof(frac), "%.3f", b.remaining);
      ESP_LOGI(TAG, "  bucket %s window=%s remainingFraction=%s resetTime=%s%s", b.id.c_str(), b.window.c_str(), frac,
               b.reset_time.c_str(), b.disabled ? " disabled" : "");
    }
  }
  GeminiReading r = pick_gemini_windows(buckets);
  this->result_u5_ = r.used_5h;
  this->result_u7_ = r.used_7d;
  this->result_r5_ = r.reset_5h;
  this->result_r7_ = r.reset_7d;
}

void GeminiUsage::loop() {
  if (this->poll_pending_ && !this->running_) {
    if (this->auth_dead_) {
      this->poll_pending_ = false;
    } else if (tls_gate_take()) {
      this->poll_pending_ = false;
      this->start_poll_task_();
    }
  }
  if (!this->done_)
    return;
  this->done_ = false;
  this->running_ = false;
  tls_gate_give();
  // A 200 without any Gemini window (account not onboarded, unexpected
  // body) backs off like an error: retrying every poll cannot fix it.
  bool got_data = this->result_code_ == 200 && (this->result_u5_ >= 0.0f || this->result_u7_ >= 0.0f);
  if (got_data) {
    this->failures_ = 0;
  } else {
    this->failures_++;
    this->skip_polls_ = backoff_skip_polls(this->failures_);
  }
  ESP_LOGD(TAG, "Poll done: code=%d u5=%.0f u7=%.0f", this->result_code_, this->result_u5_, this->result_u7_);
  this->callbacks_.call(this->result_u5_, this->result_u7_, this->result_r5_, this->result_r7_,
                        this->result_code_);
}

}  // namespace tokentide_poller
}  // namespace esphome
