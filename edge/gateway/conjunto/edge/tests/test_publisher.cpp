#include <catch2/catch_test_macros.hpp>

#ifdef _WIN32
#include <process.h>
#else
#include <unistd.h>
#endif

#include <atomic>
#include <chrono>
#include <string>
#include <thread>

#include <httplib.h>
#include <nlohmann/json.hpp>

#include "gateway/config.hpp"
#include "gateway/event.hpp"
#include "gateway/publisher.hpp"

using gateway::Config;
using gateway::Event;
using gateway::Publisher;

namespace {

int current_process_id() {
#ifdef _WIN32
    return ::_getpid();
#else
    return ::getpid();
#endif
}

struct MockServer {
    httplib::Server server;
    std::thread th;
    int port{0};
    std::atomic<int> last_status{200};
    std::atomic<int> hits{0};
    std::string last_body;

    MockServer() {
        port = 20000 + (current_process_id() % 10000);
        server.Post("/analyze/reception", [this](const httplib::Request& req, httplib::Response& res) {
            hits.fetch_add(1);
            last_body = req.body;
            res.status = last_status.load();
            res.set_content(R"({"ok":true})", "application/json");
        });
        th = std::thread([this]() { server.listen("127.0.0.1", port); });
        // Esperar a que el server esté escuchando.
        for (int i = 0; i < 50 && !server.is_running(); ++i)
            std::this_thread::sleep_for(std::chrono::milliseconds(20));
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
    }

    ~MockServer() {
        server.stop();
        if (th.joinable()) th.join();
    }
};

Event sample_event() {
    Event e;
    e.id = "evt-1";
    e.tenant_id = "t1";
    e.device_id = "esp32-001";
    e.type = "sensor.pir";
    e.payload_json = R"({"zone":"P1-Z3","duration_s":5})";
    e.timestamp_ms = 1700000000000LL;
    e.received_at_ms = 1700000000001LL;
    return e;
}

}  // namespace

TEST_CASE("Publisher: 200 OK es exitoso y no retryable", "[publisher]") {
    MockServer mock;
    Config cfg;
    cfg.forward_url = "http://127.0.0.1:" + std::to_string(mock.port) + "/analyze/reception";
    Publisher pub{cfg};

    mock.last_status.store(200);
    const auto result = pub.publish(sample_event());

    REQUIRE(result.ok);
    REQUIRE(result.http_status == 200);
    REQUIRE_FALSE(result.retryable);
    REQUIRE(mock.hits.load() == 1);
    REQUIRE(mock.last_body.find("tenant_id") != std::string::npos);
}

TEST_CASE("Publisher: 500 es retryable", "[publisher]") {
    MockServer mock;
    Config cfg;
    cfg.forward_url = "http://127.0.0.1:" + std::to_string(mock.port) + "/analyze/reception";
    Publisher pub{cfg};

    mock.last_status.store(500);
    const auto result = pub.publish(sample_event());

    REQUIRE_FALSE(result.ok);
    REQUIRE(result.http_status == 500);
    REQUIRE(result.retryable);
}

TEST_CASE("Publisher: 422 no es retryable", "[publisher]") {
    MockServer mock;
    Config cfg;
    cfg.forward_url = "http://127.0.0.1:" + std::to_string(mock.port) + "/analyze/reception";
    Publisher pub{cfg};

    mock.last_status.store(422);
    const auto result = pub.publish(sample_event());

    REQUIRE_FALSE(result.ok);
    REQUIRE(result.http_status == 422);
    REQUIRE_FALSE(result.retryable);
}

TEST_CASE("Publisher: 429 es retryable", "[publisher]") {
    MockServer mock;
    Config cfg;
    cfg.forward_url = "http://127.0.0.1:" + std::to_string(mock.port) + "/analyze/reception";
    Publisher pub{cfg};

    mock.last_status.store(429);
    const auto result = pub.publish(sample_event());

    REQUIRE_FALSE(result.ok);
    REQUIRE(result.http_status == 429);
    REQUIRE(result.retryable);
}

TEST_CASE("Publisher: puerto cerrado produce error retryable", "[publisher]") {
    Config cfg;
    cfg.forward_url = "http://127.0.0.1:1/analyze/reception";  // puerto reservado/inexistente
    cfg.http_timeout = std::chrono::milliseconds(300);
    Publisher pub{cfg};

    const auto result = pub.publish(sample_event());
    REQUIRE_FALSE(result.ok);
    REQUIRE(result.retryable);
}

TEST_CASE("Publisher: rechaza protocolos no HTTP sin reintentar", "[publisher]") {
    Config cfg;
    cfg.forward_url = "ftp://example.invalid/reception";
    Publisher pub{cfg};

    const auto result = pub.publish(sample_event());

    REQUIRE_FALSE(result.ok);
    REQUIRE_FALSE(result.retryable);
    REQUIRE(result.error.find("http:// o https://") != std::string::npos);
}
