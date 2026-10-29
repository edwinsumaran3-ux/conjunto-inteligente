#include "sensors/sensor_base.hpp"

namespace fw {

bool Debouncer::feed(bool raw_state, std::uint32_t now_ms) {
    if (!initialized_) {
        stable_ = raw_state;
        last_raw_ = raw_state;
        last_change_ms_ = now_ms;
        initialized_ = true;
        return false;
    }

    if (raw_state != last_raw_) {
        last_raw_ = raw_state;
        last_change_ms_ = now_ms;
        return false;
    }

    if (raw_state != stable_ && (now_ms - last_change_ms_) >= debounce_ms_) {
        stable_ = raw_state;
        return true;
    }
    return false;
}

}  // namespace fw
