#include "unity.h"
#include "backoff.hpp"

using namespace fw;

void test_backoff_first_is_initial(void) {
    Backoff b{100, 5000, 2.0, 0.0};
    b.seed(1);
    TEST_ASSERT_EQUAL_UINT32(100, b.next());
}

void test_backoff_grows_and_caps(void) {
    Backoff b{100, 500, 2.0, 0.0};
    b.seed(1);
    TEST_ASSERT_EQUAL_UINT32(100, b.next());
    TEST_ASSERT_EQUAL_UINT32(200, b.next());
    TEST_ASSERT_EQUAL_UINT32(400, b.next());
    TEST_ASSERT_EQUAL_UINT32(500, b.next());  // capped
    TEST_ASSERT_EQUAL_UINT32(500, b.next());
}

void test_backoff_reset(void) {
    Backoff b{100, 5000, 2.0, 0.0};
    b.seed(1);
    (void)b.next();
    (void)b.next();
    b.reset();
    TEST_ASSERT_EQUAL_UINT32(100, b.current());
}

int main(int, char**) {
    UNITY_BEGIN();
    RUN_TEST(test_backoff_first_is_initial);
    RUN_TEST(test_backoff_grows_and_caps);
    RUN_TEST(test_backoff_reset);
    return UNITY_END();
}
