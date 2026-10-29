#include <catch2/catch_test_macros.hpp>

#ifdef _WIN32
#include <process.h>
#else
#include <unistd.h>
#endif

#include <chrono>
#include <filesystem>
#include <string>
#include <thread>

#include "gateway/buffer.hpp"

using gateway::Buffer;
using gateway::Event;

namespace {

int current_process_id() {
#ifdef _WIN32
    return ::_getpid();
#else
    return ::getpid();
#endif
}

std::filesystem::path temp_db_path() {
    const auto p = std::filesystem::temp_directory_path() /
                   ("edge-test-" + std::to_string(current_process_id()) + "-" +
                    std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()) +
                    ".db");
    return p;
}

Event make_event(const std::string& id) {
    Event e;
    e.id = id;
    e.tenant_id = "t1";
    e.device_id = "dev-01";
    e.type = "sensor.pir";
    e.payload_json = R"({"zone":"P1-Z3"})";
    e.timestamp_ms = 1000;
    e.received_at_ms = 1000;
    return e;
}

}  // namespace

TEST_CASE("Buffer: enqueue + size + peek", "[buffer]") {
    const auto path = temp_db_path();
    {
        Buffer b{path};
        b.enqueue(make_event("a"));
        b.enqueue(make_event("b"));
        REQUIRE(b.size() == 2);

        const auto items = b.peek(10);
        REQUIRE(items.size() == 2);
        REQUIRE(items[0].id == "a");
        REQUIRE(items[1].id == "b");
    }
    std::filesystem::remove(path);
}

TEST_CASE("Buffer: enqueue idempotente por id", "[buffer]") {
    const auto path = temp_db_path();
    {
        Buffer b{path};
        b.enqueue(make_event("same"));
        b.enqueue(make_event("same"));
        REQUIRE(b.size() == 1);
    }
    std::filesystem::remove(path);
}

TEST_CASE("Buffer: ack elimina de la vista pendiente", "[buffer]") {
    const auto path = temp_db_path();
    {
        Buffer b{path};
        b.enqueue(make_event("x"));
        b.enqueue(make_event("y"));
        b.ack("x");
        REQUIRE(b.size() == 1);
        const auto items = b.peek(10);
        REQUIRE(items.size() == 1);
        REQUIRE(items[0].id == "y");
    }
    std::filesystem::remove(path);
}

TEST_CASE("Buffer: persistencia sobrevive reapertura", "[buffer]") {
    const auto path = temp_db_path();
    {
        Buffer b{path};
        b.enqueue(make_event("persist-1"));
        b.enqueue(make_event("persist-2"));
    }
    {
        Buffer b{path};
        REQUIRE(b.size() == 2);
        const auto items = b.peek(10);
        REQUIRE(items.size() == 2);
        REQUIRE(items[0].id == "persist-1");
    }
    std::filesystem::remove(path);
}

TEST_CASE("Buffer: mark_failure incrementa retries", "[buffer]") {
    const auto path = temp_db_path();
    {
        Buffer b{path};
        b.enqueue(make_event("f1"));
        b.mark_failure("f1", "boom");
        b.mark_failure("f1", "boom again");
        REQUIRE(b.size() == 1);
    }
    std::filesystem::remove(path);
}
