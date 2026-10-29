#pragma once

#include <chrono>
#include <cstdint>
#include <random>

namespace gateway {

/// Backoff exponencial con jitter. Reutilizable por el publisher y por el MQTT reconnect.
class ExponentialBackoff {
public:
    ExponentialBackoff(std::chrono::milliseconds initial,
                       std::chrono::milliseconds max,
                       double multiplier = 2.0,
                       double jitter_fraction = 0.2);

    /// Devuelve el siguiente delay. Cada llamada aumenta el delay hasta `max`.
    std::chrono::milliseconds next();

    /// Vuelve al estado inicial (delay = initial).
    void reset();

    [[nodiscard]] std::chrono::milliseconds current() const noexcept { return current_; }

private:
    std::chrono::milliseconds initial_;
    std::chrono::milliseconds max_;
    double multiplier_;
    double jitter_fraction_;
    std::chrono::milliseconds current_;
    std::mt19937_64 rng_;
};

}  // namespace gateway
