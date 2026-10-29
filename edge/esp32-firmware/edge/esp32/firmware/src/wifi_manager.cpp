#include "wifi_manager.hpp"

#include <cstring>

#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"

#include "logging.hpp"
#include "backoff.hpp"

namespace fw {

namespace {
constexpr const char* TAG = "wifi";
constexpr EventBits_t WIFI_CONNECTED_BIT = BIT0;

EventGroupHandle_t g_event_group = nullptr;
esp_timer_handle_t g_retry_timer = nullptr;
Backoff g_retry_backoff{1000, 30000};
std::uint32_t g_retry_count = 0;

void retry_connect(void*) {
    const esp_err_t err = esp_wifi_connect();
    if (err != ESP_OK) {
        FW_LOGW(TAG, "No se pudo iniciar reconexión WiFi: %s", esp_err_to_name(err));
    }
}
}  // namespace

WifiManager::WifiManager(std::string ssid, std::string password)
    : ssid_(std::move(ssid)), password_(std::move(password)) {}

WifiManager::~WifiManager() = default;

esp_err_t WifiManager::init() {
    if (g_event_group == nullptr) {
        g_event_group = xEventGroupCreate();
    }
    if (g_retry_timer == nullptr) {
        const esp_timer_create_args_t retry_timer_args{
            .callback = &retry_connect,
            .arg = nullptr,
            .dispatch_method = ESP_TIMER_TASK,
            .name = "wifi_retry",
            .skip_unhandled_events = true,
        };
        ESP_ERROR_CHECK(esp_timer_create(&retry_timer_args, &g_retry_timer));
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
        WIFI_CONNECTED_BIT,
        pdFALSE,
        pdTRUE,
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
            xEventGroupClearBits(g_event_group, WIFI_CONNECTED_BIT);
            if (self->cb_) self->cb_(false, self->cb_user_);

            ++g_retry_count;
            const auto retry_delay_ms = g_retry_backoff.next();
            if (esp_timer_is_active(g_retry_timer)) {
                ESP_ERROR_CHECK(esp_timer_stop(g_retry_timer));
            }
            const esp_err_t timer_err = esp_timer_start_once(
                g_retry_timer,
                static_cast<std::uint64_t>(retry_delay_ms) * 1000ULL);
            if (timer_err != ESP_OK) {
                FW_LOGE(TAG, "No se pudo programar reconexión WiFi: %s",
                        esp_err_to_name(timer_err));
            } else {
                FW_LOGW(TAG, "Reconexión WiFi #%u en %u ms",
                        static_cast<unsigned>(g_retry_count),
                        static_cast<unsigned>(retry_delay_ms));
            }
        }
    } else if (std::strcmp(event_base, IP_EVENT) == 0 && event_id == IP_EVENT_STA_GOT_IP) {
        auto* event = static_cast<ip_event_got_ip_t*>(event_data);
        FW_LOGI(TAG, "IP obtenida: " IPSTR, IP2STR(&event->ip_info.ip));
        g_retry_count = 0;
        g_retry_backoff.reset();
        if (esp_timer_is_active(g_retry_timer)) {
            ESP_ERROR_CHECK(esp_timer_stop(g_retry_timer));
        }
        xEventGroupSetBits(g_event_group, WIFI_CONNECTED_BIT);
        self->connected_ = true;
        if (self->cb_) self->cb_(true, self->cb_user_);
    }
}

}  // namespace fw
