"""argparse registration for singine collibra subcommands.

Subcommand families:
    id, contract, io, query, quantum, server  — original surface
    repo, notify, secure, sdlc               — repo/pipeline/transport surface

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

    # ── repo ──────────────────────────────────────────────────────────────────
    _add_repo_parser(collibra_sub)

    # ── notify ────────────────────────────────────────────────────────────────
    _add_notify_parser(collibra_sub)

    # ── secure ────────────────────────────────────────────────────────────────
    _add_secure_parser(collibra_sub)

    # ── sdlc ──────────────────────────────────────────────────────────────────
    _add_sdlc_parser(collibra_sub)


# ═════════════════════════════════════════════════════════════════════════════
# repo — repository discovery, daily commit, cron schedule
# ═════════════════════════════════════════════════════════════════════════════

def _cmd_repo_find(args: argparse.Namespace) -> int:
    from pathlib import Path
    from .repo import find_local_repos, repo_info
    root = Path(args.root).expanduser()
    repos = find_local_repos(root, depth=args.depth)
    payload = {
        "ok": True,
        "root": str(root),
        "count": len(repos),
        "repos": [str(r) for r in repos],
    }
    return _print_payload(payload, as_json=args.json)


def _cmd_repo_remote(args: argparse.Namespace) -> int:
    from .repo import find_remote_repos
    payload = find_remote_repos(
        provider=args.provider,
        org=args.org,
        token=args.token,
    )
    return _print_payload(payload, as_json=args.json)


def _cmd_repo_status(args: argparse.Namespace) -> int:
    from pathlib import Path
    from .repo import find_local_repos, repo_info
    root = Path(args.root).expanduser()
    repos = find_local_repos(root, depth=args.depth)
    payload = {
        "ok": True,
        "root": str(root),
        "count": len(repos),
        "repos": [repo_info(r).as_dict() for r in repos],
    }
    return _print_payload(payload, as_json=args.json)


def _cmd_repo_daily_commit(args: argparse.Namespace) -> int:
    from pathlib import Path
    from .repo import find_local_repos, daily_commit
    root = Path(args.root).expanduser()
    repos = find_local_repos(root, depth=args.depth)
    payload = daily_commit(
        paths=repos,
        message=args.message,
        dry_run=args.dry_run,
        push=args.push,
    )
    return _print_payload(payload, as_json=args.json)


def _cmd_repo_schedule_install(args: argparse.Namespace) -> int:
    from .repo import schedule_install
    payload = schedule_install(
        root=args.root,
        hour=args.hour,
        notify_email=args.notify_email,
        push=args.push,
    )
    return _print_payload(payload, as_json=args.json)


def _cmd_repo_schedule_remove(args: argparse.Namespace) -> int:
    from .repo import schedule_remove
    return _print_payload(schedule_remove(), as_json=args.json)


def _cmd_repo_schedule_status(args: argparse.Namespace) -> int:
    from .repo import schedule_status
    return _print_payload(schedule_status(), as_json=args.json)


def _add_repo_parser(collibra_sub: argparse._SubParsersAction) -> None:
    repo_parser = collibra_sub.add_parser(
        "repo",
        help="Repository discovery, daily commit, and cron scheduling",
    )
    repo_parser.set_defaults(func=lambda a: (repo_parser.print_help(), 1)[1])
    repo_sub = repo_parser.add_subparsers(dest="collibra_repo_action")

    p = repo_sub.add_parser("find", help="Scan local filesystem for git repos")
    p.add_argument("--root", default="~/ws", help="Search root (default: ~/ws)")
    p.add_argument("--depth", type=int, default=4, help="Max directory depth (default: 4)")
    p.add_argument("--json", action="store_true", help="Emit JSON")
    p.set_defaults(func=_cmd_repo_find)

    p = repo_sub.add_parser("remote", help="List remote repos via REST API")
    p.add_argument("--provider", default="github", choices=["github", "gitlab"],
                   help="Provider (default: github)")
    p.add_argument("--org", default="", help="Organisation or group (omit for authenticated user)")
    p.add_argument("--token", default="", help="API token (falls back to GITHUB_TOKEN env var)")
    p.add_argument("--json", action="store_true", help="Emit JSON")
    p.set_defaults(func=_cmd_repo_remote)

    p = repo_sub.add_parser("status", help="Show dirty/clean state of discovered repos")
    p.add_argument("--root", default="~/ws", help="Search root (default: ~/ws)")
    p.add_argument("--depth", type=int, default=4, help="Max directory depth (default: 4)")
    p.add_argument("--json", action="store_true", help="Emit JSON")
    p.set_defaults(func=_cmd_repo_status)

    p = repo_sub.add_parser("daily-commit", help="Stage and commit all dirty repos under --root")
    p.add_argument("--root", default="~/ws", help="Search root (default: ~/ws)")
    p.add_argument("--depth", type=int, default=4, help="Max directory depth (default: 4)")
    p.add_argument("--message", default="chore: scheduled daily commit [singine-collibra]",
                   help="Commit message")
    p.add_argument("--dry-run", action="store_true", help="Report without committing")
    p.add_argument("--push", action="store_true", help="git push after each commit")
    p.add_argument("--json", action="store_true", help="Emit JSON")
    p.set_defaults(func=_cmd_repo_daily_commit)

    schedule_parser = repo_sub.add_parser("schedule", help="Manage the daily-commit cron entry")
    schedule_parser.set_defaults(func=lambda a: (schedule_parser.print_help(), 1)[1])
    sched_sub = schedule_parser.add_subparsers(dest="collibra_repo_schedule_action")

    p = sched_sub.add_parser("install", help="Install crontab entry for daily-commit")
    p.add_argument("--root", default="~/ws", help="Search root passed to daily-commit")
    p.add_argument("--hour", type=int, default=23, help="Hour (UTC) to run (default: 23)")
    p.add_argument("--notify-email", default="", metavar="ADDR",
                   help="Email address for commit summary (optional)")
    p.add_argument("--push", action="store_true", help="Pass --push to daily-commit")
    p.add_argument("--json", action="store_true", help="Emit JSON")
    p.set_defaults(func=_cmd_repo_schedule_install)

    p = sched_sub.add_parser("remove", help="Remove the daily-commit crontab entry")
    p.add_argument("--json", action="store_true", help="Emit JSON")
    p.set_defaults(func=_cmd_repo_schedule_remove)

    p = sched_sub.add_parser("status", help="Show current cron schedule status")
    p.add_argument("--json", action="store_true", help="Emit JSON")
    p.set_defaults(func=_cmd_repo_schedule_status)


# ═════════════════════════════════════════════════════════════════════════════
# notify — SMTP email via Docker edge + markupware envelope
# ═════════════════════════════════════════════════════════════════════════════

def _cmd_notify_email(args: argparse.Namespace) -> int:
    from .notify import send_email, send_from_stdin
    if args.stdin:
        payload = send_from_stdin(
            to=args.to, subject=args.subject,
            dry_run=args.dry_run, context=args.context,
        )
    else:
        payload = send_email(
            to=args.to, subject=args.subject,
            body=args.body or "",
            from_addr=args.from_addr,
            dry_run=args.dry_run,
            context=args.context,
        )
    return _print_payload(payload, as_json=args.json)


def _cmd_notify_status(args: argparse.Namespace) -> int:
    from .notify import smtp_status
    return _print_payload(smtp_status(), as_json=args.json)


def _cmd_notify_configure(args: argparse.Namespace) -> int:
    from .notify import notify_configure
    payload = notify_configure(
        smtp_url=args.smtp_url,
        edge_host=args.edge_host,
        from_addr=args.from_addr,
    )
    return _print_payload(payload, as_json=args.json)


def _add_notify_parser(collibra_sub: argparse._SubParsersAction) -> None:
    notify_parser = collibra_sub.add_parser(
        "notify",
        help="SMTP email via Docker edge instance with Markupware envelope",
    )
    notify_parser.set_defaults(func=lambda a: (notify_parser.print_help(), 1)[1])
    notify_sub = notify_parser.add_subparsers(dest="collibra_notify_action")

    p = notify_sub.add_parser("email", help="Send an email through the edge smtpAgent service")
    p.add_argument("--to", required=True, metavar="ADDR", help="Recipient address")
    p.add_argument("--subject", required=True, help="Email subject")
    p.add_argument("--body", default="", help="Plain-text body (or use --stdin)")
    p.add_argument("--stdin", action="store_true", help="Read body from stdin")
    p.add_argument("--from", dest="from_addr", default="", metavar="ADDR",
                   help="Sender address (default: SINGINE_NOTIFY_FROM env var)")
    p.add_argument("--dry-run", action="store_true", help="Print payload without sending")
    p.add_argument("--context", default="", help="SDLC context label for Markupware headers")
    p.add_argument("--json", action="store_true", help="Emit JSON")
    p.set_defaults(func=_cmd_notify_email)

    p = notify_sub.add_parser("status", help="Health check of the smtpAgent service")
    p.add_argument("--json", action="store_true", help="Emit JSON")
    p.set_defaults(func=_cmd_notify_status)

    p = notify_sub.add_parser("configure", help="Show or validate notification configuration")
    p.add_argument("--smtp-url", default="", help="Override smtpAgent endpoint URL")
    p.add_argument("--edge-host", default="", help="Docker edge host for smtpAgent")
    p.add_argument("--from", dest="from_addr", default="", metavar="ADDR", help="Default from address")
    p.add_argument("--json", action="store_true", help="Emit JSON")
    p.set_defaults(func=_cmd_notify_configure)


# ═════════════════════════════════════════════════════════════════════════════
# secure — context-aware transport (TLS / SSH tunnel / WireGuard / markupware)
# ═════════════════════════════════════════════════════════════════════════════

def _cmd_secure_context(args: argparse.Namespace) -> int:
    from .secure import detect_context
    return _print_payload(detect_context().as_dict(), as_json=args.json)


def _cmd_secure_cert(args: argparse.Namespace) -> int:
    from .secure import openssl_cert_info
    return _print_payload(openssl_cert_info(args.host, args.port), as_json=args.json)


def _cmd_secure_tunnel_start(args: argparse.Namespace) -> int:
    from .secure import ssh_tunnel_start
    payload = ssh_tunnel_start(
        remote_host=args.remote_host,
        local_port=args.local_port,
        remote_port=args.remote_port,
        remote_user=args.user,
        identity_file=args.identity,
    )
    return _print_payload(payload, as_json=args.json)


def _cmd_secure_tunnel_stop(args: argparse.Namespace) -> int:
    from .secure import ssh_tunnel_stop
    return _print_payload(ssh_tunnel_stop(local_port=args.local_port), as_json=args.json)


def _cmd_secure_tunnel_status(args: argparse.Namespace) -> int:
    from .secure import ssh_tunnel_status
    return _print_payload(ssh_tunnel_status(local_port=args.local_port), as_json=args.json)


def _cmd_secure_vpn_status(args: argparse.Namespace) -> int:
    from .secure import vpn_status
    return _print_payload(vpn_status(), as_json=args.json)


def _cmd_secure_vpn_up(args: argparse.Namespace) -> int:
    from .secure import vpn_up
    return _print_payload(vpn_up(args.config), as_json=args.json)


def _cmd_secure_vpn_down(args: argparse.Namespace) -> int:
    from .secure import vpn_down
    return _print_payload(vpn_down(args.config), as_json=args.json)


def _add_secure_parser(collibra_sub: argparse._SubParsersAction) -> None:
    secure_parser = collibra_sub.add_parser(
        "secure",
        help="Context-aware secure transport: TLS, SSH tunnel, WireGuard VPN",
    )
    secure_parser.set_defaults(func=lambda a: (secure_parser.print_help(), 1)[1])
    secure_sub = secure_parser.add_subparsers(dest="collibra_secure_action")

    p = secure_sub.add_parser("context", help="Detect and display current secure transport context")
    p.add_argument("--json", action="store_true", help="Emit JSON")
    p.set_defaults(func=_cmd_secure_context)

    p = secure_sub.add_parser("cert", help="Probe TLS certificate for a host via openssl s_client")
    p.add_argument("host", help="Hostname to probe")
    p.add_argument("--port", type=int, default=443, help="Port (default: 443)")
    p.add_argument("--json", action="store_true", help="Emit JSON")
    p.set_defaults(func=_cmd_secure_cert)

    tunnel_parser = secure_sub.add_parser("tunnel", help="Manage SSH tunnels")
    tunnel_parser.set_defaults(func=lambda a: (tunnel_parser.print_help(), 1)[1])
    tunnel_sub = tunnel_parser.add_subparsers(dest="collibra_secure_tunnel_action")

    p = tunnel_sub.add_parser("start", help="Start a background SSH tunnel")
    p.add_argument("remote_host", help="Remote host to tunnel through")
    p.add_argument("--local-port", type=int, default=8026, help="Local bind port (default: 8026)")
    p.add_argument("--remote-port", type=int, default=8026, help="Remote port (default: 8026)")
    p.add_argument("--user", default="", help="SSH username")
    p.add_argument("--identity", default="", metavar="FILE", help="SSH identity file")
    p.add_argument("--json", action="store_true", help="Emit JSON")
    p.set_defaults(func=_cmd_secure_tunnel_start)

    p = tunnel_sub.add_parser("stop", help="Stop an SSH tunnel")
    p.add_argument("--local-port", type=int, default=8026, help="Local port of tunnel to stop")
    p.add_argument("--json", action="store_true", help="Emit JSON")
    p.set_defaults(func=_cmd_secure_tunnel_stop)

    p = tunnel_sub.add_parser("status", help="Check whether an SSH tunnel is active")
    p.add_argument("--local-port", type=int, default=8026, help="Local port to check")
    p.add_argument("--json", action="store_true", help="Emit JSON")
    p.set_defaults(func=_cmd_secure_tunnel_status)

    vpn_parser = secure_sub.add_parser("vpn", help="Manage WireGuard VPN")
    vpn_parser.set_defaults(func=lambda a: (vpn_parser.print_help(), 1)[1])
    vpn_sub = vpn_parser.add_subparsers(dest="collibra_secure_vpn_action")

    p = vpn_sub.add_parser("status", help="Show WireGuard interface status")
    p.add_argument("--json", action="store_true", help="Emit JSON")
    p.set_defaults(func=_cmd_secure_vpn_status)

    p = vpn_sub.add_parser("up", help="Bring up a WireGuard interface via wg-quick")
    p.add_argument("config", help="Interface name or path to .conf file")
    p.add_argument("--json", action="store_true", help="Emit JSON")
    p.set_defaults(func=_cmd_secure_vpn_up)

    p = vpn_sub.add_parser("down", help="Bring down a WireGuard interface via wg-quick")
    p.add_argument("config", help="Interface name or path to .conf file")
    p.add_argument("--json", action="store_true", help="Emit JSON")
    p.set_defaults(func=_cmd_secure_vpn_down)


# ═════════════════════════════════════════════════════════════════════════════
# sdlc — on-the-fly SDLC process generation and pipeline dispatch
# ═════════════════════════════════════════════════════════════════════════════

def _cmd_sdlc_generate(args: argparse.Namespace) -> int:
    from pathlib import Path as _Path
    from .sdlc import generate
    out = _Path(args.out).expanduser() if args.out else None
    payload = generate(
        env=args.env,
        mode=args.mode,
        kind=args.kind,
        out=out,
        project=args.project,
    )
    return _print_payload(payload, as_json=args.json)


def _cmd_sdlc_pipeline(args: argparse.Namespace) -> int:
    from pathlib import Path as _Path
    from .sdlc import dispatch
    sdlc_path = _Path(args.sdlc).expanduser()
    payload = dispatch(sdlc_path=sdlc_path, dry_run=args.dry_run)
    return _print_payload(payload, as_json=args.json)


def _cmd_sdlc_dispatch(args: argparse.Namespace) -> int:
    from pathlib import Path as _Path
    from .sdlc import dispatch
    sdlc_path = _Path(args.sdlc).expanduser()
    payload = dispatch(sdlc_path=sdlc_path, step_name=args.step, dry_run=args.dry_run)
    return _print_payload(payload, as_json=args.json)


def _add_sdlc_parser(collibra_sub: argparse._SubParsersAction) -> None:
    from .sdlc import KNOWN_KINDS, KNOWN_MODES, KNOWN_ENVS
    sdlc_parser = collibra_sub.add_parser(
        "sdlc",
        help="On-the-fly SDLC process generation and data-product pipeline dispatch",
    )
    sdlc_parser.set_defaults(func=lambda a: (sdlc_parser.print_help(), 1)[1])
    sdlc_sub = sdlc_parser.add_subparsers(dest="collibra_sdlc_action")

    p = sdlc_sub.add_parser("generate", help="Generate a .sdlc.yaml for a data product pipeline")
    p.add_argument("--env", default="", choices=KNOWN_ENVS + [""],
                   help="SDLC environment (default: SINGINE_ENV or dev)")
    p.add_argument("--mode", default="sequential", choices=KNOWN_MODES,
                   help="Pipeline dispatch mode (default: sequential)")
    p.add_argument("--kind", default="DataProduct", choices=KNOWN_KINDS,
                   help="Data product kind (default: DataProduct)")
    p.add_argument("--project", default="", help="Project label (default: kind)")
    p.add_argument("--out", default="", metavar="PATH",
                   help="Write YAML to this path (stdout if omitted)")
    p.add_argument("--json", action="store_true", help="Emit JSON envelope")
    p.set_defaults(func=_cmd_sdlc_generate)

    p = sdlc_sub.add_parser("pipeline", help="Run all steps in a .sdlc.yaml file")
    p.add_argument("sdlc", help="Path to .sdlc.yaml file")
    p.add_argument("--dry-run", action="store_true", help="Report steps without executing")
    p.add_argument("--json", action="store_true", help="Emit JSON")
    p.set_defaults(func=_cmd_sdlc_pipeline)

    p = sdlc_sub.add_parser("dispatch", help="Run a single named step from a .sdlc.yaml file")
    p.add_argument("sdlc", help="Path to .sdlc.yaml file")
    p.add_argument("--step", default="", metavar="NAME", help="Step name to run")
    p.add_argument("--dry-run", action="store_true", help="Report without executing")
    p.add_argument("--json", action="store_true", help="Emit JSON")
    p.set_defaults(func=_cmd_sdlc_dispatch)
