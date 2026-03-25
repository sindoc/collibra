"""argparse registration for singine collibra id/contract/pipeline/server subcommands.

Called from singine's build_parser() via dynamic import.

Usage (inside singine's build_parser):
    from singine_collibra.command import add_collibra_subcommands
    add_collibra_subcommands(collibra_sub)
"""
from __future__ import annotations

import argparse


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


# ── Parser registration ───────────────────────────────────────────────────────

def add_collibra_subcommands(collibra_sub: argparse._SubParsersAction) -> None:
    """Register id, contract, pipeline, server subcommands under ``singine collibra``."""

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
