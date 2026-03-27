"""argparse registration for singine collibra id/contract/io/pipeline/server subcommands.

Called from singine's build_parser() via dynamic import.

Usage (inside singine's build_parser):
    from singine_collibra.command import add_collibra_subcommands
    add_collibra_subcommands(collibra_sub)
"""
from __future__ import annotations

import argparse
import json

from .io import add_collibra_io_parser


# ── Command handlers ──────────────────────────────────────────────────────────

def _cmd_id_gen(args: argparse.Namespace) -> int:
    from .idgen import gen
    return gen(ns=args.ns, project=args.project, kind=args.kind)


def _cmd_id_gen_topic(args: argparse.Namespace) -> int:
    from .idgen import gen_topic
    return gen_topic(project=args.project)


def _cmd_id_import(args: argparse.Namespace) -> int:
    from .idgen import import_id
    return import_id(uuid=args.uuid, kind=args.kind, project=args.project)


def _cmd_id_tags(args: argparse.Namespace) -> int:
    from .idgen import tags
    return tags()


def _cmd_id_push_tags(args: argparse.Namespace) -> int:
    from .idgen import push_tags
    return push_tags()


def _cmd_id_detect_conflicts(args: argparse.Namespace) -> int:
    from .idgen import detect_conflicts
    return detect_conflicts()


def _cmd_id_resolve_conflicts(args: argparse.Namespace) -> int:
    from .idgen import resolve_conflicts
    return resolve_conflicts(strategy=args.strategy)


def _cmd_contract_new(args: argparse.Namespace) -> int:
    from .contract import new
    return new(project=args.project, kind=args.kind)


def _cmd_contract_list(args: argparse.Namespace) -> int:
    from .contract import list_contracts
    return list_contracts()


def _cmd_contract_status(args: argparse.Namespace) -> int:
    from .contract import set_status
    return set_status(contract_id=args.contract_id, status=args.status)


def _cmd_contract_pipeline(args: argparse.Namespace) -> int:
    from .contract import pipeline
    return pipeline(contract_id=getattr(args, "contract_id", "") or "")


def _cmd_contract_step(args: argparse.Namespace) -> int:
    from .contract import step
    return step(n=args.n, contract_id=getattr(args, "contract_id", "") or "")


def _cmd_contract_advance(args: argparse.Namespace) -> int:
    from .contract import advance
    return advance(contract_id=getattr(args, "contract_id", "") or "")


def _cmd_contract_progress(args: argparse.Namespace) -> int:
    from .contract import progress
    return progress(
        contract_id=getattr(args, "contract_id", "") or "",
        all_contracts=getattr(args, "all", False),
        as_json=getattr(args, "json", False),
    )


def _cmd_server_start(args: argparse.Namespace) -> int:
    from .server import start
    return start(port=args.port, mode=args.mode)


def _cmd_server_stop(args: argparse.Namespace) -> int:
    from .server import stop
    return stop()


def _cmd_server_status(args: argparse.Namespace) -> int:
    from .server import status
    return status()


def _cmd_server_dmz(args: argparse.Namespace) -> int:
    from .server import dmz
    return dmz(port=args.port)


def _workspace_depth(value: str) -> int:
    mapping = {
        "self": 0,
        "+": 1,
        "++": 2,
        "+++": 3,
        "++++": 4,
        "+++++": 5,
    }
    if value not in mapping:
        raise argparse.ArgumentTypeError(f"invalid workspace depth: {value}")
    return mapping[value]


def _print_payload(payload: object, *, as_json: bool) -> int:
    if as_json:
        print(json.dumps(payload, indent=2, default=str))
        return 0
    if isinstance(payload, dict):
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(payload)
    return 0


def _cmd_query_status(args: argparse.Namespace) -> int:
    from .chip_queries import _GRAMMAR_XML, _RPC_HTTP_MAP

    payload = {
        "ok": True,
        "grammar_xml": {
            "path": str(_GRAMMAR_XML),
            "exists": _GRAMMAR_XML.exists(),
        },
        "rpc_bindings": sorted(_RPC_HTTP_MAP),
    }
    return _print_payload(payload, as_json=args.json)


