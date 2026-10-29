#pragma once

#include <cstdint>
#include <functional>
#include <string>

#include "esp_err.h"
#include "mqtt_client.h"

namespace fw {

/// Estados del MQTT normalizados para el resto del firmware.
enum class MqttState { Disconnected, Connecting, Connected };

class MqttManager {
public:
    struct Options {
        std::string uri;          // mqtts://host:port o mqtt://host:port
        std::string username;
        std::string password;
        std::string client_id;
        std::string lwt_topic;    // last will
        std::string lwt_payload;  // JSON del último mensaje antes de morir
        int qos = 1;
        int keepalive_s = 20;
    };

    using StateCallback = std::function<void(MqttState)>;

    explicit MqttManager(Options opts);
    ~MqttManager();

    MqttManager(const MqttManager&) = delete;
    MqttManager& operator=(const MqttManager&) = delete;

    esp_err_t start();
    void stop();

    /// Publica un mensaje. Devuelve ESP_OK si el envío se encoló.
    esp_err_t publish(const std::string& topic,
                      const std::string& payload,
                      int qos = 1,
                      bool retain = false);

    [[nodiscard]] MqttState state() const noexcept { return state_; }
    [[nodiscard]] bool connected() const noexcept { return state_ == MqttState::Connected; }

    void on_state_change(StateCallback cb) { state_cb_ = std::move(cb); }

private:
    Options opts_;
    esp_mqtt_client_handle_t client_{nullptr};
    MqttState state_{MqttState::Disconnected};
    StateCallback state_cb_;

    void set_state(MqttState s);
    static void event_handler(void* args, esp_event_base_t base, int32_t event_id, void* event_data);
};

}  // namespace fw
