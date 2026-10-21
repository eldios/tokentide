#include "http_body.h"

namespace esphome {
namespace tokentide_poller {

esp_err_t body_event_handler(esp_http_client_event_t *evt) {
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

}  // namespace tokentide_poller
}  // namespace esphome
