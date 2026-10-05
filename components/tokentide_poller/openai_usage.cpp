#include "openai_usage.h"
#include "tls_gate.h"
#include "esphome/core/log.h"
#include "esphome/components/json/json_util.h"

#include "esp_crt_bundle.h"
#include "esp_http_client.h"
#include "esp_timer.h"
#include "nvs.h"

#include <cstring>

namespace esphome {
namespace tokentide_poller {

static const char *const TAG = "tokentide_openai";

// Own NVS namespace, written with the raw (thread-safe) NVS API: the
// rotation commit happens inside the poll task, where ESPHome's
// preference queue must not be touched.
static const char *const NVS_NS = "tokentide";
static const char *const NVS_KEY_RT = "oai_rt";
static const char *const NVS_KEY_SEED = "oai_seed";

// Access tokens live 10 days; the Codex CLI refreshes after 8. Uptime
// based on purpose: no wall-clock dependency, and a reboot simply
// refreshes again.
static const int64_t REFRESH_DUE_US = 8LL * 24 * 3600 * 1000000LL;

struct BodyBuffer {
  std::string data;
  size_t cap{0};
  // A body over cap would parse as broken JSON at best; callers must
  // check this instead of trusting the parse outcome.
  bool truncated{false};
};

static esp_err_t body_event_handler(esp_http_client_event_t *evt) {
  if (evt->event_id != HTTP_EVENT_ON_DATA)
    return ESP_OK;
  auto *b = static_cast<BodyBuffer *>(evt->user_data);
  size_t room = b->cap > b->data.size() ? b->cap - b->data.size() : 0;
  size_t n = (size_t) evt->data_len < room ? (size_t) evt->data_len : room;
  if ((size_t) evt->data_len > room)
    b->truncated = true;
  b->data.append(static_cast<const char *>(evt->data), n);
  return ESP_OK;
}

void OpenAIUsage::setup() {
  // Resume the persisted rotation chain only when it was seeded from the
  // currently configured refresh token; a changed config means the user
  // re-provisioned and the stored chain is stale.
  nvs_handle_t h;
  if (nvs_open(NVS_NS, NVS_READONLY, &h) == ESP_OK) {
    uint32_t seed = 0;
    size_t len = 0;
    if (nvs_get_u32(h, NVS_KEY_SEED, &seed) == ESP_OK && seed == fnv1_hash(this->seed_refresh_token_) &&
        nvs_get_str(h, NVS_KEY_RT, nullptr, &len) == ESP_OK && len > 1) {
      std::string stored(len, '\0');
      if (nvs_get_str(h, NVS_KEY_RT, &stored[0], &len) == ESP_OK) {
        stored.resize(strlen(stored.c_str()));
        this->refresh_token_ = std::move(stored);
        ESP_LOGD(TAG, "Resuming persisted refresh-token chain");
      }
    }
    nvs_close(h);
  }
  if (this->refresh_token_.empty())
    this->refresh_token_ = this->seed_refresh_token_;
}

void OpenAIUsage::persist_refresh_token_() {
  nvs_handle_t h;
  esp_err_t err = nvs_open(NVS_NS, NVS_READWRITE, &h);
  if (err == ESP_OK) {
    err = nvs_set_str(h, NVS_KEY_RT, this->refresh_token_.c_str());
    if (err == ESP_OK)
      err = nvs_set_u32(h, NVS_KEY_SEED, fnv1_hash(this->seed_refresh_token_));
    if (err == ESP_OK)
      err = nvs_commit(h);
    nvs_close(h);
  }
  if (err != ESP_OK) {
    // Losing a rotated token orphans the chain after the next reboot.
    ESP_LOGE(TAG, "Failed to persist rotated refresh token: %s", esp_err_to_name(err));
  }
}

void OpenAIUsage::poll() {
  if (this->auth_dead_) {
    ESP_LOGD(TAG, "Refresh chain dead, poll skipped");
    return;
  }
  if (this->running_ || this->poll_pending_) {
    ESP_LOGD(TAG, "Poll already in flight or queued, skipping");
    return;
  }
  if (!tls_gate_take()) {
    this->poll_pending_ = true;
    ESP_LOGD(TAG, "TLS gate busy, poll queued");
    return;
  }
  this->start_poll_task_();
}

void OpenAIUsage::start_poll_task_() {
  this->running_ = true;
  // TLS handshake needs generous stack; the task is short-lived.
  if (xTaskCreate(OpenAIUsage::poll_task, "tokentide_oai", 12288, this, 1, nullptr) != pdPASS) {
    ESP_LOGW(TAG, "Failed to create poll task");
    this->running_ = false;
    tls_gate_give();
  }
}

void OpenAIUsage::poll_task(void *param) {
  auto *self = static_cast<OpenAIUsage *>(param);
  self->run_poll_();
  self->done_ = true;
  vTaskDelete(nullptr);
}

void OpenAIUsage::run_poll_() {
  this->result_u5_ = -1.0f;
  this->result_u7_ = -1.0f;
  this->result_r5_ = 0;
  this->result_r7_ = 0;
  if (!this->ensure_access_token_())
    return;  // result_code_ already describes the failure
  this->fetch_usage_();
  if (this->result_code_ == 401) {
    // Access token no longer accepted: refresh on the next poll.
    this->access_token_.clear();
  }
}

bool OpenAIUsage::ensure_access_token_() {
  if (!this->access_token_.empty() && esp_timer_get_time() < this->access_refresh_due_us_)
    return true;
  return this->refresh_tokens_();
}

bool OpenAIUsage::refresh_tokens_() {
  BodyBuffer body;
  // The response can carry both an id_token and an access_token JWT,
  // kilobytes each; truncation here is chain-threatening, so leave real
  // headroom.
  body.cap = 32768;

  esp_http_client_config_t cfg{};
  cfg.url = "https://auth.openai.com/oauth/token";
  cfg.method = HTTP_METHOD_POST;
  cfg.timeout_ms = 15000;
  cfg.crt_bundle_attach = esp_crt_bundle_attach;
  cfg.event_handler = body_event_handler;
  cfg.user_data = &body;
  // Default RX buffer is 512 bytes; the token endpoint also answers with
  // fat response headers. Request headers are small here (the refresh
  // token travels in the POST body, not the TX header buffer).
  cfg.buffer_size = 4096;

  esp_http_client_handle_t client = esp_http_client_init(&cfg);
  if (client == nullptr) {
    this->result_code_ = 0;
    return false;
  }

  // The ChatGPT refresh grant is JSON-encoded (unlike the form-encoded
  // authorization-code grant) and the client is public: no secret.
  std::string payload = json::build_json([this](JsonObject root) {
    root["grant_type"] = "refresh_token";
    root["client_id"] = this->client_id_;
    root["refresh_token"] = this->refresh_token_;
  });
  esp_http_client_set_header(client, "Content-Type", "application/json");
  esp_http_client_set_header(client, "User-Agent", "tokentide");
  esp_http_client_set_post_field(client, payload.c_str(), (int) payload.size());

  esp_err_t err = esp_http_client_perform(client);
  int status = (err == ESP_OK) ? esp_http_client_get_status_code(client) : -1;
  esp_http_client_cleanup(client);

  if (err != ESP_OK) {
    ESP_LOGW(TAG, "Token refresh failed: %s", esp_err_to_name(err));
    this->result_code_ = 0;
    return false;
  }
  if (status != 200) {
    if (status >= 400 && status < 500) {
      // The grant itself was rejected (expired, reused or revoked chain):
      // unrecoverable without a fresh seed, so stop polling instead of
      // hammering a dead endpoint.
      this->auth_dead_ = true;
      this->result_code_ = 401;
      ESP_LOGE(TAG, "Refresh token rejected (HTTP %d); re-seed openai_refresh_token from a fresh login", status);
    } else {
      this->result_code_ = 0;
      ESP_LOGW(TAG, "Token refresh failed: HTTP %d, retrying next poll", status);
    }
    return false;
  }

  if (body.truncated) {
    // The server may already have rotated the grant with the new refresh
    // token lost in the cut tail. Retrying with the old (possibly spent)
    // token would end the chain at the server, so stop polling; the next
    // boot resolves it against the persisted state, or a fresh seed does.
    this->auth_dead_ = true;
    this->result_code_ = 401;
    ESP_LOGE(TAG, "Token refresh response truncated (> %u bytes); re-seed openai_refresh_token if polling does not recover after a reboot",
             (unsigned) body.cap);
    return false;
  }

  std::string new_access, new_refresh;
  json::parse_json(body.data, [&](JsonObject root) -> bool {
    new_access = root["access_token"] | "";
    new_refresh = root["refresh_token"] | "";
    return true;
  });
  if (new_access.empty()) {
    ESP_LOGW(TAG, "Token refresh response carried no access_token");
    this->result_code_ = 0;
    return false;
  }
  // The old refresh token is spent the moment the server rotates it:
  // commit the new one before anything else can fail.
  if (!new_refresh.empty() && new_refresh != this->refresh_token_) {
    this->refresh_token_ = new_refresh;
    this->persist_refresh_token_();
  }
  this->access_token_ = new_access;
  this->access_refresh_due_us_ = esp_timer_get_time() + REFRESH_DUE_US;
  ESP_LOGD(TAG, "Access token refreshed");
  return true;
}

void OpenAIUsage::fetch_usage_() {
  BodyBuffer body;
  body.cap = 8192;

  esp_http_client_config_t cfg{};
  cfg.url = "https://chatgpt.com/backend-api/wham/usage";
  cfg.method = HTTP_METHOD_GET;
  cfg.timeout_ms = 15000;
  cfg.crt_bundle_attach = esp_crt_bundle_attach;
  cfg.event_handler = body_event_handler;
  cfg.user_data = &body;
  // Both default 512-byte client buffers are too small here: the request
  // carries the multi-KB access-token JWT in the Authorization header
  // (TX) and chatgpt.com answers with multi-KB response headers (RX);
  // undersized buffers fail the request with ESP_ERR_HTTP_FETCH_HEADER.
  // Both buffers live inside the client and are freed with
  // esp_http_client_cleanup.
  cfg.buffer_size = 4096;
  size_t tx_size = this->access_token_.size() + 1536;
  if (tx_size < 2048)
    tx_size = 2048;
  cfg.buffer_size_tx = (int) tx_size;

  esp_http_client_handle_t client = esp_http_client_init(&cfg);
  if (client == nullptr) {
    this->result_code_ = 0;
    return;
  }

  std::string auth = "Bearer " + this->access_token_;
  esp_http_client_set_header(client, "Authorization", auth.c_str());
  esp_http_client_set_header(client, "ChatGPT-Account-Id", this->account_id_.c_str());
  esp_http_client_set_header(client, "User-Agent", "tokentide");

  esp_err_t err = esp_http_client_perform(client);
  if (err != ESP_OK) {
    ESP_LOGW(TAG, "Usage fetch failed: %s", esp_err_to_name(err));
    this->result_code_ = 0;
    esp_http_client_cleanup(client);
    return;
  }
  this->result_code_ = esp_http_client_get_status_code(client);
  esp_http_client_cleanup(client);

  if (this->result_code_ != 200)
    return;
  if (body.truncated) {
    // Unlike the refresh, nothing is lost here: report a network error
    // and let the next poll retry.
    ESP_LOGW(TAG, "Usage response truncated (> %u bytes)", (unsigned) body.cap);
    this->result_code_ = 0;
    return;
  }
  json::parse_json(body.data, [this](JsonObject root) -> bool {
    JsonObject rl = root["rate_limit"];
    if (rl.isNull())
      return false;
    JsonObject p = rl["primary_window"];
    if (!p.isNull()) {
      this->result_u5_ = p["used_percent"] | -1.0f;
      this->result_r5_ = p["reset_at"] | (int64_t) 0;
    }
    JsonObject s = rl["secondary_window"];
    if (!s.isNull()) {
      this->result_u7_ = s["used_percent"] | -1.0f;
      this->result_r7_ = s["reset_at"] | (int64_t) 0;
    }
    return true;
  });
}

void OpenAIUsage::loop() {
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
  ESP_LOGD(TAG, "Poll done: code=%d u5=%.0f u7=%.0f", this->result_code_, this->result_u5_,
           this->result_u7_);
  this->callbacks_.call(this->result_u5_, this->result_u7_, this->result_r5_, this->result_r7_,
                        this->result_code_);
}

}  // namespace tokentide_poller
}  // namespace esphome
