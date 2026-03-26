"""
Collibra REST API client for Singine.

Reads configuration from environment variables:
  COLLIBRA_BASE_URL      e.g. https://lutino.collibra.com
  COLLIBRA_USERNAME      Basic auth username
  COLLIBRA_PASSWORD      Basic auth password
  COLLIBRA_TOKEN         Bearer token (alternative to username/password)

All public functions return a dict envelope:
  ok: bool
  data: list | dict
  count: int           (list responses only)
  error: str           (only when ok=False)
  env: dict            (sanitised config summary — never contains secrets)
"""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def _base_url() -> str:
    url = os.environ.get("COLLIBRA_BASE_URL", "").rstrip("/")
    if not url:
        raise EnvironmentError(
            "COLLIBRA_BASE_URL is not set. "
            "Export it before running singine collibra commands, e.g.:\n"
            "  export COLLIBRA_BASE_URL=https://lutino.collibra.com"
        )
    return url


def _auth_header() -> str:
    token = os.environ.get("COLLIBRA_TOKEN")
    if token:
        return f"Bearer {token}"
    username = os.environ.get("COLLIBRA_USERNAME", "")
    password = os.environ.get("COLLIBRA_PASSWORD", "")
    if username and password:
        encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
        return f"Basic {encoded}"
    raise EnvironmentError(
        "Collibra credentials not found. "
        "Set COLLIBRA_TOKEN or both COLLIBRA_USERNAME and COLLIBRA_PASSWORD."
    )


def _env_summary() -> Dict[str, str]:
    """Return sanitised env config — safe to include in JSON output."""
    base = os.environ.get("COLLIBRA_BASE_URL", "")
    token = os.environ.get("COLLIBRA_TOKEN")
    username = os.environ.get("COLLIBRA_USERNAME", "")
    return {
        "base_url": base,
        "auth": "bearer" if token else ("basic" if username else "none"),
    }


def check_env() -> Dict[str, Any]:
    """Return a validation report for the current Collibra environment config."""
    issues: List[str] = []
    try:
        _base_url()
    except EnvironmentError as exc:
        issues.append(str(exc))
    try:
        _auth_header()
    except EnvironmentError as exc:
        issues.append(str(exc))
    return {"ok": len(issues) == 0, "issues": issues, "env": _env_summary()}


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def _get(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    """Execute a GET against the Collibra REST v2 API and return parsed JSON."""
    base = _base_url()
    auth = _auth_header()

    query = ""
    if params:
        filtered = {k: v for k, v in params.items() if v is not None}
        if filtered:
            query = "?" + urllib.parse.urlencode(filtered)

    url = f"{base}/rest/2.0{path}{query}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": auth,
            "Accept": "application/json",
            "User-Agent": "singine-collibra/0.1",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        raise RuntimeError(
            f"Collibra API error {exc.code} {exc.reason} for {url}: {body[:300]}"
        ) from exc


def _post(path: str, payload: Dict[str, Any]) -> Any:
    """Execute a POST against the Collibra REST v2 API and return parsed JSON."""
    base = _base_url()
    auth = _auth_header()
    url = f"{base}/rest/2.0{path}"
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": auth,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "singine-collibra/0.1",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        raise RuntimeError(
            f"Collibra API error {exc.code} {exc.reason} for {url}: {body[:300]}"
        ) from exc


def _results(raw: Any) -> List[Any]:
    """Extract results list from a Collibra paged response or plain list."""
    if isinstance(raw, dict):
        return raw.get("results", [raw])
    if isinstance(raw, list):
        return raw
    return [raw]


def _envelope(data: List[Any]) -> Dict[str, Any]:
    return {"ok": True, "data": data, "count": len(data), "env": _env_summary()}


# ---------------------------------------------------------------------------
# Resource fetchers
# ---------------------------------------------------------------------------

def fetch_communities(
    name: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    """Fetch Communities from Collibra.

    Args:
        name:  Optional name filter (prefix match).
        limit: Maximum number of results (default 50).
    """
    params: Dict[str, Any] = {"limit": limit, "offset": 0}
    if name:
        params["name"] = name
    return _envelope(_results(_get("/communities", params)))


def create_community(
    name: str,
    description: Optional[str] = None,
    parent_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a Collibra community.

    When ``parent_id`` is omitted, a root community is created.
    """
    payload: Dict[str, Any] = {"name": name}
    if description:
        payload["description"] = description
    if parent_id:
        payload["parentId"] = parent_id
    created = _post("/communities", payload)
    return {"ok": True, "data": created, "env": _env_summary()}


def fetch_domains(
    community_id: Optional[str] = None,
    domain_type: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    """Fetch Domains from Collibra.

    Args:
        community_id: UUID of the parent community.
        domain_type:  Domain type name filter (e.g. 'Glossary').
        limit:        Maximum number of results (default 50).
    """
    params: Dict[str, Any] = {"limit": limit, "offset": 0}
    if community_id:
        params["communityId"] = community_id
    if domain_type:
        params["type"] = domain_type
    return _envelope(_results(_get("/domains", params)))


def fetch_asset_types(limit: int = 200) -> Dict[str, Any]:
    """Fetch all AssetTypes from Collibra."""
    return _envelope(_results(_get("/assetTypes", {"limit": limit})))


def fetch_views(
    location: Optional[str] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    """Fetch Views (tableViewConfig containers) from Collibra.

    Args:
        location: View location filter (e.g. 'catalog|reports').
        limit:    Maximum number of results.
    """
    params: Dict[str, Any] = {"limit": limit}
    if location:
        params["location"] = location
    return _envelope(_results(_get("/views", params)))


def fetch_workflows(limit: int = 50) -> Dict[str, Any]:
    """Fetch Workflow definitions from Collibra."""
    return _envelope(_results(_get("/workflowDefinitions", {"limit": limit})))


def search_assets(
    query: str,
    asset_type: Optional[str] = None,
    domain_id: Optional[str] = None,
    limit: int = 25,
) -> Dict[str, Any]:
    """Search Assets by name across Collibra.

    Args:
        query:      Name search string (prefix/contains match).
        asset_type: AssetType publicId filter (e.g. 'DataSet').
        domain_id:  Restrict search to one Domain UUID.
        limit:      Maximum number of results (default 25).
    """
    params: Dict[str, Any] = {"name": query, "limit": limit, "offset": 0}
    if asset_type:
        params["typePublicId"] = asset_type
    if domain_id:
        params["domainId"] = domain_id
    return _envelope(_results(_get("/assets", params)))
