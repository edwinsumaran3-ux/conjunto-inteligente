#include "sensors/pir_sensor.hpp"

#include "driver/gpio.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"

#include "logging.hpp"

namespace fw {

namespace {
constexpr const char* TAG = "pir";
}  // namespace

PirSensor::PirSensor(Config cfg) : cfg_(cfg) {}

PirSensor::~PirSensor() {
    if (queue_ != nullptr) vQueueDelete(queue_);
}

void PirSensor::init() {
    queue_ = xQueueCreate(16, sizeof(std::uint32_t));

    gpio_config_t io{};
    io.intr_type    = GPIO_INTR_POSEDGE;
    io.mode         = GPIO_MODE_INPUT;
    io.pin_bit_mask = 1ULL << cfg_.gpio;
    io.pull_down_en = GPIO_PULLDOWN_DISABLE;
    io.pull_up_en   = GPIO_PULLUP_DISABLE;
    ESP_ERROR_CHECK(gpio_config(&io));

    gpio_install_isr_service(0);
    ESP_ERROR_CHECK(gpio_isr_handler_add(
        static_cast<gpio_num_t>(cfg_.gpio), &PirSensor::isr_handler, this));

    FW_LOGI(TAG, "PIR inicializado en GPIO %d (debounce %ums, cooldown %ums)",
            cfg_.gpio, static_cast<unsigned>(cfg_.debounce_ms),
            static_cast<unsigned>(cfg_.cooldown_ms));
}

void IRAM_ATTR PirSensor::isr_handler(void* arg) {
    auto* self = static_cast<PirSensor*>(arg);
    const std::uint32_t now_ms = static_cast<std::uint32_t>(esp_timer_get_time() / 1000);
    BaseType_t hp_task_woken = pdFALSE;
    xQueueSendFromISR(self->queue_, &now_ms, &hp_task_woken);
    if (hp_task_woken == pdTRUE) portYIELD_FROM_ISR();
}

bool PirSensor::wait_event(std::uint32_t* out_timestamp_ms, std::uint32_t timeout_ms) {
    std::uint32_t ts = 0;
    const TickType_t ticks = timeout_ms == 0 ? portMAX_DELAY : pdMS_TO_TICKS(timeout_ms);
    if (xQueueReceive(queue_, &ts, ticks) != pdTRUE) return false;
    if (out_timestamp_ms) *out_timestamp_ms = ts;
    return true;
}

void PirSensor::consume() {
    std::uint32_t ts;
    while (xQueueReceive(queue_, &ts, 0) == pdTRUE) {}
}

}  // namespace fw
