#pragma once
#include <cstdint>
#include <string_view>
namespace conjunto::edge {
enum class SafetyState { Armed, Safe, KillSwitch, Quarantined };
enum class CommandDecision { Accept, InvalidSignature, Expired, Replay, CapabilityDenied, SafetyBlocked };
inline bool safety_allows(SafetyState s, std::string_view command) {
    if (s == SafetyState::KillSwitch || s == SafetyState::Quarantined) return command == "safe_state";
    if (s == SafetyState::Safe) return command == "safe_state" || command == "stop_pump" || command == "stop_drone_mission" || command == "lock";
    return true;
}
}
