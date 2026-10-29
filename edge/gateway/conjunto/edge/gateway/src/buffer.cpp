#include "gateway/buffer.hpp"

#include <sqlite3.h>

#include <chrono>
#include <cstdint>
#include <stdexcept>
#include <string>

namespace gateway {

namespace {

std::int64_t now_ms() {
    using namespace std::chrono;
    return duration_cast<milliseconds>(system_clock::now().time_since_epoch()).count();
}

class Stmt {
public:
    Stmt(sqlite3* db, const char* sql) {
        if (sqlite3_prepare_v2(db, sql, -1, &stmt_, nullptr) != SQLITE_OK) {
            throw std::runtime_error(std::string{"SQLite prepare error: "} + sqlite3_errmsg(db));
        }
    }
    ~Stmt() { if (stmt_) sqlite3_finalize(stmt_); }
    Stmt(const Stmt&) = delete;
    Stmt& operator=(const Stmt&) = delete;

    sqlite3_stmt* raw() const noexcept { return stmt_; }

    void bind_text(int idx, const std::string& v) {
        // SQLITE_TRANSIENT es (sqlite3_destructor_type)-1; se escribe sin cast C
        // para no disparar -Wold-style-cast.
        const auto transient =
            reinterpret_cast<sqlite3_destructor_type>(static_cast<std::intptr_t>(-1));
        if (sqlite3_bind_text(stmt_, idx, v.c_str(), static_cast<int>(v.size()), transient) !=
            SQLITE_OK)
            throw std::runtime_error("SQLite bind_text error");
    }
    void bind_int64(int idx, std::int64_t v) {
        if (sqlite3_bind_int64(stmt_, idx, v) != SQLITE_OK)
            throw std::runtime_error("SQLite bind_int64 error");
    }

    bool step_row() {
        const int rc = sqlite3_step(stmt_);
        if (rc == SQLITE_ROW)  return true;
        if (rc == SQLITE_DONE) return false;
        throw std::runtime_error("SQLite step error");
    }

private:
    sqlite3_stmt* stmt_{nullptr};
};

void exec_or_throw(sqlite3* db, const char* sql) {
    char* err = nullptr;
    if (sqlite3_exec(db, sql, nullptr, nullptr, &err) != SQLITE_OK) {
        const std::string msg = err ? err : "unknown sqlite error";
        sqlite3_free(err);
        throw std::runtime_error("SQLite exec error: " + msg);
    }
}

}  // namespace

Buffer::Buffer(const std::filesystem::path& path) {
    if (sqlite3_open(path.string().c_str(), &db_) != SQLITE_OK) {
        const std::string msg = db_ ? sqlite3_errmsg(db_) : "unknown";
        if (db_) { sqlite3_close(db_); db_ = nullptr; }
        throw std::runtime_error("No se pudo abrir SQLite: " + msg);
    }
    exec_or_throw(db_, "PRAGMA journal_mode=WAL;");
    exec_or_throw(db_, "PRAGMA synchronous=NORMAL;");
    exec_or_throw(db_, "PRAGMA foreign_keys=ON;");
    migrate();
}

Buffer::~Buffer() {
    if (db_) sqlite3_close(db_);
}

void Buffer::migrate() {
    exec_or_throw(db_, R"sql(
        CREATE TABLE IF NOT EXISTS events (
            id              TEXT PRIMARY KEY,
            tenant_id       TEXT NOT NULL,
            device_id       TEXT NOT NULL,
            type            TEXT NOT NULL,
            payload_json    TEXT NOT NULL,
            timestamp_ms    INTEGER NOT NULL,
            received_at_ms  INTEGER NOT NULL,
            retries         INTEGER NOT NULL DEFAULT 0,
            last_error      TEXT,
            acked_at_ms     INTEGER
        );
    )sql");

    exec_or_throw(db_, "CREATE INDEX IF NOT EXISTS ix_events_pending "
                       "ON events(received_at_ms) WHERE acked_at_ms IS NULL;");
}

void Buffer::enqueue(const Event& event) {
    std::lock_guard lock{mtx_};
    Stmt s{db_, "INSERT OR IGNORE INTO events "
                "(id, tenant_id, device_id, type, payload_json, timestamp_ms, received_at_ms) "
                "VALUES (?, ?, ?, ?, ?, ?, ?);"};
    s.bind_text(1, event.id);
    s.bind_text(2, event.tenant_id);
    s.bind_text(3, event.device_id);
    s.bind_text(4, event.type);
    s.bind_text(5, event.payload_json);
    s.bind_int64(6, event.timestamp_ms);
    s.bind_int64(7, event.received_at_ms);
    if (s.step_row()) throw std::runtime_error("INSERT inesperado devolvió fila");
}

std::vector<Event> Buffer::peek(std::size_t max) const {
    std::lock_guard lock{mtx_};
    Stmt s{db_, "SELECT id, tenant_id, device_id, type, payload_json, timestamp_ms, received_at_ms "
                "FROM events WHERE acked_at_ms IS NULL "
                "ORDER BY received_at_ms ASC LIMIT ?;"};
    s.bind_int64(1, static_cast<std::int64_t>(max));

    std::vector<Event> out;
    out.reserve(max);
    while (s.step_row()) {
        Event e;
        e.id             = reinterpret_cast<const char*>(sqlite3_column_text(s.raw(), 0));
        e.tenant_id      = reinterpret_cast<const char*>(sqlite3_column_text(s.raw(), 1));
        e.device_id      = reinterpret_cast<const char*>(sqlite3_column_text(s.raw(), 2));
        e.type           = reinterpret_cast<const char*>(sqlite3_column_text(s.raw(), 3));
        e.payload_json   = reinterpret_cast<const char*>(sqlite3_column_text(s.raw(), 4));
        e.timestamp_ms   = sqlite3_column_int64(s.raw(), 5);
        e.received_at_ms = sqlite3_column_int64(s.raw(), 6);
        out.push_back(std::move(e));
    }
    return out;
}

void Buffer::ack(const std::string& id) {
    std::lock_guard lock{mtx_};
    Stmt s{db_, "UPDATE events SET acked_at_ms = ? WHERE id = ?;"};
    s.bind_int64(1, now_ms());
    s.bind_text(2, id);
    if (s.step_row()) throw std::runtime_error("UPDATE inesperado devolvió fila");
}

void Buffer::mark_failure(const std::string& id, const std::string& error) {
    std::lock_guard lock{mtx_};
    Stmt s{db_, "UPDATE events SET retries = retries + 1, last_error = ? WHERE id = ?;"};
    s.bind_text(1, error);
    s.bind_text(2, id);
    if (s.step_row()) throw std::runtime_error("UPDATE inesperado devolvió fila");
}

std::size_t Buffer::size() const {
    std::lock_guard lock{mtx_};
    Stmt s{db_, "SELECT COUNT(*) FROM events WHERE acked_at_ms IS NULL;"};
    if (!s.step_row()) return 0;
    return static_cast<std::size_t>(sqlite3_column_int64(s.raw(), 0));
}

std::optional<std::int64_t> Buffer::last_ack_at_ms() const {
    std::lock_guard lock{mtx_};
    Stmt s{db_, "SELECT MAX(acked_at_ms) FROM events;"};
    if (!s.step_row()) return std::nullopt;
    if (sqlite3_column_type(s.raw(), 0) == SQLITE_NULL) return std::nullopt;
    return sqlite3_column_int64(s.raw(), 0);
}

}  // namespace gateway
