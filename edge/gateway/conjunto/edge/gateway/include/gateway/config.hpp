#pragma once

#include <chrono>
#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <optional>
#include <string>

namespace gateway {

/// Configuración del gateway. Todos los campos se cargan de variables de entorno.
/// Documentación de cada variable en edge/README.md.
struct Config {
    // MQTT
    std::string mqtt_host{"localhost"};
    std::uint16_t mqtt_port{1883};
    std::string mqtt_topic{"conjunto/+/events"};
    std::string mqtt_client_id;
    std::string mqtt_username;
    std::string mqtt_password;
    std::string device_id;
    std::string device_private_key;
    std::string tenant_id;
    std::string command_verify_key;
    std::string mqtt_ca_file;
    bool mqtt_use_tls{false};
    int mqtt_keepalive_seconds{20};
    int mqtt_qos{1};

    // Backend
    std::string forward_url{"http://localhost:8000/analyze/reception"};
    std::string api_key;
    std::chrono::milliseconds http_timeout{std::chrono::milliseconds(5000)};

    // Buffer local
    std::filesystem::path buffer_path{"edge-events.db"};
    std::size_t batch_size{50};
    std::chrono::milliseconds flush_interval{std::chrono::milliseconds(1000)};

    // Reintentos
    std::chrono::milliseconds initial_backoff{std::chrono::milliseconds(500)};
    std::chrono::milliseconds max_backoff{std::chrono::milliseconds(30'000)};
    double backoff_multiplier{2.0};
    std::size_t max_retries{20};

    // Health
    int health_port{8080};

    // Logs
    std::string log_level{"INFO"};

    /// Carga la configuración desde variables de entorno.
    static Config from_env();

    /// Valida invariantes. Lanza std::runtime_error si algo es inconsistente.
    void validate() const;
};

}  // namespace gateway
