#pragma once

#include "esphome/core/component.h"
#include "esphome/components/lvgl/lvgl_proxy.h"

#include <esp_http_server.h>
#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>

namespace esphome {
namespace tokentide_screenshot {

// Dev/QA helper: GET /screenshot on a tiny embedded HTTP server returns
// the current LVGL screen as a 24-bit BMP. The screen is rendered in
// horizontal strips of about 4 KB each, so boards without PSRAM can take
// one too. Rendering runs in loop() (LVGL is not thread-safe), which waits
// for the server task to send each strip before drawing the next: the
// widgets cannot change halfway through an image.
// LAN-only and unauthenticated - opt-in, not part of the default config.
class TokentideScreenshot : public Component {
 public:
  void set_port(uint16_t port) { this->port_ = port; }
  void setup() override;
  void loop() override;
  float get_setup_priority() const override { return setup_priority::AFTER_WIFI; }

 protected:
  static esp_err_t handler_(httpd_req_t *req);
  void render_strip_(lv_obj_t *screen, int32_t y0);

  uint16_t port_{8081};
  httpd_handle_t server_{nullptr};

  // Server task -> loop(): a request is waiting. loop() -> server task: a
  // strip (or the end of the image) is ready. Server task -> loop(): sent.
  SemaphoreHandle_t requested_{nullptr};
  SemaphoreHandle_t strip_ready_{nullptr};
  SemaphoreHandle_t strip_sent_{nullptr};

  // Filled by loop() before each strip_ready_ give, read by the server task.
  lv_draw_buf_t *strip_{nullptr};
  int32_t width_{0};
  int32_t height_{0};
  int32_t rows_{0};  // rows in the current strip, 0 = image done or failed
  bool failed_{false};
  // Set by the server task when the client goes away mid-image.
  volatile bool aborted_{false};
};

}  // namespace tokentide_screenshot
}  // namespace esphome
