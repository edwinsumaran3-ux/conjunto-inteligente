#pragma once

#include <atomic>
#include <functional>
#include <string>
#include <mutex>

#include "gateway/config.hpp"
#include "gateway/event.hpp"

namespace gateway {

/// Wrapper RAII alrededor de Paho MQTT C (sync API).
/// Los callbacks se ejecutan en el hilo que llama a run_loop().
class MqttClient {
public:
    using EventCallback = std::function<void(Event&&)>;

    MqttClient(const Config& config, EventCallback on_event);
    ~MqttClient();

    MqttClient(const MqttClient&) = delete;
    MqttClient& operator=(const MqttClient&) = delete;

    /// Conecta y suscribe al topic configurado. Lanza si falla.
    void connect();

    /// Bucle bloqueante de receive. Retorna cuando stop() es llamado.
    void run_loop();
    bool publish(const std::string& topic, const std::string& payload, int qos);

    /// Señala el bucle para que termine.
    void stop() noexcept { running_.store(false, std::memory_order_relaxed); }

    [[nodiscard]] bool connected() const noexcept {
        return connected_.load(std::memory_order_relaxed);
    }

private:
    const Config& config_;
    EventCallback on_event_;
    void* handle_{nullptr};  // MQTTClient opaco (typedef void*)
    std::atomic<bool> running_{false};
    std::atomic<bool> connected_{false};
    mutable std::mutex publish_mtx_;
};

}  // namespace gateway
