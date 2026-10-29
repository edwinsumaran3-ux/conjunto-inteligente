#include "unity.h"
#include "sensors/sensor_base.hpp"

using namespace fw;

void test_debounce_initializes(void) {
    Debouncer d{100};
    TEST_ASSERT_FALSE(d.feed(false, 0));
    TEST_ASSERT_FALSE(d.stable_state());
}

void test_debounce_confirms_after_window(void) {
    Debouncer d{100};
    (void)d.feed(false, 0);
    TEST_ASSERT_FALSE(d.feed(true, 10));
    TEST_ASSERT_FALSE(d.feed(true, 50));
    TEST_ASSERT_TRUE(d.feed(true, 150));
    TEST_ASSERT_TRUE(d.stable_state());
}

void test_debounce_ignores_bounces(void) {
    Debouncer d{100};
    (void)d.feed(false, 0);
    (void)d.feed(true, 10);
    (void)d.feed(false, 20);
    (void)d.feed(true, 30);
    TEST_ASSERT_FALSE(d.feed(true, 40));
    TEST_ASSERT_TRUE(d.feed(true, 200));
}

int main(int, char**) {
    UNITY_BEGIN();
    RUN_TEST(test_debounce_initializes);
    RUN_TEST(test_debounce_confirms_after_window);
    RUN_TEST(test_debounce_ignores_bounces);
    return UNITY_END();
}
