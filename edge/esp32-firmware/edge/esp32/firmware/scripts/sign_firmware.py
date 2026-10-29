"""
Firma el binario compilado usando espsecure.py (incluido en ESP-IDF).
Requiere que la variable de entorno SECURE_BOOT_SIGNING_KEY apunte a la clave.
En CI, esta clave se inyecta desde el secret manager.
"""
import os
import subprocess
from pathlib import Path

Import("env")  # noqa: F821  — PlatformIO

def sign_firmware(source, target, env):
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

    signed = firmware.with_suffix(".signed.bin")
    cmd = [
        "espsecure.py", "sign_data",
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
