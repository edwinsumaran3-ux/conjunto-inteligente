#include "gateway/app.hpp"

#include <chrono>
#include <csignal>
#include <stdexcept>

#include "gateway/backoff.hpp"
#include "gateway/logging.hpp"

namespace gateway {

namespace {
std::atomic<App*> g_app{nullptr};

void signal_handler(int /*sig*/) {
    if (auto* app = g_app.load()) app->request_stop();
}

std::int64_t now_ms() {
    return std::chrono::duration_cast<std::chrono::milliseconds>(
               std::chrono::system_clock::now().time_since_epoch())
        .count();
}
}  // namespace

App::App(Config config) : config_(std::move(config)) {
    set_log_level(config_.log_level);
    buffer_    = std::make_unique<Buffer>(config_.buffer_path);
    publisher_ = std::make_unique<Publisher>(config_);
    mqtt_      = std::make_unique<MqttClient>(
        config_, [this](Event&& e) { handle_event(std::move(e)); });
    health_    = std::make_unique<HealthServer>(config_, *buffer_, metrics_);
    command_client_ = std::make_unique<CommandClient>(config_, *mqtt_, publisher_->sequence_store());
}

App::~App() {
    request_stop();
    if (command_client_) command_client_->stop();
    if (mqtt_) mqtt_->stop();
    if (flush_thread_.joinable()) flush_thread_.join();
}

void App::handle_event(Event&& event) {
    try {
        buffer_->enqueue(event);
        metrics_.events_received.fetch_add(1, std::memory_order_relaxed);
        LOG_INFO("Evento encolado",
                 {{"id", event.id}, {"type", event.type}, {"device", event.device_id}});
    } catch (const std::exception& ex) {
        LOG_ERROR("No se pudo encolar evento", {{"error", ex.what()}, {"id", event.id}});
    }
}

void App::flush_loop() {
    ExponentialBackoff backoff{config_.initial_backoff,
                               config_.max_backoff,
                               config_.backoff_multiplier,
                               0.2};

    while (!stop_.load(std::memory_order_relaxed)) {
        try {
            const auto batch = buffer_->peek(config_.batch_size);
            if (batch.empty()) {
                std::this_thread::sleep_for(config_.flush_interval);
                backoff.reset();
                continue;
            }

            bool any_failure = false;
            for (const auto& ev : batch) {
                if (stop_.load(std::memory_order_relaxed)) break;

                const auto result = publisher_->publish(ev);
                if (result.ok) {
                    buffer_->ack(ev.id);
                    metrics_.events_published.fetch_add(1, std::memory_order_relaxed);
                    metrics_.last_publish_at_ms.store(now_ms(), std::memory_order_relaxed);
                    LOG_INFO("Evento publicado",
                             {{"id", ev.id}, {"http", result.http_status},
                              {"ms", result.duration.count()}});
                } else {
                    any_failure = true;
                    buffer_->mark_failure(ev.id, result.error);
                    metrics_.events_failed.fetch_add(1, std::memory_order_relaxed);
                    metrics_.last_publish_error_at_ms.store(now_ms(), std::memory_order_relaxed);
                    LOG_WARN("Fallo publicación",
                             {{"id", ev.id}, {"error", result.error},
                              {"retryable", result.retryable}});

                    if (!result.retryable) {
                        LOG_ERROR("Error no retryable; se descarta el evento", {{"id", ev.id}});
                        buffer_->ack(ev.id);
                    }
                }
            }

            if (any_failure) {
                const auto delay = backoff.next();
                LOG_INFO("Backoff activo", {{"ms", delay.count()}});
                std::this_thread::sleep_for(delay);
            } else {
                backoff.reset();
            }
        } catch (const std::exception& ex) {
            LOG_ERROR("Excepción en flush_loop", {{"error", ex.what()}});
            std::this_thread::sleep_for(std::chrono::seconds(2));
        }
    }
}

int App::run() {
    g_app.store(this, std::memory_order_relaxed);
    std::signal(SIGINT, signal_handler);
    std::signal(SIGTERM, signal_handler);

    health_->start();

    flush_thread_ = std::thread([this]() { flush_loop(); });

    int exit_code = 0;
    try {
        mqtt_->connect();
        command_client_->start();
        // Si ya llegó una señal antes de conectar, no entrar al loop.
        if (stop_.load(std::memory_order_relaxed)) mqtt_->stop();
        // Hilo auxiliar que traduce la señal de parada al cliente MQTT.
        std::thread watcher([this]() {
            while (!stop_.load(std::memory_order_relaxed))
                std::this_thread::sleep_for(std::chrono::milliseconds(100));
            mqtt_->stop();
        });
        mqtt_->run_loop();
        request_stop();
        watcher.join();
    } catch (const std::exception& ex) {
        LOG_ERROR("MQTT falló", {{"error", ex.what()}});
        exit_code = 1;
    }

    request_stop();
    mqtt_->stop();
    if (command_client_) command_client_->stop();
    if (flush_thread_.joinable()) flush_thread_.join();
    health_->stop();

    LOG_INFO("Gateway detenido",
             {{"published", metrics_.events_published.load()},
              {"failed", metrics_.events_failed.load()},
              {"received", metrics_.events_received.load()}});

    return exit_code;
}

}  // namespace gateway
