#pragma once

#include <cstdint>

#include "sensors/sensor_base.hpp"

namespace fw {

/// Detección de manipulación: cuando la carcasa se abre, un pin con pull-up
/// cae a GND. Se usa polling + debounce para evitar falsos positivos.
class TamperSensor {
public:
    struct Config {
        int gpio;
        std::uint32_t debounce_ms = 50;
        bool active_low = true;
    };

    explicit TamperSensor(Config cfg) : cfg_(cfg), debouncer_(cfg.debounce_ms) {}

    void init();
    bool poll(std::uint32_t now_ms);
    [[nodiscard]] bool is_tampered() const noexcept { return debouncer_.stable_state(); }

private:
    Config cfg_;
    Debouncer debouncer_;
};

}  // namespace fw
