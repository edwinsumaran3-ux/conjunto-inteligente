#pragma once
#include <Arduino.h>
void watchdog_register_tasks(TaskHandle_t sensor, TaskHandle_t net, TaskHandle_t store);
void watchdog_init();
void watchdog_feed();
void watchdog_supervise();
void watchdog_kick_sensor();
void watchdog_kick_net();
void watchdog_kick_store();
