"""Collibra I/O workflows for Singine.

This module begins the ``singine collibra io`` family with connection-oriented
preflight commands. The goal is to explain which I/O path is appropriate and to
verify the data-plane before touching the Collibra UI.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .chip import (
    cmd_collibra_io_chip_configure,
    cmd_collibra_io_chip_status,
    cmd_collibra_io_chip_tools_list,
)
from .metamodel import DEFAULT_METAMODEL_ROOT, MetamodelSnapshot, load_snapshot


_DEFAULT_EDGE_NAMESPACE = "collibra-edge"
_DEFAULT_EDGE_COMPONENT = "edge-controller"
_DEFAULT_PG_CONTAINER = "singine-pg"
_DEFAULT_EDGE_HOST = "host.docker.internal"
_DEFAULT_LOCAL_HOST = "127.0.0.1"
_DEFAULT_PG_PORT = 55432
_DEFAULT_PG_DATABASE = "singine_bridge"
_DEFAULT_PG_USER = "singine"
_DEFAULT_PG_PASSWORD = "singine"
_DEFAULT_DRIVER_VERSION = "42.7.10"
_REPO_ROOT = Path(__file__).resolve().parents[3]
_METAMODEL_SCRIPT = _REPO_ROOT / "id-gen" / "collibra" / "metamodel_7step.sh"
_MODEL_XML = _REPO_ROOT / "docs" / "xml" / "singine-collibra-model.xml"


def _run(cmd: Sequence[str], *, capture: bool = True, text: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(list(cmd), capture_output=capture, text=text)


def _tcp_probe(host: str, port: int, timeout: float = 3.0) -> Tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, "connected"
    except Exception as exc:
        return False, str(exc)


def _docker_ps(name: str) -> Dict[str, Any]:
    result = _run(
        ["docker", "ps", "--filter", f"name=^{name}$", "--format", "{{.Names}}\t{{.Image}}\t{{.Ports}}"]
    )
    if result.returncode != 0:
        return {"ok": False, "error": (result.stderr or "").strip() or "docker ps failed"}
    line = result.stdout.strip()
    if not line:
        return {"ok": False, "error": f"container {name} not running"}
    parts = line.split("\t")
    return {
        "ok": True,
        "name": parts[0],
        "image": parts[1] if len(parts) > 1 else "",
        "ports": parts[2] if len(parts) > 2 else "",
    }


def _docker_psql(container: str, user: str, database: str, sql: str) -> Dict[str, Any]:
    result = _run(
        ["docker", "exec", container, "psql", "-U", user, "-d", database, "-At", "-c", sql]
    )
    return {
        "ok": result.returncode == 0,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "exit_code": result.returncode,
    }


def _kubectl_exec(namespace: str, component: str, shell_snippet: str) -> Dict[str, Any]:
    result = _run(
        ["kubectl", "exec", "-n", namespace, f"deploy/{component}", "--", "sh", "-lc", shell_snippet]
    )
    return {
        "ok": result.returncode == 0,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "exit_code": result.returncode,
    }


def _kubectl_logs(namespace: str, component: str, tail: int = 400) -> Dict[str, Any]:
    result = _run(["kubectl", "logs", "-n", namespace, f"deploy/{component}", f"--tail={tail}"])
    return {
        "ok": result.returncode == 0,
        "stdout": result.stdout,
        "stderr": result.stderr.strip(),
        "exit_code": result.returncode,
    }


def _kubectl_get_jobs(namespace: str) -> Dict[str, Any]:
    result = _run(
        ["kubectl", "get", "jobs", "-n", namespace, "--sort-by=.metadata.creationTimestamp"]
    )
    return {
        "ok": result.returncode == 0,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "exit_code": result.returncode,
    }


def _kubectl_get_secrets(namespace: str) -> Dict[str, Any]:
    result = _run(["kubectl", "get", "secrets", "-n", namespace, "--no-headers"])
    return {
        "ok": result.returncode == 0,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "exit_code": result.returncode,
    }


def _driver_path(version: str) -> Path:
    return Path.home() / ".m2" / "repository" / "org" / "postgresql" / "postgresql" / version / f"postgresql-{version}.jar"


def _collibra_ok(result: Dict[str, Any], args: argparse.Namespace) -> int:
    if getattr(args, "json", True):
        print(json.dumps(result))
    else:
        data = result.get("data", {})
        if isinstance(data, dict):
            print(data.get("name") or data.get("displayName") or str(data))
        else:
            print(str(data))
    return 0 if result.get("ok") else 1


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _normalize_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _extract_python_literal(text: str, marker: str) -> Any:
    start = text.find(marker)
    if start < 0:
        return None
    eq = text.find("=", start)
    if eq < 0:
        return None
    i = eq + 1
    while i < len(text) and text[i].isspace():
        i += 1
    if i >= len(text) or text[i] not in "[{":
        return None
    opening = text[i]
    closing = "}" if opening == "{" else "]"
    depth = 0
    in_string = False
    string_delim = ""
    escape = False
    for j in range(i, len(text)):
        ch = text[j]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == string_delim:
                in_string = False
            continue
        if ch in ("'", '"'):
            in_string = True
            string_delim = ch
            continue
        if ch == opening:
            depth += 1
        elif ch == closing:
            depth -= 1
            if depth == 0:
                return ast.literal_eval(text[i : j + 1])
    return None


def _extract_fallback_asset_types(text: str) -> List[Dict[str, Any]]:
    match = re.search(r"""echo\s+'(\{"results":\[.*?\]\})'""", text, re.DOTALL)
    if not match:
        return []
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []
    return payload.get("results", [])


def _load_metamodel_extracts() -> Dict[str, Any]:
    script_text = _METAMODEL_SCRIPT.read_text(encoding="utf-8")
    asset_types = _extract_fallback_asset_types(script_text)
    classifications = _extract_python_literal(script_text, "classifications")
    orm_facts = _extract_python_literal(script_text, "orm_facts")

    xml_asset_types: List[str] = []
    if _MODEL_XML.exists():
        root = ET.parse(_MODEL_XML).getroot()
        xml_asset_types.extend(
            elem.get("assetType", "").strip()
            for elem in root.findall(".//collibra-ref")
            if elem.get("assetType")
        )
        xml_asset_types.extend(
            elem.get("assetType", "").strip()
            for elem in root.findall(".//collibra-catalog/asset")
            if elem.get("assetType")
        )
        xml_asset_types.extend(
            elem.get("name", "").strip()
            for elem in root.findall(".//mock-data/assets/asset-types/type")
            if elem.get("name")
        )

    merged_asset_types: Dict[str, Dict[str, Any]] = {}
    for item in asset_types:
        name = item.get("name")
        if name:
            merged_asset_types[_normalize_label(name)] = item
    for name in xml_asset_types:
        key = _normalize_label(name)
        merged_asset_types.setdefault(key, {"name": name})

    return {
        "asset_types": sorted(merged_asset_types.values(), key=lambda item: item.get("name", "")),
        "classifications": classifications or {},
        "orm_facts": orm_facts or [],
        "sources": {
            "script": str(_METAMODEL_SCRIPT),
            "model_xml": str(_MODEL_XML),
        },
    }


def _parse_scope_assignment(value: str) -> Dict[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("scope assignment must use NAME=VALUE")
    name, assigned = value.split("=", 1)
    name = name.strip()
    assigned = assigned.strip()
    if not name or not assigned:
        raise argparse.ArgumentTypeError("scope assignment must use NAME=VALUE")
    return {"name": name, "value": assigned}


def _parse_attribute_binding(value: str) -> Dict[str, str]:
    parts = [part.strip() for part in value.split(":", 1)]
    name = parts[0]
    if not name:
        raise argparse.ArgumentTypeError("attribute binding requires ATTRIBUTE[:CSV_HEADER]")
    return {"name": name, "csv_header": parts[1] if len(parts) > 1 and parts[1] else _slug(name)}


def _parse_relation_binding(value: str) -> Dict[str, str]:
    parts = [part.strip() for part in value.split(":")]
    if len(parts) not in {3, 4} or not all(parts[:3]):
        raise argparse.ArgumentTypeError(
            "relation binding requires SUBJECT:VERB:OBJECT[:CSV_HEADER]"
        )
    subject, verb, obj = parts[:3]
    csv_header = parts[3] if len(parts) == 4 and parts[3] else _slug(f"{verb}_{obj}")
    return {"subject": subject, "verb": verb, "object": obj, "csv_header": csv_header}


def _discover_view_configs(
    *,
    domain_id: Optional[str],
    location: Optional[str],
    limit: int,
) -> Dict[str, Any]:
    from .rest import check_env, fetch_views

    env = check_env()
    if not env.get("ok"):
        return {
            "available": False,
            "reason": "; ".join(env.get("issues", [])),
            "domain": [],
            "global": [],
        }

    try:
        response = fetch_views(location=location, limit=limit)
    except Exception as exc:
        return {
            "available": False,
            "reason": str(exc),
            "domain": [],
            "global": [],
        }

    def matches_domain(view: Dict[str, Any]) -> bool:
        if not domain_id:
            return False
        tokens = {
            str(view.get("domainId", "")),
            str(view.get("resourceId", "")),
            str((view.get("scope") or {}).get("domainId", "")),
        }
        return domain_id in tokens

    def is_global(view: Dict[str, Any]) -> bool:
        return not any(
            [
                view.get("domainId"),
                view.get("resourceId"),
                (view.get("scope") or {}).get("domainId"),
            ]
        )

    raw_views = response.get("data", [])
    domain_views = [view for view in raw_views if matches_domain(view)]
    global_views = [view for view in raw_views if is_global(view)]
    return {
        "available": True,
        "reason": "",
        "domain": domain_views,
        "global": global_views,
    }


def _view_summary(view: Dict[str, Any]) -> Dict[str, Any]:
    name = view.get("name") or view.get("displayName") or view.get("resourceName") or "unnamed-view"
    return {
        "id": view.get("id"),
        "name": name,
        "type": view.get("type") or view.get("resourceType") or "view",
        "domain_id": view.get("domainId") or (view.get("scope") or {}).get("domainId"),
    }


def _infer_driver_columns(views: Sequence[Dict[str, Any]]) -> List[str]:
    columns: List[str] = []
    seen: set[str] = set()
    for view in views:
        for key in ("columns", "columnConfigs", "displayedColumns", "fields"):
            raw = view.get(key)
            if not isinstance(raw, list):
                continue
            for item in raw:
                label = ""
                if isinstance(item, str):
                    label = item
                elif isinstance(item, dict):
                    label = (
                        item.get("name")
                        or item.get("header")
                        or item.get("label")
                        or item.get("field")
                        or item.get("id")
                        or ""
                    )
                if label and label not in seen:
                    columns.append(label)
                    seen.add(label)
    return columns


def _find_asset_type(asset_types: Sequence[Dict[str, Any]], asset_type_name: str) -> Optional[Dict[str, Any]]:
    target = _normalize_label(asset_type_name)
    for item in asset_types:
        if _normalize_label(str(item.get("name", ""))) == target:
            return item
    return None


def _infer_relations_for_asset_type(
    orm_facts: Sequence[Dict[str, Any]],
    asset_type_name: str,
) -> List[Dict[str, str]]:
    target = _normalize_label(asset_type_name)
    inferred: List[Dict[str, str]] = []
    for fact in orm_facts:
        subject = str(fact.get("subject", ""))
        obj = str(fact.get("object", ""))
        if _normalize_label(subject) != target:
            continue
        verb = str(fact.get("verb", "relatedTo"))
        header_seed = obj
        inferred.append(
            {
                "subject": subject,
                "verb": verb,
                "object": obj,
                "csv_header": _slug(header_seed),
            }
        )
    return inferred


def _dedupe_column_headers(columns: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    counters: Dict[str, int] = {}
    deduped: List[Dict[str, Any]] = []
    for column in columns:
        updated = dict(column)
        base = str(updated.get("csv_header") or "column")
        count = counters.get(base, 0)
        updated["csv_header"] = base if count == 0 else f"{base}_{count + 1}"
        counters[base] = count + 1
        deduped.append(updated)
    return deduped


def _render_csv_headers(columns: Sequence[Dict[str, Any]]) -> List[str]:
    return [str(column.get("csv_header")) for column in columns]


def _render_sample_row(columns: Sequence[Dict[str, Any]], scope: Optional[Dict[str, str]]) -> Dict[str, str]:
    row: Dict[str, str] = {}
    for column in columns:
        binding = column.get("binding", {})
        csv_header = str(column.get("csv_header"))
        if binding.get("type") == "system" and binding.get("name") == "name":
            row[csv_header] = "Example Asset"
        elif binding.get("type") == "system" and binding.get("name") == "description":
            row[csv_header] = "Imported from CSV"
        elif binding.get("type") == "attribute":
            row[csv_header] = f"example_{_slug(str(binding.get('name', 'value')))}"
        elif binding.get("type") == "relation":
            row[csv_header] = f"lookup:{binding.get('object')}"
        elif binding.get("type") == "scope" and scope:
            row[csv_header] = scope.get("value", "")
    return row


def _snapshot_or_error(path: Optional[str]) -> MetamodelSnapshot:
    return load_snapshot(path)


def _edge_tcp_probe(namespace: str, component: str, host: str, port: int) -> Dict[str, Any]:
    snippet = (
        "if command -v nc >/dev/null 2>&1; then "
        f"nc -z -w 3 {host} {port}; "
        "elif command -v busybox >/dev/null 2>&1; then "
        f"busybox nc -z -w 3 {host} {port}; "
        "elif command -v python3 >/dev/null 2>&1; then "
        f"python3 -c \"import socket; socket.create_connection(({host!r}, {port}), 3); print('connected')\"; "
        "else "
        "echo 'no tcp probe tool available in edge runtime' >&2; exit 127; "
        "fi"
    )
    return _kubectl_exec(namespace, component, snippet)


def cmd_collibra_io_edge_connection_probe_postgres(args: argparse.Namespace) -> int:
    driver = _driver_path(args.driver_version)
    local_jdbc = f"jdbc:postgresql://{args.local_host}:{args.port}/{args.database}"
    edge_jdbc = f"jdbc:postgresql://{args.edge_host}:{args.port}/{args.database}"

    docker_status = _docker_ps(args.container)
    local_socket_ok, local_socket_detail = _tcp_probe(args.local_host, args.port)
    local_db = _docker_psql(
        args.container,
        args.user,
        args.database,
        "select current_database(), current_user;"
    ) if docker_status.get("ok") else {"ok": False, "stderr": docker_status.get("error", "")}

    edge_dns = _kubectl_exec(
        args.namespace,
        args.component,
        f"getent hosts {args.edge_host} || cat /etc/hosts | grep {args.edge_host} || true",
    )
    edge_tcp = _edge_tcp_probe(args.namespace, args.component, args.edge_host, args.port)
    edge_tcp_available = edge_tcp.get("exit_code") != 127
    jobs = _kubectl_get_jobs(args.namespace)
    edge_logs = _kubectl_logs(args.namespace, args.component, tail=500)
    log_text = edge_logs.get("stdout", "")
    edge_received_connection = args.connection_id in log_text if args.connection_id else "Connections currently present in CDIP:" in log_text
    edge_create_secret_seen = "CreateOrUpdateSecret" in log_text
    edge_run_capability_seen = "RunCapability" in log_text or "Dispatching 'RunCapability'" in log_text

    payload = {
        "ok": True,
        "command": "collibra io edge connection probe postgres",
        "connection_name": args.name,
        "connection_id": args.connection_id,
        "local_jdbc_url": local_jdbc,
        "edge_jdbc_url": edge_jdbc,
        "driver": {
            "version": args.driver_version,
            "path": str(driver),
            "cached": driver.exists(),
        },
        "local": {
            "docker_container": docker_status,
            "socket_probe": {"ok": local_socket_ok, "detail": local_socket_detail},
            "database_probe": local_db,
        },
        "edge_runtime": {
            "namespace": args.namespace,
            "component": args.component,
            "dns_probe": edge_dns,
            "tcp_probe": edge_tcp,
            "tcp_probe_available": edge_tcp_available,
            "jobs": jobs,
            "received_connection_secret": edge_received_connection,
            "create_or_update_secret_seen": edge_create_secret_seen,
            "run_capability_seen": edge_run_capability_seen,
        },
        "api_support": {
            "remote_connection_create": False,
            "reason": "No supported public REST path has been established yet for creating Edge connections directly; use UI or later-validated internal APIs.",
        },
        "recommendation": [],
    }

    recs: List[str] = payload["recommendation"]
    if not local_socket_ok:
        recs.append("Fix workstation reachability to the PostgreSQL port before testing through Edge.")
    if not local_db.get("ok"):
        recs.append("Fix PostgreSQL authentication or database existence before testing through Edge.")
    if not driver.exists():
        recs.append("Cache the pgJDBC driver first with: singine collibra edge create datasource connection --download-driver")
    if edge_dns.get("ok") and edge_tcp_available and not edge_tcp.get("ok"):
        recs.append("Edge resolves the PostgreSQL host, but cannot open the TCP port yet. Check host mapping, port exposure, and local firewall rules.")
    if edge_dns.get("ok") and not edge_tcp_available:
        recs.append("Edge resolves the PostgreSQL host. TCP preflight from the controller container is unavailable because the runtime image does not ship a generic probe tool.")
    if edge_dns.get("ok") and edge_received_connection and not edge_run_capability_seen:
        recs.append("The connection secret reached Edge, but no capability test was dispatched yet. Re-run the UI test action.")
    if not edge_received_connection:
        recs.append("The connection secret is not visible in Edge controller logs yet. Save or refresh the connection in Collibra first.")
    if not recs:
        recs.append("The local data plane looks ready. Trigger a real Collibra Edge connection test next.")

    if args.json:
        print(json.dumps(payload))
        return 0

    print(f"[collibra io edge connection probe postgres] name={args.name}")
    print(f"  JDBC (Edge):   {edge_jdbc}")
    print(f"  JDBC (local):  {local_jdbc}")
    print(f"  Driver cache:  {'yes' if driver.exists() else 'no'}  {driver}")
    print(f"  Local socket:  {'ok' if local_socket_ok else 'fail'}  {local_socket_detail}")
    print(f"  Local DB:      {'ok' if local_db.get('ok') else 'fail'}  {local_db.get('stdout') or local_db.get('stderr', '')}")
    print(f"  Edge DNS:      {'ok' if edge_dns.get('ok') else 'fail'}  {edge_dns.get('stdout') or edge_dns.get('stderr', '')}")
    if edge_tcp_available:
        print(f"  Edge TCP:      {'ok' if edge_tcp.get('ok') else 'fail'}  {edge_tcp.get('stdout') or edge_tcp.get('stderr', '') or 'connected'}")
    else:
        print(f"  Edge TCP:      unavailable  {edge_tcp.get('stderr', '') or 'no generic TCP probe tool in edge-controller image'}")
    print(f"  Edge secret:   {'seen' if edge_received_connection else 'not-seen'}")
    print(f"  Edge command:  CreateOrUpdateSecret={'yes' if edge_create_secret_seen else 'no'}  RunCapability={'yes' if edge_run_capability_seen else 'no'}")
    if jobs.get("ok"):
        print(f"  Edge jobs:     {jobs.get('stdout') or 'none'}")
    print("  Next:")
    for item in recs:
        print(f"    - {item}")
    return 0


def cmd_collibra_io_create_community(args: argparse.Namespace) -> int:
    from .rest import create_community

    name = args.top_level or args.name
    if not name:
        print(json.dumps({"ok": False, "error": "Provide --name or -topLevel/--top-level"}))
        return 1
    try:
        return _collibra_ok(
            create_community(
                name=name,
                description=getattr(args, "description", None),
                parent_id=getattr(args, "parent_id", None),
            ),
            args,
        )
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1


def cmd_collibra_io_create_template(args: argparse.Namespace) -> int:
    snapshot: Optional[MetamodelSnapshot] = None
    asset_type_name = args.asset_type
    snapshot_error = ""
    try:
        snapshot = _snapshot_or_error(getattr(args, "metamodel_root", None))
        asset_type_model = snapshot.asset_type(args.asset_type)
        if asset_type_model is not None:
            asset_type_name = asset_type_model.name
    except Exception as exc:
        snapshot_error = str(exc)

    extracts = _load_metamodel_extracts()
    asset_type = _find_asset_type(extracts["asset_types"], asset_type_name)
    if asset_type is None and snapshot is None:
        payload = {
            "ok": False,
            "error": f"Unknown asset type: {args.asset_type}",
            "known_asset_types": [item.get("name") for item in extracts["asset_types"]],
            "metamodel_error": snapshot_error,
        }
        print(json.dumps(payload, indent=2))
        return 1
    if asset_type is None:
        asset_type = {"id": getattr(asset_type_model, "id", ""), "name": asset_type_name}

    scope_assignment = args.scope_attribute
    view_configs = _discover_view_configs(
        domain_id=args.domain_id,
        location=args.location,
        limit=args.view_limit,
    )
    disk_views: List[Dict[str, Any]] = []
    if snapshot is not None:
        disk_views = [
            {
                "id": view.id,
                "name": view.name,
                "location": view.location,
                "type": view.view_type,
                "columns": view.driver_columns(),
            }
            for view in snapshot.view_candidates(asset_type["name"])
        ]
    driver_views = disk_views + view_configs["domain"] + view_configs["global"]
    driver_columns = _infer_driver_columns(driver_views)

    if args.relation:
        relations = args.relation
    elif snapshot is not None and snapshot.asset_type(asset_type["name"]) and snapshot.asset_type(asset_type["name"]).assignment:
        relations = [
            {
                "subject": asset_type["name"],
                "verb": relation.public_id or relation.name,
                "object": relation.peer_asset_type(asset_type["name"]) or relation.name,
                "csv_header": _slug(relation.peer_asset_type(asset_type["name"]) or relation.public_id or relation.name),
            }
            for relation in snapshot.asset_type(asset_type["name"]).assignment.relation_characteristics()
        ]
    else:
        relations = _infer_relations_for_asset_type(extracts["orm_facts"], asset_type["name"])

    if args.attribute:
        attributes = args.attribute
    elif snapshot is not None and snapshot.asset_type(asset_type["name"]) and snapshot.asset_type(asset_type["name"]).assignment:
        attributes = [
            {
                "name": attribute.public_id or attribute.name,
                "csv_header": _slug(attribute.public_id or attribute.name),
            }
            for attribute in snapshot.asset_type(asset_type["name"]).assignment.attribute_characteristics()
            if (attribute.public_id or attribute.name).lower() not in {"description"}
        ]
    else:
        attributes = []

    columns: List[Dict[str, Any]] = [
        {
            "csv_header": "name",
            "binding": {"type": "system", "name": "name"},
            "required": True,
        },
        {
            "csv_header": "description",
            "binding": {"type": "system", "name": "description"},
            "required": False,
        },
    ]
    if scope_assignment:
        columns.append(
            {
                "csv_header": _slug(scope_assignment["name"]),
                "binding": {
                    "type": "scope",
                    "name": scope_assignment["name"],
                    "value": scope_assignment["value"],
                },
                "required": True,
            }
        )
    for attribute in attributes:
        columns.append(
            {
                "csv_header": attribute["csv_header"],
                "binding": {"type": "attribute", "name": attribute["name"]},
                "required": False,
            }
        )
    for relation in relations:
        columns.append(
            {
                "csv_header": relation["csv_header"],
                "binding": {
                    "type": "relation",
                    "subject": relation["subject"],
                    "verb": relation["verb"],
                    "object": relation["object"],
                },
                "required": False,
            }
        )
    columns = _dedupe_column_headers(columns)

    payload = {
        "ok": True,
        "command": "collibra io create template",
        "template_kind": "collibra-csv-import",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "template": {
            "name": args.name,
            "asset_type": asset_type["name"],
            "domain_id": args.domain_id,
            "view": {
                "name": args.view_name or f"{args.name} Import View",
                "location": args.location,
                "driver_column_order": driver_columns,
                "scope": {
                    "attribute_assignment": scope_assignment,
                    "relation_assignments": relations,
                },
                "columns": columns,
            },
            "csv": {
                "delimiter": args.delimiter,
                "headers": _render_csv_headers(columns),
                "sample_row": _render_sample_row(columns, scope_assignment),
            },
            "import": {
                "mode": "upsert-by-name-with-scoped-assignments",
                "driver_view_precedence": ["domain", "global"],
                "metamodel_sources": extracts["sources"],
                "metamodel_export_root": str(snapshot.root) if snapshot is not None else None,
            },
        },
        "driver": {
            "view_configs": {
                "available": view_configs["available"],
                "reason": view_configs["reason"],
                "disk": [_view_summary(view) for view in disk_views],
                "domain": [_view_summary(view) for view in view_configs["domain"]],
                "global": [_view_summary(view) for view in view_configs["global"]],
            },
            "metamodel": {
                "asset_type": asset_type,
                "classification": extracts["classifications"].get(asset_type["name"]),
                "inferred_relations": _infer_relations_for_asset_type(
                    extracts["orm_facts"],
                    asset_type["name"],
                ),
                "snapshot_loaded": snapshot is not None,
                "snapshot_error": snapshot_error,
            },
        },
    }

    output_path = Path(args.output).expanduser() if args.output else None
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(json.dumps({"ok": True, "output": str(output_path), "template": payload["template"]["name"]}))
        return 0

    print(json.dumps(payload, indent=2))
    return 0


def cmd_collibra_io_metamodel_status(args: argparse.Namespace) -> int:
    try:
        snapshot = _snapshot_or_error(args.root)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1
    payload = {
        "ok": True,
        "command": "collibra io metamodel status",
        "root": str(snapshot.root),
        "version": snapshot.version,
        "stats": snapshot.stats,
        "asset_type_examples": sorted(item.name for item in list(snapshot.asset_types.values())[:10]),
    }
    print(json.dumps(payload, indent=2))
    return 0


def cmd_collibra_io_metamodel_visualize(args: argparse.Namespace) -> int:
    try:
        snapshot = _snapshot_or_error(args.root)
        if args.format == "mermaid":
            payload = snapshot.to_mermaid(asset_type_name=args.asset_type) if args.asset_type else snapshot.to_mermaid_landscape()
        else:
            if args.asset_type:
                asset_type = snapshot.asset_type(args.asset_type)
                if asset_type is None:
                    raise KeyError(args.asset_type)
                payload = {
                    "ok": True,
                    "command": "collibra io metamodel visualize",
                    "root": str(snapshot.root),
                    "asset_type": asset_type.as_opmodel(),
                    "views": [
                        {
                            "id": view.id,
                            "name": view.name,
                            "location": view.location,
                            "type": view.view_type,
                            "assignment_asset_types": view.assignment_asset_types,
                        }
                        for view in snapshot.view_candidates(asset_type.name)
                    ],
                }
            else:
                payload = {
                    "ok": True,
                    "command": "collibra io metamodel visualize",
                    "root": str(snapshot.root),
                    "version": snapshot.version,
                    "stats": snapshot.stats,
                    "asset_types": [item.as_opmodel() for item in sorted(snapshot.asset_types.values(), key=lambda x: x.name)],
                    "views": [
                        {
                            "id": view.id,
                            "name": view.name,
                            "location": view.location,
                            "type": view.view_type,
                            "assignment_asset_types": view.assignment_asset_types,
                        }
                        for view in sorted(snapshot.views.values(), key=lambda x: x.name)
                    ],
                }
        if args.output:
            out = Path(args.output).expanduser()
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(payload if isinstance(payload, str) else json.dumps(payload, indent=2), encoding="utf-8")
            print(json.dumps({"ok": True, "output": str(out)}, indent=2))
            return 0
        print(payload if isinstance(payload, str) else json.dumps(payload, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1


def cmd_collibra_io_metamodel_export(args: argparse.Namespace) -> int:
    try:
        snapshot = _snapshot_or_error(args.root)
        if args.format == "opmodel":
            payload = snapshot.to_opmodel(asset_type_name=args.asset_type)
        else:
            asset_type = snapshot.asset_type(args.asset_type) if args.asset_type else None
            if args.format == "template":
                ns = argparse.Namespace(
                    name=args.name or f"{(asset_type.name if asset_type else 'collibra')}-import",
                    asset_type=asset_type.name if asset_type else args.asset_type,
                    view_name=args.view_name,
                    domain_id=args.domain_id,
                    location=args.location,
                    scope_attribute=None,
                    attribute=None,
                    relation=None,
                    view_limit=args.view_limit,
                    delimiter=args.delimiter,
                    output=args.output,
                    metamodel_root=args.root,
                )
                return cmd_collibra_io_create_template(ns)
            raise ValueError(f"Unsupported export format: {args.format}")
        if args.output:
            out = Path(args.output).expanduser()
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            print(json.dumps({"ok": True, "output": str(out)}, indent=2))
            return 0
        print(json.dumps(payload, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1


def cmd_collibra_io_edge_datasource_diagnose(args: argparse.Namespace) -> int:
    secrets = _kubectl_get_secrets(args.namespace)
    jobs = _kubectl_get_jobs(args.namespace)
    edge_logs = _kubectl_logs(args.namespace, args.component, tail=args.tail)
    log_text = edge_logs.get("stdout", "")

    secret_lines = [line for line in (secrets.get("stdout") or "").splitlines() if line.strip()]
    secret_names = [line.split()[0] for line in secret_lines if line.split()]
    connection_secret_present = args.id in secret_names

    non_system_secret_names = [
        name for name in secret_names
        if name not in {args.id, "blue-key", "collibra-edge-repo-creds", "edge-repositories", "edge-secret"}
        and not name.startswith("sh.helm.release.")
    ]
    capability_list_lines = [
        line for line in log_text.splitlines() if "Capabilities currently present in CDIP:" in line
    ]
    capability_inventory = capability_list_lines[-1] if capability_list_lines else ""
    capability_inventory_empty = "Capabilities currently present in CDIP: []" in capability_inventory if capability_inventory else False

    connection_list_lines = [
        line for line in log_text.splitlines() if "Connections currently present in CDIP:" in line
    ]
    run_capability_lines = [
        line for line in log_text.splitlines() if "RunCapability" in line
    ]
    create_secret_lines = [
        line for line in log_text.splitlines() if "CreateOrUpdateSecret" in line
    ]
    datasource_mentions = [line for line in log_text.splitlines() if args.id in line]
    connection_inventory = connection_list_lines[-1] if connection_list_lines else ""

    capability_ids = re.findall(
        r"Capabilities currently present in CDIP: \[([^\]]*)\]",
        capability_inventory,
    )
    capability_secret_names = []
    if capability_ids:
        capability_secret_names = [item.strip() for item in capability_ids[-1].split(",") if item.strip()]
    elif not capability_inventory_empty:
        capability_secret_names = non_system_secret_names

    connection_ids = re.findall(
        r"Connections currently present in CDIP: \[([^\]]*)\]",
        connection_inventory,
    )
    if connection_ids and capability_secret_names:
        excluded = {item.strip() for item in connection_ids[-1].split(",") if item.strip()}
        capability_secret_names = [name for name in capability_secret_names if name not in excluded]

    capability_secret_present = bool(capability_secret_names)

    payload = {
        "ok": True,
        "command": "collibra io edge datasource diagnose",
        "datasource_id": args.id,
        "namespace": args.namespace,
        "component": args.component,
        "connection_secret_present": connection_secret_present,
        "capability_secret_present": capability_secret_present,
        "capability_secret_names": capability_secret_names,
        "jobs": jobs.get("stdout", ""),
        "controller": {
            "create_or_update_secret_seen": bool(create_secret_lines),
            "run_capability_seen": bool(run_capability_lines),
            "connection_inventory": connection_inventory,
            "capability_inventory": capability_inventory,
            "datasource_mentions": datasource_mentions[-5:],
        },
        "recommendation": [],
    }

    recs: List[str] = payload["recommendation"]
    if not connection_secret_present:
        recs.append("The datasource connection secret is absent from Edge. Save the datasource in Collibra first.")
    if connection_secret_present and not capability_secret_present:
        recs.append("The datasource exists on Edge, but no capability instance is present. Finish the JDBC metadata capability assignment in Collibra.")
    if connection_secret_present and capability_secret_present and not run_capability_lines:
        recs.append("A capability appears to exist, but no run was dispatched yet. Trigger List databases or Test connection again.")
    if capability_inventory_empty:
        recs.append("Edge reports zero capability instances in CDIP. This matches Collibra's noCapabilityInstancesFound error.")
    if jobs.get("ok") and not (jobs.get("stdout") or "").strip():
        recs.append("No Edge jobs are currently present. A real metadata call has not launched a job.")
    if not recs:
        recs.append("Datasource wiring looks present. Inspect the next dispatched job for the actual JDBC outcome.")

    if args.json:
        print(json.dumps(payload))
        return 0

    print(f"[collibra io edge datasource diagnose] id={args.id}")
    print(f"  Connection secret:   {'yes' if connection_secret_present else 'no'}")
    print(f"  Capability secret:   {'yes' if capability_secret_present else 'no'}")
    if payload["capability_secret_names"]:
        print(f"  Capability names:    {', '.join(payload['capability_secret_names'])}")
    print(f"  Controller inventory:")
    print(f"    Connections: {payload['controller']['connection_inventory'] or 'n/a'}")
    print(f"    Capabilities: {payload['controller']['capability_inventory'] or 'n/a'}")
    print(f"  Controller events:   CreateOrUpdateSecret={'yes' if payload['controller']['create_or_update_secret_seen'] else 'no'}  RunCapability={'yes' if payload['controller']['run_capability_seen'] else 'no'}")
    print(f"  Edge jobs:           {jobs.get('stdout') or 'none'}")
    print("  Next:")
    for item in recs:
        print(f"    - {item}")
    return 0


def add_collibra_io_parser(collibra_sub: argparse._SubParsersAction) -> None:
    io_parser = collibra_sub.add_parser(
        "io",
        help="Governed I/O workflows around the Collibra platform",
    )
    io_parser.set_defaults(func=lambda a: (io_parser.print_help(), 1)[1])
    io_sub = io_parser.add_subparsers(dest="collibra_io_subject")

    create_parser = io_sub.add_parser(
        "create",
        help="Create Collibra resources through governed I/O workflows",
    )
    create_parser.set_defaults(func=lambda a: (create_parser.print_help(), 1)[1])
    create_sub = create_parser.add_subparsers(dest="collibra_io_create_subject")

    community_parser = create_sub.add_parser(
        "community",
        help="Create a Collibra community",
    )
    community_parser.add_argument("--name", help="Community name")
    community_parser.add_argument("-topLevel", dest="top_level", help="Create a top-level community with this name")
    community_parser.add_argument("--top-level", dest="top_level", help="Create a top-level community with this name")
    community_parser.add_argument("--description", help="Community description")
    community_parser.add_argument("--parent-id", help="Parent community UUID for a sub-community")
    community_parser.add_argument("--json", action="store_true", default=True)
    community_parser.set_defaults(func=cmd_collibra_io_create_community)

    template_parser = create_sub.add_parser(
        "template",
        help="Generate a CSV import template and view specification from the Collibra metamodel and available ViewConfigs",
    )
    template_parser.add_argument("--name", required=True, help="Logical template name")
    template_parser.add_argument("--asset-type", required=True, help="Collibra asset type to import, e.g. 'Business Term'")
    template_parser.add_argument("--view-name", help="Explicit ViewConfig name to emit in the template")
    template_parser.add_argument("--domain-id", help="Domain UUID whose ViewConfigs should override global ones")
    template_parser.add_argument("--location", default="catalog", help="View location filter for Collibra /views lookup (default: catalog)")
    template_parser.add_argument("--scope-attribute", type=_parse_scope_assignment, help="Scoped assignment applied to each imported row, in NAME=VALUE form")
    template_parser.add_argument("--attribute", action="append", type=_parse_attribute_binding, help="Attribute binding in ATTRIBUTE[:CSV_HEADER] form; repeatable")
    template_parser.add_argument("--relation", action="append", type=_parse_relation_binding, help="Relation binding in SUBJECT:VERB:OBJECT[:CSV_HEADER] form; repeatable")
    template_parser.add_argument("--view-limit", type=int, default=100, help="Maximum number of ViewConfigs to inspect when Collibra access is configured")
    template_parser.add_argument("--delimiter", default=",", help="CSV delimiter to encode in the template (default: ,)")
    template_parser.add_argument("--output", help="Write the generated template JSON to this path")
    template_parser.add_argument("--metamodel-root", default=str(DEFAULT_METAMODEL_ROOT), help="Path to the exported Collibra metamodel package root")
    template_parser.set_defaults(func=cmd_collibra_io_create_template)

    metamodel_parser = io_sub.add_parser(
        "metamodel",
        help="Load, visualize, and export the Collibra metamodel in a Singine-friendly form",
    )
    metamodel_parser.set_defaults(func=lambda a: (metamodel_parser.print_help(), 1)[1])
    metamodel_sub = metamodel_parser.add_subparsers(dest="collibra_io_metamodel_action")

    metamodel_status_parser = metamodel_sub.add_parser(
        "status",
        help="Summarize the exported Collibra metamodel package on disk",
    )
    metamodel_status_parser.add_argument("--root", default=str(DEFAULT_METAMODEL_ROOT), help="Path to the metamodel export root")
    metamodel_status_parser.set_defaults(func=cmd_collibra_io_metamodel_status)

    metamodel_visualize_parser = metamodel_sub.add_parser(
        "visualize",
        help="Visualize one asset type and its assigned relations",
    )
    metamodel_visualize_parser.add_argument("--asset-type", help="Asset type name or publicId; omit for the full metamodel landscape")
    metamodel_visualize_parser.add_argument("--root", default=str(DEFAULT_METAMODEL_ROOT), help="Path to the metamodel export root")
    metamodel_visualize_parser.add_argument("--format", default="json", choices=["json", "mermaid"], help="Visualization output format")
    metamodel_visualize_parser.add_argument("--output", help="Write the visualization output to this path")
    metamodel_visualize_parser.set_defaults(func=cmd_collibra_io_metamodel_visualize)

    metamodel_export_parser = metamodel_sub.add_parser(
        "export",
        help="Export the metamodel as Singine opmodel JSON or as a CSV import template",
    )
    metamodel_export_parser.add_argument("--root", default=str(DEFAULT_METAMODEL_ROOT), help="Path to the metamodel export root")
    metamodel_export_parser.add_argument("--format", default="opmodel", choices=["opmodel", "template"], help="Export format")
    metamodel_export_parser.add_argument("--asset-type", help="Restrict the export to one asset type")
    metamodel_export_parser.add_argument("--name", help="Template name when --format template is used")
    metamodel_export_parser.add_argument("--view-name", help="Explicit view name when --format template is used")
    metamodel_export_parser.add_argument("--domain-id", help="Domain UUID for live ViewConfig discovery")
    metamodel_export_parser.add_argument("--location", default="catalog", help="View location for live ViewConfig discovery")
    metamodel_export_parser.add_argument("--view-limit", type=int, default=100, help="Maximum number of live ViewConfigs to inspect")
    metamodel_export_parser.add_argument("--delimiter", default=",", help="CSV delimiter when --format template is used")
    metamodel_export_parser.add_argument("--output", help="Write the export to this path")
    metamodel_export_parser.set_defaults(func=cmd_collibra_io_metamodel_export)

    chip_parser = io_sub.add_parser(
        "chip",
        help="Use the Collibra CHIP MCP server as the default governed Collibra I/O backend",
    )
    chip_parser.set_defaults(func=lambda a: (chip_parser.print_help(), 1)[1])
    chip_sub = chip_parser.add_subparsers(dest="collibra_io_chip_subject")

    status_parser = chip_sub.add_parser(
        "status",
        help="Validate the local CHIP binary, client wiring, and stdio startup probe",
    )
    status_parser.add_argument(
        "--binary",
        default="~/ws/github/collibra/chip/.build/chip",
        help="Path to the source-built chip binary",
    )
    status_parser.add_argument("--json", action="store_true")
    status_parser.set_defaults(func=cmd_collibra_io_chip_status)

    configure_parser = chip_sub.add_parser(
        "configure",
        help="Wire Codex and/or Claude to the source-built CHIP binary",
    )
    configure_parser.add_argument("client", choices=["codex", "claude", "all"], help="Client to configure")
    configure_parser.add_argument(
        "--binary",
        default="~/ws/github/collibra/chip/.build/chip",
        help="Path to the source-built chip binary",
    )
    configure_parser.add_argument("--json", action="store_true")
    configure_parser.set_defaults(func=cmd_collibra_io_chip_configure)

    tools_parser = chip_sub.add_parser(
        "tools",
        help="Inspect tool metadata exposed by CHIP",
    )
    tools_parser.set_defaults(func=lambda a: (tools_parser.print_help(), 1)[1])
    tools_sub = tools_parser.add_subparsers(dest="collibra_io_chip_tools_action")

    tools_list_parser = tools_sub.add_parser(
        "list",
        help="Start CHIP briefly and list the tools it registers",
    )
    tools_list_parser.add_argument(
        "--binary",
        default="~/ws/github/collibra/chip/.build/chip",
        help="Path to the source-built chip binary",
    )
    tools_list_parser.add_argument("--json", action="store_true")
    tools_list_parser.set_defaults(func=cmd_collibra_io_chip_tools_list)

    edge_parser = io_sub.add_parser(
        "edge",
        help="Collibra Edge I/O workflows",
    )
    edge_parser.set_defaults(func=lambda a: (edge_parser.print_help(), 1)[1])
    edge_sub = edge_parser.add_subparsers(dest="collibra_io_edge_subject")

    connection_parser = edge_sub.add_parser(
        "connection",
        help="Inspect and preflight Edge connections before using the Collibra UI",
    )
    connection_parser.set_defaults(func=lambda a: (connection_parser.print_help(), 1)[1])
    connection_sub = connection_parser.add_subparsers(dest="collibra_io_edge_connection_action")

    probe_parser = connection_sub.add_parser(
        "probe-postgres",
        help="Preflight a PostgreSQL-backed Edge connection from the workstation and the live Edge runtime",
    )
    probe_parser.add_argument("--name", default="sindoc-singine-pg-dev-101", help="Logical connection name for reporting")
    probe_parser.add_argument("--connection-id", help="Collibra connection UUID if known")
    probe_parser.add_argument("--container", default=_DEFAULT_PG_CONTAINER, help=f"Docker PostgreSQL container name (default: {_DEFAULT_PG_CONTAINER})")
    probe_parser.add_argument("--edge-host", default=_DEFAULT_EDGE_HOST, help=f"Host visible from Edge (default: {_DEFAULT_EDGE_HOST})")
    probe_parser.add_argument("--local-host", default=_DEFAULT_LOCAL_HOST, help=f"Host visible from the local workstation (default: {_DEFAULT_LOCAL_HOST})")
    probe_parser.add_argument("--port", type=int, default=_DEFAULT_PG_PORT, help=f"PostgreSQL port (default: {_DEFAULT_PG_PORT})")
    probe_parser.add_argument("--database", default=_DEFAULT_PG_DATABASE, help=f"Database name (default: {_DEFAULT_PG_DATABASE})")
    probe_parser.add_argument("--user", default=_DEFAULT_PG_USER, help=f"Database user (default: {_DEFAULT_PG_USER})")
    probe_parser.add_argument("--password", default=_DEFAULT_PG_PASSWORD, help=f"Database password (default: {_DEFAULT_PG_PASSWORD})")
    probe_parser.add_argument("--driver-version", default=_DEFAULT_DRIVER_VERSION, help=f"pgJDBC version to expect in cache (default: {_DEFAULT_DRIVER_VERSION})")
    probe_parser.add_argument("--namespace", default=_DEFAULT_EDGE_NAMESPACE, help=f"Kubernetes namespace (default: {_DEFAULT_EDGE_NAMESPACE})")
    probe_parser.add_argument("--component", default=_DEFAULT_EDGE_COMPONENT, help=f"Edge deployment to inspect (default: {_DEFAULT_EDGE_COMPONENT})")
    probe_parser.add_argument("--json", action="store_true")
    probe_parser.set_defaults(func=cmd_collibra_io_edge_connection_probe_postgres)

    datasource_parser = edge_sub.add_parser(
        "datasource",
        help="Diagnose datasource wiring between Collibra and the Edge runtime",
    )
    datasource_parser.set_defaults(func=lambda a: (datasource_parser.print_help(), 1)[1])
    datasource_sub = datasource_parser.add_subparsers(dest="collibra_io_edge_datasource_action")

    diagnose_parser = datasource_sub.add_parser(
        "diagnose",
        help="Diagnose why a datasource is not resolving to a runnable Edge capability",
    )
    diagnose_parser.add_argument("--id", required=True, help="Datasource UUID / Edge connection secret name")
    diagnose_parser.add_argument("--namespace", default=_DEFAULT_EDGE_NAMESPACE, help=f"Kubernetes namespace (default: {_DEFAULT_EDGE_NAMESPACE})")
    diagnose_parser.add_argument("--component", default=_DEFAULT_EDGE_COMPONENT, help=f"Edge deployment to inspect (default: {_DEFAULT_EDGE_COMPONENT})")
    diagnose_parser.add_argument("--tail", type=int, default=600, help="Number of controller log lines to inspect (default: 600)")
    diagnose_parser.add_argument("--json", action="store_true")
    diagnose_parser.set_defaults(func=cmd_collibra_io_edge_datasource_diagnose)
