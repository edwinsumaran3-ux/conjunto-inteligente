#pragma once

#include <cstddef>
#include <cstdint>

#include "driver/uart.h"
#include "esp_adc/adc_oneshot.h"
#include "ds18b20.h"
#include "event_publisher.hpp"
#include "onewire_bus.h"

namespace fw {

class InstallationSensors {
public:
    explicit InstallationSensors(EventPublisher& publisher) : publisher_(publisher) {}

    void init();
    void poll(std::uint32_t now_ms);

private:
    bool read_adc(adc_channel_t channel, int* raw);
    bool read_pzem(float* voltage_v, float* current_a, float* power_w,
                   float* energy_kwh, float* frequency_hz, int* power_factor_pct);
    static std::uint16_t modbus_crc16(const std::uint8_t* data, std::size_t length);

    EventPublisher& publisher_;
    adc_oneshot_unit_handle_t adc_handle_{};
    onewire_bus_handle_t onewire_bus_{};
    ds18b20_device_handle_t ds18b20_{};
    bool adc_ready_{false};
    bool float_ready_{false};
    bool float_initialized_{false};
    bool previous_water_detected_{false};
    bool pzem_ready_{false};
    std::uint32_t last_sample_ms_{0};
};

}  // namespace fw
