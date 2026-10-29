#pragma once

#include <cstdint>
#include <string>

#include "mqtt_manager.hpp"

namespace fw {

/// Construye y publica eventos que cumplen byte a byte el contrato Event
/// definido en el Edge Gateway (Bloque 3).
class EventPublisher {
public:
    EventPublisher(MqttManager& mqtt,
                   std::string tenant_id,
                   std::string device_id)
        : mqtt_(mqtt),
          tenant_id_(std::move(tenant_id)),
          device_id_(std::move(device_id)) {}

    /// Publica un evento de sensor. `payload_json` es el sub-objeto "payload" del contrato.
    /// Devuelve true si el mensaje fue aceptado por el cliente MQTT.
    bool publish_event(const std::string& type,
                       const std::string& payload_json,
                       const std::string& event_id_override = "");

    /// Publica un evento de heartbeat con batería, RSSI, uptime.
    bool publish_heartbeat(int battery_mv,
                           int rssi_dbm,
                           std::uint32_t uptime_s,
                           std::uint32_t free_heap_bytes);

    /// ID único por dispositivo y ordenable por tiempo (delegado a EventIdGenerator).
    static std::string generate_event_id(const std::string& device_id,
                                         std::uint64_t timestamp_ms,
                                         std::uint32_t counter);

private:
    MqttManager& mqtt_;
    std::string tenant_id_;
    std::string device_id_;
    std::uint32_t counter_{0};

    [[nodiscard]] std::string topic() const;
    bool publish_raw(const std::string& json);
};

}  // namespace fw
