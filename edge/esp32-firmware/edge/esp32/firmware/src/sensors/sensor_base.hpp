#pragma once

#include <cstdint>

namespace fw {

/// Interfaz abstracta de sensor con debounce simple.
class ISensor {
public:
    virtual ~ISensor() = default;
    virtual void init() = 0;

    /// Lee el estado actual ya debounced. true = evento activo.
    [[nodiscard]] virtual bool read() const = 0;

    /// Devuelve true si el estado cambió desde la última lectura y limpia el flag.
    virtual bool consume_change() = 0;
};

/// Filtro de debounce por software, testeable en nativo.
/// Recibe muestras de estado crudo (bool) con timestamps en ms y decide
/// si hubo un cambio confirmado.
class Debouncer {
public:
    explicit Debouncer(std::uint32_t debounce_ms) : debounce_ms_(debounce_ms) {}

    /// Alimenta una muestra. Devuelve true si la transición es confirmada.
    bool feed(bool raw_state, std::uint32_t now_ms);

    [[nodiscard]] bool stable_state() const noexcept { return stable_; }

private:
    std::uint32_t debounce_ms_;
    bool stable_{false};
    bool last_raw_{false};
    std::uint32_t last_change_ms_{0};
    bool initialized_{false};
};

}  // namespace fw
