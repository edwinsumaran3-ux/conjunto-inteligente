#include "gateway/event.hpp"

#include <chrono>
#include <stdexcept>

namespace gateway {

namespace {

std::int64_t now_ms() {
    using namespace std::chrono;
    return duration_cast<milliseconds>(system_clock::now().time_since_epoch()).count();
}

std::string build_description(const Event& e, const nlohmann::json& payload) {
    std::string base = "Evento " + e.type + " desde dispositivo " + e.device_id;
    if (payload.contains("zone") && payload["zone"].is_string()) {
        base += " en zona " + payload["zone"].get<std::string>();
    }
    if (payload.contains("description") && payload["description"].is_string()) {
        base += ". " + payload["description"].get<std::string>();
    }
    if (payload.contains("duration_s") && payload["duration_s"].is_number()) {
        base += " (duración " + std::to_string(payload["duration_s"].get<int>()) + "s)";
    }
    return base;
}

}  // namespace

nlohmann::json Event::to_json() const {
    return nlohmann::json{
        {"id", id},
        {"tenant_id", tenant_id},
        {"device_id", device_id},
        {"type", type},
        {"payload", payload_json},
        {"timestamp_ms", timestamp_ms},
        {"received_at_ms", received_at_ms},
    };
}

Event Event::from_json(const nlohmann::json& j) {
    Event e;
    e.id             = j.at("id").get<std::string>();
    e.tenant_id      = j.at("tenant_id").get<std::string>();
    e.device_id      = j.at("device_id").get<std::string>();
    e.type           = j.at("type").get<std::string>();
    e.timestamp_ms   = j.at("timestamp_ms").get<std::int64_t>();
    e.received_at_ms = j.value("received_at_ms", now_ms());

    if (j.contains("payload")) {
        const auto& p = j["payload"];
        if (p.is_string()) {
            e.payload_json = p.get<std::string>();
        } else {
            e.payload_json = p.dump();
        }
    } else {
        e.payload_json = "{}";
    }

    if (e.id.empty())        throw std::runtime_error("Event.id vacío");
    if (e.tenant_id.empty()) throw std::runtime_error("Event.tenant_id vacío");
    if (e.device_id.empty()) throw std::runtime_error("Event.device_id vacío");
    if (e.type.empty())      throw std::runtime_error("Event.type vacío");

    return e;
}

nlohmann::json Event::parsed_payload() const {
    if (payload_json.empty()) return nlohmann::json::object();
    try {
        return nlohmann::json::parse(payload_json);
    } catch (const nlohmann::json::parse_error&) {
        // Payload no es JSON: se envuelve como string.
        return nlohmann::json{{"raw", payload_json}};
    }
}

nlohmann::json Event::to_reception_request() const {
    const auto payload = parsed_payload();
    const std::string description = build_description(*this, payload);

    nlohmann::json evidence = nlohmann::json::array();
    evidence.push_back({
        {"kind", "sensor"},
        {"note", "Evento crudo: " + payload.dump()},
    });

    return nlohmann::json{
        {"tenant_id", tenant_id},
        {"reporter_kind", "sensor"},
        {"description", description},
        {"evidence", evidence},
        {"reported_at_iso", std::to_string(timestamp_ms)},
    };
}

}  // namespace gateway
