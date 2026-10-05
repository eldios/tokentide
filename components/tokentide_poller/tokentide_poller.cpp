#include "tokentide_poller.h"
#include "tls_gate.h"
#include "esphome/core/log.h"

#include "esp_crt_bundle.h"
#include "esp_http_client.h"

#include <cinttypes>
#include <cstdlib>
#include <cstring>
#include <ctime>

namespace esphome {
namespace tokentide_poller {

static const char *const TAG = "tokentide_poller";

// Header values arrive either as a unix epoch or as RFC3339; normalize to
// epoch without timegm (absent from newlib) via days-from-civil.
static int64_t parse_reset_ts(const char *v) {
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

struct ProbeHeaders {
  char u5[16]{};
  char u7[16]{};
  char r5[40]{};
  char r7[40]{};
  char status[32]{};
};

static esp_err_t http_event_handler(esp_http_client_event_t *evt) {
  if (evt->event_id != HTTP_EVENT_ON_HEADER)
    return ESP_OK;
  auto *h = static_cast<ProbeHeaders *>(evt->user_data);
  auto grab = [&](const char *name, char *dst, size_t n) {
    if (strcasecmp(evt->header_key, name) == 0)
      strlcpy(dst, evt->header_value, n);
  };
  grab("anthropic-ratelimit-unified-5h-utilization", h->u5, sizeof(h->u5));
  grab("anthropic-ratelimit-unified-7d-utilization", h->u7, sizeof(h->u7));
  grab("anthropic-ratelimit-unified-5h-reset", h->r5, sizeof(h->r5));
  grab("anthropic-ratelimit-unified-7d-reset", h->r7, sizeof(h->r7));
  grab("anthropic-ratelimit-unified-status", h->status, sizeof(h->status));
  return ESP_OK;
}

void TokentidePoller::poll() {
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

void TokentidePoller::start_poll_task_() {
  this->running_ = true;
  // TLS handshake needs generous stack; the task is short-lived.
  if (xTaskCreate(TokentidePoller::poll_task, "tokentide_poll", 12288, this, 1, nullptr) != pdPASS) {
    ESP_LOGW(TAG, "Failed to create poll task");
    this->running_ = false;
    tls_gate_give();
  }
}

void TokentidePoller::poll_task(void *param) {
  auto *self = static_cast<TokentidePoller *>(param);
  self->run_probe_();
  self->done_ = true;
  vTaskDelete(nullptr);
}

void TokentidePoller::run_probe_() {
  ProbeHeaders headers;

  esp_http_client_config_t cfg{};
  cfg.url = "https://api.anthropic.com/v1/messages";
  cfg.method = HTTP_METHOD_POST;
  cfg.timeout_ms = 15000;
  cfg.crt_bundle_attach = esp_crt_bundle_attach;
  cfg.event_handler = http_event_handler;
  cfg.user_data = &headers;

  esp_http_client_handle_t client = esp_http_client_init(&cfg);
  if (client == nullptr) {
    this->result_code_ = 0;
    return;
  }

  std::string auth = "Bearer " + this->token_;
  esp_http_client_set_header(client, "Authorization", auth.c_str());
  esp_http_client_set_header(client, "anthropic-version", "2023-06-01");
  esp_http_client_set_header(client, "anthropic-beta", "oauth-2025-04-20");
  esp_http_client_set_header(client, "Content-Type", "application/json");
  esp_http_client_set_header(client, "User-Agent", "claude-code/2.1.5");

  std::string body = "{\"model\":\"" + this->model_ +
                     "\",\"max_tokens\":1,\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}]}";
  esp_http_client_set_post_field(client, body.c_str(), (int) body.size());

  esp_err_t err = esp_http_client_perform(client);
  if (err == ESP_OK) {
    this->result_code_ = esp_http_client_get_status_code(client);
    this->result_u5_ = headers.u5[0] ? strtof(headers.u5, nullptr) : -1.0f;
    this->result_u7_ = headers.u7[0] ? strtof(headers.u7, nullptr) : -1.0f;
    this->result_r5_ = parse_reset_ts(headers.r5);
    this->result_r7_ = parse_reset_ts(headers.r7);
    this->result_status_ = headers.status;
  } else {
    ESP_LOGW(TAG, "Probe failed: %s", esp_err_to_name(err));
    this->result_code_ = 0;
    this->result_u5_ = -1.0f;
    this->result_u7_ = -1.0f;
    this->result_status_.clear();
  }
  esp_http_client_cleanup(client);
}

void TokentidePoller::check_status() {
  if (this->status_running_) {
    ESP_LOGD(TAG, "Status check already in flight, skipping");
    return;
  }
  if (!tls_gate_take()) {
    // Not queued on purpose: a dropped check just waits for the next
    // 15-min interval and the status dot goes a little stale.
    ESP_LOGD(TAG, "Another TLS task in flight, skipping status check");
    return;
  }
  this->status_running_ = true;
  if (xTaskCreate(TokentidePoller::status_task, "tokentide_stat", 12288, this, 1, nullptr) != pdPASS) {
    ESP_LOGW(TAG, "Failed to create status task");
    this->status_running_ = false;
    tls_gate_give();
  }
}

void TokentidePoller::status_task(void *param) {
  auto *self = static_cast<TokentidePoller *>(param);
  self->run_status_probe_();
  self->status_done_ = true;
  vTaskDelete(nullptr);
}

struct StatusBody {
  char buf[600]{};
  size_t len{0};
};

static esp_err_t status_event_handler(esp_http_client_event_t *evt) {
  if (evt->event_id != HTTP_EVENT_ON_DATA)
    return ESP_OK;
  auto *b = static_cast<StatusBody *>(evt->user_data);
  size_t room = sizeof(b->buf) - 1 - b->len;
  size_t n = (size_t) evt->data_len < room ? (size_t) evt->data_len : room;
  memcpy(b->buf + b->len, evt->data, n);
  b->len += n;
  return ESP_OK;
}

void TokentidePoller::run_status_probe_() {
  StatusBody body;

  esp_http_client_config_t cfg{};
  cfg.url = "https://status.anthropic.com/api/v2/status.json";
  cfg.method = HTTP_METHOD_GET;
  cfg.timeout_ms = 15000;
  cfg.crt_bundle_attach = esp_crt_bundle_attach;
  cfg.event_handler = status_event_handler;
  cfg.user_data = &body;

  this->status_result_ = "unknown";
  esp_http_client_handle_t client = esp_http_client_init(&cfg);
  if (client == nullptr)
    return;

  esp_err_t err = esp_http_client_perform(client);
  if (err == ESP_OK && esp_http_client_get_status_code(client) == 200) {
    // Tiny fixed payload; a string scan beats pulling in a JSON parser.
    const char *tag = "\"indicator\":\"";
    const char *p = strstr(body.buf, tag);
    if (p != nullptr) {
      p += strlen(tag);
      const char *e = strchr(p, '"');
      if (e != nullptr && (size_t)(e - p) < 24)
        this->status_result_.assign(p, e - p);
    }
  } else {
    ESP_LOGW(TAG, "Status check failed: %s", esp_err_to_name(err));
  }
  esp_http_client_cleanup(client);
}

void TokentidePoller::loop() {
  if (this->poll_pending_ && !this->running_ && tls_gate_take()) {
    this->poll_pending_ = false;
    this->start_poll_task_();
  }
  if (this->status_done_) {
    this->status_done_ = false;
    this->status_running_ = false;
    tls_gate_give();
    ESP_LOGD(TAG, "Status check done: %s", this->status_result_.c_str());
    this->status_callbacks_.call(this->status_result_);
  }
  if (!this->done_)
    return;
  this->done_ = false;
  this->running_ = false;
  // Give the gate back before the callbacks: the chained provider poll
  // (tokentide_poller.openai_poll in on_result) must be able to take it.
  tls_gate_give();
  ESP_LOGD(TAG, "Poll done: code=%d u5=%.2f u7=%.2f", this->result_code_, this->result_u5_,
           this->result_u7_);
  this->callbacks_.call(this->result_u5_, this->result_u7_, this->result_r5_, this->result_r7_,
                        this->result_status_, this->result_code_);
}

}  // namespace tokentide_poller
}  // namespace esphome
