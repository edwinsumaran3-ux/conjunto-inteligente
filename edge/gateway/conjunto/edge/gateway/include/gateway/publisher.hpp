#pragma once

#include <chrono>
#include <string>
#include <memory>

#include <nlohmann/json.hpp>

#include "gateway/config.hpp"
#include "gateway/event.hpp"
#include "gateway/sequence_store.hpp"
#include "gateway/transport_signer.hpp"

namespace gateway {

/// Resultado de un intento de publicación.
struct PublishResult {
    bool ok{false};
    int http_status{0};
    std::string error;
    std::chrono::milliseconds duration{0};
    bool retryable{false};
};

/// Publica eventos al backend vía HTTP.
/// Clasifica errores: 4xx (excepto 408, 429) no son retryables; 5xx sí lo son.
class Publisher {
public:
    explicit Publisher(const Config& config);

    [[nodiscard]] PublishResult publish(const Event& event) const;
    SequenceStore& sequence_store() noexcept { return sequence_store_; }

private:
    const Config& config_;
    mutable SequenceStore sequence_store_;
    std::unique_ptr<TransportSigner> signer_;
};

}  // namespace gateway
