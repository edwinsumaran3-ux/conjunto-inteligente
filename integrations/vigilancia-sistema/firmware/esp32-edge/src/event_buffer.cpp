#include "event_buffer.h"
static const char* PATH="/events.bin";
bool EventBuffer::begin(){mutex=xSemaphoreCreateMutex();if(!LittleFS.begin(true))return false;return load();}
bool EventBuffer::push(const SecurityEvent&e){if(xSemaphoreTake(mutex,pdMS_TO_TICKS(100))!=pdTRUE)return false;if(count>=BUFFER_MAX_EVENTS){xSemaphoreGive(mutex);return false;}ring[tail]=e;tail=(tail+1)%BUFFER_MAX_EVENTS;count++;bool ok=persist();xSemaphoreGive(mutex);return ok;}
bool EventBuffer::peek(SecurityEvent&o){if(xSemaphoreTake(mutex,pdMS_TO_TICKS(100))!=pdTRUE)return false;bool ok=count>0;if(ok)o=ring[head];xSemaphoreGive(mutex);return ok;}
bool EventBuffer::ack(const char*id){if(xSemaphoreTake(mutex,pdMS_TO_TICKS(100))!=pdTRUE)return false;if(!count||strcmp(ring[head].event_id,id)!=0){xSemaphoreGive(mutex);return false;}head=(head+1)%BUFFER_MAX_EVENTS;count--;bool ok=persist();xSemaphoreGive(mutex);return ok;}
size_t EventBuffer::size(){return count;}
bool EventBuffer::persist(){File f=LittleFS.open(PATH,"w");if(!f)return false;f.write((uint8_t*)&head,sizeof(head));f.write((uint8_t*)&tail,sizeof(tail));f.write((uint8_t*)&count,sizeof(count));if(count)for(size_t i=0;i<BUFFER_MAX_EVENTS;i++)f.write((uint8_t*)&ring[i],sizeof(SecurityEvent));f.flush();f.close();return true;}
bool EventBuffer::load(){File f=LittleFS.open(PATH,"r");if(!f){head=tail=count=0;return true;}if(f.read((uint8_t*)&head,sizeof(head))!=sizeof(head)||f.read((uint8_t*)&tail,sizeof(tail))!=sizeof(tail)||f.read((uint8_t*)&count,sizeof(count))!=sizeof(count)){f.close();head=tail=count=0;return false;}if(count>BUFFER_MAX_EVENTS){f.close();head=tail=count=0;return false;}for(size_t i=0;i<BUFFER_MAX_EVENTS&&f.available();i++)f.read((uint8_t*)&ring[i],sizeof(SecurityEvent));f.close();return true;}
