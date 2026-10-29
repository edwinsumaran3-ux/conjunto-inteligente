#include "gateway/transport_signer.hpp"
#include <openssl/evp.h>
#include <openssl/pem.h>
#include <openssl/err.h>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <vector>
namespace gateway {
TransportSigner::TransportSigner(std::string gateway_id, std::filesystem::path private_key_path):gateway_id_(std::move(gateway_id)){
    if(gateway_id_.empty() || private_key_path.empty()) throw std::runtime_error("Identidad edge no configurada");
    FILE* f=fopen(private_key_path.string().c_str(),"rb"); if(!f) throw std::runtime_error("No se pudo abrir EDGE__DEVICE_PRIVATE_KEY");
    EVP_PKEY* p=nullptr; if(!PEM_read_PrivateKey(f,&p,nullptr,nullptr)){fclose(f); throw std::runtime_error("Clave privada edge inválida");} fclose(f); key_=p;
    if(EVP_PKEY_base_id(p)!=EVP_PKEY_ED25519){EVP_PKEY_free(p); key_=nullptr; throw std::runtime_error("La clave edge debe ser Ed25519");}
}
TransportSigner::~TransportSigner(){if(key_) EVP_PKEY_free(static_cast<EVP_PKEY*>(key_));}
std::string TransportSigner::sign(const std::string& message) const{
    EVP_MD_CTX* ctx=EVP_MD_CTX_new(); if(!ctx) throw std::runtime_error("EVP_MD_CTX_new failed");
    size_t len=0; auto* p=static_cast<EVP_PKEY*>(key_);
    if(EVP_DigestSignInit(ctx,nullptr,nullptr,nullptr,p)!=1 || EVP_DigestSign(ctx,nullptr,&len,reinterpret_cast<const unsigned char*>(message.data()),message.size())!=1){EVP_MD_CTX_free(ctx); throw std::runtime_error("Ed25519 signing failed");}
    std::vector<unsigned char> sig(len); if(EVP_DigestSign(ctx,sig.data(),&len,reinterpret_cast<const unsigned char*>(message.data()),message.size())!=1){EVP_MD_CTX_free(ctx); throw std::runtime_error("Ed25519 signing failed");} EVP_MD_CTX_free(ctx);
    static constexpr char alphabet[] =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::string encoded;
    encoded.reserve(((len + 2) / 3) * 4);
    for (size_t index = 0; index < len; index += 3) {
        unsigned int value = static_cast<unsigned int>(sig[index]) << 16;
        if (index + 1 < len) {
            value |= static_cast<unsigned int>(sig[index + 1]) << 8;
        }
        if (index + 2 < len) {
            value |= static_cast<unsigned int>(sig[index + 2]);
        }
        encoded.push_back(alphabet[(value >> 18) & 63]);
        encoded.push_back(alphabet[(value >> 12) & 63]);
        encoded.push_back(index + 1 < len ? alphabet[(value >> 6) & 63] : '=');
        encoded.push_back(index + 2 < len ? alphabet[value & 63] : '=');
    }
    return encoded;
}
}
