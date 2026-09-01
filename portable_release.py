#!/usr/bin/env python3
"""Build one self-contained Debian package for the current Bullseye ARM64 host."""

from __future__ import annotations

import hashlib
import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from build import BuildError, read_version


ROOT = Path(__file__).resolve().parent
PACKAGE_ROOT = ROOT / "build" / "bullseye-arm64-root"
OUTPUT = ROOT / "output"
INSTALL_ROOT = PACKAGE_ROOT / "opt" / "votu-fieldops"


def write(path: Path, content: str, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if mode is not None:
        path.chmod(mode)


def validate_host() -> None:
    os_release = Path("/etc/os-release").read_text(encoding="utf-8")
    if "VERSION_CODENAME=bullseye" not in os_release:
        raise BuildError("Este pacote deve ser gerado no Raspberry Pi OS Bullseye.")
    if platform.machine().lower() not in {"aarch64", "arm64"}:
        raise BuildError("Este builder simples gera somente Bullseye ARM64.")
    if sys.version_info[:2] != (3, 13):
        raise BuildError("Execute este builder pelo Python 3.13 da .venv.")


def copy_runtime() -> None:
    runtime = INSTALL_ROOT / "runtime"
    base_runtime = Path(sys.base_prefix)
    shutil.copytree(base_runtime, runtime, symlinks=False)

    source_packages = Path(sys.prefix) / "lib" / "python3.13" / "site-packages"
    target_packages = runtime / "lib" / "python3.13" / "site-packages"
    shutil.copytree(source_packages, target_packages, dirs_exist_ok=True, symlinks=False)

    # Ferramentas usadas somente para construir não fazem parte do aplicativo.
    for pattern in ("nuitka*", "Nuitka*", "ordered_set*", "ordered-set*"):
        for path in target_packages.glob(pattern):
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()


def copy_application() -> None:
    app = INSTALL_ROOT / "app"
    shutil.copytree(ROOT / "src", app / "src", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copytree(ROOT / "assets", app / "assets")
    shutil.copy2(ROOT / "assets" / "logo-long.png", INSTALL_ROOT / "votu-fieldops.png")


def create_debian_files(version: str) -> None:
    size_kib = sum(path.stat().st_size for path in INSTALL_ROOT.rglob("*") if path.is_file()) // 1024
    control = f"""Package: votu-fieldops
Version: {version}
Section: utils
Priority: optional
Architecture: arm64
Installed-Size: {size_kib}
Maintainer: VOTU Robotics <engineering@votu.local>
Depends: libc6, libgl1, libegl1, libxkbcommon-x11-0, libxcb-cursor0
Description: Votu FieldOps para Raspberry Pi OS Bullseye ARM64
 Aplicação desktop autocontida para operação e transmissão de mapas de campo.
"""
    write(PACKAGE_ROOT / "DEBIAN" / "control", control)
    write(
        PACKAGE_ROOT / "DEBIAN" / "postinst",
        """#!/bin/sh
set -e
chmod 0755 /opt/votu-fieldops/runtime/bin/python3 /usr/bin/votu-fieldops
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications || true
fi
exit 0
""",
        0o755,
    )
    write(
        PACKAGE_ROOT / "DEBIAN" / "postrm",
        """#!/bin/sh
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications || true
fi
exit 0
""",
        0o755,
    )
    launcher = """#!/bin/sh
export PYTHONNOUSERSITE=1
export QT_AUTO_SCREEN_SCALE_FACTOR=1
exec /opt/votu-fieldops/runtime/bin/python3 /opt/votu-fieldops/app/src/interface.py "$@"
"""
    write(PACKAGE_ROOT / "usr" / "bin" / "votu-fieldops", launcher, 0o755)
    desktop = """[Desktop Entry]
Type=Application
Name=Votu FieldOps
Comment=Operação e transmissão de mapas de campo
Exec=/usr/bin/votu-fieldops
Icon=votu-fieldops
Terminal=false
Categories=Utility;Science;
StartupNotify=true
"""
    write(PACKAGE_ROOT / "usr" / "share" / "applications" / "votu-fieldops.desktop", desktop)
    icon = PACKAGE_ROOT / "usr" / "share" / "icons" / "hicolor" / "256x256" / "apps"
    icon.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "assets" / "logo-long.png", icon / "votu-fieldops.png")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    try:
        validate_host()
        version = read_version()
        if PACKAGE_ROOT.exists():
            shutil.rmtree(PACKAGE_ROOT)
        OUTPUT.mkdir(parents=True, exist_ok=True)
        copy_runtime()
        copy_application()
        create_debian_files(version)
        artifact = OUTPUT / f"VotuFieldOps-{version}-bullseye-arm64.deb"
        subprocess.run(
            ["dpkg-deb", "--root-owner-group", "-Zgzip", "-z6", "--build", str(PACKAGE_ROOT), str(artifact)],
            check=True,
        )
        checksum = sha256(artifact)
        write(OUTPUT / "SHA256SUMS", f"{checksum}  {artifact.name}\n")
        metadata = {
            "application": "Votu FieldOps",
            "version": version,
            "platform": "Raspberry Pi OS Bullseye",
            "architecture": "arm64",
            "artifact": artifact.name,
            "sha256": checksum,
            "size": artifact.stat().st_size,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        write(OUTPUT / "release.json", json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")
        print(artifact)
        return 0
    except (BuildError, OSError, subprocess.CalledProcessError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
