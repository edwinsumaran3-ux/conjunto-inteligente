#pragma once

#include <atomic>
#include <memory>
#include <thread>

#include "gateway/buffer.hpp"
#include "gateway/command_client.hpp"
#include "gateway/config.hpp"
#include "gateway/health_server.hpp"
#include "gateway/metrics.hpp"
#include "gateway/mqtt_client.hpp"
#include "gateway/publisher.hpp"

namespace gateway {

/// Orquesta el ciclo de vida completo del gateway.
class App {
public:
    explicit App(Config config);
    ~App();

    App(const App&) = delete;
    App& operator=(const App&) = delete;

    /// Bloquea hasta que se invoque request_stop() (por señal o programáticamente).
    /// Devuelve 0 si terminó por señal limpia, distinto de 0 si hubo error.
    int run();

    /// Pide la terminación ordenada.
    void request_stop() noexcept { stop_.store(true, std::memory_order_relaxed); }

private:
    Config config_;
    std::unique_ptr<Buffer> buffer_;
    std::unique_ptr<Publisher> publisher_;
    std::unique_ptr<MqttClient> mqtt_;
    std::unique_ptr<HealthServer> health_;
    std::unique_ptr<CommandClient> command_client_;
    Metrics metrics_;
    std::atomic<bool> stop_{false};
    std::thread flush_thread_;

    void flush_loop();
    void handle_event(Event&& event);
};

}  // namespace gateway
