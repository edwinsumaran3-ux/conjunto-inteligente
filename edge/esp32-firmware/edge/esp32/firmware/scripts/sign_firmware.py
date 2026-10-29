"""
Firma el binario compilado usando espsecure.py (incluido en ESP-IDF).
Requiere que la variable de entorno SECURE_BOOT_SIGNING_KEY apunte a la clave.
En CI, esta clave se inyecta desde el secret manager.
"""
import os
import subprocess
import sys
from pathlib import Path

Import("env")  # noqa: F821  — PlatformIO

def sign_firmware(source, target, env):
    build_dir = Path(env.subst("$BUILD_DIR"))
    sdkconfig_header = build_dir / "config" / "sdkconfig.h"
    if not sdkconfig_header.is_file():
        raise FileNotFoundError(f"Configuración ESP-IDF no encontrada: {sdkconfig_header}")

    sdkconfig = sdkconfig_header.read_text(encoding="utf-8")
    if "#define CONFIG_SECURE_BOOT_V2_ENABLED 1" not in sdkconfig:
        raise RuntimeError(
            "Release requiere Secure Boot V2. Verifica la revisión del ESP32; "
            "no se firmará con una configuración V1."
        )

    key = os.getenv("SECURE_BOOT_SIGNING_KEY")
    if not key:
        raise RuntimeError(
            "SECURE_BOOT_SIGNING_KEY es obligatorio para esp32dev-release."
        )

    key_file = Path(key)
    if not key_file.is_file():
        raise FileNotFoundError(f"Clave de firma no encontrada: {key_file}")

    firmware = Path(str(target[0]))
    if not firmware.is_file():
        raise FileNotFoundError(f"Firmware no encontrado para firma: {firmware}")

    esptool_package = env.PioPlatform().get_package_dir("tool-esptoolpy")
    espsecure = Path(esptool_package) / "espsecure.py"
    if not espsecure.is_file():
        raise FileNotFoundError(f"espsecure.py no encontrado: {espsecure}")

    signed = firmware.with_suffix(".signed.bin")
    cmd = [
        sys.executable, str(espsecure), "sign_data",
        "--version", "2",
        "--keyfile", str(key_file),
        "--output", str(signed),
        str(firmware),
    ]
    print(f"[sign] Firmando {firmware.name} -> {signed.name}")
    subprocess.run(cmd, check=True)
    if not signed.is_file():
        raise RuntimeError(f"espsecure.py no generó el archivo firmado: {signed}")

env.AddPostAction("$BUILD_DIR/${PROGNAME}.bin", sign_firmware)  # noqa: F821
