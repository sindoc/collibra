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
            self._json(200, {"total": 0, "offset": 0, "limit": 25, "results": []})

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
