#include <catch2/catch_test_macros.hpp>

#include <chrono>
#include <stdexcept>
#include <vector>

#include "gateway/backoff.hpp"

using namespace std::chrono_literals;
using gateway::ExponentialBackoff;

TEST_CASE("Backoff: primer delay es cercano al inicial", "[backoff]") {
    ExponentialBackoff b{100ms, 5000ms, 2.0, 0.0};
    const auto d = b.next();
    REQUIRE(d == 100ms);
}

TEST_CASE("Backoff: crece hasta el limite", "[backoff]") {
    ExponentialBackoff b{100ms, 500ms, 2.0, 0.0};
    std::vector<std::chrono::milliseconds> delays;
    for (int i = 0; i < 6; ++i) delays.push_back(b.next());

    REQUIRE(delays[0] == 100ms);
    REQUIRE(delays[1] == 200ms);
    REQUIRE(delays[2] == 400ms);
    REQUIRE(delays[3] == 500ms);  // capped
    REQUIRE(delays[4] == 500ms);
    REQUIRE(delays[5] == 500ms);
}

TEST_CASE("Backoff: reset vuelve al inicial", "[backoff]") {
    ExponentialBackoff b{100ms, 5000ms, 2.0, 0.0};
    (void)b.next();
    (void)b.next();
    b.reset();
    REQUIRE(b.current() == 100ms);
}

TEST_CASE("Backoff: constructor valida argumentos", "[backoff]") {
    REQUIRE_THROWS_AS(ExponentialBackoff(0ms, 100ms, 2.0, 0.0), std::invalid_argument);
    REQUIRE_THROWS_AS(ExponentialBackoff(100ms, 50ms, 2.0, 0.0), std::invalid_argument);
    REQUIRE_THROWS_AS(ExponentialBackoff(100ms, 200ms, 0.5, 0.0), std::invalid_argument);
}
