from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import build
import release


class BuildSystemTests(unittest.TestCase):
    def test_version_is_semantic(self):
        self.assertRegex(build.read_version(), r"^\d+\.\d+\.\d+$")

    def test_supported_debian_architectures(self):
        self.assertEqual(build.normalized_arch("aarch64"), "arm64")
        self.assertEqual(build.normalized_arch("armv7l"), "armhf")
        self.assertEqual(build.normalized_arch("x86_64"), "amd64")

    def test_unknown_architecture_is_rejected(self):
        with self.assertRaises(build.BuildError):
            build.normalized_arch("mips")

    def test_nuitka_command_is_standalone_and_uses_pyqt6(self):
        command = build.nuitka_command("release")
        self.assertIn("--standalone", command)
        self.assertIn("--enable-plugin=pyqt6", command)
        self.assertTrue(any(item.startswith("--include-data-dir=") for item in command))
        self.assertNotIn("--onefile", command)

    def test_installer_templates_have_required_placeholders(self):
        config = (build.ROOT / "installer/config/config.xml").read_text(encoding="utf-8")
        package = (build.ROOT / "installer/packages/package.xml").read_text(encoding="utf-8")
        self.assertIn("@VERSION@", config)
        self.assertIn("@VERSION@", package)
        self.assertIn("/opt/votu-fieldops", config)

    def test_release_metadata_contains_hashes(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            artifact = output / "sample.deb"
            artifact.write_bytes(b"votu")
            info = build.BuildMetadata("1.0.0", "release", "aarch64", "arm64")
            with mock.patch.object(release, "OUTPUT_DIR", output):
                release.create_metadata(info, [artifact])
            data = json.loads((output / "release.json").read_text(encoding="utf-8"))
            self.assertEqual(data["version"], "1.0.0")
            self.assertEqual(data["architecture"], "arm64")
            self.assertEqual(len(data["artifacts"][0]["sha256"]), 64)
            self.assertTrue((output / "SHA256SUMS").is_file())


if __name__ == "__main__":
    unittest.main()

