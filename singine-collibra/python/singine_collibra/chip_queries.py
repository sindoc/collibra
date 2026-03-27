"""MCP query DSL for the Collibra CHIP server.

Implements the ``~ws(self, ...+ ++ +++ ++++ +++++)`` workspace traversal,
``codeLookup().lambda_().exec().try_catch_claude()`` fluent execution chain,
typed ``TypeRetrieval`` queries, and an HTTP-compatible gRPC bridge against
``singine.persistence.v1``.

Entry-point grammar: ``docs/xml/chip-queries.xml`` (consumed by Go ``lang=XML.g()``).
JProfiler targets declared in grammar; attach via ``discover_jvm_targets()``.
"""

from __future__ import annotations

import enum
import json
import traceback
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar

from .chip import (
    ChipPaths,
    ChipRequest,
    ChipResponse,
    ChipSession,
)

T = TypeVar("T")

_GRAMMAR_XML = Path(__file__).parent.parent.parent.parent / "docs" / "xml" / "chip-queries.xml"


# ── Workspace depth: ~ws(self, + ++ +++ ++++ +++++) ──────────────────────────

class WorkspaceDepth(enum.IntEnum):
    """Depth levels for ``~ws(self, ...)`` traversal.

    Symbol    Level  Meaning
    ------    -----  -------
    self        0    Workspace root only (SELF)
    +           1    Immediate children (SHALLOW)
    ++          2    Two levels deep (MEDIUM)
    +++         3    Three levels deep (DEEP)
    ++++        4    Four levels deep (DEEPER)
    +++++       5    Full recursive traversal (FULL)
    """
    SELF    = 0
    SHALLOW = 1
    MEDIUM  = 2
    DEEP    = 3
    DEEPER  = 4
    FULL    = 5


@dataclass
class WorkspaceContext:
    """Represents ``~ws(self, depth)`` — root of all chip MCP queries.

    Example::

        ctx = WorkspaceContext(depth=WorkspaceDepth.FULL)
        result = ctx.codeLookup("elia electricity domain").exec().try_catch_claude()
    """
    root: Path = field(default_factory=lambda: Path("~/ws").expanduser())
    depth: WorkspaceDepth = WorkspaceDepth.SELF
    paths: ChipPaths = field(default_factory=ChipPaths)

    def at(self, depth: WorkspaceDepth) -> "WorkspaceContext":
        return WorkspaceContext(root=self.root, depth=depth, paths=self.paths)

    def codeLookup(self, term: str, *, scope: Optional[str] = None) -> "CodeLookupQuery":  # noqa: N802
        return CodeLookupQuery(ctx=self, term=term, scope=scope)


# ── Type retrieval ─────────────────────────────────────────────────────────────

@dataclass
class TypeRef:
    """Collibra asset type reference from a chip code-lookup result."""
    iri: str
    type_name: str
    collibra_id: str
    asset_type: str
    fragments: List[str] = field(default_factory=list)


@dataclass
class TypeRetrieval:
    """Full type definition returned by the ``collibra/type_retrieve`` tool."""
    type_ref: TypeRef
    properties: Dict[str, Any] = field(default_factory=dict)
    relations: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_chip_result(cls, result: Any) -> "TypeRetrieval":
        if not isinstance(result, dict):
            result = {}
        ref = TypeRef(
            iri=result.get("type_iri", ""),
            type_name=result.get("type_name", ""),
            collibra_id=result.get("collibra_id", ""),
            asset_type=result.get("asset_type", ""),
            fragments=result.get("fragments", []),
        )
        return cls(
            type_ref=ref,
            properties=result.get("properties", {}),
            relations=result.get("relations", []),
        )


# ── Lambda/exec chain: .lambda_().exec().try_catch_claude() ──────────────────

