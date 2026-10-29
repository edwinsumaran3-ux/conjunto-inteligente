#include <exception>
#include <iostream>
#include <utility>

#include "gateway/app.hpp"
#include "gateway/config.hpp"
#include "gateway/logging.hpp"

int main() {
    try {
        auto config = gateway::Config::from_env();
        gateway::App app{std::move(config)};
        return app.run();
    } catch (const std::exception& ex) {
        std::cerr << R"({"level":"ERROR","message":"Fallo arrancando gateway","error":")"
                  << ex.what() << "\"}" << '\n';
        return 2;
    }
}
