#include "backoff.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace fw {

namespace {
// xorshift64 — determinista, sin librerías.
std::uint64_t xorshift64(std::uint64_t& state) noexcept {
    state ^= state << 13;
    state ^= state >> 7;
    state ^= state << 17;
    return state;
}

double next_uniform(std::uint64_t& state) noexcept {
    return static_cast<double>(xorshift64(state) % 1'000'000) / 1'000'000.0;
}
}  // namespace

Backoff::Backoff(std::uint32_t initial_ms,
                 std::uint32_t max_ms,
                 double multiplier,
                 double jitter_fraction) noexcept
    : initial_ms_(initial_ms),
      max_ms_(max_ms),
      multiplier_(multiplier),
      jitter_fraction_(jitter_fraction),
      current_ms_(initial_ms),
      rng_state_(0x9E3779B97F4A7C15ULL) {}

std::uint32_t Backoff::next() noexcept {
    // Rango de jitter: [1 - jf, 1 + jf]
    const double r = next_uniform(rng_state_);
    const double factor = 1.0 + (r * 2.0 - 1.0) * jitter_fraction_;

    const auto jittered = static_cast<std::uint32_t>(
        std::llround(static_cast<double>(current_ms_) * factor));

    // Avanza estado para la próxima llamada.
    const double grown = static_cast<double>(current_ms_) * multiplier_;
    const auto capped = static_cast<std::uint32_t>(
        std::min<double>(grown, static_cast<double>(max_ms_)));
    current_ms_ = std::max<std::uint32_t>(capped, initial_ms_);

    return std::clamp<std::uint32_t>(jittered, 1u, max_ms_);
}

void Backoff::seed(std::uint64_t s) noexcept { rng_state_ = s == 0 ? 1 : s; }

}  // namespace fw