@dataclass
class LambdaExec:
    """Wraps a chip MCP call in a deferred ``lambda_().exec()`` chain.

    Calling ``.try_catch_claude()`` returns the result on success or an
    MCP-compatible error envelope that Claude can interpret and recover from.
    """
    fn: Callable[[], Any]
    _result: Optional[Any] = field(default=None, init=False, repr=False)
    _error: Optional[Exception] = field(default=None, init=False, repr=False)

    def exec(self) -> "LambdaExec":  # noqa: A003
        try:
            self._result = self.fn()
        except Exception as exc:  # noqa: BLE001
            self._error = exc
        return self

    def try_catch_claude(self, *, default: Any = None) -> Any:
        """``tryCatchClaude`` — return result or an MCP-compatible error envelope."""
        if self._error is None:
            return self._result
        return {
            "ok": False,
            "error": str(self._error),
            "traceback": traceback.format_exc(),
            "mcp_error": {
                "code": -32000,
                "message": str(self._error),
                "data": {
                    "source": "chip_queries.tryCatchClaude",
                    "type": type(self._error).__name__,
                    "recovery": "delegate to Claude MCP session for re-evaluation",
                },
            },
            "default": default,
        }


# ── CodeLookup query: codeLookup().lambda_().exec() ──────────────────────────

@dataclass
class CodeLookupQuery:
    """``codeLookup()`` — chip MCP tool call for Collibra type and code lookup.

    Grammar reference: ``chip-queries.xml`` query-type id="code-lookup".
    """
    ctx: WorkspaceContext
    term: str
    scope: Optional[str] = None

    def _build_request(self) -> ChipRequest:
        params: Dict[str, Any] = {
            "term": self.term,
            "depth": int(self.ctx.depth),
        }
        if self.scope:
            params["scope"] = self.scope
        return ChipRequest(
            method="tools/call",
            params={"name": "collibra/code_lookup", "arguments": params},
            request_id=str(uuid.uuid4()),
        )

    def lambda_(                                                # noqa: N802
        self,
        transform: Optional[Callable[[ChipResponse], T]] = None,
    ) -> LambdaExec:
        """Return a ``LambdaExec`` wrapping the chip call + optional transform."""
        request = self._build_request()
        paths = self.ctx.paths

        def _fn() -> Any:
            with ChipSession(paths.binary) as session:
                resp = session.request(request)
            if transform is not None:
                return transform(resp)
            return resp

        return LambdaExec(fn=_fn)

    def exec(self) -> LambdaExec:
        """Shorthand: ``lambda_().exec()``."""
        return self.lambda_().exec()

    def type_retrieval(self) -> LambdaExec:
        """Execute and map result to a typed ``TypeRetrieval`` object."""
        def _transform(resp: ChipResponse) -> TypeRetrieval:
            raw = resp.result or {}
            content = raw.get("content", [{}])
            try:
                data = json.loads(content[0].get("text", "{}")) if content else {}
            except (json.JSONDecodeError, IndexError, TypeError):
                data = {}
            return TypeRetrieval.from_chip_result(data)

        return self.lambda_(_transform).exec()


# ── HTTP-compatible gRPC bridge ───────────────────────────────────────────────

@dataclass
class GrpcHttpRequest:
    """An HTTP-transcoded gRPC request (grpc-gateway style).

    Compatible with both native gRPC/HTTP2 and plain HTTP/1.1 JSON.
    Service: ``singine.persistence.v1`` — see persistence.proto.
    HTTP bindings: ``chip-queries.xml`` grpc-http-bindings section.
    """
    rpc: str
    body: Dict[str, Any]
    base_url: str = "http://127.0.0.1:9090"
    grpc_port: int = 50051
    use_http: bool = True


_RPC_HTTP_MAP: Dict[str, Tuple[str, str]] = {
    "GenId":        ("POST",  "/v1/id/gen"),
    "QueryLineage": ("GET",   "/v1/lineage"),
    "ShortestPath": ("POST",  "/v1/path"),
    "Categorise":   ("POST",  "/v1/category"),
    "Similarity":   ("POST",  "/v1/similarity"),
    "Migrate":      ("POST",  "/v1/migrate"),
}


