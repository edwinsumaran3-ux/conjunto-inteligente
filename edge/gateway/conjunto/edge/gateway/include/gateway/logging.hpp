#pragma once

#include <iostream>
#include <mutex>
#include <string>
#include <utility>

#include <nlohmann/json.hpp>

namespace gateway {

/// Logger JSON mínimo, sin dependencias. Formato: una línea JSON por evento.
/// Suficiente para que OTel/Loki lo capturen. Se puede reemplazar por spdlog
/// cuando se requiera rotación avanzada.
namespace logging {

enum class Level { Debug, Info, Warn, Error };

inline Level level_from_string(const std::string& s) {
    if (s == "DEBUG") return Level::Debug;
    if (s == "INFO")  return Level::Info;
    if (s == "WARN")  return Level::Warn;
    if (s == "ERROR") return Level::Error;
    return Level::Info;
}

inline const char* level_to_string(Level l) {
    switch (l) {
        case Level::Debug: return "DEBUG";
        case Level::Info:  return "INFO";
        case Level::Warn:  return "WARN";
        case Level::Error: return "ERROR";
    }
    return "INFO";
}

inline Level& global_level() {
    static Level level = Level::Info;
    return level;
}

inline std::mutex& global_mutex() {
    static std::mutex m;
    return m;
}

inline void log(Level lvl, const std::string& message, const nlohmann::json& extra = {}) {
    if (lvl < global_level()) return;
    nlohmann::json j{
        {"level", level_to_string(lvl)},
        {"message", message},
    };
    if (extra.is_object()) {
        for (auto it = extra.begin(); it != extra.end(); ++it) {
            j[it.key()] = it.value();
        }
    }
    std::lock_guard lock{global_mutex()};
    std::cerr << j.dump() << '\n';
}

}  // namespace logging

inline void set_log_level(const std::string& level) {
    logging::global_level() = logging::level_from_string(level);
}

}  // namespace gateway

// Macros variádicas: el segundo argumento es un initializer-list JSON con comas
// internas, p. ej. LOG_INFO("msg", {{"a", 1}, {"b", 2}}).
#define LOG_DEBUG(msg, ...) \
    ::gateway::logging::log(::gateway::logging::Level::Debug, (msg), ::nlohmann::json(__VA_ARGS__))
#define LOG_INFO(msg, ...) \
    ::gateway::logging::log(::gateway::logging::Level::Info, (msg), ::nlohmann::json(__VA_ARGS__))
#define LOG_WARN(msg, ...) \
    ::gateway::logging::log(::gateway::logging::Level::Warn, (msg), ::nlohmann::json(__VA_ARGS__))
#define LOG_ERROR(msg, ...) \
    ::gateway::logging::log(::gateway::logging::Level::Error, (msg), ::nlohmann::json(__VA_ARGS__))
