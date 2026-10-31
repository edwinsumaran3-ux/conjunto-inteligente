#include "sensors/installation_sensors.hpp"

#include <array>
#include <cstdio>

#include "dht.h"
#include "driver/gpio.h"
#include "esp_err.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "logging.hpp"

namespace fw {
namespace {

constexpr const char* TAG = "installation_sensors";

constexpr gpio_num_t PIN_DHT22 = GPIO_NUM_4;
constexpr gpio_num_t PIN_DS18B20 = GPIO_NUM_15;
constexpr gpio_num_t PIN_FLOAT_SWITCH = GPIO_NUM_27;
constexpr gpio_num_t PIN_ACS712_ADC = GPIO_NUM_35;
constexpr gpio_num_t PIN_PRESSURE_ADC = GPIO_NUM_34;
constexpr gpio_num_t PIN_PZEM_TX = GPIO_NUM_16;
constexpr gpio_num_t PIN_PZEM_RX = GPIO_NUM_17;
constexpr std::uint32_t SAMPLE_INTERVAL_MS = 5000;
constexpr std::uint8_t PZEM_ADDRESS = 0xF8;
constexpr std::size_t PZEM_RESPONSE_SIZE = 25;

}  // namespace

void InstallationSensors::init() {
    gpio_config_t float_config{};
    float_config.intr_type = GPIO_INTR_DISABLE;
    float_config.mode = GPIO_MODE_INPUT;
    float_config.pin_bit_mask = 1ULL << PIN_FLOAT_SWITCH;
    float_config.pull_up_en = GPIO_PULLUP_ENABLE;
    float_config.pull_down_en = GPIO_PULLDOWN_DISABLE;
    const esp_err_t float_err = gpio_config(&float_config);
    float_ready_ = float_err == ESP_OK;
    if (!float_ready_) {
        FW_LOGE(TAG, "No se pudo configurar el flotador: %s", esp_err_to_name(float_err));
    }

    adc_oneshot_unit_init_cfg_t adc_unit_config{};
    adc_unit_config.unit_id = ADC_UNIT_1;
    adc_unit_config.ulp_mode = ADC_ULP_MODE_DISABLE;
    esp_err_t err = adc_oneshot_new_unit(&adc_unit_config, &adc_handle_);
    if (err == ESP_OK) {
        adc_oneshot_chan_cfg_t channel_config{};
        channel_config.atten = ADC_ATTEN_DB_12;
        channel_config.bitwidth = ADC_BITWIDTH_DEFAULT;
        err = adc_oneshot_config_channel(adc_handle_, ADC_CHANNEL_7, &channel_config);
        if (err == ESP_OK) {
            err = adc_oneshot_config_channel(adc_handle_, ADC_CHANNEL_6, &channel_config);
        }
    }
    adc_ready_ = err == ESP_OK;
    if (!adc_ready_) {
        FW_LOGE(TAG, "No se pudieron configurar ADC1: %s", esp_err_to_name(err));
    }

    onewire_bus_config_t bus_config{};
    bus_config.bus_gpio_num = PIN_DS18B20;
    bus_config.flags.en_pull_up = true;
    onewire_bus_rmt_config_t rmt_config{};
    rmt_config.max_rx_bytes = 10;
    err = onewire_new_bus_rmt(&bus_config, &rmt_config, &onewire_bus_);
    if (err == ESP_OK) {
        ds18b20_config_t device_config{};
        err = ds18b20_new_device_from_bus(onewire_bus_, &device_config, &ds18b20_);
    }
    if (err != ESP_OK) {
        FW_LOGW(TAG, "DS18B20 no disponible; revisar sensor y pull-up externo: %s",
                esp_err_to_name(err));
        ds18b20_ = nullptr;
    }

    uart_config_t uart_config{};
    uart_config.baud_rate = 9600;
    uart_config.data_bits = UART_DATA_8_BITS;
    uart_config.parity = UART_PARITY_DISABLE;
    uart_config.stop_bits = UART_STOP_BITS_1;
    uart_config.flow_ctrl = UART_HW_FLOWCTRL_DISABLE;
    uart_config.source_clk = UART_SCLK_DEFAULT;
    err = uart_param_config(UART_NUM_2, &uart_config);
    if (err == ESP_OK) {
        err = uart_set_pin(UART_NUM_2, PIN_PZEM_TX, PIN_PZEM_RX,
                           UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE);
    }
    if (err == ESP_OK) {
        err = uart_driver_install(UART_NUM_2, 256, 0, 0, nullptr, 0);
    }
    pzem_ready_ = err == ESP_OK;
    if (!pzem_ready_) {
        FW_LOGE(TAG, "No se pudo configurar UART2 para PZEM: %s", esp_err_to_name(err));
    }

    FW_LOGI(TAG,
            "Sensores listos: DHT22=GPIO4 DS18B20=GPIO15 flotador=GPIO27 "
            "ACS712=GPIO35 presion=GPIO34 PZEM TX=GPIO16 RX=GPIO17");
}

void InstallationSensors::poll(std::uint32_t now_ms) {
    if (now_ms - last_sample_ms_ < SAMPLE_INTERVAL_MS) {
        return;
    }
    last_sample_ms_ = now_ms;

    if (float_ready_) {
        const bool water_detected = gpio_get_level(PIN_FLOAT_SWITCH) == 0;
        if (!float_initialized_ || water_detected != previous_water_detected_) {
            char payload[80]{};
            std::snprintf(payload, sizeof(payload),
                          "{\"water_detected\":%s,\"contact_active\":%s}",
                          water_detected ? "true" : "false",
                          water_detected ? "true" : "false");
            publisher_.publish_event("sensor.water_level", payload);
            previous_water_detected_ = water_detected;
            float_initialized_ = true;
        }
    }

    float humidity = 0.0F;
    float air_temperature = 0.0F;
    if (dht_read_float_data(DHT_TYPE_AM2301, PIN_DHT22, &humidity, &air_temperature)
        == ESP_OK) {
        char payload[112]{};
        std::snprintf(payload, sizeof(payload),
                      "{\"temperature_c\":%.2f,\"humidity_pct\":%.2f}",
                      static_cast<double>(air_temperature),
                      static_cast<double>(humidity));
        publisher_.publish_event("sensor.environment", payload);
    } else {
        FW_LOGW(TAG, "No se pudo leer el DHT22");
    }

    if (ds18b20_ != nullptr) {
        float water_temperature = 0.0F;
        if (ds18b20_trigger_temperature_conversion(ds18b20_) == ESP_OK
            && ds18b20_get_temperature(ds18b20_, &water_temperature) == ESP_OK) {
            char payload[64]{};
            std::snprintf(payload, sizeof(payload), "{\"temperature_c\":%.2f}",
                          static_cast<double>(water_temperature));
            publisher_.publish_event("sensor.water_temperature", payload);
        } else {
            FW_LOGW(TAG, "No se pudo leer el DS18B20");
        }
    }

    int acs712_raw = 0;
    if (read_adc(ADC_CHANNEL_7, &acs712_raw)) {
        char payload[64]{};
        std::snprintf(payload, sizeof(payload), "{\"raw_adc\":%d,\"max_adc\":4095}",
                      acs712_raw);
        publisher_.publish_event("sensor.current_raw", payload);
    }

    int pressure_raw = 0;
    if (read_adc(ADC_CHANNEL_6, &pressure_raw)) {
        char payload[64]{};
        std::snprintf(payload, sizeof(payload), "{\"raw_adc\":%d,\"max_adc\":4095}",
                      pressure_raw);
        publisher_.publish_event("sensor.pressure_raw", payload);
    }

    if (pzem_ready_) {
        float voltage_v = 0.0F;
        float current_a = 0.0F;
        float power_w = 0.0F;
        float energy_kwh = 0.0F;
        float frequency_hz = 0.0F;
        int power_factor_pct = 0;
        if (read_pzem(&voltage_v, &current_a, &power_w, &energy_kwh,
                      &frequency_hz, &power_factor_pct)) {
            char payload[192]{};
            std::snprintf(payload, sizeof(payload),
                          "{\"voltage_v\":%.1f,\"current_a\":%.3f,"
                          "\"power_w\":%.1f,\"energy_kwh\":%.3f,"
                          "\"frequency_hz\":%.1f,\"power_factor_pct\":%d}",
                          static_cast<double>(voltage_v),
                          static_cast<double>(current_a),
                          static_cast<double>(power_w),
                          static_cast<double>(energy_kwh),
                          static_cast<double>(frequency_hz),
                          power_factor_pct);
            publisher_.publish_event("sensor.energy", payload);
        } else {
            FW_LOGW(TAG, "Sin respuesta valida del PZEM-004T v3.0");
        }
    }
}

bool InstallationSensors::read_adc(adc_channel_t channel, int* raw) {
    if (!adc_ready_ || raw == nullptr) {
        return false;
    }

    std::int32_t total = 0;
    constexpr int SAMPLE_COUNT = 16;
    for (int i = 0; i < SAMPLE_COUNT; ++i) {
        int sample = 0;
        const esp_err_t err = adc_oneshot_read(adc_handle_, channel, &sample);
        if (err != ESP_OK) {
            FW_LOGW(TAG, "Error de lectura ADC: %s", esp_err_to_name(err));
            return false;
        }
        total += sample;
    }
    *raw = static_cast<int>(total / SAMPLE_COUNT);
    return true;
}

std::uint16_t InstallationSensors::modbus_crc16(const std::uint8_t* data,
                                                 std::size_t length) {
    std::uint16_t crc = 0xFFFF;
    for (std::size_t i = 0; i < length; ++i) {
        crc ^= data[i];
        for (int bit = 0; bit < 8; ++bit) {
            crc = (crc & 1U) != 0U
                ? static_cast<std::uint16_t>((crc >> 1U) ^ 0xA001U)
                : static_cast<std::uint16_t>(crc >> 1U);
        }
    }
    return crc;
}

bool InstallationSensors::read_pzem(float* voltage_v, float* current_a, float* power_w,
                                    float* energy_kwh, float* frequency_hz,
                                    int* power_factor_pct) {
    if (voltage_v == nullptr || current_a == nullptr || power_w == nullptr
        || energy_kwh == nullptr || frequency_hz == nullptr || power_factor_pct == nullptr) {
        return false;
    }

    std::array<std::uint8_t, 8> request{
        PZEM_ADDRESS, 0x04, 0x00, 0x00, 0x00, 0x0A, 0x00, 0x00
    };
    const std::uint16_t request_crc = modbus_crc16(request.data(), 6);
    request[6] = static_cast<std::uint8_t>(request_crc & 0xFFU);
    request[7] = static_cast<std::uint8_t>(request_crc >> 8U);

    uart_flush_input(UART_NUM_2);
    if (uart_write_bytes(UART_NUM_2, request.data(), request.size())
        != static_cast<int>(request.size())) {
        return false;
    }
    if (uart_wait_tx_done(UART_NUM_2, pdMS_TO_TICKS(100)) != ESP_OK) {
        return false;
    }

    std::array<std::uint8_t, PZEM_RESPONSE_SIZE> response{};
    std::size_t received = 0;
    const TickType_t deadline = xTaskGetTickCount() + pdMS_TO_TICKS(500);
    while (received < response.size() && xTaskGetTickCount() < deadline) {
        const int count = uart_read_bytes(
            UART_NUM_2, response.data() + received,
            response.size() - received, pdMS_TO_TICKS(50));
        if (count > 0) {
            received += static_cast<std::size_t>(count);
        }
    }

    if (received != response.size() || response[0] != PZEM_ADDRESS
        || response[1] != 0x04 || response[2] != 20) {
        return false;
    }

    const std::uint16_t response_crc = static_cast<std::uint16_t>(response[23])
        | static_cast<std::uint16_t>(response[24] << 8U);
    if (modbus_crc16(response.data(), response.size() - 2) != response_crc) {
        return false;
    }

    const auto read_u16 = [&response](std::size_t register_index) {
        const std::size_t offset = 3 + register_index * 2;
        return static_cast<std::uint16_t>(
            (static_cast<std::uint16_t>(response[offset]) << 8U)
            | response[offset + 1]);
    };
    const auto read_u32 = [&read_u16](std::size_t register_index) {
        return (static_cast<std::uint32_t>(read_u16(register_index + 1)) << 16U)
            | read_u16(register_index);
    };

    *voltage_v = static_cast<float>(read_u16(0)) / 10.0F;
    *current_a = static_cast<float>(read_u32(1)) / 1000.0F;
    *power_w = static_cast<float>(read_u32(3)) / 10.0F;
    *energy_kwh = static_cast<float>(read_u32(5)) / 1000.0F;
    *frequency_hz = static_cast<float>(read_u16(7)) / 10.0F;
    *power_factor_pct = static_cast<int>(read_u16(8));
    return true;
}

}  // namespace fw