def grpc_http_call(req: GrpcHttpRequest) -> Dict[str, Any]:
    """Execute a gRPC call via HTTP/JSON transcoding (grpc-gateway pattern).

    ``use_http=True`` — plain HTTP/1.1 POST/GET with JSON body.
    ``use_http=False`` — returns a stub signalling native gRPC is needed.
    """
    import urllib.error
    import urllib.request

    if req.rpc not in _RPC_HTTP_MAP:
        return {"ok": False, "error": f"Unknown RPC: {req.rpc}. Known: {sorted(_RPC_HTTP_MAP)}"}

    method, path = _RPC_HTTP_MAP[req.rpc]
    url = req.base_url.rstrip("/") + path

    if not req.use_http:
        host = req.base_url.split("//")[-1].split(":")[0]
        return {
            "ok": False,
            "mode": "grpc-native",
            "note": "Set use_http=True for HTTP/JSON transcoding, or use a grpc channel directly.",
            "endpoint": f"{host}:{req.grpc_port}",
            "rpc": req.rpc,
        }

    encoded = json.dumps(req.body).encode("utf-8")
    http_req = urllib.request.Request(
        url,
        data=encoded if method == "POST" else None,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Singine-Rpc": req.rpc,
            "X-Singine-Version": "persistence/v1",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(http_req, timeout=10) as response:
            return {"ok": True, "status": response.status, "body": json.loads(response.read())}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": exc.code, "error": exc.reason}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


# ── JProfiler attachment descriptors ─────────────────────────────────────────

@dataclass
class JProfilerTarget:
    """Descriptor for a JVM process (Groovy or Clojure) to attach JProfiler to.

    Grammar reference: ``chip-queries.xml`` jprofiler-targets section.
    """
    process_id: str
    runtime: str           # "groovy" | "clojure"
    pid: Optional[int]
    agent_path: Path
    config_id: str
    nowait: bool = True

    def attach_args(self) -> str:
        """Produce the JVM ``-agentpath:`` argument string."""
        return (
            f"-agentpath:{self.agent_path}"
            f"=port=8849"
            f",nowait={'y' if self.nowait else 'n'}"
            f",id={self.config_id}"
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "process_id": self.process_id,
            "runtime": self.runtime,
            "pid": self.pid,
            "agent_path": str(self.agent_path),
            "config_id": self.config_id,
            "attach_args": self.attach_args(),
        }


_GROOVY_PATTERNS  = {"groovy.ui.GroovyMain", "org.codehaus.groovy", "groovy"}
_CLOJURE_PATTERNS = {"clojure.main", "singine.persistence.core"}


def discover_jvm_targets(
    *,
    agent_path: Path = Path("/opt/jprofiler/bin/linux-x64/libjprofilerti.so"),
) -> List[JProfilerTarget]:
    """Discover running Groovy and Clojure JVM processes via ``jps -l``.

    Returns a ``JProfilerTarget`` for each matched process.
    Grammar reference: ``chip-queries.xml`` jprofiler-targets section.
    """
    import subprocess

    targets: List[JProfilerTarget] = []
    try:
        result = subprocess.run(["jps", "-l"], capture_output=True, text=True, timeout=10)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return targets

    for line in result.stdout.splitlines():
        parts = line.split(None, 1)
        if len(parts) < 2:
            continue
        pid_str, main_class = parts
        runtime: Optional[str] = None
        config_id: Optional[str] = None
        if any(p in main_class for p in _GROOVY_PATTERNS):
            runtime, config_id = "groovy", "chip.profiler.groovy"
        elif any(p in main_class for p in _CLOJURE_PATTERNS):
            runtime, config_id = "clojure", "chip.profiler.clojure"
        if runtime and config_id:
            targets.append(JProfilerTarget(
                process_id=main_class,
                runtime=runtime,
                pid=int(pid_str),
                agent_path=agent_path,
                config_id=config_id,
            ))
    return targets
