#pragma once

#include <cstdint>

#include "sensors/sensor_base.hpp"

namespace fw {

/// Reed switch para puertas/ventanas. Lee por polling (no ISR) para permitir
/// debounce robusto en firmware, con muestreo desde el task.
class MagneticSensor {
public:
    struct Config {
        int gpio;
        std::uint32_t debounce_ms;
        bool active_low;  // true si el circuito cierra a GND
    };

    explicit MagneticSensor(Config cfg) : cfg_(cfg), debouncer_(cfg.debounce_ms) {}

    void init();

    /// Muestrea el GPIO y actualiza el debouncer. Devuelve true si cambió
    /// a estado estable nuevo. `now_ms` viene del caller.
    bool poll(std::uint32_t now_ms);

    [[nodiscard]] bool is_open() const noexcept { return debouncer_.stable_state(); }

private:
    Config cfg_;
    Debouncer debouncer_;
};

}  // namespace fw
