#pragma once
#include <cstdint>
#include <filesystem>
#include <string>
namespace gateway {
class TransportSigner {
public:
    TransportSigner(std::string gateway_id, std::filesystem::path private_key_path);
    ~TransportSigner();
    TransportSigner(const TransportSigner&) = delete;
    TransportSigner& operator=(const TransportSigner&) = delete;
    std::string sign(const std::string& canonical_message) const;
    const std::string& gateway_id() const noexcept { return gateway_id_; }
private:
    std::string gateway_id_;
    void* key_{nullptr};
};
}
