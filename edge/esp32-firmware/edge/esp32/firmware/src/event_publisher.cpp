#include "event_publisher.hpp"

#include <cstdio>
#include <ctime>
#include <sstream>

#include "event_id.hpp"
#include "logging.hpp"

namespace fw {

namespace {
constexpr const char* TAG = "event";
}  // namespace

std::string EventPublisher::generate_event_id(const std::string& device_id,
                                               std::uint64_t timestamp_ms,
                                               std::uint32_t counter) {
    return EventIdGenerator::generate(device_id, timestamp_ms, counter);
}

bool EventPublisher::publish_event(const std::string& type,
                                    const std::string& payload_json,
                                    const std::string& event_id_override) {
    const std::uint64_t now_ms = static_cast<std::uint64_t>(
        std::time(nullptr)) * 1000ULL;

    const std::string event_id = event_id_override.empty()
        ? generate_event_id(device_id_, now_ms, ++counter_)
        : event_id_override;

    // Construcción manual del JSON — control byte a byte del contrato.
    std::ostringstream o;
    o << "{"
      << "\"id\":\"" << event_id << "\","
      << "\"tenant_id\":\"" << tenant_id_ << "\","
      << "\"device_id\":\"" << device_id_ << "\","
      << "\"type\":\"" << type << "\","
      << "\"payload\":" << (payload_json.empty() ? "{}" : payload_json) << ","
      << "\"timestamp_ms\":" << now_ms
      << "}";

    return publish_raw(o.str());
}

bool EventPublisher::publish_heartbeat(int battery_mv,
                                        int rssi_dbm,
                                        std::uint32_t uptime_s,
                                        std::uint32_t free_heap_bytes) {
    std::ostringstream payload;
    payload << "{"
            << "\"battery_mv\":" << battery_mv << ","
            << "\"rssi_dbm\":" << rssi_dbm << ","
            << "\"uptime_s\":" << uptime_s << ","
            << "\"free_heap_bytes\":" << free_heap_bytes
            << "}";

    return publish_event("device.heartbeat", payload.str());
}

bool EventPublisher::publish_raw(const std::string& json) {
    const std::string t = topic();
    const auto err = mqtt_.publish(t, json, /*qos=*/1, /*retain=*/false);
    if (err != ESP_OK) {
        FW_LOGW(TAG, "No se pudo publicar a %s: %s", t.c_str(), esp_err_to_name(err));
        return false;
    }
    FW_LOGI(TAG, "Evento publicado a %s (%zu bytes)", t.c_str(), json.size());
    return true;
}

std::string EventPublisher::topic() const {
    return "conjunto/" + tenant_id_ + "/events";
}

}  // namespace fw
