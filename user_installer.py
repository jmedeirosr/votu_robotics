#!/usr/bin/env python3
"""Create a passwordless per-user installer for Bullseye ARM64."""

from __future__ import annotations

import hashlib
import json
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw

from build import BuildError, read_version
from portable_release import INSTALL_ROOT, OUTPUT, validate_host, write


ROOT = Path(__file__).resolve().parent


HEADER = r'''#!/bin/sh
set -eu
case "$(uname -m)" in
    aarch64|arm64) ;;
    *) echo "Este instalador funciona somente em Raspberry Pi ARM64." >&2; exit 1 ;;
esac

if ! grep -q 'VERSION_CODENAME=bullseye' /etc/os-release 2>/dev/null; then
    echo "Este instalador foi criado somente para Raspberry Pi OS Bullseye." >&2
    exit 1
fi

TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT INT TERM
ARCHIVE_LINE=$(awk '/^__VOTU_ARCHIVE_BELOW__$/ { print NR + 1; exit }' "$0")
tail -n "+$ARCHIVE_LINE" "$0" | tar -xzf - -C "$TEMP_DIR"
export PYTHONNOUSERSITE=1
"$TEMP_DIR/runtime/bin/python3" "$TEMP_DIR/installer_wizard.py" --install --payload "$TEMP_DIR"
exit $?
__VOTU_ARCHIVE_BELOW__
'''

