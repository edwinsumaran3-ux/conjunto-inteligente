#pragma once

#define FW_VERSION_MAJOR 0
#define FW_VERSION_MINOR 1
#define FW_VERSION_PATCH 0

#define FW_VERSION_STRING "0.1.0"

// Compilar con `-DFW_BUILD_GIT_SHA=\"abc1234\"` en CI.
#ifndef FW_BUILD_GIT_SHA
#define FW_BUILD_GIT_SHA "dev"
#endif
