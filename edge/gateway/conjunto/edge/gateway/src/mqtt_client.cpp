#include "gateway/mqtt_client.hpp"

#include <MQTTClient.h>

#include <chrono>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <string_view>
#include <thread>

#include "gateway/logging.hpp"

namespace gateway {

namespace {

// El topic que llega por MQTT viene con longitud explícita.
std::string topic_to_string(const char* topic, int len) {
    if (len > 0) return std::string{topic, static_cast<std::size_t>(len)};
    return std::string{topic};
}

// Extrae tenant_id del topic si el patrón es "conjunto/<tenant>/events".
// Si no matchea, devuelve "unknown".
std::string extract_tenant(const std::string& topic) {
    constexpr std::string_view prefix = "conjunto/";
    if (!topic.starts_with(prefix)) return "unknown";
    const auto rest = std::string_view{topic}.substr(prefix.size());
    const auto slash = rest.find('/');
    if (slash == std::string_view::npos) return "unknown";
    return std::string{rest.substr(0, slash)};
}

std::int64_t now_ms() {
    using namespace std::chrono;
    return duration_cast<milliseconds>(system_clock::now().time_since_epoch()).count();
}

}  // namespace

MqttClient::MqttClient(const Config& config, EventCallback on_event)
    : config_(config), on_event_(std::move(on_event)) {}

MqttClient::~MqttClient() {
    stop();
    if (handle_ != nullptr) {
        MQTTClient client = handle_;
        if (MQTTClient_isConnected(client)) {
            MQTTClient_disconnect(client, 1000);
        }
        MQTTClient_destroy(&client);
        handle_ = nullptr;
    }
}

void MqttClient::connect() {
    if (handle_ != nullptr) throw std::runtime_error("MqttClient ya conectado");

    const std::string uri = (config_.mqtt_use_tls ? "ssl://" : "tcp://") + config_.mqtt_host +
                            ":" + std::to_string(config_.mqtt_port);

    MQTTClient client = nullptr;
    const int rc_create = MQTTClient_create(&client, uri.c_str(), config_.mqtt_client_id.c_str(),
                                            MQTTCLIENT_PERSISTENCE_NONE, nullptr);
    if (rc_create != MQTTCLIENT_SUCCESS) {
        throw std::runtime_error("MQTTClient_create falló: " + std::to_string(rc_create));
    }
    handle_ = client;

    // Importante: NO se registran callbacks con MQTTClient_setCallbacks.
    // En la API síncrona, MQTTClient_receive() solo funciona sin callbacks.
    MQTTClient_connectOptions conn_opts = MQTTClient_connectOptions_initializer;
    conn_opts.keepAliveInterval = config_.mqtt_keepalive_seconds;
    conn_opts.cleansession      = 1;
    conn_opts.connectTimeout    = 10;
    conn_opts.retryInterval     = 1;

    if (!config_.mqtt_username.empty()) conn_opts.username = config_.mqtt_username.c_str();
    if (!config_.mqtt_password.empty()) conn_opts.password = config_.mqtt_password.c_str();

    MQTTClient_SSLOptions ssl_opts = MQTTClient_SSLOptions_initializer;
    if (config_.mqtt_use_tls) {
        if (!config_.mqtt_ca_file.empty()) ssl_opts.trustStore = config_.mqtt_ca_file.c_str();
        ssl_opts.enableServerCertAuth = 1;
        conn_opts.ssl = &ssl_opts;
    }

    const int rc_connect = MQTTClient_connect(client, &conn_opts);
    if (rc_connect != MQTTCLIENT_SUCCESS) {
        throw std::runtime_error("MQTTClient_connect falló: " + std::to_string(rc_connect));
    }

    const int rc_sub = MQTTClient_subscribe(client, config_.mqtt_topic.c_str(), config_.mqtt_qos);
    if (rc_sub != MQTTCLIENT_SUCCESS) {
        MQTTClient_disconnect(client, 1000);
        throw std::runtime_error("MQTTClient_subscribe falló: " + std::to_string(rc_sub));
    }

    connected_.store(true, std::memory_order_relaxed);
    running_.store(true, std::memory_order_relaxed);

    LOG_INFO("MQTT conectado",
             {{"uri", uri}, {"topic", config_.mqtt_topic}, {"qos", config_.mqtt_qos}});
}

bool MqttClient::publish(const std::string& topic, const std::string& payload, int qos) {
    std::lock_guard lock{publish_mtx_};
    if (handle_ == nullptr || !connected()) return false;
    MQTTClient_message msg = MQTTClient_message_initializer;
    msg.payload = const_cast<char*>(payload.data());
    msg.payloadlen = static_cast<int>(payload.size());
    msg.qos = qos;
    msg.retained = 0;
    MQTTClient_deliveryToken token = 0;
    const int rc = MQTTClient_publishMessage(static_cast<MQTTClient>(handle_), topic.c_str(), &msg, &token);
    if (rc != MQTTCLIENT_SUCCESS) return false;
    return MQTTClient_waitForCompletion(static_cast<MQTTClient>(handle_), token, 5000) == MQTTCLIENT_SUCCESS;
}

void MqttClient::run_loop() {
    if (handle_ == nullptr) throw std::runtime_error("MqttClient no conectado");
    MQTTClient client = handle_;

    while (running_.load(std::memory_order_relaxed)) {
        char* topic = nullptr;
        int topic_len = 0;
        MQTTClient_message* msg = nullptr;

        const int rc = MQTTClient_receive(client, &topic, &topic_len, &msg, 1000);

        if (rc != MQTTCLIENT_SUCCESS) {  // el timeout devuelve SUCCESS con msg == nullptr
            LOG_WARN("MQTT receive error", {{"rc", rc}});
            connected_.store(false, std::memory_order_relaxed);
            std::this_thread::sleep_for(std::chrono::seconds(2));
            continue;
        }

        // Timeout: Paho devuelve SUCCESS con msg == nullptr.
        if (msg == nullptr || topic == nullptr) continue;

        try {
            const std::string topic_str = topic_to_string(topic, topic_len);
            const std::string body{static_cast<const char*>(msg->payload),
                                   static_cast<std::size_t>(msg->payloadlen)};

            LOG_DEBUG("MQTT mensaje recibido", {{"topic", topic_str}, {"bytes", body.size()}});

            nlohmann::json raw = nlohmann::json::parse(body);

            // Si el JSON no trae tenant_id, se deriva del topic.
            if (raw.is_object() && !raw.contains("tenant_id")) {
                raw["tenant_id"] = extract_tenant(topic_str);
            }
            Event event = Event::from_json(raw);
            if (event.received_at_ms == 0) event.received_at_ms = now_ms();

            on_event_(std::move(event));
        } catch (const std::exception& ex) {
            LOG_ERROR("Fallo procesando mensaje MQTT", {{"error", ex.what()}});
        }

        MQTTClient_freeMessage(&msg);
        MQTTClient_free(topic);
    }

    connected_.store(false, std::memory_order_relaxed);
}

}  // namespace gateway
