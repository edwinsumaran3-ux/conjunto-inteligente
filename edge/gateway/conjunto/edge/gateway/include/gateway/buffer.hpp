#pragma once

#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <mutex>
#include <optional>
#include <string>
#include <vector>

#include "gateway/event.hpp"

struct sqlite3;

namespace gateway {

/// Cola persistente de eventos. Usa SQLite en modo WAL para sobrevivir
/// reinicios y para no perder eventos cuando el backend no responde.
class Buffer {
public:
    explicit Buffer(const std::filesystem::path& path);
    ~Buffer();

    Buffer(const Buffer&) = delete;
    Buffer& operator=(const Buffer&) = delete;
    Buffer(Buffer&&) = delete;
    Buffer& operator=(Buffer&&) = delete;

    /// Encola un evento. Idempotente por id: si ya existe, se ignora.
    void enqueue(const Event& event);

    /// Devuelve hasta `max` eventos ordenados por received_at_ms ASC.
    [[nodiscard]] std::vector<Event> peek(std::size_t max) const;

    /// Marca un evento como confirmado (sale de la vista pendiente).
    void ack(const std::string& id);

    /// Registra un fallo de publicación. Aumenta el contador de reintentos.
    void mark_failure(const std::string& id, const std::string& error);

    /// Número de eventos pendientes.
    [[nodiscard]] std::size_t size() const;

    /// Timestamp ms del último ack (para métricas).
    [[nodiscard]] std::optional<std::int64_t> last_ack_at_ms() const;

private:
    sqlite3* db_{nullptr};
    mutable std::mutex mtx_;

    void migrate();
};

}  // namespace gateway
