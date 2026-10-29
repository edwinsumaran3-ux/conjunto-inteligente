#include "gateway/backoff.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace gateway {

ExponentialBackoff::ExponentialBackoff(std::chrono::milliseconds initial,
                                       std::chrono::milliseconds max,
                                       double multiplier,
                                       double jitter_fraction)
    : initial_(initial),
      max_(max),
      multiplier_(multiplier),
      jitter_fraction_(jitter_fraction),
      current_(initial),
      rng_(std::random_device{}()) {
    if (initial <= std::chrono::milliseconds::zero())
        throw std::invalid_argument("initial debe ser > 0");
    if (max < initial) throw std::invalid_argument("max debe ser >= initial");
    if (multiplier < 1.0) throw std::invalid_argument("multiplier debe ser >= 1.0");
    if (jitter_fraction < 0.0 || jitter_fraction > 1.0)
        throw std::invalid_argument("jitter_fraction fuera de [0, 1]");
}

std::chrono::milliseconds ExponentialBackoff::next() {
    const auto base = current_;

    // jitter ± jitter_fraction * base
    std::uniform_real_distribution<double> dist(-jitter_fraction_, jitter_fraction_);
    const double factor = 1.0 + dist(rng_);
    const auto jittered_ms = static_cast<std::int64_t>(
        std::llround(static_cast<double>(base.count()) * factor));

    // Avanza el estado para la próxima llamada.
    const double next_ms = static_cast<double>(current_.count()) * multiplier_;
    const auto capped = std::min<std::int64_t>(
        static_cast<std::int64_t>(std::llround(next_ms)),
        max_.count());
    current_ = std::chrono::milliseconds{std::max<std::int64_t>(capped, initial_.count())};

    const auto clamped = std::clamp<std::int64_t>(jittered_ms, 1, max_.count());
    return std::chrono::milliseconds{clamped};
}

void ExponentialBackoff::reset() {
    current_ = initial_;
}

}  // namespace gateway
