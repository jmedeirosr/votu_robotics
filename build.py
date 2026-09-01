#!/usr/bin/env python3
"""Compile Votu FieldOps with Nuitka and prepare its distributable payload."""

from __future__ import annotations

import argparse
import ast
import importlib.util
import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BUILD_DIR = ROOT / "build"
NUITKA_DIR = BUILD_DIR / "nuitka"
STAGE_DIR = BUILD_DIR / "stage"
ENTRYPOINT = ROOT / "src" / "interface.py"
VERSION_FILE = ROOT / "src" / "version.py"
REQUIRED_PATHS = (
    ENTRYPOINT,
    VERSION_FILE,
    ROOT / "assets",
    ROOT / "pyproject.toml",
    ROOT / "uv.lock",
)


class BuildError(RuntimeError):
    """A release prerequisite or build stage failed."""


@dataclass(frozen=True)
class BuildMetadata:
    version: str
    channel: str
    machine: str
    deb_arch: str


def read_version() -> str:
    tree = ast.parse(VERSION_FILE.read_text(encoding="utf-8"), filename=str(VERSION_FILE))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets):
                value = ast.literal_eval(node.value)
                if isinstance(value, str) and re.fullmatch(r"\d+\.\d+\.\d+", value):
                    return value
    raise BuildError("src/version.py deve definir __version__ no formato X.Y.Z.")


def normalized_arch(machine: str | None = None) -> str:
    machine = (machine or platform.machine()).lower()
    aliases = {
        "aarch64": "arm64",
        "arm64": "arm64",
        "armv7l": "armhf",
        "armv7": "armhf",
        "x86_64": "amd64",
        "amd64": "amd64",
    }
    try:
        return aliases[machine]
    except KeyError as exc:
        raise BuildError(f"Arquitetura não suportada para empacotamento Debian: {machine}") from exc


def metadata(channel: str) -> BuildMetadata:
    version = read_version()
    if channel == "nightly":
        build_id = os.environ.get("SOURCE_DATE_EPOCH", "local")
        version = f"{version}+nightly.{build_id}"
    return BuildMetadata(version, channel, platform.machine(), normalized_arch())


def run(command: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(command), flush=True)
    completed = subprocess.run(command, cwd=cwd, env=env, check=False)
    if completed.returncode:
        raise BuildError(f"Comando falhou com código {completed.returncode}: {' '.join(command)}")


def clean() -> None:
    for path in (BUILD_DIR, ROOT / "output"):
        if path.exists():
            shutil.rmtree(path)
    for cache in ROOT.rglob("__pycache__"):
        if ".venv" not in cache.parts:
            shutil.rmtree(cache)


def validate(*, require_tools: bool = True) -> BuildMetadata:
    missing = [str(path.relative_to(ROOT)) for path in REQUIRED_PATHS if not path.exists()]
    if missing:
        raise BuildError("Arquivos obrigatórios ausentes: " + ", ".join(missing))
    info = metadata("release")
    if info.deb_arch not in {"armhf", "arm64", "amd64"}:
        raise BuildError(f"Arquitetura não suportada: {info.deb_arch}")
    if sys.version_info >= (3, 14):
        raise BuildError(
            "Python 3.14 ainda é experimental no Nuitka usado pelo projeto. "
            "Crie o ambiente de build com Python 3.12 ou 3.13."
        )
    if require_tools and importlib.util.find_spec("nuitka") is None:
        raise BuildError(
            "Nuitka não está instalado neste ambiente. Execute "
            "`python -m pip install -e '.[build]'` ou `uv sync --extra build`."
        )
    if require_tools and shutil.which("gcc") is None:
        raise BuildError("Compilador C não encontrado. Instale o pacote build-essential.")
    if require_tools and shutil.which("patchelf") is None:
        raise BuildError(
            "patchelf não encontrado. Instale com `sudo apt install patchelf` "
            "antes de compilar em modo standalone."
        )
    return info


def run_tests() -> None:
    run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
    sources = sorted(str(path) for path in (ROOT / "src").glob("*.py"))
    run([sys.executable, "-m", "py_compile", *sources])


def nuitka_command(channel: str) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "nuitka",
        "--standalone",
        "--enable-plugin=pyqt6",
        "--assume-yes-for-downloads",
        f"--output-dir={NUITKA_DIR}",
        "--output-filename=votu-fieldops",
        f"--include-data-dir={ROOT / 'assets'}=assets",
        "--nofollow-import-to=tkinter,IPython",
    ]
    if channel == "debug":
        command.extend(("--debug", "--show-progress"))
    else:
        # Full LTO can spend tens of minutes swapping on Raspberry Pi. The
        # standalone output remains native and self-contained without it.
        command.extend(("--python-flag=no_docstrings", "--lto=no"))
    command.append(str(ENTRYPOINT))
    return command


def find_distribution() -> Path:
    candidates = sorted(NUITKA_DIR.glob("*.dist"))
    for candidate in candidates:
        if (candidate / "votu-fieldops").is_file():
            return candidate
    raise BuildError("O Nuitka terminou sem produzir a distribuição standalone esperada.")


def stage_distribution(distribution: Path) -> Path:
    if STAGE_DIR.exists():
        shutil.rmtree(STAGE_DIR)
    app_dir = STAGE_DIR / "app"
    shutil.copytree(distribution, app_dir, symlinks=True)
    executable = app_dir / "votu-fieldops"
    executable.chmod(executable.stat().st_mode | 0o111)
    return STAGE_DIR


def build(channel: str, *, do_clean: bool = True, tests: bool = True, dry_run: bool = False) -> Path:
    if do_clean:
        clean()
    validate(require_tools=not dry_run)
    if tests:
        run_tests()
    command = nuitka_command(channel)
    if dry_run:
        print("+", " ".join(command))
        return STAGE_DIR
    NUITKA_DIR.mkdir(parents=True, exist_ok=True)
    build_env = os.environ.copy()
    build_env["XDG_CACHE_HOME"] = str(BUILD_DIR / "cache")
    run(command, env=build_env)
    return stage_distribution(find_distribution())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--channel", choices=("debug", "release", "nightly"), default="release")
    parser.add_argument("--no-clean", action="store_true")
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        build(
            args.channel,
            do_clean=not args.no_clean,
            tests=not args.skip_tests,
            dry_run=args.dry_run,
        )
    except BuildError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
