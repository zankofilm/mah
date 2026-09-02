import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class WindowsPackageTests(unittest.TestCase):
    def test_windows_release_assets_exist(self):
        for relative in (
            "assets/javanrood_app.ico",
            "windows_version_info.txt",
            "windows_release_check.py",
            "installer/JavanroodSetup.iss",
            "build_windows.bat",
            "build_setup_windows.bat",
        ):
            self.assertTrue((ROOT / relative).exists(), relative)

    def test_installer_preserves_user_data(self):
        source = (ROOT / "installer" / "JavanroodSetup.iss").read_text(encoding="utf-8")
        self.assertIn("PrivilegesRequired=lowest", source)
        self.assertIn("preinstall_backups", source)
        self.assertIn("BackupExistingData", source)
        self.assertIn("{localappdata}", source)

    def test_pyinstaller_metadata(self):
        source = (ROOT / "javanrood.spec").read_text(encoding="utf-8")
        self.assertIn("javanrood_app.ico", source)
        self.assertIn("windows_version_info.txt", source)
        self.assertIn('console=False', source)

    def test_macos_launchers_removed_from_windows_package(self):
        self.assertFalse((ROOT / "install_macos.command").exists())
        self.assertFalse((ROOT / "run_macos.command").exists())

    def test_windows_app_identity_hooked_before_qapplication(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("configure_windows_process()", source)
        self.assertLess(source.index("configure_windows_process()"), source.index("QApplication(sys.argv)"))


if __name__ == "__main__":
    unittest.main()
