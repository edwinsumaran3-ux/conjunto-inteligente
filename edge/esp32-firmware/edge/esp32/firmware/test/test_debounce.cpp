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
    (void)d.feed(false, 0);      // init: stable=false
    TEST_ASSERT_FALSE(d.feed(true, 10));   // raw change
    TEST_ASSERT_FALSE(d.feed(true, 50));   // aún dentro de ventana
    TEST_ASSERT_TRUE(d.feed(true, 150));   // 140ms > 100ms → confirma
    TEST_ASSERT_TRUE(d.stable_state());
}

void test_debounce_ignores_bounces(void) {
    Debouncer d{100};
    (void)d.feed(false, 0);
    (void)d.feed(true, 10);
    (void)d.feed(false, 20);  // rebote: cambio a false
    (void)d.feed(true, 30);   // rebote otra vez
    TEST_ASSERT_FALSE(d.feed(true, 40));  // no pasó ventana desde 30
    TEST_ASSERT_TRUE(d.feed(true, 200));  // ahora sí
}

int main(int, char**) {
    UNITY_BEGIN();
    RUN_TEST(test_debounce_initializes);
    RUN_TEST(test_debounce_confirms_after_window);
    RUN_TEST(test_debounce_ignores_bounces);
    return UNITY_END();
}
