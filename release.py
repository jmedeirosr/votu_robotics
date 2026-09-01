#!/usr/bin/env python3
"""Create the Debian package, QtIFW wizard and release metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import build as builder


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"
RELEASE_URL = os.environ.get("RELEASE_BASE_URL", "")
DESKTOP_ENTRY = """[Desktop Entry]
Type=Application
Name=Votu FieldOps
Comment=Operação e transmissão de mapas de campo
Exec=/usr/bin/votu-fieldops
Icon=votu-fieldops
Terminal=false
Categories=Utility;Science;
StartupNotify=true
"""


def write(path: Path, content: str, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if mode is not None:
        path.chmod(mode)


def copy_payload(destination: Path) -> None:
    source = builder.STAGE_DIR / "app"
    if not source.is_dir():
        raise builder.BuildError("Payload compilado ausente. Execute a etapa de build primeiro.")
    shutil.copytree(source, destination / "app", symlinks=True)
    shutil.copy2(ROOT / "assets" / "logo-long.png", destination / "votu-fieldops.png")
    uninstall = """#!/bin/sh
set -eu
if [ -x /opt/votu-fieldops/maintenancetool ]; then
    exec /opt/votu-fieldops/maintenancetool
fi
if command -v pkexec >/dev/null 2>&1; then
    exec pkexec apt-get remove votu-fieldops
fi
echo "Execute: sudo apt-get remove votu-fieldops" >&2
exit 1
"""
    write(destination / "uninstall" / "uninstall.sh", uninstall, 0o755)


def build_debian(info: builder.BuildMetadata) -> Path:
    root = builder.BUILD_DIR / "debian-root"
    if root.exists():
        shutil.rmtree(root)
    install_root = root / "opt" / "votu-fieldops"
    copy_payload(install_root)
    installed_size = sum(path.stat().st_size for path in install_root.rglob("*") if path.is_file()) // 1024
    control = f"""Package: votu-fieldops
Version: {info.version}
Section: utils
Priority: optional
Architecture: {info.deb_arch}
Installed-Size: {installed_size}
Maintainer: VOTU Robotics <engineering@votu.local>
Depends: libc6, libgl1, libegl1, libxkbcommon-x11-0, libxcb-cursor0
Recommends: desktop-file-utils
Description: Votu FieldOps para operação de mapas de campo
 Aplicação desktop para geração, visualização e transmissão serial de mapas.
"""
    write(root / "DEBIAN" / "control", control)
    postinst = """#!/bin/sh
