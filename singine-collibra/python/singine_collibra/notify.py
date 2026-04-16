"""SMTP email notification via the Docker edge instance.

Transport chain:
    singine notify email  →  smtpAgent Clojure service (edge Docker network)
                          →  SMTP relay

Channel is selected by secure.py context:
    dev     → direct HTTP to 127.0.0.1:8026
    staging → HTTP over SSH tunnel
    prod    → HTTP over WireGuard VPN

All outbound requests are wrapped in a Markupware security envelope
(X-Markupware-Signature / X-Markupware-Context headers).

Environment variables:
    SMTP_SERVICE_URL      Override smtpAgent endpoint (default: http://127.0.0.1:8026)
    SINGINE_NOTIFY_FROM   From address (default: singine@localhost)
    MARKUPWARE_SECRET_KEY HMAC key for envelope signing (default: dev-key)
    SINGINE_ENV           dev / staging / prod (drives transport selection)
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone


_DEFAULT_SMTP_SERVICE = "http://127.0.0.1:8026"
_MARKUPWARE_KEY_ENV = "MARKUPWARE_SECRET_KEY"


# ── Markupware envelope ───────────────────────────────────────────────────────

def _markupware_sign(payload: str) -> str:
    """HMAC-SHA256 hex signature for *payload* using the markupware key."""
    key = os.environ.get(_MARKUPWARE_KEY_ENV, "markupware-dev-key").encode()
    return hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()


def _markupware_headers(payload: str, context: str = "") -> dict:
    return {
        "Content-Type": "application/json",
        "X-Markupware-Signature": _markupware_sign(payload),
        "X-Markupware-Context": context or os.environ.get("SINGINE_ENV", "dev"),
        "X-Markupware-Timestamp": datetime.now(timezone.utc).isoformat(),
        "X-Singine-Agent": "singine-collibra/notify",
    }


# ── Transport resolution ──────────────────────────────────────────────────────

def _smtp_service_url() -> str:
    """Return the smtpAgent endpoint, respecting env overrides."""
    return os.environ.get(
        "SMTP_SERVICE_URL",
        os.environ.get("SINGINE_SMTP_URL", _DEFAULT_SMTP_SERVICE),
    )


def _edge_smtp_url() -> str:
    """Resolve smtpAgent URL via the Docker edge network when available."""
    # If running inside Docker, edge-site is reachable by service name
    docker_host = os.environ.get("SINGINE_EDGE_HOST", "")
    if docker_host:
        port = os.environ.get("SINGINE_SMTP_PORT", "8026")
        return f"http://{docker_host}:{port}"
    return _smtp_service_url()


# ── Core send ─────────────────────────────────────────────────────────────────

def send_email(
    to: str,
    subject: str,
    body: str,
    from_addr: str = "",
    dry_run: bool = False,
    context: str = "",
) -> dict:
    """Send an email through the smtpAgent service with Markupware envelope.

    Args:
        to:        Recipient address.
        subject:   Email subject.
        body:      Plain-text body.
        from_addr: Sender address (falls back to SINGINE_NOTIFY_FROM env var).
        dry_run:   When True, return the payload without sending.
        context:   SDLC context label forwarded in Markupware headers.
    """
    from_addr = from_addr or os.environ.get("SINGINE_NOTIFY_FROM", "singine@localhost")
    payload = {
        "cmd": "send",
        "to": to,
        "from": from_addr,
        "subject": subject,
        "body": body,
    }
    payload_str = json.dumps(payload)

    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "payload": payload,
            "smtp_url": _edge_smtp_url(),
        }

    headers = _markupware_headers(payload_str, context)
    url = f"{_edge_smtp_url()}/send"

    try:
        req = urllib.request.Request(
            url,
            data=payload_str.encode(),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
        return {"ok": True, "smtp_response": result, "to": to, "subject": subject}
    except urllib.error.URLError as exc:
        return {"ok": False, "error": str(exc), "smtp_url": url}


def send_from_stdin(
    to: str,
    subject: str,
    dry_run: bool = False,
    context: str = "",
) -> dict:
    """Read body from stdin and send. Used for piped daily-commit output."""
    body = sys.stdin.read()
    return send_email(to=to, subject=subject, body=body, dry_run=dry_run, context=context)


def smtp_status() -> dict:
    """Health check of the smtpAgent service."""
    url = f"{_edge_smtp_url()}/status"
    try:
        req = urllib.request.Request(
            url,
            headers={
                "X-Singine-Agent": "singine-collibra/notify",
                "X-Markupware-Context": os.environ.get("SINGINE_ENV", "dev"),
            },
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        return {"ok": True, "smtp_service": data, "url": url}
    except urllib.error.URLError as exc:
        return {"ok": False, "error": str(exc), "url": url}


def notify_configure(
    smtp_url: str = "",
    edge_host: str = "",
    from_addr: str = "",
) -> dict:
    """Print/validate notification configuration (does not persist to disk)."""
    resolved_url = smtp_url or _edge_smtp_url()
    return {
        "ok": True,
        "smtp_url": resolved_url,
        "edge_host": edge_host or os.environ.get("SINGINE_EDGE_HOST", "(not set)"),
        "from_addr": from_addr or os.environ.get("SINGINE_NOTIFY_FROM", "singine@localhost"),
        "env": os.environ.get("SINGINE_ENV", "dev"),
        "hint": "Set SMTP_SERVICE_URL or SINGINE_EDGE_HOST to change the endpoint.",
    }
