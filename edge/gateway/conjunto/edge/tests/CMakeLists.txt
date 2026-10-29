if(NOT TARGET Catch2::Catch2WithMain)
    find_package(Catch2 3 REQUIRED)
endif()

add_executable(edge-tests
    test_event.cpp
    test_backoff.cpp
    test_buffer.cpp
    test_command_client.cpp
    test_publisher.cpp
)
target_link_libraries(edge-tests
    PRIVATE
        conjunto-edge-core
        Catch2::Catch2WithMain
)

list(APPEND CMAKE_MODULE_PATH ${catch2_SOURCE_DIR}/extras)
include(CTest)
include(Catch)
catch_discover_tests(edge-tests)
