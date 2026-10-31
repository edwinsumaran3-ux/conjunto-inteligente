#include <cstdio>
#include <cstring>
#include <string>

#include "esp_event.h"
#include "esp_log.h"
#include "esp_sleep.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "nvs_flash.h"

#include "config.hpp"
#include "event_publisher.hpp"
#include "heartbeat.hpp"
#include "logging.hpp"
#include "mqtt_manager.hpp"
#include "ota_manager.hpp"
#if defined(INSTALLATION_SENSOR_MODE)
#include "sensors/installation_sensors.hpp"
#else
#include "sensors/magnetic_sensor.hpp"
#include "sensors/pir_sensor.hpp"
#include "sensors/tamper_sensor.hpp"
#endif
#include "wifi_manager.hpp"

namespace {
constexpr const char* TAG = "main";

#if !defined(INSTALLATION_SENSOR_MODE)
// Pines del perfil original de seguridad.
constexpr int PIN_PIR      = 27;
constexpr int PIN_MAGNETIC = 26;
constexpr int PIN_TAMPER   = 25;
#endif

#if defined(FW_RELEASE_BUILD)
bool has_release_configuration(const fw::Config& config) {
    return !config.wifi_ssid.empty()
        && config.wifi_ssid != "Wokwi-GUEST"
        && !config.wifi_password.empty()
        && config.mqtt_uri.rfind("mqtts://", 0) == 0
        && !config.mqtt_username.empty()
        && !config.mqtt_password.empty()
        && !config.mqtt_client_id.empty()
        && config.mqtt_client_id != "esp32-default"
        && !config.tenant_id.empty()
        && config.tenant_id != "tenant-default"
        && !config.device_id.empty()
        && config.device_id != "device-default"
        && !config.device_type.empty()
        && config.device_type != "sensor.unknown";
}
#endif

// Contexto compartido con el task de sensores (declarado a nivel de archivo).
struct SensorCtx {
#if defined(INSTALLATION_SENSOR_MODE)
    fw::InstallationSensors* installation;
#else
    fw::PirSensor* pir;
    fw::MagneticSensor* magnetic;
    fw::TamperSensor* tamper;
    fw::EventPublisher* publisher;
#endif
};

void sensor_task(void* arg) {
    auto* ctx = static_cast<SensorCtx*>(arg);

    while (true) {
        const std::uint32_t now_ms = static_cast<std::uint32_t>(
            esp_timer_get_time() / 1000);

#if defined(INSTALLATION_SENSOR_MODE)
        ctx->installation->poll(now_ms);
        vTaskDelay(pdMS_TO_TICKS(50));
#else
        // PIR (bloquea hasta 50 ms en la cola; actúa como cadencia del loop)
        std::uint32_t pir_ts = 0;
        if (ctx->pir->wait_event(&pir_ts, 50)) {
            const bool published = ctx->publisher->publish_event(
                "sensor.pir",
                "{\"zone\":\"default\",\"duration_s\":1}");
            FW_LOGI(TAG, "Evento PIR %s (ts=%u)",
                    published ? "publicado" : "no publicado",
                    static_cast<unsigned>(pir_ts));
        }

        // Magnético
        if (ctx->magnetic->poll(now_ms)) {
            const bool open = ctx->magnetic->is_open();
            const std::string payload = std::string{"{\"state\":\""}
                + (open ? "open" : "closed") + "\"}";
            const bool published = ctx->publisher->publish_event("sensor.magnetic", payload);
            FW_LOGI(TAG, "Evento magnético %s: %s",
                    published ? "publicado" : "no publicado",
                    open ? "open" : "closed");
        }

        // Tamper
        if (ctx->tamper->poll(now_ms)) {
            const bool tampered = ctx->tamper->is_tampered();
            const std::string payload = std::string{"{\"state\":\"tamper\",\"active\":"}
                + (tampered ? "true" : "false") + "}";
            const bool published = ctx->publisher->publish_event("device.tamper", payload);
            FW_LOGW(TAG, "Evento tamper %s: %s",
                    published ? "publicado" : "no publicado",
                    tampered ? "ALERTA" : "ok");
        }
#endif
    }
}
}  // namespace

