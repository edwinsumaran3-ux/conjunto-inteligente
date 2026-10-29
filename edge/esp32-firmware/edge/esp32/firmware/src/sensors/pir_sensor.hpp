#pragma once

#include <atomic>
#include <cstdint>

#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"

#include "sensors/sensor_base.hpp"

namespace fw {

/// Sensor PIR conectado a un GPIO con interrupción en flanco ascendente.
/// La ISR solo encola un timestamp; el debounce y la publicación se hacen
/// en el task de sensores.
class PirSensor {
public:
    struct Config {
        int gpio;
        std::uint32_t debounce_ms;
        std::uint32_t cooldown_ms;  // mínimo entre eventos publicados
    };

    explicit PirSensor(Config cfg);
    ~PirSensor();

    void init();

    /// Bloquea hasta que hay un evento confirmado. Devuelve el timestamp.
    /// `timeout_ms` = 0 → espera infinita.
    bool wait_event(std::uint32_t* out_timestamp_ms, std::uint32_t timeout_ms);

    /// Vacía la cola de detecciones pendientes.
    void consume();

private:
    Config cfg_;
    QueueHandle_t queue_{nullptr};

    static void IRAM_ATTR isr_handler(void* arg);
};

}  // namespace fw
