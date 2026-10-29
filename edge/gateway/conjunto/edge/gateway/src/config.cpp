#include "gateway/config.hpp"

#ifdef _WIN32
#include <process.h>
#else
#include <unistd.h>
#endif

#include <charconv>
#include <cstdlib>
#include <optional>
#include <stdexcept>
#include <string>
#include <string_view>
#include <system_error>

namespace gateway::detail {

int current_process_id() {
#ifdef _WIN32
    return ::_getpid();
#else
    return ::getpid();
#endif
}

std::string env_or(const char* key, const std::string& fallback) {
    const char* v = std::getenv(key);
    if (v == nullptr || *v == '\0') return fallback;
    return std::string{v};
}

std::optional<std::string> env_opt(const char* key) {
    const char* v = std::getenv(key);
    if (v == nullptr || *v == '\0') return std::nullopt;
    return std::string{v};
}

template <typename T>
T env_number(const char* key, T fallback) {
    const char* v = std::getenv(key);
    if (v == nullptr || *v == '\0') return fallback;
    T out{};
    std::string_view sv{v};
    auto [ptr, ec] = std::from_chars(sv.data(), sv.data() + sv.size(), out);
    if (ec != std::errc{} || ptr != sv.data() + sv.size()) {
        throw std::runtime_error(std::string{"Valor numérico inválido para "} + key + ": " + v);
    }
    return out;
}

bool env_bool(const char* key, bool fallback) {
    const char* v = std::getenv(key);
    if (v == nullptr || *v == '\0') return fallback;
    const std::string s{v};
    return s == "1" || s == "true" || s == "TRUE" || s == "yes" || s == "on";
}

double env_double(const char* key, double fallback) {
    const char* v = std::getenv(key);
    if (v == nullptr || *v == '\0') return fallback;
    try {
        return std::stod(v);
    } catch (const std::exception&) {
        throw std::runtime_error(std::string{"Valor decimal inválido para "} + key + ": " + v);
    }
}

}  // namespace gateway::detail

namespace gateway {

Config Config::from_env() {
    using namespace detail;

    Config cfg;

    cfg.mqtt_host          = env_or("EDGE__MQTT_HOST", cfg.mqtt_host);
    cfg.mqtt_port          = env_number<std::uint16_t>("EDGE__MQTT_PORT", cfg.mqtt_port);
    cfg.mqtt_topic         = env_or("EDGE__MQTT_TOPIC", cfg.mqtt_topic);
    cfg.mqtt_client_id     = env_or("EDGE__MQTT_CLIENT_ID",
                                    "conjunto-edge-" + std::to_string(detail::current_process_id()));
    cfg.mqtt_username      = env_or("EDGE__MQTT_USERNAME", "");
    cfg.mqtt_password      = env_or("EDGE__MQTT_PASSWORD", "");
    cfg.device_id          = env_or("EDGE__DEVICE_ID", "");
    cfg.device_private_key = env_or("EDGE__DEVICE_PRIVATE_KEY", "");
    cfg.tenant_id          = env_or("EDGE__TENANT_ID", "");
    cfg.command_verify_key = env_or("EDGE__COMMAND_VERIFY_KEY", "");
    cfg.mqtt_ca_file       = env_or("EDGE__MQTT_CA_FILE", "");
    cfg.mqtt_use_tls       = env_bool("EDGE__MQTT_USE_TLS", false);
    cfg.mqtt_keepalive_seconds = env_number<int>("EDGE__MQTT_KEEPALIVE", cfg.mqtt_keepalive_seconds);
    cfg.mqtt_qos           = env_number<int>("EDGE__MQTT_QOS", cfg.mqtt_qos);

    cfg.forward_url        = env_or("EDGE__FORWARD_URL", cfg.forward_url);
    cfg.api_key            = env_or("EDGE__API_KEY", "");
    cfg.http_timeout       = std::chrono::milliseconds{env_number<int>(
        "EDGE__HTTP_TIMEOUT_MS", static_cast<int>(cfg.http_timeout.count()))};

    if (auto p = env_opt("EDGE__BUFFER_PATH")) cfg.buffer_path = *p;
    cfg.batch_size         = env_number<std::size_t>("EDGE__BATCH_SIZE", cfg.batch_size);
    cfg.flush_interval     = std::chrono::milliseconds{env_number<int>(
        "EDGE__FLUSH_INTERVAL_MS", static_cast<int>(cfg.flush_interval.count()))};

    cfg.initial_backoff    = std::chrono::milliseconds{env_number<int>(
        "EDGE__INITIAL_BACKOFF_MS", static_cast<int>(cfg.initial_backoff.count()))};
    cfg.max_backoff        = std::chrono::milliseconds{env_number<int>(
        "EDGE__MAX_BACKOFF_MS", static_cast<int>(cfg.max_backoff.count()))};
    cfg.backoff_multiplier = env_double("EDGE__BACKOFF_MULTIPLIER", cfg.backoff_multiplier);
    cfg.max_retries        = env_number<std::size_t>("EDGE__MAX_RETRIES", cfg.max_retries);

    cfg.health_port        = env_number<int>("EDGE__HEALTH_PORT", cfg.health_port);
    cfg.log_level          = env_or("EDGE__LOG_LEVEL", cfg.log_level);

    cfg.validate();
    return cfg;
}

void Config::validate() const {
    if (mqtt_host.empty()) throw std::runtime_error("EDGE__MQTT_HOST no puede estar vacío.");
    if (mqtt_port == 0)    throw std::runtime_error("EDGE__MQTT_PORT debe ser > 0.");
    if (mqtt_topic.empty()) throw std::runtime_error("EDGE__MQTT_TOPIC no puede estar vacío.");
    if (forward_url.empty()) throw std::runtime_error("EDGE__FORWARD_URL no puede estar vacío.");
    if (device_id.empty()) throw std::runtime_error("EDGE__DEVICE_ID es obligatorio para transporte autenticado.");
    if (device_private_key.empty()) throw std::runtime_error("EDGE__DEVICE_PRIVATE_KEY es obligatorio para transporte autenticado.");
    if (tenant_id.empty()) throw std::runtime_error("EDGE__TENANT_ID es obligatorio para transporte autenticado.");
    if (command_verify_key.size() < 32) throw std::runtime_error("EDGE__COMMAND_VERIFY_KEY debe tener >=32 bytes.");
    if (batch_size == 0)   throw std::runtime_error("EDGE__BATCH_SIZE debe ser > 0.");
    if (initial_backoff <= std::chrono::milliseconds::zero())
        throw std::runtime_error("EDGE__INITIAL_BACKOFF_MS debe ser > 0.");
    if (max_backoff < initial_backoff)
        throw std::runtime_error("EDGE__MAX_BACKOFF_MS debe ser >= EDGE__INITIAL_BACKOFF_MS.");
    if (backoff_multiplier < 1.0)
        throw std::runtime_error("EDGE__BACKOFF_MULTIPLIER debe ser >= 1.0.");
    if (health_port <= 0 || health_port > 65535)
        throw std::runtime_error("EDGE__HEALTH_PORT fuera de rango.");
    if (mqtt_qos != 0 && mqtt_qos != 1 && mqtt_qos != 2)
        throw std::runtime_error("EDGE__MQTT_QOS debe ser 0, 1 o 2.");
}

}  // namespace gateway