def _cmd_query_jprofiler_targets(args: argparse.Namespace) -> int:
    from pathlib import Path

    from .chip_queries import discover_jvm_targets

    payload = {
        "ok": True,
        "targets": [
            target.as_dict()
            for target in discover_jvm_targets(agent_path=Path(args.agent_path).expanduser())
        ],
    }
    return _print_payload(payload, as_json=args.json)


def _cmd_query_grpc_bindings(args: argparse.Namespace) -> int:
    from .chip_queries import _RPC_HTTP_MAP

    payload = {
        "ok": True,
        "bindings": [
            {"rpc": rpc, "method": method, "path": path}
            for rpc, (method, path) in sorted(_RPC_HTTP_MAP.items())
        ],
    }
    return _print_payload(payload, as_json=args.json)


def _query_context(args: argparse.Namespace):
    from .chip_queries import WorkspaceContext, WorkspaceDepth

    return WorkspaceContext(depth=WorkspaceDepth(args.depth))


def _cmd_query_code_lookup(args: argparse.Namespace) -> int:
    ctx = _query_context(args)
    result = ctx.codeLookup(args.term, scope=args.scope).exec().try_catch_claude()
    return _print_payload(result, as_json=args.json)


def _cmd_query_type_retrieval(args: argparse.Namespace) -> int:
    ctx = _query_context(args)
    result = ctx.codeLookup(args.term, scope=args.scope).type_retrieval().try_catch_claude()
    return _print_payload(result, as_json=args.json)


def _cmd_query_grpc_http_call(args: argparse.Namespace) -> int:
    from .chip_queries import GrpcHttpRequest, grpc_http_call

    body = json.loads(args.body)
    payload = grpc_http_call(
        GrpcHttpRequest(
            rpc=args.rpc,
            body=body,
            base_url=args.base_url,
            grpc_port=args.grpc_port,
            use_http=not args.native_grpc,
        )
    )
    return _print_payload(payload, as_json=args.json)


def _cmd_quantum_status(args: argparse.Namespace) -> int:
    from pathlib import Path

    from .quantum_catalog import loadCodeTableFromBaseFromShiva

    docs_root = Path(__file__).parent.parent.parent.parent / "docs" / "quantum"
    payload = {
        "ok": True,
        "code_table_size": len(loadCodeTableFromBaseFromShiva()),
        "artifacts": {
            "tex": str(docs_root / "chip-quantum-catalog.tex"),
            "svg": str(docs_root / "complex-plane.svg"),
            "xml": str(docs_root / "quantum-catalog.xml"),
        },
    }
    return _print_payload(payload, as_json=args.json)


def _cmd_quantum_load_shiva(args: argparse.Namespace) -> int:
    from pathlib import Path

    from .quantum_catalog import loadCodeTableFromBaseFromShiva

    payload = {
        "ok": True,
        "db": str(Path(args.db).expanduser()),
        "entries": {
            code: entry.__dict__
            for code, entry in loadCodeTableFromBaseFromShiva(db=Path(args.db).expanduser()).items()
        },
    }
    return _print_payload(payload, as_json=args.json)


def _cmd_quantum_refdata(args: argparse.Namespace) -> int:
    from .quantum_catalog import refData

    entry = refData(args.code)
    payload = {"ok": entry is not None, "entry": entry.__dict__ if entry else None}
    return _print_payload(payload, as_json=args.json)


