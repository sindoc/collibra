#!/usr/bin/env python3
"""
mock_dgc.py — minimal Collibra DGC edge mock for local development.

Implements just enough of the DGC REST surface for the edge stack to
start cleanly without a real Collibra license:

  GET  /rest/2.0/ping            → 200  (CDN and health checks)
  GET  /rest/2.0/communities     → empty list
  GET  /graphql/2.0              → minimal GraphQL stub
  ANY  *                         → 200 stub response

Run on port 7080.
"""

import http.server
import json
import os
import sys
from datetime import datetime, timezone

PORT = int(os.environ.get("COLLIBRA_HTTP_PORT", 7080))
SITE_ID = os.environ.get("COLLIBRA_EDGE_HOSTNAME", "edge-mock")

# ── Representative sample data ────────────────────────────────────────────────

_COMMUNITIES = [
    {"id": "comm-001", "name": "Data Governance",    "description": "Collibra-governed data catalogue community"},
    {"id": "comm-002", "name": "AI Platform",        "description": "AI session and model governance"},
    {"id": "comm-003", "name": "Lutino.io Platform", "description": "Core platform capabilities and processes"},
]

_ASSETS = [
    # Business Terms
    {"id": "ast-bt-001", "name": "Business Term",       "type": {"name": "Business Term"}, "definition": "A canonical definition managed in the Collibra glossary"},
    {"id": "ast-bt-002", "name": "Data Product",        "type": {"name": "Business Term"}, "definition": "A governed, discoverable data asset exposed via a defined interface"},
    {"id": "ast-bt-003", "name": "Collibra Asset",      "type": {"name": "Business Term"}, "definition": "Any entity registered in the Collibra catalog"},
    {"id": "ast-bt-004", "name": "Edge Node",           "type": {"name": "Business Term"}, "definition": "A Collibra Edge deployment node connecting an on-premise site to the cloud DGC"},
    # Business Capabilities
    {"id": "ast-bc-001", "name": "Data Cataloguing",    "type": {"name": "Business Capability"}, "definition": "Discover, register, and govern data assets"},
    {"id": "ast-bc-002", "name": "AI Governance",       "type": {"name": "Business Capability"}, "definition": "Policy-backed governance of AI sessions and mandates"},
    {"id": "ast-bc-003", "name": "Edge Connectivity",   "type": {"name": "Business Capability"}, "definition": "Connect on-premise systems to Collibra Cloud via Edge nodes"},
    # Business Processes
    {"id": "ast-bp-001", "name": "Asset Registration",  "type": {"name": "Business Process"}, "definition": "Register and classify data assets in the catalogue"},
    {"id": "ast-bp-002", "name": "Edge Ingest",         "type": {"name": "Business Process"}, "definition": "Pull Collibra assets into the Singine cortex bridge via REST"},
    # Data Categories
    {"id": "ast-dc-001", "name": "Personal Data",       "type": {"name": "Data Category"}, "definition": "Data relating to an identified or identifiable natural person"},
    {"id": "ast-dc-002", "name": "Operational Metrics", "type": {"name": "Data Category"}, "definition": "Runtime metrics, logs, and telemetry from platform services"},
    # Policies
    {"id": "ast-po-001", "name": "AI Access Policy",    "type": {"name": "Policy"}, "definition": "Governs which AI systems may access which data and operations"},
]


class DgcMockHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(f"[dgc-mock] {self.address_string()} {fmt % args}", flush=True)

    def _json(self, status: int, body: dict):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-Mock-DGC", "true")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        path = self.path.split("?")[0]

        if path in ("/rest/2.0/ping", "/ping"):
            self._json(200, {"status": "ok", "mock": True, "ts": datetime.now(timezone.utc).isoformat()})

        elif path.startswith("/rest/2.0/communities"):
            self._json(200, {"total": len(_COMMUNITIES), "offset": 0, "limit": 25,
                              "results": _COMMUNITIES})

        elif path.startswith("/rest/2.0/assets"):
            # Filter by typeNames query param if present
            qs = self.path[self.path.find("?")+1:] if "?" in self.path else ""
            type_filter = None
            for part in qs.split("&"):
                if part.startswith("typeNames="):
                    type_filter = part[len("typeNames="):].replace("%20", " ").replace("+", " ")
            if type_filter:
                filtered = [a for a in _ASSETS if a["type"]["name"] == type_filter]
            else:
                filtered = _ASSETS
            limit  = int(next((p.split("=")[1] for p in qs.split("&") if p.startswith("limit=")),  "100"))
            offset = int(next((p.split("=")[1] for p in qs.split("&") if p.startswith("offset=")), "0"))
            page   = filtered[offset: offset + limit]
            self._json(200, {"total": len(filtered), "offset": offset, "limit": limit,
                              "results": page})

        elif path.startswith("/rest/2.0/"):
            self._json(200, {"mock": True, "path": path, "results": []})

        elif path in ("/graphql/2.0", "/graphql/knowledgeGraph/v1"):
            self._json(200, {"data": {}, "errors": []})

        else:
            self._json(200, {"mock": True, "path": path})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        _ = self.rfile.read(length)
        path = self.path.split("?")[0]
        self._json(200, {"mock": True, "path": path, "ok": True})

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()


if __name__ == "__main__":
    print(f"[dgc-mock] Collibra DGC mock starting on :{PORT}", flush=True)
    print(f"[dgc-mock] hostname={SITE_ID}", flush=True)
    server = http.server.HTTPServer(("0.0.0.0", PORT), DgcMockHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[dgc-mock] shutting down", flush=True)
        sys.exit(0)
