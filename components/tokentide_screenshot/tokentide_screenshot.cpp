#include "tokentide_screenshot.h"
#include "esphome/core/application.h"
#include "esphome/core/log.h"

#include "src/core/lv_refr_private.h"
#include "src/display/lv_display_private.h"

#include <algorithm>
#include <cstring>

namespace esphome {
namespace tokentide_screenshot {

static const char *const TAG = "tokentide_screenshot";

// Strip buffer budget: a few rows of the screen. With the TCP buffers of
// the chunks in flight a capture costs about three times this, which a
// board without PSRAM must find next to LVGL and a TLS poll.
static const uint32_t STRIP_BYTES = 4096;
// How long either side waits for the other before giving up on an image;
// loop() feeds the task watchdog (5 s) between strips.
static const TickType_t HANDOFF_TIMEOUT = pdMS_TO_TICKS(2000);

void TokentideScreenshot::setup() {
  this->requested_ = xSemaphoreCreateBinary();
  this->strip_ready_ = xSemaphoreCreateBinary();
  this->strip_sent_ = xSemaphoreCreateBinary();
  if (this->requested_ == nullptr || this->strip_ready_ == nullptr || this->strip_sent_ == nullptr) {
    ESP_LOGW(TAG, "Failed to create the screenshot semaphores");
    this->mark_failed();
    return;
  }
  httpd_config_t cfg = HTTPD_DEFAULT_CONFIG();
  cfg.server_port = this->port_;
  cfg.ctrl_port = this->port_ + 10000;
  if (httpd_start(&this->server_, &cfg) != ESP_OK) {
    ESP_LOGW(TAG, "Failed to start screenshot server on port %u", this->port_);
    this->mark_failed();
    return;
  }
  httpd_uri_t uri{};
  uri.uri = "/screenshot";
  uri.method = HTTP_GET;
  uri.handler = TokentideScreenshot::handler_;
  uri.user_ctx = this;
  httpd_register_uri_handler(this->server_, &uri);
  ESP_LOGI(TAG, "Screenshot server listening on port %u, path /screenshot", this->port_);
}

// Draws rows y0.. of the screen into strip_, the way lv_snapshot draws a
// whole object into a full-size buffer.
void TokentideScreenshot::render_strip_(lv_obj_t *screen, int32_t y0) {
  lv_draw_buf_clear(this->strip_, nullptr);

  lv_layer_t layer;
  lv_layer_init(&layer);
  layer.draw_buf = this->strip_;
  layer.color_format = LV_COLOR_FORMAT_RGB565;
  layer.buf_area = {0, y0, this->width_ - 1, y0 + (int32_t) this->strip_->header.h - 1};
  lv_area_t clip = {0, y0, this->width_ - 1, y0 + this->rows_ - 1};
  layer._clip_area = clip;
  layer.phy_clip_area = clip;

  lv_draw_unit_send_event(nullptr, LV_EVENT_CHILD_CREATED, &layer);
  lv_display_t *disp = lv_obj_get_display(screen);
  lv_display_t *disp_old = lv_refr_get_disp_refreshing();
  lv_layer_t *layer_old = disp->layer_head;
  disp->layer_head = &layer;
  lv_refr_set_disp_refreshing(disp);

  lv_obj_redraw(&layer, screen);
  layer.all_tasks_added = true;
  while (layer.draw_task_head) {
    lv_draw_dispatch_wait_for_request();
    lv_draw_dispatch();
  }

  disp->layer_head = layer_old;
  lv_refr_set_disp_refreshing(disp_old);
  lv_draw_unit_send_event(nullptr, LV_EVENT_SCREEN_LOAD_START, &layer);
  lv_draw_unit_send_event(nullptr, LV_EVENT_CHILD_DELETED, &layer);
}

void TokentideScreenshot::loop() {
  if (this->requested_ == nullptr || xSemaphoreTake(this->requested_, 0) != pdTRUE)
    return;

  lv_obj_t *screen = lv_scr_act();
  this->width_ = lv_obj_get_width(screen);
  this->height_ = lv_obj_get_height(screen);
  uint32_t strip_h = STRIP_BYTES / ((uint32_t) this->width_ * 2);
  if (strip_h == 0)
    strip_h = 1;
  this->strip_ = lv_draw_buf_create(this->width_, strip_h, LV_COLOR_FORMAT_RGB565, 0);
  this->failed_ = (this->strip_ == nullptr);
  this->aborted_ = false;

  if (!this->failed_) {
    for (int32_t y0 = 0; y0 < this->height_; y0 += (int32_t) strip_h) {
      this->rows_ = std::min<int32_t>((int32_t) strip_h, this->height_ - y0);
      this->render_strip_(screen, y0);
      xSemaphoreGive(this->strip_ready_);
      bool sent = xSemaphoreTake(this->strip_sent_, HANDOFF_TIMEOUT) == pdTRUE;
      App.feed_wdt();
      if (!sent || this->aborted_) {
        ESP_LOGW(TAG, "Screenshot client stopped reading at row %d", (int) y0);
        break;
      }
    }
  }

  this->rows_ = 0;
  xSemaphoreGive(this->strip_ready_);
  if (this->strip_ != nullptr) {
    lv_draw_buf_destroy(this->strip_);
    this->strip_ = nullptr;
  }
}

esp_err_t TokentideScreenshot::handler_(httpd_req_t *req) {
  auto *self = static_cast<TokentideScreenshot *>(req->user_ctx);
  // Drop an end-of-image signal left over from a request that timed out.
  xSemaphoreTake(self->strip_ready_, 0);
  xSemaphoreGive(self->requested_);

  if (xSemaphoreTake(self->strip_ready_, HANDOFF_TIMEOUT) != pdTRUE || self->failed_ || self->rows_ == 0) {
    httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "screenshot failed (out of memory?)");
    return ESP_OK;
  }