def _parse_complex_csv(value: str) -> list[complex]:
    try:
        return [complex(part.strip()) for part in value.split(",") if part.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _cmd_quantum_cosine(args: argparse.Namespace) -> int:
    from .quantum_catalog import cosine

    payload = (
        cosine()(args.u, args.v)
        .similarity()
        .complex()
        .resolve()
        .xml()
        .catalog()
        .collibra()
    )
    return _print_payload(payload, as_json=args.json)


def _cmd_quantum_bubble_leader(args: argparse.Namespace) -> int:
    from .quantum_catalog import bubbleLeader

    payload = (
        bubbleLeader(args.items)
        .builder()
        .piotr()
        .groovy()
        .clojure()
        .c()
        .f()
        .math()
        .godel()
        .escher()
        .pg()
        .pg()
        .paulGraham()
        .build()
    )
    return _print_payload(payload, as_json=args.json)


# ── Parser registration ───────────────────────────────────────────────────────

def add_collibra_subcommands(collibra_sub: argparse._SubParsersAction) -> None:
    """Register id, contract, io, query, quantum, and server subcommands under ``singine collibra``."""

    # ── id ────────────────────────────────────────────────────────────────────
    id_parser = collibra_sub.add_parser(
        "id",
        help="Contract ID generation and namespace registry (id-gen/)",
    )
    id_parser.set_defaults(func=lambda a: (id_parser.print_help(), 1)[1])
    id_sub = id_parser.add_subparsers(dest="collibra_id_action")

    p = id_sub.add_parser("gen", help="Mint a new contract ID (git-tag persisted)")
    p.add_argument("--ns", default="c", choices=["c", "a", "b"], help="Namespace (default: c)")
    p.add_argument("--project", default="DefaultProject", help="Project label")
    p.add_argument("--kind", default="contract", help="ID kind (default: contract)")
    p.set_defaults(func=_cmd_id_gen)

    p = id_sub.add_parser("gen-topic", help="Mint a topic ID for a project")
    p.add_argument("--project", default="DefaultProject", help="Project label")
    p.set_defaults(func=_cmd_id_gen_topic)

    p = id_sub.add_parser("import", help="Register an existing Collibra UUID into a namespace")
    p.add_argument("--uuid", required=True, metavar="UUID", help="Collibra asset UUID")
    p.add_argument("--kind", required=True, metavar="KIND", help="Asset kind")
    p.add_argument("--project", default="DefaultProject", help="Project label")
    p.set_defaults(func=_cmd_id_import)

    p = id_sub.add_parser("tags", help="List all id-gen git tags")
    p.set_defaults(func=_cmd_id_tags)

    p = id_sub.add_parser("push-tags", help="Push id-gen git tags to origin")
    p.set_defaults(func=_cmd_id_push_tags)

    p = id_sub.add_parser("detect-conflicts", help="Scan for merge conflicts in namespace registries")
    p.set_defaults(func=_cmd_id_detect_conflicts)

    p = id_sub.add_parser("resolve-conflicts", help="Auto-resolve namespace registry conflicts")
    p.add_argument(
        "--strategy",
        default="COLLIBRA_WINS",
        choices=["OURS", "THEIRS", "COLLIBRA_WINS", "ASK", "MANUAL"],
        help="Resolution strategy (default: COLLIBRA_WINS)",
    )
    p.set_defaults(func=_cmd_id_resolve_conflicts)

    # ── contract ──────────────────────────────────────────────────────────────
    contract_parser = collibra_sub.add_parser(
        "contract",
        help="Data contract lifecycle — scaffold, list, advance, and track (id-gen/contracts/)",
    )
    contract_parser.set_defaults(func=lambda a: (contract_parser.print_help(), 1)[1])
    contract_sub = contract_parser.add_subparsers(dest="collibra_contract_action")

    p = contract_sub.add_parser("new", help="Scaffold a new data contract")
    p.add_argument("--project", default="DefaultProject", help="Project label")
    p.add_argument(
        "--kind",
        default="DataContract",
        choices=["DataContract", "UseCaseContract", "ServiceContract", "GovernanceContract"],
        help="Contract kind (default: DataContract)",
    )
    p.set_defaults(func=_cmd_contract_new)

    p = contract_sub.add_parser("list", help="List all contracts")
    p.set_defaults(func=_cmd_contract_list)

    p = contract_sub.add_parser("status", help="Update a contract's status")
    p.add_argument("contract_id", help="Contract ID")
    p.add_argument(
        "status",
        choices=["DRAFT", "PENDING_APPROVAL", "APPROVED", "REJECTED", "ACTIVE", "DEPRECATED"],
        help="New status",
    )
    p.set_defaults(func=_cmd_contract_status)

    p = contract_sub.add_parser("pipeline", help="Run the full 7-step ORM/SBVR pipeline for a contract")
    p.add_argument("--id", dest="contract_id", default="", metavar="CONTRACT_ID")
    p.set_defaults(func=_cmd_contract_pipeline)

    p = contract_sub.add_parser("step", help="Run a single pipeline step (1-7)")
    p.add_argument("n", type=int, choices=range(1, 8), metavar="N", help="Step number 1-7")
    p.add_argument("--id", dest="contract_id", default="", metavar="CONTRACT_ID")
    p.set_defaults(func=_cmd_contract_step)

    p = contract_sub.add_parser("advance", help="Advance contract to the next pipeline step")
    p.add_argument("--id", dest="contract_id", default="", metavar="CONTRACT_ID")
    p.set_defaults(func=_cmd_contract_advance)

    p = contract_sub.add_parser("progress", help="Show pipeline progress")
    p.add_argument("--id", dest="contract_id", default="", metavar="CONTRACT_ID")
    p.add_argument("--all", action="store_true", help="Show progress for all contracts")
    p.add_argument("--json", action="store_true", help="Emit JSON")
    p.set_defaults(func=_cmd_contract_progress)

    # ── io ────────────────────────────────────────────────────────────────────
    add_collibra_io_parser(collibra_sub)

    # ── query ─────────────────────────────────────────────────────────────────
    query_parser = collibra_sub.add_parser(
        "query",
        help="CHIP MCP query DSL helpers and persistence bridge probes",
    )
    query_parser.set_defaults(func=lambda a: (query_parser.print_help(), 1)[1])
    query_sub = query_parser.add_subparsers(dest="collibra_query_action")

    p = query_sub.add_parser("status", help="Show chip query grammar and RPC binding status")
    p.add_argument("--json", action="store_true", help="Emit JSON")
    p.set_defaults(func=_cmd_query_status)

    p = query_sub.add_parser("jprofiler-targets", help="Discover Groovy and Clojure JVM attach targets")
    p.add_argument(
        "--agent-path",
        default="/opt/jprofiler/bin/linux-x64/libjprofilerti.so",
        help="JProfiler agent shared library path",
    )
    p.add_argument("--json", action="store_true", help="Emit JSON")
    p.set_defaults(func=_cmd_query_jprofiler_targets)

    p = query_sub.add_parser("grpc-bindings", help="List HTTP-transcoded persistence RPC bindings")
    p.add_argument("--json", action="store_true", help="Emit JSON")
    p.set_defaults(func=_cmd_query_grpc_bindings)

    p = query_sub.add_parser("code-lookup", help="Run a CHIP code lookup against the configured workspace")
    p.add_argument("term", help="Search term")
    p.add_argument("--scope", default=None, help="Optional lookup scope")
    p.add_argument(
        "--depth",
        type=_workspace_depth,
        default=0,
        metavar="{self,+,++,+++,++++,+++++}",
        help="Workspace traversal depth (default: self)",
    )
    p.add_argument("--json", action="store_true", help="Emit JSON")
    p.set_defaults(func=_cmd_query_code_lookup)

    p = query_sub.add_parser("type-retrieval", help="Run a typed CHIP code lookup projection")
    p.add_argument("term", help="Search term")
    p.add_argument("--scope", default=None, help="Optional lookup scope")
    p.add_argument(
        "--depth",
        type=_workspace_depth,
        default=0,
        metavar="{self,+,++,+++,++++,+++++}",
        help="Workspace traversal depth (default: self)",
    )
    p.add_argument("--json", action="store_true", help="Emit JSON")
    p.set_defaults(func=_cmd_query_type_retrieval)

    p = query_sub.add_parser("grpc-http-call", help="Invoke a persistence RPC via the HTTP bridge")
    p.add_argument("rpc", choices=["GenId", "QueryLineage", "ShortestPath", "Categorise", "Similarity", "Migrate"])
    p.add_argument("--body", default="{}", help="JSON request body")
    p.add_argument("--base-url", default="http://127.0.0.1:9090", help="Bridge base URL")
    p.add_argument("--grpc-port", type=int, default=50051, help="Native gRPC port (for metadata only)")
    p.add_argument("--native-grpc", action="store_true", help="Return native gRPC endpoint metadata instead of using HTTP")
    p.add_argument("--json", action="store_true", help="Emit JSON")
    p.set_defaults(func=_cmd_query_grpc_http_call)

    # ── quantum ───────────────────────────────────────────────────────────────
    quantum_parser = collibra_sub.add_parser(
        "quantum",
        help="Quantum catalog, code-table, cosine, and BubbleLeader helpers",
    )
    quantum_parser.set_defaults(func=lambda a: (quantum_parser.print_help(), 1)[1])
    quantum_sub = quantum_parser.add_subparsers(dest="collibra_quantum_action")

    p = quantum_sub.add_parser("status", help="Show quantum catalog artifact and code-table status")
    p.add_argument("--json", action="store_true", help="Emit JSON")
    p.set_defaults(func=_cmd_quantum_status)

    p = quantum_sub.add_parser("load-shiva", help="Load the in-memory Shiva base-layer code table")
    p.add_argument("--db", default="/tmp/humble-idp.db", help="Reference database path")
    p.add_argument("--json", action="store_true", help="Emit JSON")
    p.set_defaults(func=_cmd_quantum_load_shiva)

    p = quantum_sub.add_parser("refdata", help="Look up a single Shiva code-table entry")
    p.add_argument("code", help="Code table key such as AAAA or FFFFF")
    p.add_argument("--json", action="store_true", help="Emit JSON")
    p.set_defaults(func=_cmd_quantum_refdata)

    p = quantum_sub.add_parser("cosine", help="Run the complex cosine -> catalog -> Collibra chain")
    p.add_argument("--u", required=True, type=_parse_complex_csv, help="Comma-separated complex vector, e.g. 1+0j,0+1j")
    p.add_argument("--v", required=True, type=_parse_complex_csv, help="Comma-separated complex vector, e.g. 0.5+0j,0+0.5j")
    p.add_argument("--json", action="store_true", help="Emit JSON")
    p.set_defaults(func=_cmd_quantum_cosine)

    p = quantum_sub.add_parser("bubble-leader", help="Run the full BubbleLeader symbolic chain")
    p.add_argument("items", nargs="*", help="Items to bubble-sort before building the chain")
    p.add_argument("--json", action="store_true", help="Emit JSON")
    p.set_defaults(func=_cmd_quantum_bubble_leader)

    # ── server ────────────────────────────────────────────────────────────────
    server_parser = collibra_sub.add_parser(
        "server",
        help="id-gen HTTP API server (net/dmz modes, port 7331)",
    )
    server_parser.set_defaults(func=lambda a: (server_parser.print_help(), 1)[1])
    server_sub = server_parser.add_subparsers(dest="collibra_server_action")

    p = server_sub.add_parser("start", help="Start the server in net mode")
    p.add_argument("--port", type=int, default=7331, help="Port (default: 7331)")
    p.add_argument("--mode", default="net", choices=["net", "dmz"], help="Access mode (default: net)")
    p.set_defaults(func=_cmd_server_start)

    p = server_sub.add_parser("stop", help="Stop the server")
    p.set_defaults(func=_cmd_server_stop)

    p = server_sub.add_parser("status", help="Health check")
    p.set_defaults(func=_cmd_server_status)

    p = server_sub.add_parser("dmz", help="Start the server in DMZ mode (restricted endpoints)")
    p.add_argument("--port", type=int, default=7331, help="Port (default: 7331)")
    p.set_defaults(func=_cmd_server_dmz)
