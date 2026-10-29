#include <Arduino.h>
#include <esp_task_wdt.h>
#include "config.h"
static uint32_t ls=0,ln=0,lst=0;void watchdog_register_tasks(TaskHandle_t,TaskHandle_t,TaskHandle_t){}void watchdog_init(){esp_task_wdt_config_t c={.timeout_ms=WDT_TIMEOUT_S*1000,.idle_core_mask=(1<<portNUM_PROCESSORS)-1,.trigger_panic=true};esp_task_wdt_init(&c);esp_task_wdt_add(NULL);ls=ln=lst=millis();}void watchdog_feed(){esp_task_wdt_reset();}void watchdog_supervise(){uint32_t n=millis();if(n-ls>15000||n-ln>30000||n-lst>60000)ESP.restart();}void watchdog_kick_sensor(){ls=millis();}void watchdog_kick_net(){ln=millis();}void watchdog_kick_store(){lst=millis();}
