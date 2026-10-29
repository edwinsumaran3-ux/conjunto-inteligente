#pragma once

#if defined(NATIVE_TEST)
#include <cstdio>
#define FW_LOGI(tag, fmt, ...) std::printf("[I][%s] " fmt "\n", tag, ##__VA_ARGS__)
#define FW_LOGW(tag, fmt, ...) std::printf("[W][%s] " fmt "\n", tag, ##__VA_ARGS__)
#define FW_LOGE(tag, fmt, ...) std::printf("[E][%s] " fmt "\n", tag, ##__VA_ARGS__)
#else
#include "esp_log.h"
#define FW_LOGI(tag, fmt, ...) ESP_LOGI(tag, fmt, ##__VA_ARGS__)
#define FW_LOGW(tag, fmt, ...) ESP_LOGW(tag, fmt, ##__VA_ARGS__)
#define FW_LOGE(tag, fmt, ...) ESP_LOGE(tag, fmt, ##__VA_ARGS__)
#endif
