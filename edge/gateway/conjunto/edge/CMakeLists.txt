cmake_minimum_required(VERSION 3.28)

project(ConjuntoEdge
    VERSION 0.1.0
    DESCRIPTION "Edge Gateway para Conjunto Inteligente"
    LANGUAGES CXX)

# ── C++ 20 estricto ──────────────────────────────────────
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
    set(CMAKE_BUILD_TYPE Debug CACHE STRING "" FORCE)
endif()

# ── Opciones ─────────────────────────────────────────────
option(EDGE_BUILD_TESTS "Build tests" ON)
option(EDGE_SANITIZE "Enable ASan+UBSan in Debug" ON)

# ── Dependencias header-only vía FetchContent ────────────
# (se declaran ANTES de los warnings estrictos para que -Werror no
#  afecte al código de terceros; además van como SYSTEM)
include(FetchContent)

FetchContent_Declare(
    nlohmann_json
    URL https://github.com/nlohmann/json/releases/download/v3.11.3/json.tar.xz
    DOWNLOAD_EXTRACT_TIMESTAMP ON
    SYSTEM)
set(JSON_BuildTests OFF CACHE INTERNAL "")
FetchContent_MakeAvailable(nlohmann_json)

FetchContent_Declare(
    cpp_httplib
    GIT_REPOSITORY https://github.com/yhirose/cpp-httplib.git
    GIT_TAG v0.18.3
    GIT_SHALLOW TRUE
    SYSTEM)
set(HTTPLIB_COMPILE OFF CACHE INTERNAL "")
FetchContent_MakeAvailable(cpp_httplib)

if(EDGE_BUILD_TESTS)
    FetchContent_Declare(
        Catch2
        GIT_REPOSITORY https://github.com/catchorg/Catch2.git
        GIT_TAG v3.7.1
        GIT_SHALLOW TRUE
        SYSTEM)
    FetchContent_MakeAvailable(Catch2)
endif()

# ── Warnings estrictos (solo para el código propio) ──────
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    add_compile_options(
        -Wall -Wextra -Wpedantic -Werror
        -Wshadow -Wnon-virtual-dtor -Wold-style-cast
        -Wcast-align -Wunused -Woverloaded-virtual
        -Wconversion -Wsign-conversion
        -Wdouble-promotion -Wformat=2
        -Wimplicit-fallthrough
    )
    if(CMAKE_BUILD_TYPE STREQUAL "Debug" AND EDGE_SANITIZE)
        add_compile_options(-fsanitize=address,undefined -fno-omit-frame-pointer)
        add_link_options(-fsanitize=address,undefined)
    endif()
elseif(MSVC)
    add_compile_options(/EHsc)
endif()

# ── Dependencias del sistema ─────────────────────────────
find_package(SQLite3 REQUIRED)
find_package(Threads REQUIRED)
find_package(OpenSSL REQUIRED)

find_path(PAHO_INCLUDE_DIR MQTTClient.h
    PATHS /usr/include /usr/local/include /opt/homebrew/include)
find_library(PAHO_MQTT_LIB
    NAMES paho-mqtt3c libpaho-mqtt3c
    PATHS /usr/lib /usr/local/lib /usr/lib/x86_64-linux-gnu /opt/homebrew/lib)

if(NOT PAHO_INCLUDE_DIR OR NOT PAHO_MQTT_LIB)
    message(FATAL_ERROR
        "libpaho-mqtt no encontrada. Instala:
         Ubuntu/Debian: sudo apt install libpaho-mqtt-dev
         macOS:         brew install paho-mqtt-c")
endif()

message(STATUS "Paho MQTT include: ${PAHO_INCLUDE_DIR}")
message(STATUS "Paho MQTT lib:     ${PAHO_MQTT_LIB}")

# ── Subdirectorios ───────────────────────────────────────
add_subdirectory(gateway)

if(EDGE_BUILD_TESTS)
    enable_testing()
    add_subdirectory(tests)
endif()
