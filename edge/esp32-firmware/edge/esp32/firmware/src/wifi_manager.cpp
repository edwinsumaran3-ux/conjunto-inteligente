#include "wifi_manager.hpp"

#include <cstring>

#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"

#include "logging.hpp"

namespace fw {

namespace {
constexpr const char* TAG = "wifi";
constexpr EventBits_t WIFI_CONNECTED_BIT = BIT0;
constexpr EventBits_t WIFI_FAIL_BIT = BIT1;

EventGroupHandle_t g_event_group = nullptr;

// Contador de reintentos del stack WiFi.
int g_retry_count = 0;
constexpr int MAX_RETRY = 10;
}  // namespace

WifiManager::WifiManager(std::string ssid, std::string password)
    : ssid_(std::move(ssid)), password_(std::move(password)) {}

WifiManager::~WifiManager() = default;

esp_err_t WifiManager::init() {
    if (g_event_group == nullptr) {
        g_event_group = xEventGroupCreate();
    }

    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    ESP_ERROR_CHECK(esp_event_handler_instance_register(
        WIFI_EVENT, ESP_EVENT_ANY_ID, &WifiManager::event_handler, this, nullptr));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(
        IP_EVENT, IP_EVENT_STA_GOT_IP, &WifiManager::event_handler, this, nullptr));

    wifi_config_t wifi_config{};
    std::strncpy(reinterpret_cast<char*>(wifi_config.sta.ssid),
                 ssid_.c_str(), sizeof(wifi_config.sta.ssid) - 1);
    std::strncpy(reinterpret_cast<char*>(wifi_config.sta.password),
                 password_.c_str(), sizeof(wifi_config.sta.password) - 1);
    wifi_config.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;
    wifi_config.sta.pmf_cfg.capable = true;
    wifi_config.sta.pmf_cfg.required = false;

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());

    FW_LOGI(TAG, "WiFi init OK, SSID=%s", ssid_.c_str());
    return ESP_OK;
}

esp_err_t WifiManager::wait_connected(std::uint32_t timeout_ms) {
    const EventBits_t bits = xEventGroupWaitBits(
        g_event_group,
        WIFI_CONNECTED_BIT | WIFI_FAIL_BIT,
        pdFALSE,
        pdFALSE,
        pdMS_TO_TICKS(timeout_ms));

    if (bits & WIFI_CONNECTED_BIT) {
        connected_ = true;
        return ESP_OK;
    }
    return ESP_ERR_TIMEOUT;
}

void WifiManager::event_handler(void* arg, const char* event_base, int32_t event_id, void* event_data) {
    auto* self = static_cast<WifiManager*>(arg);

    if (std::strcmp(event_base, WIFI_EVENT) == 0) {
        if (event_id == WIFI_EVENT_STA_START) {
            esp_wifi_connect();
        } else if (event_id == WIFI_EVENT_STA_DISCONNECTED) {
            self->connected_ = false;
            if (self->cb_) self->cb_(false, self->cb_user_);

            if (g_retry_count < MAX_RETRY) {
                esp_wifi_connect();
                ++g_retry_count;
                FW_LOGW(TAG, "Reconexión WiFi, intento %d", g_retry_count);
            } else {
                xEventGroupSetBits(g_event_group, WIFI_FAIL_BIT);
                FW_LOGE(TAG, "WiFi falló tras %d intentos", MAX_RETRY);
            }
        }
    } else if (std::strcmp(event_base, IP_EVENT) == 0 && event_id == IP_EVENT_STA_GOT_IP) {
        auto* event = static_cast<ip_event_got_ip_t*>(event_data);
        FW_LOGI(TAG, "IP obtenida: " IPSTR, IP2STR(&event->ip_info.ip));
        g_retry_count = 0;
        xEventGroupClearBits(g_event_group, WIFI_FAIL_BIT);
        xEventGroupSetBits(g_event_group, WIFI_CONNECTED_BIT);
        self->connected_ = true;
        if (self->cb_) self->cb_(true, self->cb_user_);
    }
}

}  // namespace fw
