#pragma once

#include <cstddef>
#include <string>

#include "esp_err.h"

namespace fw {

/// Resultado de un intento de OTA.
enum class OtaResult {
    NoUpdateAvailable,
    Updated,
    Failed,
    SignatureInvalid,
    VersionSameOrOlder,
};

/// Gestiona la OTA HTTPS con verificación de firma RSA.
/// Lee un manifest JSON con { version, url, sha256, signature_b64 }.
class OtaManager {
public:
    explicit OtaManager(std::string manifest_url, std::string current_version);
    ~OtaManager() = default;

    /// Consulta el manifest y aplica la actualización si corresponde.
    /// Bloqueante. Se invoca desde un task dedicado cuando se desea.
    OtaResult check_and_update();

private:
    std::string manifest_url_;
    std::string current_version_;
};

}  // namespace fw
