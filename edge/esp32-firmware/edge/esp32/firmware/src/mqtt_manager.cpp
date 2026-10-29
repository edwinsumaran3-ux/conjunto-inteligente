#include "mqtt_manager.hpp"

#include <atomic>

#include "esp_event.h"
#include "esp_log.h"
#include "esp_tls.h"
#include "esp_crt_bundle.h"

#include "logging.hpp"

namespace fw {

namespace {
constexpr const char* TAG = "mqtt";
}  // namespace

MqttManager::MqttManager(Options opts) : opts_(std::move(opts)) {}

MqttManager::~MqttManager() { stop(); }

esp_err_t MqttManager::start() {
    if (client_ != nullptr) return ESP_OK;

    const bool uses_tls = opts_.uri.rfind("mqtts://", 0) == 0;
    const bool uses_plain_mqtt = opts_.uri.rfind("mqtt://", 0) == 0;
    if (!uses_tls && !uses_plain_mqtt) {
        FW_LOGE(TAG, "Esquema MQTT no soportado");
        return ESP_ERR_INVALID_ARG;
    }
#if defined(FW_RELEASE_BUILD)
    if (!uses_tls) {
        FW_LOGE(TAG, "Release requiere mqtts:// con verificación del broker");
        return ESP_ERR_INVALID_ARG;
    }
#endif

    esp_mqtt_client_config_t cfg{};
    cfg.broker.address.uri = opts_.uri.c_str();
    if (uses_tls) {
        cfg.broker.verification.crt_bundle_attach = esp_crt_bundle_attach;
    }
    if (!opts_.username.empty()) {
        cfg.credentials.username = opts_.username.c_str();
        cfg.credentials.authentication.password = opts_.password.c_str();
    }
    cfg.credentials.client_id = opts_.client_id.c_str();
    cfg.session.keepalive = opts_.keepalive_s;
    cfg.session.disable_clean_session = false;
    cfg.network.reconnect_timeout_ms = 5000;
    cfg.network.timeout_ms = 10000;

    // Last Will and Testament — el broker lo publica si el ESP32 muere sin desconectar.
    if (!opts_.lwt_topic.empty()) {
        cfg.session.last_will.topic = opts_.lwt_topic.c_str();
        cfg.session.last_will.msg = opts_.lwt_payload.c_str();
        cfg.session.last_will.msg_len = static_cast<int>(opts_.lwt_payload.size());
        cfg.session.last_will.qos = opts_.qos;
        cfg.session.last_will.retain = false;
    }

    client_ = esp_mqtt_client_init(&cfg);
    if (client_ == nullptr) {
        FW_LOGE(TAG, "esp_mqtt_client_init falló");
        return ESP_FAIL;
    }

    ESP_ERROR_CHECK(esp_mqtt_client_register_event(
        client_, MQTT_EVENT_ANY, &MqttManager::event_handler, this));

    set_state(MqttState::Connecting);
    const esp_err_t err = esp_mqtt_client_start(client_);
    if (err != ESP_OK) {
        FW_LOGE(TAG, "esp_mqtt_client_start falló: %s", esp_err_to_name(err));
        set_state(MqttState::Disconnected);
    }
    return err;
}

void MqttManager::stop() {
    if (client_ != nullptr) {
        esp_mqtt_client_stop(client_);
        esp_mqtt_client_destroy(client_);
        client_ = nullptr;
    }
    set_state(MqttState::Disconnected);
}

esp_err_t MqttManager::publish(const std::string& topic,
                               const std::string& payload,
                               int qos,
                               bool retain) {
    if (client_ == nullptr || state_ != MqttState::Connected) {
        return ESP_ERR_INVALID_STATE;
    }
    const int msg_id = esp_mqtt_client_publish(
        client_, topic.c_str(), payload.c_str(),
        static_cast<int>(payload.size()), qos, retain ? 1 : 0);
    if (msg_id < 0) {
        FW_LOGW(TAG, "publish devolvió %d", msg_id);
        return ESP_FAIL;
    }
    return ESP_OK;
}

void MqttManager::set_state(MqttState s) {
    if (state_ == s) return;
    state_ = s;
    if (state_cb_) state_cb_(s);
}

void MqttManager::event_handler(void* args, esp_event_base_t, int32_t event_id, void* event_data) {
    auto* self = static_cast<MqttManager*>(args);
    auto* data = static_cast<esp_mqtt_event_handle_t>(event_data);

    switch (event_id) {
        case MQTT_EVENT_CONNECTED:
            FW_LOGI(TAG, "MQTT conectado a %s", self->opts_.uri.c_str());
            self->set_state(MqttState::Connected);
            break;

        case MQTT_EVENT_DISCONNECTED:
            FW_LOGW(TAG, "MQTT desconectado");
            self->set_state(MqttState::Disconnected);
            break;

        case MQTT_EVENT_ERROR:
            if (data->error_handle != nullptr) {
                if (data->error_handle->error_type == MQTT_ERROR_TYPE_TCP_TRANSPORT) {
                    FW_LOGE(TAG, "Error transporte: tls=%d sock_errno=%d",
                            data->error_handle->esp_tls_last_esp_err,
                            data->error_handle->esp_transport_sock_errno);
                }
            }
            self->set_state(MqttState::Disconnected);
            break;

        case MQTT_EVENT_PUBLISHED:
            FW_LOGI(TAG, "Publicado msg_id=%d", data->msg_id);
            break;

        default:
            break;
    }
}

}  // namespace fw