extern "C" void app_main() {
    FW_LOGI(TAG, "=== Conjunto Inteligente · Firmware %s ===",
            fw::Config::from_build().firmware_version.c_str());

    // NVS es requerida por WiFi y MQTT.
    esp_err_t nvs_err = nvs_flash_init();
    if (nvs_err == ESP_ERR_NVS_NO_FREE_PAGES || nvs_err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        FW_LOGE(TAG, "NVS requiere recuperación; no se borrará automáticamente");
        while (true) {
            vTaskDelay(pdMS_TO_TICKS(60000));
        }
    }
    ESP_ERROR_CHECK(nvs_err);

    const fw::Config config = fw::Config::from_build();

#if defined(FW_RELEASE_BUILD)
    if (!has_release_configuration(config)) {
        FW_LOGE(TAG, "Configuración de producción incompleta; firmware detenido en modo seguro");
        while (true) {
            vTaskDelay(pdMS_TO_TICKS(60000));
        }
    }
#endif

    // ── WiFi ─────────────────────────────────────────────
    fw::WifiManager wifi{config.wifi_ssid, config.wifi_password};
    if (config.wifi_ssid.empty()) {
        FW_LOGW(TAG, "WiFi sin configurar; permanece en modo sin conexión");
    } else {
        ESP_ERROR_CHECK(wifi.init());

        const esp_err_t wifi_err = wifi.wait_connected(30000);
        if (wifi_err != ESP_OK) {
            FW_LOGW(TAG, "WiFi no conectó en 30s; permanece en modo sin conexión");
        }
        if (wifi.connected()) {
            FW_LOGI(TAG, "WiFi conectado");
        }
    }

    // ── MQTT ─────────────────────────────────────────────
    fw::MqttManager::Options mqtt_opts;
    mqtt_opts.uri = config.mqtt_uri;
    mqtt_opts.username = config.mqtt_username;
    mqtt_opts.password = config.mqtt_password;
    mqtt_opts.client_id = config.mqtt_client_id;
    mqtt_opts.qos = config.mqtt_qos;
    mqtt_opts.keepalive_s = config.mqtt_keepalive_s;

    // Last will: si el dispositivo muere, el broker publica esto.
    mqtt_opts.lwt_topic = "conjunto/" + config.tenant_id + "/events";
    mqtt_opts.lwt_payload =
        R"({"type":"device.offline","payload":{"reason":"unexpected_disconnect"}})";

    fw::MqttManager mqtt{mqtt_opts};
    mqtt.on_state_change([](fw::MqttState s) {
        switch (s) {
            case fw::MqttState::Connected:    FW_LOGI(TAG, "MQTT Connected"); break;
            case fw::MqttState::Connecting:   FW_LOGI(TAG, "MQTT Connecting"); break;
            case fw::MqttState::Disconnected: FW_LOGW(TAG, "MQTT Disconnected"); break;
        }
    });
    if (config.mqtt_uri.empty()) {
        FW_LOGW(TAG, "MQTT sin configurar; publicaciones deshabilitadas");
    } else {
        ESP_ERROR_CHECK(mqtt.start());

        // Esperar conexión MQTT con timeout.
        for (int i = 0; i < 100 && !mqtt.connected(); ++i) {
            vTaskDelay(pdMS_TO_TICKS(100));
        }
        if (!mqtt.connected()) {
            FW_LOGE(TAG, "MQTT no conectó en 10s");
        }
    }

    // ── Event Publisher ──────────────────────────────────
    fw::EventPublisher publisher{mqtt, config.tenant_id, config.device_id};

    // ── Heartbeat ────────────────────────────────────────
    fw::HeartbeatTask heartbeat{publisher, static_cast<std::uint32_t>(config.heartbeat_period_s)};
    heartbeat.start();

#if defined(INSTALLATION_SENSOR_MODE)
    // ── Sensores del conjunto ────────────────────────────
    fw::InstallationSensors installation{publisher};
    installation.init();

    static SensorCtx sensor_ctx{&installation};
#else
    // ── Sensores de seguridad ────────────────────────────
    fw::PirSensor pir{{PIN_PIR, static_cast<std::uint32_t>(config.pir_debounce_ms), 500}};
    pir.init();

    fw::MagneticSensor magnetic{{PIN_MAGNETIC,
                                 static_cast<std::uint32_t>(config.magnetic_debounce_ms),
                                 /*active_low=*/true}};
    magnetic.init();

    fw::TamperSensor tamper{{PIN_TAMPER}};
    tamper.init();

    static SensorCtx sensor_ctx{&pir, &magnetic, &tamper, &publisher};
#endif

    // ── Task de sensores ─────────────────────────────────
#if defined(INSTALLATION_SENSOR_MODE)
    constexpr std::uint32_t sensor_task_stack_size = 8192;
#else
    constexpr std::uint32_t sensor_task_stack_size = 4096;
#endif
    xTaskCreate(sensor_task, "sensors", sensor_task_stack_size, &sensor_ctx, 5, nullptr);

    // ── OTA (opcional, según configuración) ─────────────
    if (!config.ota_manifest_url.empty()) {
        fw::OtaManager ota{config.ota_manifest_url, config.firmware_version};
        // Chequeo único al arrancar; el resultado se loguea.
        const auto result = ota.check_and_update();
        FW_LOGI(TAG, "Resultado OTA: %d", static_cast<int>(result));
    }

    // ── Loop principal: monitoreo de salud ───────────────
    while (true) {
        const std::uint32_t free_heap = esp_get_free_heap_size();
        const std::uint32_t min_free = esp_get_minimum_free_heap_size();
        FW_LOGI(TAG, "Heap: libre=%u min=%u | WiFi=%d MQTT=%d",
                static_cast<unsigned>(free_heap), static_cast<unsigned>(min_free),
                static_cast<int>(wifi.connected()),
                static_cast<int>(mqtt.connected()));

        // Reintentar WiFi si se cayó.
        if (!wifi.connected()) {
            FW_LOGW(TAG, "WiFi caído; reintentando...");
            esp_wifi_connect();
        }

        // Reintentar MQTT si WiFi está arriba pero MQTT no.
        if (wifi.connected() && !mqtt.connected() && mqtt.state() == fw::MqttState::Disconnected) {
            FW_LOGW(TAG, "Reiniciando MQTT...");
            mqtt.stop();
            vTaskDelay(pdMS_TO_TICKS(500));
            mqtt.start();
        }

        vTaskDelay(pdMS_TO_TICKS(30000));
    }
}
