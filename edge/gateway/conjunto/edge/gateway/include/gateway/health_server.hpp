#pragma once

#include <atomic>
#include <thread>

#include "gateway/buffer.hpp"
#include "gateway/config.hpp"
#include "gateway/metrics.hpp"

namespace gateway {

/// Servidor HTTP mínimo para liveness, readiness y métricas.
/// Corre en un hilo separado y se detiene al invocar stop().
class HealthServer {
public:
    HealthServer(const Config& config, const Buffer& buffer, Metrics& metrics);
    ~HealthServer();

    HealthServer(const HealthServer&) = delete;
    HealthServer& operator=(const HealthServer&) = delete;

    void start();
    void stop();

private:
    const Config& config_;
    const Buffer& buffer_;
    Metrics& metrics_;
    std::atomic<bool> running_{false};
    std::thread thread_;
    void* server_handle_{nullptr};
};

}  // namespace gateway
