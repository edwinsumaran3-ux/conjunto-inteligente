#pragma once
#include <Arduino.h>

// Sensor de barrera láser/infrarrojo (tripwire): el receptor IR entrega
// nivel alto mientras el haz está intacto y cae a bajo al interrumpirse.
// Se aplica debounce por tiempo para evitar falsos positivos por ruido
// óptico (polvo, insectos, vibración del soporte).
class LaserSensor {
public:
    bool begin(uint8_t pin, uint32_t debounce_ms = 80);
    bool tripped();      // true si la barrera está actualmente interrumpida (tras debounce)
    bool justTripped();  // true una sola vez, en el flanco de interrupción
private:
    uint8_t pin_ = 0;
    uint32_t debounce_ms_ = 80;
    bool stable_state_ = true;   // true = haz intacto
    bool last_raw_ = true;
    uint32_t last_change_ms_ = 0;
    bool edge_pending_ = false;
};
