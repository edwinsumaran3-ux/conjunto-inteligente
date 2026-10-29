#include "heartbeat.hpp"

#include "esp_system.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "logging.hpp"

namespace fw {

namespace {
constexpr const char* TAG = "heartbeat";
}

HeartbeatTask::HeartbeatTask(EventPublisher& publisher, std::uint32_t period_s)
    : publisher_(publisher), period_s_(period_s) {}

HeartbeatTask::~HeartbeatTask() { stop(); }

void HeartbeatTask::start() {
    if (task_handle_ != nullptr) return;
    xTaskCreate(&HeartbeatTask::task_entry, "heartbeat", 4096, this, 5,
                reinterpret_cast<TaskHandle_t*>(&task_handle_));
}

void HeartbeatTask::stop() {
    if (task_handle_ == nullptr) return;
    vTaskDelete(reinterpret_cast<TaskHandle_t>(task_handle_));
    task_handle_ = nullptr;
}

void HeartbeatTask::task_entry(void* arg) {
    static_cast<HeartbeatTask*>(arg)->run();
}

void HeartbeatTask::run() {
    while (true) {
        // Leer estado real.
        wifi_ap_record_t ap{};
        int rssi = 0;
        if (esp_wifi_sta_get_ap_info(&ap) == ESP_OK) {
            rssi = ap.rssi;
        }

        const std::uint32_t uptime_s = static_cast<std::uint32_t>(
            esp_timer_get_time() / 1'000'000ULL);

        // Batería: en hardware real leer con ADC; en dev, valor fijo.
        constexpr int battery_mv = 4100;

        const std::uint32_t free_heap = esp_get_free_heap_size();

        (void)publisher_.publish_heartbeat(battery_mv, rssi, uptime_s, free_heap);
        FW_LOGI(TAG, "Heartbeat enviado: rssi=%d uptime=%us free_heap=%u",
                rssi, uptime_s, free_heap);

        vTaskDelay(pdMS_TO_TICKS(period_s_ * 1000));
    }
}

}  // namespace fw
