#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>
#include <LittleFS.h>
struct SecurityEvent{char event_id[40];uint32_t sequence_number;uint64_t timestamp;char type[24];char priority[16];char payload[256];};
class EventBuffer{public:bool begin();bool push(const SecurityEvent&);bool peek(SecurityEvent&);bool ack(const char*);size_t size();private:SemaphoreHandle_t mutex;SecurityEvent ring[BUFFER_MAX_EVENTS];size_t head=0,tail=0,count=0;bool persist();bool load();};
