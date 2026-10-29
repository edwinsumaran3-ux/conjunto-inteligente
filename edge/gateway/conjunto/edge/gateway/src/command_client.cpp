#include "gateway/command_client.hpp"

#include <httplib.h>
#include <openssl/crypto.h>
#include <openssl/evp.h>
#include <openssl/hmac.h>

#include <chrono>
#include <stdexcept>
#include <thread>
#include <vector>

#include <nlohmann/json.hpp>

#include "gateway/logging.hpp"

namespace gateway {
namespace {

std::string hmac_hex(const std::string& message, const std::string& key) {
    unsigned char output[EVP_MAX_MD_SIZE];
    unsigned int output_length = 0;
    if (!HMAC(
            EVP_sha256(),
            key.data(),
            static_cast<int>(key.size()),
            reinterpret_cast<const unsigned char*>(message.data()),
            message.size(),
            output,
            &output_length
        )) {
        throw std::runtime_error("command HMAC generation failed");
    }

    static constexpr char hex_digits[] = "0123456789abcdef";
    std::string result;
    result.reserve(output_length * 2);
    for (unsigned int index = 0; index < output_length; ++index) {
        result.push_back(hex_digits[output[index] >> 4]);
        result.push_back(hex_digits[output[index] & 0x0f]);
    }
    return result;
}

}  // namespace

CommandClient::CommandClient(
    const Config& config,
    MqttClient& mqtt,
    SequenceStore& sequence_store
)
    : config_(config), mqtt_(mqtt), sequence_store_(sequence_store) {
    if (config_.device_id.empty() || config_.device_private_key.empty()) {
        throw std::runtime_error("edge identity required");
    }
    signer_ = std::make_unique<TransportSigner>(
        config_.device_id,
        config_.device_private_key
    );
}

CommandClient::~CommandClient() {
    stop();
}

void CommandClient::start() {
    if (running_.exchange(true)) {
        return;
    }
    worker_ = std::thread([this] { loop(); });
}

void CommandClient::stop() noexcept {
    running_.store(false);
    if (worker_.joinable()) {
        worker_.join();
    }
}

std::string CommandClient::signed_commands_path(
    const std::string& gateway_id,
    int limit
) {
    if (gateway_id.empty() || limit < 1 || limit > 50) {
        throw std::invalid_argument("invalid signed-command request");
    }
    return "/api/v1/edge-transport/commands/" + gateway_id +
           "/signed?limit=" + std::to_string(limit);
}

bool CommandClient::verify_command(
    const std::string& envelope_json,
    const std::string& signature
) const {
    const auto expected = hmac_hex(envelope_json, config_.command_verify_key);
    return signature.size() == expected.size() &&
           CRYPTO_memcmp(expected.data(), signature.data(), expected.size()) == 0;
}

void CommandClient::loop() {
    while (running_) {
        try {
            if (!mqtt_.connected()) {
                std::this_thread::sleep_for(std::chrono::seconds(1));
                continue;
            }

            const auto sequence = sequence_store_.next();
            constexpr int command_limit = 10;
            const std::string nonce =
                config_.device_id + "-pull-" + std::to_string(sequence);
            nlohmann::json payload{
                {"gateway_id", config_.device_id},
                {"nonce", nonce},
                {"sequence", sequence},
                {"limit", command_limit},
            };
            nlohmann::json signed_envelope{
                {"gateway_id", config_.device_id},
                {"nonce", nonce},
                {"sequence", sequence},
                {"payload", payload},
            };
            const auto signature = signer_->sign(signed_envelope.dump());

            const auto& url = config_.forward_url;
            const bool use_tls = url.starts_with("https://");
            const std::string scheme = use_tls ? "https://" : "http://";
            if (!url.starts_with(scheme)) {
                throw std::runtime_error(
                    "EDGE__FORWARD_URL must use http:// or https://"
                );
            }

            const auto authority_and_path = url.substr(scheme.size());
            const auto slash = authority_and_path.find('/');
            const auto host_port = authority_and_path.substr(0, slash);
            if (host_port.empty()) {
                throw std::runtime_error("EDGE__FORWARD_URL has no host");
            }

            const auto colon = host_port.find(':');
            const std::string host = colon == std::string::npos
                                         ? host_port
                                         : host_port.substr(0, colon);
            int port = use_tls ? 443 : 80;
            if (colon != std::string::npos) {
                port = std::stoi(host_port.substr(colon + 1));
                if (port < 1 || port > 65535) {
                    throw std::runtime_error(
                        "EDGE__FORWARD_URL has an invalid port"
                    );
                }
            }

            const auto path =
                signed_commands_path(config_.device_id, command_limit);
            const httplib::Headers headers{
                {"X-Edge-Signature", signature},
                {"X-Edge-Tenant-Id", config_.tenant_id},
                {"X-Edge-Nonce", nonce},
                {"X-Edge-Sequence", std::to_string(sequence)},
            };

            httplib::Result response;
            if (use_tls) {
                httplib::SSLClient client(host, port);
                client.enable_server_certificate_verification(true);
                client.set_connection_timeout(config_.http_timeout);
                client.set_read_timeout(config_.http_timeout);
                client.set_write_timeout(config_.http_timeout);
                response = client.Get(path, headers);
            } else {
                httplib::Client client(host, port);
                client.set_connection_timeout(config_.http_timeout);
                client.set_read_timeout(config_.http_timeout);
                client.set_write_timeout(config_.http_timeout);
                response = client.Get(path, headers);
            }

            if (!response || response->status != 200) {
                LOG_WARN(
                    "signed command poll failed",
                    {{"status", response ? response->status : 0}}
                );
                std::this_thread::sleep_for(std::chrono::seconds(2));
                continue;
            }

            const auto root = nlohmann::json::parse(response->body);
            for (const auto& command :
                 root.value("commands", nlohmann::json::array())) {
                const auto envelope =
                    command.value("envelope", nlohmann::json::object());
                const auto command_signature =
                    command.value("signature", std::string{});
                if (!verify_command(envelope.dump(), command_signature)) {
                    LOG_WARN("signed command rejected: signature mismatch");
                    continue;
                }

                const std::string device_topic =
                    "conjunto/" + config_.tenant_id + "/devices/" +
                    config_.device_id + "/commands";
                if (!mqtt_.publish(
                        device_topic,
                        envelope.dump(),
                        config_.mqtt_qos
                    )) {
                    break;
                }
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(500));
        } catch (const std::exception& error) {
            LOG_ERROR(
                "signed command poll failed",
                {{"error", error.what()}}
            );
            std::this_thread::sleep_for(std::chrono::seconds(2));
        }
    }
}

}  // namespace gateway
