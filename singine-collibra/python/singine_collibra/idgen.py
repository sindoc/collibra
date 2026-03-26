"""Subprocess wrappers for the id-gen Makefile targets.

Each public function corresponds to a ``make`` target in id-gen/Makefile.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

from .paths import IDGEN_DIR


def _make(target: str, idgen_dir: Optional[Path] = None, **make_vars: str) -> subprocess.CompletedProcess:
    """Run a make target inside id-gen/ (or a custom dir)."""
    d = idgen_dir or IDGEN_DIR
    cmd = ["make", "-C", str(d), target]
    for k, v in make_vars.items():
        cmd.append(f"{k}={v}")
    return subprocess.run(cmd, text=True)


def gen(ns: str = "c", project: str = "DefaultProject", kind: str = "contract") -> int:
    r = _make("gen", NS=ns, PROJECT=project)
    return r.returncode


def gen_topic(project: str = "DefaultProject") -> int:
    r = _make("gen-topic", PROJECT=project)
    return r.returncode


def import_id(uuid: str, kind: str, project: str = "DefaultProject") -> int:
    r = _make("import-collibra", UUID=uuid, KIND=kind, PROJECT=project)
    return r.returncode


def list_ids(ns: str = "") -> int:
    target = f"list-{ns}" if ns else "tags"
    r = _make(target)
    return r.returncode


def tags() -> int:
    return _make("tags").returncode


def push_tags() -> int:
    return _make("push-tags").returncode


def detect_conflicts() -> int:
    return _make("detect-conflicts").returncode


def resolve_conflicts(strategy: str = "COLLIBRA_WINS") -> int:
    return _make("resolve-conflicts", STRATEGY=strategy).returncode
