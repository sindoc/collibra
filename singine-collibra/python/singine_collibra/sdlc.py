"""On-the-fly SDLC process generation for data products.

Generates a .sdlc.yaml file tailored to the current environment, pipeline
mode, and data product kind.  The generated file drives pipeline dispatch.

Pipeline modes:
    sequential  — steps run in order; halt on first failure
    competing   — steps run in order; halt on first success (race)
    fan-out     — all steps run regardless; report aggregate result

Data product kinds:
    DataProduct, AnalyticsProduct, StreamProduct, ReportProduct, APIProduct

Environments:
    dev     → dry_run=True,  notify=False, auto_push=False
    staging → dry_run=False, notify=True,  auto_push=False
    prod    → dry_run=False, notify=True,  auto_push=True

Environment variables:
    SINGINE_ENV      dev | staging | prod
    SINGINE_PROJECT  Default project label
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Optional


# ── Known kinds / modes / envs ────────────────────────────────────────────────

KNOWN_KINDS = ["DataProduct", "AnalyticsProduct", "StreamProduct", "ReportProduct", "APIProduct"]
KNOWN_MODES = ["sequential", "competing", "fan-out"]
KNOWN_ENVS = ["dev", "staging", "prod"]

# ── Pipeline step templates per data-product kind ─────────────────────────────

_PIPELINE_TEMPLATES: dict = {
    "DataProduct": [
        {"name": "ingest",    "cmd": "singine collibra io edge connection probe-postgres"},
        {"name": "classify",  "cmd": "singine collibra contract step 3"},
        {"name": "relate",    "cmd": "singine collibra contract step 4"},
        {"name": "constrain", "cmd": "singine collibra contract step 5"},
        {"name": "verbalize", "cmd": "singine collibra contract step 6"},
        {"name": "align",     "cmd": "singine collibra contract step 7"},
        {"name": "publish",   "cmd": "singine collibra id gen --project DataProduct"},
    ],
    "AnalyticsProduct": [
        {"name": "extract",  "cmd": "singine collibra io metamodel status"},
        {"name": "cosine",   "cmd": "singine collibra quantum cosine"},
        {"name": "catalog",  "cmd": "singine collibra quantum load-shiva"},
        {"name": "publish",  "cmd": "singine collibra id gen --project AnalyticsProduct"},
    ],
    "StreamProduct": [
        {"name": "probe",      "cmd": "singine collibra query grpc-bindings"},
        {"name": "categorise", "cmd": "singine collibra query grpc-http-call Categorise --body {}"},
        {"name": "publish",    "cmd": "singine collibra id gen --project StreamProduct"},
    ],
    "ReportProduct": [
        {"name": "query",   "cmd": "singine collibra query code-lookup report"},
        {"name": "bubble",  "cmd": "singine collibra quantum bubble-leader"},
        {"name": "publish", "cmd": "singine collibra id gen --project ReportProduct"},
    ],
    "APIProduct": [
        {"name": "register", "cmd": "singine collibra io create community"},
        {"name": "align",    "cmd": "singine collibra contract advance"},
        {"name": "publish",  "cmd": "singine collibra id gen --project APIProduct"},
    ],
}

_ENV_CONFIG: dict = {
    "dev":     {"notify": False, "dry_run": True,  "auto_push": False},
    "staging": {"notify": True,  "dry_run": False, "auto_push": False},
    "prod":    {"notify": True,  "dry_run": False, "auto_push": True},
}


# ── YAML serialiser (stdlib-only) ─────────────────────────────────────────────

def _yaml_scalar(v: object) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str) and any(c in v for c in ': #{}[],"'):
        escaped = v.replace('"', '\\"')
        return f'"{escaped}"'
    return str(v)


def _to_yaml(obj: object, indent: int = 0) -> str:
    pad = "  " * indent
    if isinstance(obj, dict):
        lines = []
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                lines.append(f"{pad}{k}:")
                lines.append(_to_yaml(v, indent + 1))
            else:
                lines.append(f"{pad}{k}: {_yaml_scalar(v)}")
        return "\n".join(lines)
    if isinstance(obj, list):
        lines = []
        for item in obj:
            if isinstance(item, dict):
                first = True
                for k, v in item.items():
                    prefix = f"{pad}- " if first else f"{pad}  "
                    first = False
                    if isinstance(v, (dict, list)):
                        lines.append(f"{prefix}{k}:")
                        lines.append(_to_yaml(v, indent + 2))
                    else:
                        lines.append(f"{prefix}{k}: {_yaml_scalar(v)}")
            else:
                lines.append(f"{pad}- {_yaml_scalar(item)}")
        return "\n".join(lines)
    return f"{pad}{_yaml_scalar(obj)}"


# ── Generate ──────────────────────────────────────────────────────────────────

def generate(
    env: str = "",
    mode: str = "sequential",
    kind: str = "DataProduct",
    out: Optional[Path] = None,
    project: str = "",
) -> dict:
    """Generate a .sdlc.yaml for a data product pipeline.

    Args:
        env:     SDLC environment (dev/staging/prod).  Falls back to SINGINE_ENV.
        mode:    Pipeline dispatch mode (sequential/competing/fan-out).
        kind:    Data product kind.
        out:     Write YAML to this path if given; otherwise return inline.
        project: Project label.  Falls back to SINGINE_PROJECT or *kind*.
    """
    env = (env or os.environ.get("SINGINE_ENV", "dev")).lower()
    if env not in KNOWN_ENVS:
        env = "dev"
    project = project or os.environ.get("SINGINE_PROJECT", kind)
    steps = _PIPELINE_TEMPLATES.get(kind, _PIPELINE_TEMPLATES["DataProduct"])
    env_cfg = _ENV_CONFIG.get(env, _ENV_CONFIG["dev"])

    doc = {
        "sdlc": {
            "version": "1.0",
            "project": project,
            "kind": kind,
            "env": env,
            "mode": mode,
            "generated_by": "singine collibra sdlc generate",
            "env_config": {
                "dry_run":   env_cfg["dry_run"],
                "auto_push": env_cfg["auto_push"],
                "notify":    env_cfg["notify"],
            },
            "pipeline": {
                "mode": mode,
                "steps": steps,
            },
            "notify": {
                "on_success": env_cfg["notify"],
                "on_failure": True,
                "channel": "smtp",
                "transport": "auto",
            },
            "repo": {
                "daily_commit": True,
                "auto_push": env_cfg["auto_push"],
            },
        }
    }

    yaml_str = _to_yaml(doc)

    if out:
        out = Path(out)
        out.write_text(yaml_str + "\n")
        return {"ok": True, "path": str(out), "yaml": yaml_str}
    return {"ok": True, "yaml": yaml_str}


# ── Dispatch ──────────────────────────────────────────────────────────────────

def _exec_step(cmd: str, dry_run: bool) -> dict:
    if dry_run:
        return {"ok": True, "cmd": cmd, "dry_run": True}
    try:
        proc = subprocess.run(
            cmd.split(), capture_output=True, text=True, timeout=120
        )
        return {
            "ok": proc.returncode == 0,
            "cmd": cmd,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "rc": proc.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "cmd": cmd, "error": "timeout"}
    except FileNotFoundError as exc:
        return {"ok": False, "cmd": cmd, "error": str(exc)}


def dispatch(
    sdlc_path: Path,
    step_name: str = "",
    dry_run: bool = False,
) -> dict:
    """Execute pipeline steps defined in *sdlc_path*.

    Args:
        sdlc_path:  Path to the .sdlc.yaml file.
        step_name:  Run only this named step (all steps if empty).
        dry_run:    Report what would run without executing.
    """
    sdlc_path = Path(sdlc_path)
    if not sdlc_path.exists():
        return {"ok": False, "error": f"SDLC file not found: {sdlc_path}"}

    raw = sdlc_path.read_text()

    # Extract mode
    mode_m = re.search(r"^\s*mode:\s*(\S+)", raw, re.MULTILINE)
    mode = mode_m.group(1).strip('"') if mode_m else "sequential"

    # Extract dry_run override from file (env_config section)
    dr_m = re.search(r"dry_run:\s*(true|false)", raw)
    if dr_m and not dry_run:
        dry_run = dr_m.group(1) == "true"

    # Extract steps: each "- name: X\n  cmd: Y" block
    step_blocks = re.findall(
        r"-\s+name:\s+(\S+)\n\s+cmd:\s+(.+)", raw
    )

    if not step_blocks:
        return {"ok": False, "error": "No steps found in SDLC file"}

    if step_name:
        step_blocks = [(n, c) for n, c in step_blocks if n == step_name]
        if not step_blocks:
            return {"ok": False, "error": f"Step '{step_name}' not found"}

    results = []
    for name, cmd in step_blocks:
        cmd = cmd.strip().strip('"')
        r = _exec_step(cmd, dry_run)
        r["name"] = name
        results.append(r)

        if mode == "competing" and r["ok"]:
            break  # first success wins
        if mode == "sequential" and not r["ok"]:
            break  # halt on failure

    overall_ok = (
        any(r["ok"] for r in results) if mode == "competing"
        else all(r["ok"] for r in results)
    )

    return {
        "ok": overall_ok,
        "mode": mode,
        "dry_run": dry_run,
        "steps_run": len(results),
        "results": results,
    }
