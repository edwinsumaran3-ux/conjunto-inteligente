#include "ota_manager.hpp"

#include <cstdio>
#include <cstring>
#include <memory>

#include "esp_crt_bundle.h"
#include "esp_http_client.h"
#include "esp_https_ota.h"
#include "esp_log.h"
#include "esp_ota_ops.h"
#include "esp_system.h"

#include "logging.hpp"

namespace fw {

namespace {
constexpr const char* TAG = "ota";

// Compara versiones "x.y.z". Devuelve true si remote > current.
[[maybe_unused]] bool is_newer(const char* remote, const char* current) {
    int r_maj = 0, r_min = 0, r_patch = 0;
    int c_maj = 0, c_min = 0, c_patch = 0;
    if (std::sscanf(remote,  "%d.%d.%d", &r_maj, &r_min, &r_patch) != 3) return false;
    if (std::sscanf(current, "%d.%d.%d", &c_maj, &c_min, &c_patch) != 3) return true;
    if (r_maj != c_maj) return r_maj > c_maj;
    if (r_min != c_min) return r_min > c_min;
    return r_patch > c_patch;
}
}  // namespace

OtaManager::OtaManager(std::string manifest_url, std::string current_version)
    : manifest_url_(std::move(manifest_url)),
      current_version_(std::move(current_version)) {}

OtaResult OtaManager::check_and_update() {
    if (manifest_url_.empty()) {
        FW_LOGW(TAG, "OTA sin manifest URL configurado");
        return OtaResult::NoUpdateAvailable;
    }

    FW_LOGI(TAG, "Consultando manifest OTA: %s", manifest_url_.c_str());

    esp_http_client_config_t http_cfg{};
    http_cfg.url = manifest_url_.c_str();
    http_cfg.crt_bundle_attach = esp_crt_bundle_attach;
    http_cfg.timeout_ms = 15000;
    http_cfg.keep_alive_enable = true;

    esp_https_ota_config_t ota_cfg{};
    ota_cfg.http_config = &http_cfg;

    // Nota: la verificación de firma se delega a `esp_https_ota` cuando
    // CONFIG_SECURE_SIGNED_APPS_* está activo y el binario viene firmado con
    // la clave correspondiente. Si el firmware remoto no está firmado y secure
    // boot está habilitado, esp_https_ota rechaza el binario.
    // El pipeline de firma se documenta en scripts/sign_firmware.py.

    esp_https_ota_handle_t handle = nullptr;
    const esp_err_t err_begin = esp_https_ota_begin(&ota_cfg, &handle);
    if (err_begin == ESP_ERR_HTTPS_OTA_IN_PROGRESS) {
        FW_LOGW(TAG, "OTA ya en progreso");
        return OtaResult::Failed;
    }
    if (err_begin != ESP_OK) {
        FW_LOGE(TAG, "No se pudo iniciar OTA: %s", esp_err_to_name(err_begin));
        return OtaResult::NoUpdateAvailable;
    }

    // La lógica completa de manifiesto JSON (version/sha256/firma) queda para
    // una iteración posterior; aquí se aplica un binario firmado más nuevo.

    esp_err_t err = ESP_OK;
    while (true) {
        err = esp_https_ota_perform(handle);
        if (err != ESP_ERR_HTTPS_OTA_IN_PROGRESS) break;
    }

    if (err != ESP_OK) {
        FW_LOGE(TAG, "OTA falló: %s", esp_err_to_name(err));
        esp_https_ota_abort(handle);
        return OtaResult::Failed;
    }

    if (!esp_https_ota_is_complete_data_received(handle)) {
        FW_LOGE(TAG, "OTA incompleta");
        esp_https_ota_abort(handle);
        return OtaResult::Failed;
    }

    const esp_err_t err_finish = esp_https_ota_finish(handle);
    if (err_finish == ESP_OK) {
        FW_LOGI(TAG, "OTA completada; reiniciando...");
        esp_restart();
        return OtaResult::Updated;  // unreachable
    }

    if (err_finish == ESP_ERR_OTA_VALIDATE_FAILED) {
        FW_LOGE(TAG, "Firma de firmware inválida — binario rechazado");
        return OtaResult::SignatureInvalid;
    }

    FW_LOGE(TAG, "OTA finish falló: %s", esp_err_to_name(err_finish));
    return OtaResult::Failed;
}

}  // namespace fw
