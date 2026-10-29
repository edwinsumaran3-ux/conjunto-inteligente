#include "config.hpp"

#include "firmware_version.h"

#if __has_include("secrets.h")
#include "secrets.h"
#endif

namespace fw {

Config Config::from_build() {
    Config c;

#ifdef WIFI_SSID
    c.wifi_ssid = WIFI_SSID;
#else
    c.wifi_ssid = "Wokwi-GUEST";
#endif

#ifdef WIFI_PASS
    c.wifi_password = WIFI_PASS;
#else
    c.wifi_password = "";
#endif

#ifdef MQTT_URI
    c.mqtt_uri = MQTT_URI;
#else
    c.mqtt_uri = "mqtt://broker.hivemq.com:1883";
#endif

#ifdef MQTT_USERNAME
    c.mqtt_username = MQTT_USERNAME;
#else
    c.mqtt_username = "";
#endif

#ifdef MQTT_PASSWORD
    c.mqtt_password = MQTT_PASSWORD;
#else
    c.mqtt_password = "";
#endif

#ifdef MQTT_CLIENT_ID
    c.mqtt_client_id = MQTT_CLIENT_ID;
#else
    c.mqtt_client_id = "esp32-default";
#endif

#ifdef TENANT_ID
    c.tenant_id = TENANT_ID;
#else
    c.tenant_id = "tenant-default";
#endif

#ifdef DEVICE_ID
    c.device_id = DEVICE_ID;
#else
    c.device_id = "device-default";
#endif

#ifdef DEVICE_TYPE
    c.device_type = DEVICE_TYPE;
#else
    c.device_type = "sensor.unknown";
#endif

#ifdef OTA_MANIFEST_URL
    c.ota_manifest_url = OTA_MANIFEST_URL;
#else
    c.ota_manifest_url = "";
#endif

    c.firmware_version = FW_VERSION_STRING;
    return c;
}

}  // namespace fw
