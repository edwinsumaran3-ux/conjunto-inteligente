#pragma once

#include <cstdint>

namespace fw {

/// Backoff exponencial con jitter determinista (para tests) o aleatorio (para runtime).
class Backoff {
public:
    Backoff(std::uint32_t initial_ms,
            std::uint32_t max_ms,
            double multiplier = 2.0,
            double jitter_fraction = 0.2) noexcept;

    /// Devuelve el siguiente delay en ms.
    std::uint32_t next() noexcept;

    /// Reinicia el estado interno.
    void reset() noexcept { current_ms_ = initial_ms_; }

    /// Valor actual sin consumirlo.
    [[nodiscard]] std::uint32_t current() const noexcept { return current_ms_; }

    /// Sembrar el PRNG para tests deterministas.
    void seed(std::uint64_t s) noexcept;

private:
    std::uint32_t initial_ms_;
    std::uint32_t max_ms_;
    double multiplier_;
    double jitter_fraction_;
    std::uint32_t current_ms_;
    std::uint64_t rng_state_;
};

}  // namespace fw
