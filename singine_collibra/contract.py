"""Subprocess wrappers for contract lifecycle make targets."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

from .paths import IDGEN_DIR


def _make(target: str, idgen_dir: Optional[Path] = None, **make_vars: str) -> subprocess.CompletedProcess:
    d = idgen_dir or IDGEN_DIR
    cmd = ["make", "-C", str(d), target]
    for k, v in make_vars.items():
        cmd.append(f"{k}={v}")
    return subprocess.run(cmd, text=True)


def new(project: str = "DefaultProject", kind: str = "DataContract") -> int:
    return _make("contract", PROJECT=project, KIND=kind).returncode


def list_contracts() -> int:
    return _make("contract-list").returncode


def set_status(contract_id: str, status: str) -> int:
    return _make("contract-status", CONTRACT_ID=contract_id, STATUS=status).returncode


def pipeline(contract_id: str = "") -> int:
    kwargs = {"CONTRACT_ID": contract_id} if contract_id else {}
    return _make("pipeline", **kwargs).returncode


def step(n: int, contract_id: str = "") -> int:
    kwargs = {"CONTRACT_ID": contract_id} if contract_id else {}
    return _make(f"step{n}", **kwargs).returncode


def advance(contract_id: str = "") -> int:
    kwargs = {"CONTRACT_ID": contract_id} if contract_id else {}
    return _make("advance", **kwargs).returncode


def progress(contract_id: str = "", all_contracts: bool = False, as_json: bool = False) -> int:
    if all_contracts:
        return _make("progress-all").returncode
    if as_json and contract_id:
        return _make("progress-json", CONTRACT_ID=contract_id).returncode
    kwargs = {"CONTRACT_ID": contract_id} if contract_id else {}
    return _make("progress", **kwargs).returncode
