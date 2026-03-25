"""Subprocess wrappers for the id-gen HTTP server (server/server.sh)."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

from .paths import IDGEN_DIR


def _server_sh(idgen_dir: Optional[Path] = None) -> Path:
    return (idgen_dir or IDGEN_DIR) / "server" / "server.sh"


def start(port: int = 7331, mode: str = "net", idgen_dir: Optional[Path] = None) -> int:
    sh = _server_sh(idgen_dir)
    r = subprocess.run(["bash", str(sh), "start", "--port", str(port), "--mode", mode], text=True)
    return r.returncode


def stop(idgen_dir: Optional[Path] = None) -> int:
    sh = _server_sh(idgen_dir)
    r = subprocess.run(["bash", str(sh), "stop"], text=True)
    return r.returncode


def status(idgen_dir: Optional[Path] = None) -> int:
    sh = _server_sh(idgen_dir)
    r = subprocess.run(["bash", str(sh), "status"], text=True)
    return r.returncode


def dmz(port: int = 7331, idgen_dir: Optional[Path] = None) -> int:
    sh = _server_sh(idgen_dir)
    r = subprocess.run(["bash", str(sh), "start", "--port", str(port), "--mode", "dmz"], text=True)
    return r.returncode
