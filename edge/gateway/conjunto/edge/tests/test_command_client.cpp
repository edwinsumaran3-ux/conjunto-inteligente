#include <catch2/catch_test_macros.hpp>

#include <stdexcept>

#include "gateway/command_client.hpp"

using gateway::CommandClient;

TEST_CASE("CommandClient polls the signed gateway endpoint", "[command-client]") {
    REQUIRE(
        CommandClient::signed_commands_path(
            "65ac0367-54f9-4025-9a19-9c7e1cc9d101", 10
        ) ==
        "/api/v1/edge-transport/commands/65ac0367-54f9-4025-9a19-9c7e1cc9d101/signed?limit=10"
    );
}

TEST_CASE("CommandClient rejects invalid signed-command request limits", "[command-client]") {
    REQUIRE_THROWS_AS(CommandClient::signed_commands_path("", 10), std::invalid_argument);
    REQUIRE_THROWS_AS(CommandClient::signed_commands_path("gateway", 0), std::invalid_argument);
    REQUIRE_THROWS_AS(CommandClient::signed_commands_path("gateway", 51), std::invalid_argument);
}
