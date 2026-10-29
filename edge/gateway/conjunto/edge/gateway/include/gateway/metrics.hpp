#pragma once

#include <atomic>
#include <cstdint>
#include <string>

namespace gateway {

/// Contadores atómicos sin dependencias externas. El health server los expone.
struct Metrics {
    std::atomic<std::uint64_t> events_received{0};
    std::atomic<std::uint64_t> events_published{0};
    std::atomic<std::uint64_t> events_failed{0};
    std::atomic<std::uint64_t> buffer_size{0};
    std::atomic<std::int64_t>  last_publish_at_ms{0};
    std::atomic<std::int64_t>  last_publish_error_at_ms{0};
};

}  // namespace gateway
