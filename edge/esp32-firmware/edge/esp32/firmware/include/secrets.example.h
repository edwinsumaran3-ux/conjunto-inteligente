#pragma once

// Copia este archivo a `secrets.h` y rellena con los valores reales.
// `secrets.h` está en .gitignore y NUNCA debe subirse al repo.

#define WIFI_SSID            "Conjunto-A"
#define WIFI_PASS            "super-secreta"

#define MQTT_URI             "mqtts://mqtt.conjunto.local:8883"
#define MQTT_USERNAME        "esp32-device"
#define MQTT_PASSWORD        "device-secret"
#define MQTT_CLIENT_ID       "esp32-pir-014"

#define TENANT_ID            "conjunto-abc-001"
#define DEVICE_ID            "esp32-pir-014"
#define DEVICE_TYPE          "sensor.pir"

// Endpoint OTA (HTTPS con firma RSA)
#define OTA_MANIFEST_URL     "https://ota.conjunto.local/firmware/manifest.json"

// Token Bearer para el API del core (opcional)
#define CORE_API_KEY         ""
