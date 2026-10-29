#pragma once
#include <atomic>
#include <memory>
#include <string>
#include <thread>
#include "gateway/config.hpp"
#include "gateway/mqtt_client.hpp"
#include "gateway/transport_signer.hpp"
#include "gateway/sequence_store.hpp"
namespace gateway {
class CommandClient {
public:
    CommandClient(const Config& config, MqttClient& mqtt, SequenceStore& sequence_store);
    ~CommandClient();
    void start();
    void stop() noexcept;
    static std::string signed_commands_path(const std::string& gateway_id, int limit);
private:
    const Config& config_; MqttClient& mqtt_; SequenceStore& sequence_store_; std::unique_ptr<TransportSigner> signer_; std::atomic<bool> running_{false}; std::thread worker_;
    void loop();
    bool verify_command(const std::string& envelope_json, const std::string& signature) const;
};
}
