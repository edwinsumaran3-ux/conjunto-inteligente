#include "unity.h"
#include <cstring>
#include <string>

// Generación de ID sin depender de ESP-IDF.
#include "event_id.hpp"

void test_event_id_is_unique_for_counter(void) {
    const auto a = fw::EventIdGenerator::generate("esp32-014", 1000, 1);
    const auto b = fw::EventIdGenerator::generate("esp32-014", 1000, 2);
    TEST_ASSERT_TRUE(a != b);
}

void test_event_id_deterministic(void) {
    const auto a = fw::EventIdGenerator::generate("esp32-014", 1000, 1);
    const auto b = fw::EventIdGenerator::generate("esp32-014", 1000, 1);
    TEST_ASSERT_EQUAL_STRING(a.c_str(), b.c_str());
}

void test_event_id_format(void) {
    const auto id = fw::EventIdGenerator::generate("esp32-014", 0xABCDEF, 0x1234);
    // esperado: esp32-01-00ABCDEF-1234
    TEST_ASSERT_EQUAL_STRING("esp32-01-00ABCDEF-1234", id.c_str());
}

int main(int, char**) {
    UNITY_BEGIN();
    RUN_TEST(test_event_id_is_unique_for_counter);
    RUN_TEST(test_event_id_deterministic);
    RUN_TEST(test_event_id_format);
    return UNITY_END();
}
