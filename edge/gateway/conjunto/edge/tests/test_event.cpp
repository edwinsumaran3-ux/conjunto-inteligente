#include <catch2/catch_test_macros.hpp>

#include "gateway/event.hpp"

using gateway::Event;
using nlohmann::json;

TEST_CASE("Event: roundtrip JSON conserva todos los campos", "[event]") {
    Event e;
    e.id = "01HQ-abc";
    e.tenant_id = "tenant-A";
    e.device_id = "esp32-014";
    e.type = "sensor.motion";
    e.payload_json = R"({"zone":"P1-Z3","duration_s":12})";
    e.timestamp_ms = 1730512345678LL;
    e.received_at_ms = 1730512349999LL;

    const auto j = e.to_json();
    const auto back = Event::from_json(j);

    REQUIRE(back.id == e.id);
    REQUIRE(back.tenant_id == e.tenant_id);
    REQUIRE(back.device_id == e.device_id);
    REQUIRE(back.type == e.type);
    REQUIRE(back.timestamp_ms == e.timestamp_ms);
    REQUIRE(back.received_at_ms == e.received_at_ms);
}

TEST_CASE("Event: from_json acepta payload como string", "[event]") {
    json j{
        {"id", "x"}, {"tenant_id", "t"}, {"device_id", "d"}, {"type", "sensor.pir"},
        {"payload", "{\"raw\":\"value\"}"}, {"timestamp_ms", 1}
    };
    const auto e = Event::from_json(j);
    REQUIRE(e.payload_json == "{\"raw\":\"value\"}");
}

TEST_CASE("Event: from_json lanza si falta un campo requerido", "[event]") {
    json j{{"id", "x"}, {"tenant_id", "t"}, {"device_id", "d"}};  // falta type
    REQUIRE_THROWS_AS(Event::from_json(j), nlohmann::json::exception);
}

TEST_CASE("Event: to_reception_request arma el contrato esperado", "[event]") {
    Event e;
    e.id = "01HQ-abc";
    e.tenant_id = "tenant-A";
    e.device_id = "esp32-014";
    e.type = "sensor.motion";
    e.payload_json = R"({"zone":"P1-Z3","duration_s":12})";
    e.timestamp_ms = 1730512345678LL;
    e.received_at_ms = 1730512349999LL;

    const auto req = e.to_reception_request();

    REQUIRE(req["tenant_id"] == "tenant-A");
    REQUIRE(req["reporter_kind"] == "sensor");
    REQUIRE(req["description"].get<std::string>().find("P1-Z3") != std::string::npos);
    REQUIRE(req["evidence"].is_array());
    REQUIRE(req["evidence"].size() == 1);
    REQUIRE(req["evidence"][0]["kind"] == "sensor");
}
