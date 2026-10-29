import os
import runpy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "sign_firmware.py"


class PlatformIOEnvironment:
    def __init__(self, build_dir, esptool_package):
        self.build_dir = build_dir
        self.esptool_package = esptool_package

    def AddPostAction(self, *args):
        pass

    def subst(self, variable):
        if variable == "$BUILD_DIR":
            return str(self.build_dir)
        if variable == "$PYTHONEXE":
            return os.sys.executable
        raise AssertionError(f"Unexpected PlatformIO variable: {variable}")

    def PioPlatform(self):
        return self

    def get_package_dir(self, package):
        if package != "tool-esptoolpy":
            raise AssertionError(f"Unexpected PlatformIO package: {package}")
        return str(self.esptool_package)


class SignFirmwareTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.directory = Path(self.temp_dir.name)
        self.firmware = self.directory / "firmware.bin"
        self.firmware.write_bytes(b"firmware")
        self.key = self.directory / "signing.pem"
        self.key.write_text("test key", encoding="utf-8")
        self.build_dir = self.directory / "build"
        config_dir = self.build_dir / "config"
        config_dir.mkdir(parents=True)
        (config_dir / "sdkconfig.h").write_text(
            "#define CONFIG_SECURE_BOOT_V2_ENABLED 1\n",
            encoding="utf-8",
        )
        self.esptool_package = self.directory / "esptool"
        self.esptool_package.mkdir()
        (self.esptool_package / "espsecure.py").write_text("", encoding="utf-8")
        self.environment = PlatformIOEnvironment(
            self.build_dir,
            self.esptool_package,
        )
        scope = runpy.run_path(
            str(SCRIPT),
            init_globals={
                "Import": lambda name: None,
                "env": self.environment,
            },
        )
        self.sign_firmware = scope["sign_firmware"]

    def test_release_fails_when_signing_key_is_not_configured(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "obligatorio"):
                self.sign_firmware(None, [str(self.firmware)], self.environment)

    def test_release_fails_when_secure_boot_v2_is_not_selected(self):
        config = self.build_dir / "config" / "sdkconfig.h"
        config.write_text("#define CONFIG_SECURE_BOOT_V1_ENABLED 1\n", encoding="utf-8")
        with patch.dict(os.environ, {"SECURE_BOOT_SIGNING_KEY": str(self.key)}):
            with self.assertRaisesRegex(RuntimeError, "Secure Boot V2"):
                self.sign_firmware(None, [str(self.firmware)], self.environment)

    def test_release_fails_when_signing_key_file_is_missing(self):
        with patch.dict(os.environ, {"SECURE_BOOT_SIGNING_KEY": str(self.directory / "missing.pem")}):
            with self.assertRaises(FileNotFoundError):
                self.sign_firmware(None, [str(self.firmware)], self.environment)

    def test_release_requires_signed_output(self):
        with patch.dict(os.environ, {"SECURE_BOOT_SIGNING_KEY": str(self.key)}):
            with patch("subprocess.run") as run:
                with self.assertRaisesRegex(RuntimeError, "no generó"):
                    self.sign_firmware(None, [str(self.firmware)], self.environment)
            run.assert_called_once()

    def test_release_creates_signed_artifact(self):
        def fake_sign(command, check):
            self.assertTrue(check)
            self.assertEqual(command[0], os.sys.executable)
            self.assertEqual(command[1], str(self.esptool_package / "espsecure.py"))
            self.assertEqual(command[command.index("--keyfile") + 1], str(self.key))
            Path(command[command.index("--output") + 1]).write_bytes(b"signed")

        with patch.dict(os.environ, {"SECURE_BOOT_SIGNING_KEY": str(self.key)}):
            with patch("subprocess.run", side_effect=fake_sign) as run:
                self.sign_firmware(None, [str(self.firmware)], self.environment)
            run.assert_called_once()
        self.assertEqual(self.firmware.with_suffix(".signed.bin").read_bytes(), b"signed")


if __name__ == "__main__":
    unittest.main()
