#pragma once

#include <cstdint>
#include <string>

namespace fw {

/// Configuración inmutable del firmware. Se construye desde `secrets.h` en compilación.
struct Config {
    std::string wifi_ssid;
    std::string wifi_password;

    std::string mqtt_uri;
    std::string mqtt_username;
    std::string mqtt_password;
    std::string mqtt_client_id;
    int         mqtt_qos              = 1;
    int         mqtt_keepalive_s      = 20;
    int         mqtt_reconnect_min_ms = 1000;
    int         mqtt_reconnect_max_ms = 30000;

    std::string tenant_id;
    std::string device_id;
    std::string device_type;
    std::string firmware_version;

    int         heartbeat_period_s    = 60;
    int         pir_debounce_ms       = 200;
    int         magnetic_debounce_ms  = 100;
    int         deep_sleep_after_idle_s = 0; // 0 = nunca dormir

    std::string ota_manifest_url;

    static Config from_build();
};

}  // namespace fw
