"""Singine-friendly Collibra metamodel abstractions.

This module loads Collibra operating-model exports from disk and projects them
into a stable in-memory representation that can also be aligned with Singine's
opmodel vocabulary.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


DEFAULT_METAMODEL_ROOT = Path("/Users/skh/ws/today/metamodel/reference/current/latest")


def _resource_name(payload: Dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, dict):
            nested = value.get("name")
            if nested:
                return str(nested)
        elif value:
            return str(value)
    return ""


def _json_files(path: Path) -> Iterable[Path]:
    if not path.exists():
        return []
    return sorted(file for file in path.glob("*.json") if file.is_file())


@dataclass
class Characteristic:
    id: str
    kind: str
    name: str
    public_id: str
    minimum_occurrences: int
    maximum_occurrences: Optional[int]
    direction: Optional[str] = None
    source_asset_type: Optional[str] = None
    target_asset_type: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    def peer_asset_type(self, asset_type_name: str) -> Optional[str]:
        target = asset_type_name.lower()
        if (self.source_asset_type or "").lower() == target:
            return self.target_asset_type
        if (self.target_asset_type or "").lower() == target:
            return self.source_asset_type
        return self.target_asset_type or self.source_asset_type

    def as_opmodel(self) -> Dict[str, Any]:
        payload = {
            "id": self.id,
            "kind": self.kind,
            "name": self.name,
            "public_id": self.public_id,
            "cardinality": {
                "min": self.minimum_occurrences,
                "max": self.maximum_occurrences,
            },
        }
        if self.kind == "relation":
            payload["edge"] = {
                "direction": self.direction,
                "source_asset_type": self.source_asset_type,
                "target_asset_type": self.target_asset_type,
            }
        return payload


@dataclass
class Assignment:
    id: str
    asset_type_id: str
    asset_type_name: str
    domain_types: List[str]
    characteristics: List[Characteristic]
    raw: Dict[str, Any] = field(default_factory=dict)

    def relation_characteristics(self) -> List[Characteristic]:
        return [item for item in self.characteristics if item.kind == "relation"]

    def attribute_characteristics(self) -> List[Characteristic]:
        return [item for item in self.characteristics if item.kind == "attribute"]


@dataclass
class AssetType:
    id: str
    name: str
    public_id: str
    parent_name: str
    assignment: Optional[Assignment] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    def as_opmodel(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "kind": "asset_type",
            "name": self.name,
            "public_id": self.public_id,
            "parent_name": self.parent_name,
            "attributes": [
                item.as_opmodel()
                for item in (self.assignment.attribute_characteristics() if self.assignment else [])
            ],
            "relations": [
                item.as_opmodel()
                for item in (self.assignment.relation_characteristics() if self.assignment else [])
            ],
        }


@dataclass
class ViewDefinition:
    id: str
    name: str
    location: str
    view_type: str
    assignment_asset_types: List[str]
    config: Dict[str, Any]
    raw: Dict[str, Any] = field(default_factory=dict)

    def driver_columns(self) -> List[str]:
        columns: List[str] = []
        template = self.config.get("template", {})
        for item in template.get("nodes", []):
            label = item.get("label") or item.get("id")
            if label:
                columns.append(str(label))
        return columns


@dataclass
class MetamodelSnapshot:
    root: Path
    version: str
    asset_types: Dict[str, AssetType]
    assignments: Dict[str, Assignment]
    views: Dict[str, ViewDefinition]
    stats: Dict[str, int]

    def asset_type(self, value: str) -> Optional[AssetType]:
        normalized = value.lower()
        for asset_type in self.asset_types.values():
            if asset_type.name.lower() == normalized:
                return asset_type
            if asset_type.public_id.lower() == normalized.replace(" ", ""):
                return asset_type
        return self.asset_types.get(value)

    def view_candidates(self, asset_type_name: str) -> List[ViewDefinition]:
        target = asset_type_name.lower()
        matches: List[ViewDefinition] = []
        for view in self.views.values():
            if any(name.lower() == target for name in view.assignment_asset_types):
                matches.append(view)
        return matches

    def to_opmodel(self, *, asset_type_name: Optional[str] = None) -> Dict[str, Any]:
        selected = (
            [self.asset_type(asset_type_name)] if asset_type_name else list(self.asset_types.values())
        )
        assets = [item.as_opmodel() for item in selected if item is not None]
        return {
            "kind": "singine.collibra.opmodel",
            "version": self.version,
            "source_root": str(self.root),
            "asset_types": assets,
        }

    def to_mermaid(self, *, asset_type_name: str) -> str:
        asset_type = self.asset_type(asset_type_name)
        if asset_type is None:
            raise KeyError(asset_type_name)
        lines = ["graph TD"]
        lines.append(f'  A["{asset_type.name}"]')
        if asset_type.assignment:
            for relation in asset_type.assignment.relation_characteristics():
                target = relation.peer_asset_type(asset_type.name) or relation.name
                node_id = f"N{relation.id.replace('-', '')}"
                lines.append(f'  {node_id}["{target}"]')
                edge_label = relation.public_id or relation.name
                lines.append(f'  A -->|{edge_label}| {node_id}')
        return "\n".join(lines)

    def to_mermaid_landscape(self) -> str:
        lines = ["graph TD"]
        emitted_nodes: set[str] = set()
        emitted_edges: set[str] = set()

        def node_id(value: str) -> str:
            return "N" + "".join(ch for ch in value if ch.isalnum())

        for asset_type in sorted(self.asset_types.values(), key=lambda item: item.name):
            aid = node_id(asset_type.id or asset_type.name)
            if aid not in emitted_nodes:
                lines.append(f'  {aid}["{asset_type.name}"]')
                emitted_nodes.add(aid)
            if asset_type.parent_name:
                parent = next(
                    (item for item in self.asset_types.values() if item.name == asset_type.parent_name),
                    None,
                )
                if parent is not None:
                    pid = node_id(parent.id or parent.name)
                    if pid not in emitted_nodes:
                        lines.append(f'  {pid}["{parent.name}"]')
                        emitted_nodes.add(pid)
                    edge_key = f"{pid}>{aid}>inherits"
                    if edge_key not in emitted_edges:
                        lines.append(f"  {pid} -->|inherits| {aid}")
                        emitted_edges.add(edge_key)
            if asset_type.assignment:
                for relation in asset_type.assignment.relation_characteristics():
                    peer = relation.peer_asset_type(asset_type.name)
                    if not peer:
                        continue
                    peer_type = next((item for item in self.asset_types.values() if item.name == peer), None)
                    if peer_type is None:
                        continue
                    tid = node_id(peer_type.id or peer_type.name)
                    if tid not in emitted_nodes:
                        lines.append(f'  {tid}["{peer_type.name}"]')
                        emitted_nodes.add(tid)
                    edge_label = relation.public_id or relation.name
                    edge_key = f"{aid}>{tid}>{edge_label}"
                    if edge_key not in emitted_edges:
                        lines.append(f"  {aid} -->|{edge_label}| {tid}")
                        emitted_edges.add(edge_key)
        return "\n".join(lines)


def _load_characteristics(assignment_payload: Dict[str, Any]) -> List[Characteristic]:
    items: List[Characteristic] = []
    for entry in assignment_payload.get("characteristicTypes", []):
        discr = entry.get("assignedCharacteristicTypeDiscriminator")
        if discr == "AttributeType":
            attribute = entry.get("attributeType", {})
            items.append(
                Characteristic(
                    id=str(entry.get("id", "")),
                    kind="attribute",
                    name=str(attribute.get("name", "")),
                    public_id=str(attribute.get("publicId", "")),
                    minimum_occurrences=int(entry.get("minimumOccurrences") or 0),
                    maximum_occurrences=entry.get("maximumOccurrences"),
                    raw=entry,
                )
            )
        elif discr == "RelationType":
            relation = entry.get("relationType", {})
            items.append(
                Characteristic(
                    id=str(entry.get("id", "")),
                    kind="relation",
                    name=str(relation.get("role", "")),
                    public_id=str(relation.get("publicId", "")),
                    minimum_occurrences=int(entry.get("minimumOccurrences") or 0),
                    maximum_occurrences=entry.get("maximumOccurrences"),
                    direction=entry.get("relationTypeDirection"),
                    source_asset_type=_resource_name(relation, "sourceType"),
                    target_asset_type=_resource_name(relation, "targetType"),
                    raw=entry,
                )
            )
    return items


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def detect_export_root(path: Optional[str] = None) -> Path:
    if path:
        candidate = Path(path).expanduser()
    else:
        candidate = DEFAULT_METAMODEL_ROOT
    if candidate.is_dir() and (candidate / "1.1.27").exists():
        return candidate / "1.1.27"
    if candidate.is_dir() and any((candidate / child).is_dir() for child in ("AssetType", "Assignment", "View")):
        return candidate
    nested = sorted(p for p in candidate.glob("*") if p.is_dir() and any((p / child).is_dir() for child in ("AssetType", "Assignment", "View")))
    if nested:
        direct_version = sorted(
            child for child in nested[0].glob("*")
            if child.is_dir() and any((child / name).is_dir() for name in ("AssetType", "Assignment", "View"))
        )
        if direct_version:
            return direct_version[0]
        return nested[0]
    raise FileNotFoundError(f"No Collibra metamodel export found under {candidate}")


def load_snapshot(path: Optional[str] = None) -> MetamodelSnapshot:
    root = detect_export_root(path)

    assignments_by_asset_type_id: Dict[str, Assignment] = {}
    assignments: Dict[str, Assignment] = {}
    for file in _json_files(root / "Assignment"):
        payload = _load_json(file)
        asset_type = payload.get("assetType", {})
        assignment = Assignment(
            id=str(payload.get("id", "")),
            asset_type_id=str(asset_type.get("id", "")),
            asset_type_name=str(asset_type.get("name", "")),
            domain_types=[item.get("name", "") for item in payload.get("domainTypes", []) if item.get("name")],
            characteristics=_load_characteristics(payload),
            raw=payload,
        )
        assignments[assignment.id] = assignment
        assignments_by_asset_type_id[assignment.asset_type_id] = assignment

    asset_types: Dict[str, AssetType] = {}
    for file in _json_files(root / "AssetType"):
        payload = _load_json(file)
        item = AssetType(
            id=str(payload.get("id", "")),
            name=str(payload.get("name", "")),
            public_id=str(payload.get("publicId", "")),
            parent_name=_resource_name(payload, "parent"),
            assignment=assignments_by_asset_type_id.get(str(payload.get("id", ""))),
            raw=payload,
        )
        asset_types[item.id] = item

    views: Dict[str, ViewDefinition] = {}
    for file in _json_files(root / "View"):
        payload = _load_json(file)
        config_payload = payload.get("config") or "{}"
        if isinstance(config_payload, str):
            try:
                config = json.loads(config_payload)
            except json.JSONDecodeError:
                config = {}
        else:
            config = config_payload
        item = ViewDefinition(
            id=str(payload.get("id", "")),
            name=str(payload.get("name", "")),
            location=str(payload.get("location", "")),
            view_type=str(payload.get("type", "")),
            assignment_asset_types=[
                _resource_name(rule, "assetType")
                for rule in payload.get("assignmentRules", [])
                if _resource_name(rule, "assetType")
            ],
            config=config,
            raw=payload,
        )
        views[item.id] = item

    stats = {}
    for name in (
        "AssetType",
        "Assignment",
        "AttributeType",
        "RelationType",
        "View",
        "Domain",
        "Community",
        "Workflow",
    ):
        stats[name] = len(list(_json_files(root / name)))

    return MetamodelSnapshot(
        root=root,
        version=root.name,
        asset_types=asset_types,
        assignments=assignments,
        views=views,
        stats=stats,
    )