set -e
chmod 0755 /opt/votu-fieldops/app/votu-fieldops
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications || true
fi
exit 0
"""
    postrm = """#!/bin/sh
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications || true
fi
exit 0
"""
    write(root / "DEBIAN" / "postinst", postinst, 0o755)
    write(root / "DEBIAN" / "postrm", postrm, 0o755)
    launcher = "#!/bin/sh\nexec /opt/votu-fieldops/app/votu-fieldops \"$@\"\n"
    write(root / "usr" / "bin" / "votu-fieldops", launcher, 0o755)
    write(root / "usr" / "share" / "applications" / "votu-fieldops.desktop", DESKTOP_ENTRY, 0o644)
    icon_dir = root / "usr" / "share" / "icons" / "hicolor" / "256x256" / "apps"
    icon_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "assets" / "logo-long.png", icon_dir / "votu-fieldops.png")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    artifact = OUTPUT_DIR / f"VotuFieldOps-{info.version}-{info.deb_arch}.deb"
    builder.run(["dpkg-deb", "--root-owner-group", "--build", str(root), str(artifact)])
    return artifact


def render_template(source: Path, destination: Path, replacements: dict[str, str]) -> None:
    content = source.read_text(encoding="utf-8")
    for key, value in replacements.items():
        content = content.replace(f"@{key}@", value)
    write(destination, content)


def prepare_qtifw_repository(info: builder.BuildMetadata) -> tuple[Path, Path]:
    work = builder.BUILD_DIR / "qtifw"
    if work.exists():
        shutil.rmtree(work)
    config_dir = work / "config"
    package_dir = work / "packages" / "com.votu.fieldops"
    data_dir = package_dir / "data"
    meta_dir = package_dir / "meta"
    replacements = {"VERSION": info.version, "ROOT": str(ROOT)}
    render_template(ROOT / "installer" / "config" / "config.xml", config_dir / "config.xml", replacements)
    shutil.copy2(ROOT / "installer" / "config" / "style.qss", config_dir / "style.qss")
    shutil.copy2(ROOT / "assets" / "logo-long.png", config_dir / "logo.png")
    shutil.copy2(ROOT / "assets" / "logo-icon.ico", config_dir / "installer.ico")
    render_template(ROOT / "installer" / "packages" / "package.xml", meta_dir / "package.xml", replacements)
    shutil.copy2(ROOT / "installer" / "packages" / "installscript.qs", meta_dir / "installscript.qs")
    shutil.copy2(ROOT / "installer" / "LICENSE.txt", meta_dir / "LICENSE.txt")
    copy_payload(data_dir)
    return config_dir / "config.xml", work / "packages"


def build_installer(info: builder.BuildMetadata) -> Path:
    binarycreator = shutil.which("binarycreator")
    if binarycreator is None:
        raise builder.BuildError(
            "Qt Installer Framework não encontrado (`binarycreator`). "
            "Instale o QtIFW e adicione seu diretório bin ao PATH."
        )
    config, packages = prepare_qtifw_repository(info)
    artifact = OUTPUT_DIR / f"VotuFieldOps-{info.version}-{info.deb_arch}.run"
    builder.run([binarycreator, "-c", str(config), "-p", str(packages), str(artifact)])
    artifact.chmod(0o755)
    return artifact


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_metadata(info: builder.BuildMetadata, artifacts: list[Path]) -> None:
    records = [
        {
            "name": artifact.name,
            "sha256": sha256(artifact),
            "size": artifact.stat().st_size,
            "url": f"{RELEASE_URL.rstrip('/')}/{artifact.name}" if RELEASE_URL else artifact.name,
        }
        for artifact in artifacts
    ]
    primary = records[0] if records else {"sha256": "", "url": ""}
    release = {
        "schema": 1,
        "application": "Votu FieldOps",
        "version": info.version,
        "channel": info.channel,
        "architecture": info.deb_arch,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sha256": primary["sha256"],
        "url": primary["url"],
        "notes": f"Consulte CHANGELOG.md para as alterações da versão {info.version}.",
        "artifacts": records,
    }
    write(OUTPUT_DIR / "release.json", json.dumps(release, indent=2, ensure_ascii=False) + "\n")
    manifest = {
        "schema": 1,
        "build": {
            "version": info.version,
            "channel": info.channel,
            "machine": info.machine,
            "debian_architecture": info.deb_arch,
            "python": sys.version.split()[0],
        },
        "artifacts": records,
    }
    write(OUTPUT_DIR / "manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    checksum_lines = [f"{record['sha256']}  {record['name']}" for record in records]
    write(OUTPUT_DIR / "SHA256SUMS", "\n".join(checksum_lines) + "\n")
    changelog = ROOT / "CHANGELOG.md"
    if changelog.exists():
        shutil.copy2(changelog, OUTPUT_DIR / "CHANGELOG.md")


def release(
    channel: str,
    *,
    skip_build: bool = False,
    skip_tests: bool = False,
    skip_installer: bool = False,
    dry_run: bool = False,
) -> list[Path]:
    info = builder.metadata(channel)
    if not skip_build:
        builder.build(channel, tests=not skip_tests, dry_run=dry_run)
    else:
        builder.validate(require_tools=False)
    if dry_run:
        print(f"Release validada: {info.version} ({info.deb_arch}, {channel})")
        return []
    if shutil.which("dpkg-deb") is None:
        raise builder.BuildError("dpkg-deb não encontrado. Instale dpkg-dev.")
    artifacts = [build_debian(info)]
    if not skip_installer:
        artifacts.append(build_installer(info))
    create_metadata(info, artifacts)
    return artifacts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--channel", choices=("debug", "release", "nightly"), default="release")
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--skip-installer", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        artifacts = release(
            args.channel,
            skip_build=args.skip_build,
            skip_tests=args.skip_tests,
            skip_installer=args.skip_installer,
            dry_run=args.dry_run,
        )
    except builder.BuildError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1
    if artifacts:
        print("Release concluída:")
        for artifact in artifacts:
            print(f"  {artifact}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
