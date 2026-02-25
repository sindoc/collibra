#!/usr/bin/env python3
"""
ldap_tree.py — Singine LDAP tree constructor
Builds an in-memory LDAP DN hierarchy from SQLite ldap_entities,
enforces structural constraints (orgUnit, dc, cn, uid, o),
and generates FOAF/DOAP entity links.

RFC 4512 DN: cn=smtpAgent,ou=Services,dc=singine,dc=io
"""

import sqlite3
import json
from collections import defaultdict
from typing import Optional


# ── Node ──────────────────────────────────────────────────────────────────────

class LdapNode:
    def __init__(self, gen_id: str, dn: str, entity_type: str,
                 common_name: str, org_unit: Optional[str] = None,
                 description: Optional[str] = None,
                 foaf_uri: Optional[str] = None,
                 doap_uri: Optional[str] = None):
        self.gen_id      = gen_id
        self.dn          = dn
        self.entity_type = entity_type
        self.common_name = common_name
        self.org_unit    = org_unit
        self.description = description
        self.foaf_uri    = foaf_uri
        self.doap_uri    = doap_uri
        self.children: list["LdapNode"] = []

    def to_dict(self) -> dict:
        return {
            "gen_id":      self.gen_id,
            "dn":          self.dn,
            "type":        self.entity_type,
            "cn":          self.common_name,
            "ou":          self.org_unit,
            "foaf":        self.foaf_uri,
            "doap":        self.doap_uri,
            "children":    [c.to_dict() for c in self.children],
        }


# ── Constraint validator ──────────────────────────────────────────────────────

VALID_PARENT = {
    "dc":  {None},                        # dc must be root
    "ou":  {"dc", "ou"},                  # orgUnit under dc or nested ou
    "cn":  {"ou", "dc"},                  # cn under orgUnit
    "uid": {"ou"},                        # uid only under orgUnit
    "o":   {None, "dc"},                  # org under root or dc
}

def validate_parent(child_type: str, parent_type: Optional[str]) -> bool:
    allowed = VALID_PARENT.get(child_type, set())
    return parent_type in allowed


# ── Tree builder ──────────────────────────────────────────────────────────────

class LdapTree:
    def __init__(self, conn: sqlite3.Connection):
        self.conn  = conn
        self.nodes: dict[str, LdapNode] = {}  # dn → node
        self.roots: list[LdapNode]      = []

    def load(self) -> "LdapTree":
        rows = self.conn.execute(
            "SELECT gen_id,dn,entity_type,parent_dn,common_name,"
            "org_unit,description,foaf_uri,doap_uri FROM ldap_entities"
        ).fetchall()

        # Build node map
        for r in rows:
            node = LdapNode(
                gen_id=r[0], dn=r[1], entity_type=r[2],
                common_name=r[4], org_unit=r[5],
                description=r[6], foaf_uri=r[7], doap_uri=r[8],
            )
            self.nodes[r[1]] = node

        # Link parent → child
        for r in rows:
            dn        = r[1]
            parent_dn = r[3]
            node      = self.nodes[dn]

            if parent_dn and parent_dn in self.nodes:
                parent = self.nodes[parent_dn]
                # Enforce structural constraint
                if not validate_parent(node.entity_type, parent.entity_type):
                    raise ValueError(
                        f"Constraint violation: {node.entity_type} cannot be "
                        f"child of {parent.entity_type} (dn={dn})"
                    )
                parent.children.append(node)
            else:
                self.roots.append(node)

        return self

    def to_json(self) -> str:
        return json.dumps(
            {"ldap_tree": [r.to_dict() for r in self.roots]},
            indent=2, ensure_ascii=False,
        )

    def find_by_cn(self, cn: str) -> Optional[LdapNode]:
        for node in self.nodes.values():
            if node.common_name == cn:
                return node
        return None

    def find_org_units(self) -> list[LdapNode]:
        return [n for n in self.nodes.values() if n.entity_type == "ou"]

    def shortest_dn_path(self, from_dn: str, to_dn: str) -> list[str]:
        """BFS path between two DNs in the tree (parent links)."""
        parent_map: dict[str, str] = {}
        rows = self.conn.execute(
            "SELECT dn, parent_dn FROM ldap_entities WHERE parent_dn IS NOT NULL"
        ).fetchall()
        for dn, pdn in rows:
            parent_map[dn] = pdn

        # BFS upward from from_dn
        visited = set()
        queue = [(from_dn, [from_dn])]
        while queue:
            cur, path = queue.pop(0)
            if cur in visited:
                continue
            visited.add(cur)
            if cur == to_dn:
                return path
            if cur in parent_map:
                queue.append((parent_map[cur], path + [parent_map[cur]]))
        return []


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    import argparse
    ap = argparse.ArgumentParser(description="Singine LDAP tree builder")
    ap.add_argument("--db",    default="singine.db")
    ap.add_argument("--json",  action="store_true")
    ap.add_argument("--from-dn")
    ap.add_argument("--to-dn")
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    tree = LdapTree(conn).load()

    if args.from_dn and args.to_dn:
        path = tree.shortest_dn_path(args.from_dn, args.to_dn)
        print(json.dumps({"path": path}))
    elif args.json:
        print(tree.to_json())
    else:
        for root in tree.roots:
            print_node(root, 0)

    conn.close()


def print_node(node: LdapNode, depth: int):
    indent = "  " * depth
    foaf = f" [foaf:{node.foaf_uri}]" if node.foaf_uri else ""
    print(f"{indent}{node.entity_type.upper()}={node.common_name}{foaf}")
    for child in sorted(node.children, key=lambda n: n.dn):
        print_node(child, depth + 1)


if __name__ == "__main__":
    main()