  int32_t w = self->width_, h = self->height_;
  uint32_t row_bytes = ((uint32_t) w * 3 + 3) & ~3u;
  uint32_t data_size = row_bytes * h;

  // 54-byte BMP header, 24bpp BGR, negative height = top-down rows.
  uint8_t hdr[54] = {};
  uint32_t file_size = 54 + data_size;
  hdr[0] = 'B'; hdr[1] = 'M';
  memcpy(hdr + 2, &file_size, 4);
  uint32_t off = 54, hsz = 40;
  memcpy(hdr + 10, &off, 4);
  memcpy(hdr + 14, &hsz, 4);
  int32_t bw = w, bh = -h;
  memcpy(hdr + 18, &bw, 4);
  memcpy(hdr + 22, &bh, 4);
  uint16_t planes = 1, bpp = 24;
  memcpy(hdr + 26, &planes, 2);
  memcpy(hdr + 28, &bpp, 2);
  memcpy(hdr + 34, &data_size, 4);

  httpd_resp_set_type(req, "image/bmp");
  esp_err_t err = httpd_resp_send_chunk(req, (const char *) hdr, sizeof(hdr));
  auto *row = (uint8_t *) calloc(1, row_bytes);
  if (row == nullptr)
    err = ESP_ERR_NO_MEM;

  // Each pass sends the strip loop() just drew; rows_ == 0 ends the image.
  while (err == ESP_OK && self->rows_ > 0) {
    const lv_draw_buf_t *buf = self->strip_;
    for (int32_t y = 0; y < self->rows_ && err == ESP_OK; y++) {
      const uint16_t *src = (const uint16_t *) (buf->data + (size_t) y * buf->header.stride);
      for (int32_t x = 0; x < w; x++) {
        uint16_t v = src[x];
        row[x * 3 + 0] = (uint8_t) ((v & 0x1F) << 3);          // B
        row[x * 3 + 1] = (uint8_t) (((v >> 5) & 0x3F) << 2);   // G
        row[x * 3 + 2] = (uint8_t) (((v >> 11) & 0x1F) << 3);  // R
      }
      err = httpd_resp_send_chunk(req, (const char *) row, row_bytes);
    }
    self->aborted_ = (err != ESP_OK);
    xSemaphoreGive(self->strip_sent_);
    if (err == ESP_OK && xSemaphoreTake(self->strip_ready_, HANDOFF_TIMEOUT) != pdTRUE)
      err = ESP_ERR_TIMEOUT;
  }
  free(row);
  httpd_resp_send_chunk(req, nullptr, 0);
  return err;
}

}  // namespace tokentide_screenshot
}  // namespace esphome
