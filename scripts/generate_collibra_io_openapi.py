#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_XML = ROOT / "docs" / "xml" / "singine-collibra-commands.xml"
OUTPUT_JSON = ROOT / "schema" / "singine-collibra-io-api.json"


def _segments_to_schema_name(segments: list[str]) -> str:
    words: list[str] = []
    for segment in segments:
        words.extend(part for part in re.split(r"[^A-Za-z0-9]+", segment) if part)
    return "".join(word[:1].upper() + word[1:] for word in words) + "Request"


def _to_property_name(name: str) -> str:
    raw = name.lstrip("-")
    if raw.startswith("-"):
        raw = raw.lstrip("-")
    if not raw:
        return "value"
    if "-" not in raw and raw[:1].islower() and any(ch.isupper() for ch in raw[1:]):
        return raw
    parts = [part for part in re.split(r"[-_]", raw) if part]
    if not parts:
        return raw
    head = parts[0]
    tail = "".join(part[:1].upper() + part[1:] for part in parts[1:])
    return head + tail


def _normalize_option(option: ET.Element) -> dict:
    prop = _to_property_name(option.get("name", "option"))
    payload: dict = {
        "name": prop,
        "required": option.get("required") == "true",
        "repeatable": option.get("repeatable") == "true",
        "type": option.get("type", "string"),
        "default": option.get("default"),
        "choices": option.get("choices"),
        "metavar": option.get("metavar"),
    }
    return payload


def _normalize_arg(arg: ET.Element) -> dict:
    return {
        "name": _to_property_name(arg.get("name", "arg")),
        "required": arg.get("required") == "true",
        "repeatable": False,
        "type": "string",
        "default": None,
        "choices": arg.get("choices"),
        "metavar": None,
    }


def _merge_fields(fields: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for field in fields:
        existing = merged.get(field["name"])
        if existing is None:
            merged[field["name"]] = dict(field)
            continue
        existing["required"] = existing["required"] or field["required"]
        existing["repeatable"] = existing["repeatable"] or field["repeatable"]
        existing["type"] = field["type"] if existing["type"] == "string" else existing["type"]
        existing["default"] = existing["default"] if existing["default"] is not None else field["default"]
        existing["choices"] = existing["choices"] if existing["choices"] else field["choices"]
    return list(merged.values())


def _field_schema(field: dict) -> dict:
    if field["type"] == "flag":
        schema: dict = {"type": "boolean"}
        if field["default"] is not None:
            schema["default"] = field["default"].lower() == "true"
    elif field["type"] == "int":
        schema = {"type": "integer"}
        if field["default"] is not None:
            schema["default"] = int(field["default"])
    else:
        schema = {"type": "string"}
        if field["default"] is not None:
            schema["default"] = field["default"]
    if field["choices"]:
        schema["enum"] = [choice.strip() for choice in field["choices"].split(",") if choice.strip()]
    if field["repeatable"]:
        return {"type": "array", "items": schema}
    return schema


def _http_method(segments: list[str]) -> str:
    leaf = segments[-1]
    if segments[0] == "create":
        return "post"
    if leaf in {"configure", "visualize", "export", "probe-postgres", "diagnose"}:
        return "post"
    return "get"


def _flatten_commands(node: ET.Element, prefix: list[str]) -> list[dict]:
    commands: list[dict] = []
    if node.tag == "commands":
        children = node.findall("./command")
    else:
        children = node.findall("./subcommands/command")
    for child in children:
        child_segments = prefix + [child.get("name", "command")]
        grand_children = child.findall("./subcommands/command")
        if grand_children:
            commands.extend(_flatten_commands(child, child_segments))
            continue
        commands.append({
            "segments": child_segments,
            "help": child.get("help", ""),
            "example": (child.findtext("example") or "").strip(),
            "args": _merge_fields([_normalize_arg(arg) for arg in child.findall("./args/arg")]),
            "options": _merge_fields([_normalize_option(opt) for opt in child.findall("./options/option")]),
        })
    return commands


def _build_request_schema(command: dict) -> dict:
    fields = _merge_fields(command["args"] + command["options"])
    properties = {field["name"]: _field_schema(field) for field in fields}
    required = [field["name"] for field in fields if field["required"]]
    schema: dict = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required
    return schema


def build_openapi() -> dict:
    root = ET.parse(SOURCE_XML).getroot()
    io_component = root.find("./component[@name='io']")
    if io_component is None:
        raise SystemExit(f"missing io component in {SOURCE_XML}")

    commands = _flatten_commands(io_component.find("./commands"), [])
    paths: dict = {}
    schemas: dict = {
        "CommandResult": {
            "type": "object",
            "additionalProperties": True,
            "properties": {
                "ok": {"type": "boolean"},
                "command": {"type": "string"},
                "summary": {"type": "string"},
                "data": {"type": "object"},
            },
        }
    }

    for command in commands:
        segments = command["segments"]
        path = "/api/collibra/io/" + "/".join(segments)
        method = _http_method(segments)
        operation_id = "collibraIo" + "".join(part[:1].upper() + part[1:] for part in _segments_to_schema_name(segments).removesuffix("Request").split())
        fields = _merge_fields(command["args"] + command["options"])
        operation: dict = {
            "operationId": operation_id,
            "summary": command["help"] or "Run Collibra IO workflow command",
            "responses": {
                "200": {
                    "description": "Command result",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/CommandResult"}
                        }
                    },
                }
            },
        }
        if command["example"]:
            operation["description"] = f"CLI example: `{command['example']}`"

        if method == "get":
            params = []
            for field in fields:
                params.append({
                    "name": field["name"],
                    "in": "query",
                    "required": field["required"],
                    "schema": _field_schema(field),
                })
            if params:
                operation["parameters"] = params
        else:
            schema_name = _segments_to_schema_name(segments)
            schemas[schema_name] = _build_request_schema(command)
            operation["requestBody"] = {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": f"#/components/schemas/{schema_name}"}
                    }
                },
            }

        paths[path] = {method: operation}

    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Singine Collibra IO API",
            "version": "0.1.0",
            "summary": "Generated HTTP interaction contract for the `singine collibra io` command family.",
            "description": "Generated from docs/xml/singine-collibra-commands.xml so the CLI, XML publication, and OpenAPI surface stay aligned.",
        },
        "servers": [
            {
                "url": "http://127.0.0.1:9090",
                "description": "Local Singine panel or adapter surface",
            }
        ],
        "paths": paths,
        "components": {"schemas": schemas},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate OpenAPI for singine collibra io from XML command docs")
    parser.add_argument("--stdout", action="store_true", help="Write JSON to stdout instead of the schema file")
    args = parser.parse_args()

    payload = build_openapi()
    rendered = json.dumps(payload, indent=2) + "\n"
    if args.stdout:
        print(rendered, end="")
        return 0
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(rendered, encoding="utf-8")
    print(f"wrote {OUTPUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