UNINSTALLER = r'''#!/bin/sh
set -eu
APP_ID="votu-fieldops"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
LOCATION_FILE="$DATA_HOME/$APP_ID.location"
if [ -f "$LOCATION_FILE" ]; then
    TARGET=$(cat "$LOCATION_FILE")
else
    TARGET="$DATA_HOME/$APP_ID"
fi
if [ ! -x "$TARGET/runtime/bin/python3" ] || [ ! -f "$TARGET/installer_wizard.py" ]; then
    echo "O Votu FieldOps não está instalado para este usuário." >&2
    exit 1
fi
export PYTHONNOUSERSITE=1
exec "$TARGET/runtime/bin/python3" "$TARGET/installer_wizard.py" --uninstall --target "$TARGET"
'''


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_release_icons() -> dict[str, Path]:
    icon_dir = ROOT / "build" / "release-icons"
    icon_dir.mkdir(parents=True, exist_ok=True)

    def save_icon(name: str, draw_symbol) -> Path:
        image = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((18, 18, 238, 238), radius=52, fill="#f3f7f4", outline="#176b4d", width=8)
        draw_symbol(draw)
        png = icon_dir / f"{name}.png"
        ico = icon_dir / f"{name}.ico"
        image.save(png)
        image.save(ico, sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
        return ico

    def installer_symbol(draw: ImageDraw.ImageDraw):
        draw.rounded_rectangle((55, 157, 201, 199), radius=12, fill="#176b4d")
        draw.rectangle((117, 55, 139, 141), fill="#176b4d")
        draw.polygon(((82, 112), (128, 156), (174, 112)), fill="#f6b73c", outline="#176b4d")

    def uninstaller_symbol(draw: ImageDraw.ImageDraw):
        draw.rounded_rectangle((78, 82, 178, 202), radius=14, fill="#b73535")
        draw.rounded_rectangle((66, 61, 190, 82), radius=9, fill="#7f1d1d")
        draw.rectangle((105, 47, 151, 62), fill="#7f1d1d")
        draw.line((104, 116, 152, 169), fill="#ffffff", width=14)
        draw.line((152, 116, 104, 169), fill="#ffffff", width=14)

    installer = save_icon("installer-icon", installer_symbol)
    uninstaller = save_icon("uninstaller-icon", uninstaller_symbol)

    logo = Image.open(ROOT / "assets" / "logo-long.png").convert("RGBA")
    logo_ico = icon_dir / "logo-long.ico"
    canvases = []
    for size in (256, 128, 64, 48, 32, 16):
        canvas = Image.new("RGBA", (size, size), (255, 255, 255, 0))
        fitted = logo.copy()
        fitted.thumbnail((size - max(2, size // 12), size - max(2, size // 12)), Image.Resampling.LANCZOS)
        canvas.alpha_composite(fitted, ((size - fitted.width) // 2, (size - fitted.height) // 2))
        canvases.append(canvas)
    canvases[0].save(logo_ico, append_images=canvases[1:], sizes=[image.size for image in canvases])
    logo_menu = icon_dir / "logo-long-menu.png"
    with Image.open(logo_ico) as ico_image:
        ico_image.seek(0)
        ico_image.convert("RGBA").resize((256, 256), Image.Resampling.LANCZOS).save(logo_menu)
    return {
        "installer": installer,
        "uninstaller": uninstaller,
        "logo": logo_ico,
        "logo_menu": logo_menu,
    }


def write_desktop_shortcut(path: Path, name: str, executable: Path, icon: Path) -> None:
    content = (
        "[Desktop Entry]\nType=Application\n"
        f"Name={name}\nExec={executable}\nIcon={icon}\n"
        "Terminal=false\nCategories=Utility;\nStartupNotify=true\n"
    )
    write(path, content, 0o755)


def main() -> int:
    try:
        validate_host()
        if not (INSTALL_ROOT / "runtime" / "bin" / "python3").is_file():
            raise BuildError("Execute `make bullseye` antes de gerar o instalador do usuário.")

        version = read_version()
        icons = create_release_icons()
        OUTPUT.mkdir(parents=True, exist_ok=True)
        artifact = OUTPUT / f"VotuFieldOps-Installer-{version}-bullseye-arm64.sh"
        with artifact.open("wb") as destination:
            destination.write(HEADER.encode("utf-8"))
            with tarfile.open(fileobj=destination, mode="w|gz", compresslevel=6) as archive:
                for child in sorted(INSTALL_ROOT.iterdir()):
                    archive.add(child, arcname=child.name, recursive=True)
                archive.add(ROOT / "installer" / "user_wizard.py", arcname="installer_wizard.py")
                archive.add(ROOT / "installer" / "LICENSE.txt", arcname="LICENSE.txt")
                archive.add(ROOT / "assets" / "logo-long.png", arcname="logo-long.png")
                archive.add(icons["logo"], arcname="logo-long.ico")
                archive.add(icons["logo_menu"], arcname="logo-long-menu.png")
                archive.add(icons["installer"], arcname="installer-icon.ico")
                archive.add(icons["uninstaller"], arcname="uninstaller-icon.ico")
        artifact.chmod(0o755)

        uninstaller = OUTPUT / f"VotuFieldOps-Uninstaller-{version}-bullseye-arm64.sh"
        write(uninstaller, UNINSTALLER, 0o755)
        installer_shortcut = OUTPUT / "VotuFieldOps Installer.desktop"
        uninstaller_shortcut = OUTPUT / "VotuFieldOps Uninstaller.desktop"
        write_desktop_shortcut(installer_shortcut, "Instalar Votu FieldOps", artifact, icons["installer"])
        write_desktop_shortcut(uninstaller_shortcut, "Desinstalar Votu FieldOps", uninstaller, icons["uninstaller"])

        checksum = sha256(artifact)
        uninstall_checksum = sha256(uninstaller)
        write(
            OUTPUT / "SHA256SUMS.user-installer",
            f"{checksum}  {artifact.name}\n{uninstall_checksum}  {uninstaller.name}\n",
        )
        metadata = {
            "application": "Votu FieldOps",
            "version": version,
            "platform": "Raspberry Pi OS Bullseye",
            "architecture": "arm64",
            "installation": "per-user, passwordless",
            "artifact": artifact.name,
            "sha256": checksum,
            "uninstaller": uninstaller.name,
            "uninstaller_sha256": uninstall_checksum,
            "size": artifact.stat().st_size,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        write(OUTPUT / "release-user.json", json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")
        print(artifact)
        return 0
    except (BuildError, OSError, tarfile.TarError) as exc:
        print(f"ERRO: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
