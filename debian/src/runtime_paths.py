"""Paths that work both from source and from a PyInstaller bundle."""

from __future__ import annotations

import os
import sys
from pathlib import Path


APP_ID = "votu-fieldops"


def resource_path(relative_path: str) -> Path:
    """Return a bundled read-only resource path."""
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return bundle_root / relative_path


def user_data_path() -> Path:
    """Return the per-user writable data directory."""
    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    path = base / APP_ID
    path.mkdir(parents=True, exist_ok=True)
    return path


def user_state_path() -> Path:
    """Return the per-user writable state/log directory."""
    base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    path = base / APP_ID
    path.mkdir(parents=True, exist_ok=True)
    return path
