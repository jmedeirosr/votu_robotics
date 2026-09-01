"""Paths that work both from source and from a Nuitka standalone bundle."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from version import APP_ID


def resource_path(relative_path: str) -> Path:
    """Return a bundled read-only resource path."""
    bundle_root = Path(__file__).resolve().parent.parent
    if "__compiled__" in globals():
        bundle_root = Path(sys.argv[0]).resolve().parent
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
