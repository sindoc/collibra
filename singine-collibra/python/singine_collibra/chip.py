"""Structured Collibra CHIP orchestration for ``singine collibra io``.

This module wraps the Go-based Collibra MCP server (``chip``) using typed
request/response envelopes and an Activity-shaped execution report. The goal is
to keep Collibra-specific MCP logic in the Collibra repo while letting Singine
provide the CLI/runtime shell.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, IO, List, Optional

try:
    from singine.lens.activity import Activity, ActivityType, Agent, AgentRole, AgentType
except Exception:  # pragma: no cover - Singine is expected at runtime, but keep import soft.
    Activity = None  # type: ignore[assignment]
    ActivityType = None  # type: ignore[assignment]
    Agent = None  # type: ignore[assignment]
    AgentRole = None  # type: ignore[assignment]
    AgentType = None  # type: ignore[assignment]


_DEFAULT_CHIP_BINARY = Path("~/ws/github/collibra/chip/.build/chip").expanduser()
_DEFAULT_CHIP_CONFIG = Path("~/.config/collibra/mcp.yaml").expanduser()
_DEFAULT_CODEX_CONFIG = Path("~/.codex/config.toml").expanduser()
_DEFAULT_CLAUDE_CONFIG = Path("~/Library/Application Support/Claude/claude_desktop_config.json").expanduser()
_DEFAULT_PROTOCOL_VERSION = "2025-03-26"


@dataclass
class ChipPaths:
    binary: Path = _DEFAULT_CHIP_BINARY
    mcp_config: Path = _DEFAULT_CHIP_CONFIG
    codex_config: Path = _DEFAULT_CODEX_CONFIG
    claude_config: Path = _DEFAULT_CLAUDE_CONFIG

    def describe(self) -> Dict[str, Any]:
        return {
            "binary": {"path": str(self.binary), "exists": self.binary.exists(), "executable": self.binary.exists() and self.binary.stat().st_mode & 0o111 != 0},
            "mcp_config": {"path": str(self.mcp_config), "exists": self.mcp_config.exists()},
            "codex_config": {"path": str(self.codex_config), "exists": self.codex_config.exists()},
            "claude_config": {"path": str(self.claude_config), "exists": self.claude_config.exists()},
        }


@dataclass
class ChipRequest:
    method: str
    params: Dict[str, Any] = field(default_factory=dict)
    request_id: Optional[str] = None
    jsonrpc: str = "2.0"

    def payload(self) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "jsonrpc": self.jsonrpc,
            "method": self.method,
        }
        if self.request_id is not None:
            body["id"] = self.request_id
        if self.params:
            body["params"] = self.params
        return body


@dataclass
class ChipResponse:
    ok: bool
    method: str
    request_id: Optional[str]
    result: Any = None
    error: Optional[Dict[str, Any]] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChipActivityReport:
    activity_id: str
    status: str
    description: str
    tool_count: int
    binary_path: str
    metadata: Dict[str, Any]

    def as_activity(self) -> Dict[str, Any]:
        if not all([Activity, ActivityType, Agent, AgentRole, AgentType]):
            return {
                "activity_id": self.activity_id,
                "activity_type": "Task Execution",
                "status": self.status,
                "description": self.description,
                "metadata": self.metadata,
            }
        agent = Agent(
            agent_id="software:collibra:chip",
            agent_type=AgentType.SOFTWARE_APPLICATION,
            display_name="Collibra CHIP MCP Server",
            roles=[AgentRole.DATA_PROCESSOR],
            metadata={"binary_path": self.binary_path},
        )
        activity = Activity(
            entity_id=self.activity_id,
            activity_id=self.activity_id,
            activity_type=ActivityType.TASK_EXECUTION,
            entity_type="Activity",
            display_name="Collibra CHIP MCP handshake",
            source_type="collibra_chip",
            source_id=self.binary_path,
            metadata=self.metadata,
            description=self.description,
            status=self.status,
        )
        activity.add_agent(agent)
        return {
            "entity_id": activity.entity_id,
            "activity_id": activity.activity_id,
            "activity_type": activity.activity_type.value,
            "entity_type": activity.entity_type,
            "display_name": activity.display_name,
            "source_type": activity.source_type,
            "source_id": activity.source_id,
            "metadata": activity.metadata,
            "description": activity.description,
            "status": activity.status,
            "agents": [
                {
                    "agent_id": entry.agent_id,
                    "agent_type": entry.agent_type.value,
                    "display_name": entry.display_name,
                    "roles": [role.value for role in entry.roles],
                    "metadata": entry.metadata,
                }
                for entry in activity.agents
            ],
        }


class ChipSession:
    """Minimal MCP stdio client for a local ``chip`` process."""

    def __init__(self, binary: Path) -> None:
        self.binary = binary
        self.proc: Optional[subprocess.Popen[bytes]] = None

    def __enter__(self) -> "ChipSession":
        self.proc = subprocess.Popen(
            [str(self.binary)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        if not self.proc:
            return
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=3)

    def request(self, request: ChipRequest) -> ChipResponse:
        if not self.proc or not self.proc.stdin or not self.proc.stdout:
            raise RuntimeError("chip process is not running")
        payload = request.payload()
        encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.proc.stdin.write(b"Content-Length: " + str(len(encoded)).encode("ascii") + b"\r\n\r\n" + encoded)
        self.proc.stdin.flush()
        raw = _read_message(self.proc.stdout)
        if raw.get("id") != request.request_id:
            raise RuntimeError(f"Unexpected MCP response id: expected {request.request_id}, got {raw.get('id')}")
        return ChipResponse(
            ok="error" not in raw,
            method=request.method,
            request_id=request.request_id,
            result=raw.get("result"),
            error=raw.get("error"),
            raw=raw,
        )

    def notify(self, method: str, params: Optional[Dict[str, Any]] = None) -> None:
        if not self.proc or not self.proc.stdin:
            raise RuntimeError("chip process is not running")
        request = ChipRequest(method=method, params=params or {}, request_id=None)
        payload = request.payload()
        encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.proc.stdin.write(b"Content-Length: " + str(len(encoded)).encode("ascii") + b"\r\n\r\n" + encoded)
        self.proc.stdin.flush()

    def stderr_text(self) -> str:
        if not self.proc or not self.proc.stderr:
            return ""
        try:
            return self.proc.stderr.read().decode("utf-8", errors="replace").strip()
        except Exception:
            return ""


def _read_message(stream: IO[bytes]) -> Dict[str, Any]:
    headers: Dict[str, str] = {}
    while True:
        line = stream.readline()
        if not line:
            raise RuntimeError("chip closed stdout before returning an MCP response")
        if line in (b"\r\n", b"\n"):
            break
        key, _, value = line.decode("utf-8", errors="replace").partition(":")
        headers[key.strip().lower()] = value.strip()
    content_length = int(headers.get("content-length", "0"))
    if content_length <= 0:
        raise RuntimeError(f"Invalid MCP content-length: {headers.get('content-length')!r}")
    body = stream.read(content_length)
    if len(body) != content_length:
        raise RuntimeError("Incomplete MCP response body")
    return json.loads(body.decode("utf-8"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _chip_server_reference(paths: ChipPaths) -> Dict[str, Any]:
    return {
        "command": str(paths.binary),
        "type": "stdio",
    }


def _codex_has_chip(paths: ChipPaths) -> bool:
    if not paths.codex_config.exists():
        return False
    text = paths.codex_config.read_text(encoding="utf-8")
    return (
        "[mcp_servers.collibra]" in text
        and f'command = "{paths.binary}"' in text
    )


def _claude_has_chip(paths: ChipPaths) -> bool:
    if not paths.claude_config.exists():
        return False
    try:
        payload = json.loads(paths.claude_config.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return payload.get("mcpServers", {}).get("collibra", {}).get("command") == str(paths.binary)


def _startup_probe(paths: ChipPaths, *, wait_seconds: float = 1.0) -> Dict[str, Any]:
    proc = subprocess.Popen(
        [str(paths.binary)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        time.sleep(wait_seconds)
        running = proc.poll() is None
        if running:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
        stdout = proc.stdout.read() if proc.stdout else ""
        stderr = proc.stderr.read() if proc.stderr else ""
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=3)
    tool_lines = []
    for line in stderr.splitlines():
        marker = "Registering tool: "
        if marker in line:
            tool_lines.append(line.split(marker, 1)[1].strip())
    return {
        "ok": "Listening on stdio" in stderr and bool(tool_lines),
        "listening_on_stdio": "Listening on stdio" in stderr,
        "tool_names": tool_lines,
        "stdout": stdout.strip(),
        "stderr": stderr.strip(),
        "exit_code": proc.returncode,
    }


def configure_codex(paths: ChipPaths) -> Dict[str, Any]:
    text = paths.codex_config.read_text(encoding="utf-8") if paths.codex_config.exists() else ""
    section = f'\n[mcp_servers.collibra]\ncommand = "{paths.binary}"\n'
    changed = False
    if "[mcp_servers.collibra]" not in text:
        if text and not text.endswith("\n"):
            text += "\n"
        text += section
        paths.codex_config.parent.mkdir(parents=True, exist_ok=True)
        paths.codex_config.write_text(text, encoding="utf-8")
        changed = True
    return {
        "ok": True,
        "client": "codex",
        "changed": changed,
        "path": str(paths.codex_config),
        "configured": _codex_has_chip(paths),
    }


def configure_claude(paths: ChipPaths) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    if paths.claude_config.exists():
        payload = json.loads(paths.claude_config.read_text(encoding="utf-8"))
    payload.setdefault("mcpServers", {})["collibra"] = _chip_server_reference(paths)
    paths.claude_config.parent.mkdir(parents=True, exist_ok=True)
    paths.claude_config.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return {
        "ok": True,
        "client": "claude",
        "changed": True,
        "path": str(paths.claude_config),
        "configured": _claude_has_chip(paths),
    }


def probe_chip(paths: ChipPaths) -> Dict[str, Any]:
    errors: List[str] = []
    startup: Optional[Dict[str, Any]] = None

    if not paths.binary.exists():
        errors.append(f"chip binary not found at {paths.binary}")
    elif not paths.mcp_config.exists():
        errors.append(f"chip config not found at {paths.mcp_config}")
    else:
        startup = _startup_probe(paths)
        if not startup.get("ok"):
            errors.append("chip did not reach a healthy stdio startup state")

    tools = []
    if startup:
        tools = [{"name": item, "description": ""} for item in startup.get("tool_names", [])]

    metadata = {
        "timestamp": _now_iso(),
        "paths": paths.describe(),
        "codex_configured": _codex_has_chip(paths),
        "claude_configured": _claude_has_chip(paths),
        "startup_ok": bool(startup and startup.get("ok")),
        "listening_on_stdio": bool(startup and startup.get("listening_on_stdio")),
        "transport_note": "chip stdio is client-owned; this probe validates startup and registered tools before Claude/Codex attach.",
        "stderr": (startup or {}).get("stderr", ""),
    }
    activity = ChipActivityReport(
        activity_id=f"activity:collibra:chip:{uuid.uuid4()}",
        status="completed" if not errors and startup and startup.get("ok") else "failed",
        description="Validate the Collibra CHIP MCP server and enumerate its tools.",
        tool_count=len(tools),
        binary_path=str(paths.binary),
        metadata=metadata,
    )
    return {
        "ok": not errors and bool(startup and startup.get("ok")),
        "command": "collibra io chip status",
        "chip": {
            "paths": paths.describe(),
            "codex_configured": _codex_has_chip(paths),
            "claude_configured": _claude_has_chip(paths),
            "startup": startup,
            "initialize": None,
            "tools": tools,
            "tool_count": len(tools),
            "stderr": (startup or {}).get("stderr", ""),
        },
        "activity": activity.as_activity(),
        "errors": errors,
    }


def _print_chip_payload(payload: Dict[str, Any], *, as_json: bool) -> int:
    if as_json:
        print(json.dumps(payload))
        return 0 if payload.get("ok") else 1

    if payload.get("command") == "collibra io chip status":
        chip = payload["chip"]
        print("[collibra io chip status]")
        print(f"  Binary:            {'ok' if chip['paths']['binary']['exists'] else 'missing'}  {chip['paths']['binary']['path']}")
        print(f"  MCP config:        {'ok' if chip['paths']['mcp_config']['exists'] else 'missing'}  {chip['paths']['mcp_config']['path']}")
        print(f"  Codex configured:  {'yes' if chip['codex_configured'] else 'no'}")
        print(f"  Claude configured: {'yes' if chip['claude_configured'] else 'no'}")
        print(f"  CHIP startup:      {'ok' if chip['startup'] and chip['startup']['ok'] else 'fail'}")
        print(f"  MCP tools:         {chip['tool_count']}")
        for tool in chip["tools"][:10]:
            print(f"    - {tool['name']}")
        if payload.get("errors"):
            print("  Errors:")
            for error in payload["errors"]:
                print(f"    - {error}")
    elif payload.get("command") == "collibra io chip tools list":
        print("[collibra io chip tools list]")
        for tool in payload.get("tools", []):
            if tool.get("description"):
                print(f"  {tool['name']}: {tool['description']}")
            else:
                print(f"  {tool['name']}")
    else:
        print(json.dumps(payload, indent=2))
    return 0 if payload.get("ok") else 1


def cmd_collibra_io_chip_status(args: argparse.Namespace) -> int:
    paths = ChipPaths(binary=Path(args.binary).expanduser())
    return _print_chip_payload(probe_chip(paths), as_json=args.json)


def cmd_collibra_io_chip_tools_list(args: argparse.Namespace) -> int:
    paths = ChipPaths(binary=Path(args.binary).expanduser())
    probe = probe_chip(paths)
    payload = {
        "ok": probe.get("ok", False),
        "command": "collibra io chip tools list",
        "tools": probe.get("chip", {}).get("tools", []),
        "activity": probe.get("activity"),
        "errors": probe.get("errors", []),
    }
    return _print_chip_payload(payload, as_json=args.json)


def cmd_collibra_io_chip_configure(args: argparse.Namespace) -> int:
    paths = ChipPaths(binary=Path(args.binary).expanduser())
    results: List[Dict[str, Any]] = []
    if args.client in {"codex", "all"}:
        results.append(configure_codex(paths))
    if args.client in {"claude", "all"}:
        results.append(configure_claude(paths))
    payload = {
        "ok": all(item.get("ok") for item in results),
        "command": "collibra io chip configure",
        "results": results,
        "chip": _chip_server_reference(paths),
    }
    if args.json:
        print(json.dumps(payload))
        return 0 if payload["ok"] else 1
    print(f"[collibra io chip configure] client={args.client}")
    for item in results:
        print(f"  {item['client']}: {'configured' if item['configured'] else 'not-configured'}  {item['path']}")
    return 0 if payload["ok"] else 1
