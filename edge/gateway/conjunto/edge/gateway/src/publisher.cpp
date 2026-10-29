#include "gateway/publisher.hpp"

#include <httplib.h>

#include "gateway/logging.hpp"

namespace gateway {

Publisher::Publisher(const Config& config) : config_(config), sequence_store_(config.buffer_path.string() + ".sequence.db") { if (!config.device_id.empty() && !config.device_private_key.empty()) signer_ = std::make_unique<TransportSigner>(config.device_id, config.device_private_key); }

PublishResult Publisher::publish(const Event& event) const {
    PublishResult result;

    // Separar host/port/path desde forward_url.
    const std::string& url = config_.forward_url;
    std::string scheme;
    if (url.starts_with("https://")) {
        scheme = "https://";
    } else if (url.starts_with("http://")) {
        scheme = "http://";
    } else {
        result.error = "EDGE__FORWARD_URL debe usar http:// o https://";
        result.retryable = false;
        return result;
    }

    const auto without_scheme = url.substr(scheme.size());
    const auto slash_pos = without_scheme.find('/');
    if (slash_pos == std::string::npos) {
        result.error = "EDGE__FORWARD_URL sin path";
        result.retryable = false;
        return result;
    }
    const std::string host_port = without_scheme.substr(0, slash_pos);
    const std::string path      = without_scheme.substr(slash_pos);

    const auto colon_pos = host_port.find(':');
    const std::string host = colon_pos == std::string::npos
                                 ? host_port
                                 : host_port.substr(0, colon_pos);
    int port = scheme == "https://" ? 443 : 80;
    if (colon_pos != std::string::npos) {
        try {
            port = std::stoi(host_port.substr(colon_pos + 1));
        } catch (const std::exception&) {
            result.error = "EDGE__FORWARD_URL con puerto inválido";
            result.retryable = false;
            return result;
        }
    }

    std::string body;
    httplib::Headers headers{{"User-Agent", "conjunto-edge-gateway/1.0"}};
    if (signer_) {
        const auto sequence = sequence_store_.next();
        const std::string nonce = event.id + "-" + std::to_string(sequence);
        nlohmann::json payload{{"event_id", event.id}, {"gateway_id", signer_->gateway_id()},
                               {"nonce", nonce}, {"sequence", sequence},
                               {"occurred_at_ms", event.timestamp_ms}, {"event_type", event.type},
                               {"device_id", event.device_id}, {"payload", event.parsed_payload()}};
        nlohmann::json signing_payload{{"gateway_id", signer_->gateway_id()}, {"nonce", nonce},
                                       {"sequence", sequence}, {"payload", payload}};
        body = payload.dump();
        headers.emplace("X-Edge-Gateway-Id", signer_->gateway_id());
        headers.emplace("X-Edge-Tenant-Id", config_.tenant_id);
        headers.emplace("X-Edge-Nonce", nonce);
        headers.emplace("X-Edge-Sequence", std::to_string(sequence));
        headers.emplace("X-Edge-Signature", signer_->sign(signing_payload.dump()));
    } else {
        body = event.to_reception_request().dump();
    }
    if (!config_.api_key.empty()) headers.emplace("Authorization", "Bearer " + config_.api_key);

    const auto started = std::chrono::steady_clock::now();

    httplib::Result res;
    if (scheme == "https://") {
        httplib::SSLClient cli{host, port};
        cli.enable_server_certificate_verification(true);
        cli.set_connection_timeout(config_.http_timeout);
        cli.set_read_timeout(config_.http_timeout);
        cli.set_write_timeout(config_.http_timeout);
        res = cli.Post(path, headers, body, "application/json");
    } else {
        httplib::Client cli{host, port};
        cli.set_connection_timeout(config_.http_timeout);
        cli.set_read_timeout(config_.http_timeout);
        cli.set_write_timeout(config_.http_timeout);
        res = cli.Post(path, headers, body, "application/json");
    }

    result.duration = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now() - started);

    if (!res) {
        result.ok = false;
        result.error = httplib::to_string(res.error());
        // Errores de red/timeout: retryable.
        result.retryable = true;
        return result;
    }

    result.http_status = res->status;
    if (res->status >= 200 && res->status < 300) {
        result.ok = true;
        result.retryable = false;
        return result;
    }

    result.ok = false;
    result.error = "HTTP " + std::to_string(res->status) + " — " + res->body.substr(0, 200);

    // 4xx no retryable excepto 408 Request Timeout y 429 Too Many Requests.
    result.retryable = !(res->status >= 400 && res->status < 500 &&
                         res->status != 408 && res->status != 429);

    return result;
}

}  // namespace gateway
