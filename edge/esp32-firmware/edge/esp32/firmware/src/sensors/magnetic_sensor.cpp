#include "sensors/magnetic_sensor.hpp"

#include "driver/gpio.h"

#include "logging.hpp"

namespace fw {

namespace {
constexpr const char* TAG = "magnetic";
}

void MagneticSensor::init() {
    gpio_config_t io{};
    io.intr_type    = GPIO_INTR_DISABLE;
    io.mode         = GPIO_MODE_INPUT;
    io.pin_bit_mask = 1ULL << cfg_.gpio;
    io.pull_up_en   = cfg_.active_low ? GPIO_PULLUP_ENABLE : GPIO_PULLUP_DISABLE;
    io.pull_down_en = cfg_.active_low ? GPIO_PULLDOWN_DISABLE : GPIO_PULLDOWN_ENABLE;
    ESP_ERROR_CHECK(gpio_config(&io));
    FW_LOGI(TAG, "Magnético inicializado en GPIO %d (active_low=%d)",
            cfg_.gpio, static_cast<int>(cfg_.active_low));
}

bool MagneticSensor::poll(std::uint32_t now_ms) {
    const int level = gpio_get_level(static_cast<gpio_num_t>(cfg_.gpio));
    // Si active_low, "cerrado" = 0 → sensor "abierto" cuando lee 1.
    const bool raw_open = cfg_.active_low ? (level == 1) : (level == 0);
    return debouncer_.feed(raw_open, now_ms);
}

}  // namespace fw
