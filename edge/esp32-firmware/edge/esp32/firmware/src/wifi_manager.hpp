#pragma once

#include <cstdint>
#include <string>

#include "esp_err.h"

namespace fw {

class WifiManager {
public:
    WifiManager(std::string ssid, std::string password);
    ~WifiManager();

    WifiManager(const WifiManager&) = delete;
    WifiManager& operator=(const WifiManager&) = delete;

    /// Inicializa el stack WiFi en modo STA. Idempotente.
    esp_err_t init();

    /// Espera hasta conectar o agotar timeout. 0 = éxito.
    esp_err_t wait_connected(std::uint32_t timeout_ms);

    [[nodiscard]] bool connected() const noexcept { return connected_; }

    /// Registra callback llamado cuando la conexión cambia.
    using StateCallback = void (*)(bool connected, void* user);
    void on_state_change(StateCallback cb, void* user) {
        cb_ = cb;
        cb_user_ = user;
    }

private:
    std::string ssid_;
    std::string password_;
    bool connected_{false};
    StateCallback cb_{nullptr};
    void* cb_user_{nullptr};

    static void event_handler(void* arg, const char* event_base, int32_t event_id, void* event_data);
};

}  // namespace fw
