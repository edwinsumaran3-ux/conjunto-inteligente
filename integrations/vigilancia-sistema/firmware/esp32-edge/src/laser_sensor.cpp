#include "laser_sensor.h"

bool LaserSensor::begin(uint8_t pin, uint32_t debounce_ms) {
    pin_ = pin;
    debounce_ms_ = debounce_ms;
    pinMode(pin_, INPUT_PULLUP);
    stable_state_ = digitalRead(pin_) == HIGH;
    last_raw_ = stable_state_;
    last_change_ms_ = millis();
    return true;
}

bool LaserSensor::tripped() {
    bool raw = digitalRead(pin_) == HIGH;
    uint32_t now = millis();
    if (raw != last_raw_) {
        last_raw_ = raw;
        last_change_ms_ = now;
    }
    if ((now - last_change_ms_) >= debounce_ms_ && raw != stable_state_) {
        bool was_intact = stable_state_;
        stable_state_ = raw;
        if (was_intact && !stable_state_) edge_pending_ = true; // flanco: se interrumpió el haz
    }
    return !stable_state_;
}

bool LaserSensor::justTripped() {
    tripped();
    if (edge_pending_) {
        edge_pending_ = false;
        return true;
    }
    return false;
}
