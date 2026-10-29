#pragma once

#include <cstdint>

#include "event_publisher.hpp"

namespace fw {

/// Tarea que publica un heartbeat cada N segundos.
/// El intervalo se configura en Config::heartbeat_period_s.
class HeartbeatTask {
public:
    HeartbeatTask(EventPublisher& publisher, std::uint32_t period_s);
    ~HeartbeatTask();

    HeartbeatTask(const HeartbeatTask&) = delete;
    HeartbeatTask& operator=(const HeartbeatTask&) = delete;

    void start();
    void stop();

private:
    EventPublisher& publisher_;
    std::uint32_t period_s_;
    void* task_handle_{nullptr};

    static void task_entry(void* arg);
    void run();
};

}  // namespace fw
