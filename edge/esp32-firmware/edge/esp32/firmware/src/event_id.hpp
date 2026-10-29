#pragma once
#include <cstdint>
#include <cstdio>
#include <string>

namespace fw {

class EventIdGenerator {
public:
    static std::string generate(const std::string& device_id,
                                 std::uint64_t timestamp_ms,
                                 std::uint32_t counter) {
        char buf[128];
        std::snprintf(buf, sizeof(buf), "%.8s-%08X-%04X",
                      device_id.c_str(),
                      static_cast<unsigned int>(timestamp_ms & 0xFFFFFFFFULL),
                      static_cast<unsigned int>(counter & 0xFFFF));
        return std::string{buf};
    }
};

}  // namespace fw
