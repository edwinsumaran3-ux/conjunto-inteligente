#pragma once

#include <cstdint>
#include <optional>
#include <string>

#include <nlohmann/json.hpp>

namespace gateway {

/// Evento recibido por MQTT desde un sensor, cámara o dispositivo edge.
/// No confundir con eventos de dominio del core .NET: este es el formato
/// "raw" del gateway antes de convertirlo al contrato del AI Orchestrator.
struct Event {
    std::string id;              // ID único (ULID-like o similar)
    std::string tenant_id;       // Tenant dueño del conjunto
    std::string device_id;       // Identificador físico del dispositivo
    std::string type;            // "sensor.motion", "sensor.magnetic", "camera.detection", ...
    std::string payload_json;    // JSON crudo del sensor
    std::int64_t timestamp_ms{0};   // ms desde epoch UTC
    std::int64_t received_at_ms{0}; // ms desde epoch UTC cuando el gateway lo recibió

    /// Serializa el evento a JSON.
    [[nodiscard]] nlohmann::json to_json() const;

    /// Construye un Event desde JSON. Lanza nlohmann::json::exception si el schema no cuadra.
    static Event from_json(const nlohmann::json& j);

    /// Parsea el payload interno como JSON (puede venir como string o como objeto).
    [[nodiscard]] nlohmann::json parsed_payload() const;

    /// Traduce el evento a un Request compatible con el AI Orchestrator
    /// POST /analyze/reception.
    [[nodiscard]] nlohmann::json to_reception_request() const;
};

}  // namespace gateway
