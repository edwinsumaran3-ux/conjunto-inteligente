#include "gateway/health_server.hpp"

#include <httplib.h>

#include <chrono>
#include <string>

#include <nlohmann/json.hpp>

#include "gateway/logging.hpp"

namespace gateway {

HealthServer::HealthServer(const Config& config, const Buffer& buffer, Metrics& metrics)
    : config_(config), buffer_(buffer), metrics_(metrics) {}

HealthServer::~HealthServer() {
    stop();
}

void HealthServer::start() {
    if (running_.exchange(true)) return;

    auto* server = new httplib::Server{};
    server_handle_ = server;

    server->Get("/health", [](const httplib::Request&, httplib::Response& res) {
        res.set_content(R"({"status":"ok"})", "application/json");
    });

    server->Get("/ready", [this](const httplib::Request&, httplib::Response& res) {
        const bool ready = true;  // En producción: chequear conexión MQTT real.
        nlohmann::json j{{"status", ready ? "ready" : "not_ready"},
                         {"buffer_size", buffer_.size()}};
        res.status = ready ? 200 : 503;
        res.set_content(j.dump(), "application/json");
    });

    server->Get("/metrics", [this](const httplib::Request&, httplib::Response& res) {
        nlohmann::json j{
            {"events_received",       metrics_.events_received.load()},
            {"events_published",      metrics_.events_published.load()},
            {"events_failed",         metrics_.events_failed.load()},
            {"buffer_size",           buffer_.size()},
            {"last_publish_at_ms",    metrics_.last_publish_at_ms.load()},
            {"last_publish_error_at_ms", metrics_.last_publish_error_at_ms.load()},
        };
        res.set_content(j.dump(), "application/json");
    });

    thread_ = std::thread([this, server]() {
        LOG_INFO("Health server arrancando", {{"port", config_.health_port}});
        if (!server->listen("0.0.0.0", config_.health_port)) {
            LOG_ERROR("Health server no pudo bindear el puerto", {{"port", config_.health_port}});
        }
    });
}

void HealthServer::stop() {
    if (!running_.exchange(false)) return;
    if (server_handle_ != nullptr) {
        auto* server = static_cast<httplib::Server*>(server_handle_);
        server->stop();
        if (thread_.joinable()) thread_.join();
        delete server;
        server_handle_ = nullptr;
    } else if (thread_.joinable()) {
        thread_.join();
    }
}

}  // namespace gateway
