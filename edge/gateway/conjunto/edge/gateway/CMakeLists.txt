# Librería reutilizable (la consumen tests y el binario).
add_library(conjunto-edge-core STATIC
    src/config.cpp
    src/event.cpp
    src/backoff.cpp
    src/buffer.cpp
    src/mqtt_client.cpp
    src/publisher.cpp
    src/sequence_store.cpp
    src/transport_signer.cpp
    src/command_client.cpp
    src/health_server.cpp
    src/app.cpp
)

target_include_directories(conjunto-edge-core
    PUBLIC
        ${CMAKE_CURRENT_SOURCE_DIR}/include
    PRIVATE
        ${PAHO_INCLUDE_DIR}
)

target_link_libraries(conjunto-edge-core
    PUBLIC
        SQLite::SQLite3
        nlohmann_json::nlohmann_json
        httplib::httplib
        Threads::Threads
        OpenSSL::SSL
        OpenSSL::Crypto
    PRIVATE
        ${PAHO_MQTT_LIB}
)
target_compile_definitions(conjunto-edge-core PUBLIC CPPHTTPLIB_OPENSSL_SUPPORT)

# Binario ejecutable
add_executable(conjunto-edge-gateway src/main.cpp)
target_link_libraries(conjunto-edge-gateway PRIVATE conjunto-edge-core)

# Copiar compile_commands.json a la raíz del módulo para clangd
add_custom_command(TARGET conjunto-edge-gateway POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            ${CMAKE_BINARY_DIR}/compile_commands.json
            ${CMAKE_SOURCE_DIR}/compile_commands.json
    BYPRODUCTS ${CMAKE_SOURCE_DIR}/compile_commands.json
    COMMENT "Copiando compile_commands.json"
)
