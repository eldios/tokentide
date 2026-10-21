#pragma once

#include "esp_http_client.h"

#include <string>

namespace esphome {
namespace tokentide_poller {

// Response body collected by body_event_handler, capped at cap bytes.
struct BodyBuffer {
  std::string data;
  size_t cap{0};
  // A body over cap would parse as broken JSON at best; callers must
  // check this instead of trusting the parse outcome.
  bool truncated{false};
};

// esp_http_client event handler appending HTTP_EVENT_ON_DATA chunks to
// the BodyBuffer passed as user_data.
esp_err_t body_event_handler(esp_http_client_event_t *evt);

}  // namespace tokentide_poller
}  // namespace esphome
