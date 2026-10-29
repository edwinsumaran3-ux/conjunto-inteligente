import os
import runpy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "sign_firmware.py"


class PlatformIOEnvironment:
    def AddPostAction(self, *args):
        pass


class SignFirmwareTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.directory = Path(self.temp_dir.name)
        self.firmware = self.directory / "firmware.bin"
        self.firmware.write_bytes(b"firmware")
        self.key = self.directory / "signing.pem"
        self.key.write_text("test key", encoding="utf-8")
        scope = runpy.run_path(
            str(SCRIPT),
            init_globals={
                "Import": lambda name: None,
                "env": PlatformIOEnvironment(),
            },
        )
        self.sign_firmware = scope["sign_firmware"]

    def test_release_fails_when_signing_key_is_not_configured(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "obligatorio"):
                self.sign_firmware(None, [str(self.firmware)], None)

    def test_release_fails_when_signing_key_file_is_missing(self):
        with patch.dict(os.environ, {"SECURE_BOOT_SIGNING_KEY": str(self.directory / "missing.pem")}):
            with self.assertRaises(FileNotFoundError):
                self.sign_firmware(None, [str(self.firmware)], None)

    def test_release_requires_signed_output(self):
        with patch.dict(os.environ, {"SECURE_BOOT_SIGNING_KEY": str(self.key)}):
            with patch("subprocess.run") as run:
                with self.assertRaisesRegex(RuntimeError, "no generó"):
                    self.sign_firmware(None, [str(self.firmware)], None)
            run.assert_called_once()

    def test_release_creates_signed_artifact(self):
        def fake_sign(command, check):
            self.assertTrue(check)
            self.assertEqual(command[command.index("--keyfile") + 1], str(self.key))
            Path(command[command.index("--output") + 1]).write_bytes(b"signed")

        with patch.dict(os.environ, {"SECURE_BOOT_SIGNING_KEY": str(self.key)}):
            with patch("subprocess.run", side_effect=fake_sign) as run:
                self.sign_firmware(None, [str(self.firmware)], None)
            run.assert_called_once()
        self.assertEqual(self.firmware.with_suffix(".signed.bin").read_bytes(), b"signed")


if __name__ == "__main__":
    unittest.main()
