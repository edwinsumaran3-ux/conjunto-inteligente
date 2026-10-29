#pragma once
#include <cstdint>
#include <filesystem>
#include <mutex>
struct sqlite3;
namespace gateway {
class SequenceStore {
public:
    explicit SequenceStore(const std::filesystem::path& path);
    ~SequenceStore();
    SequenceStore(const SequenceStore&) = delete;
    SequenceStore& operator=(const SequenceStore&) = delete;
    std::uint64_t next();
private:
    sqlite3* db_{nullptr};
    std::mutex mtx_;
};
}
