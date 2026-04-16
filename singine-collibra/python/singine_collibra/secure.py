"""Context-aware secure transport selection.

Detects the current device/network context and selects the appropriate channel:

    dev / local   → direct TLS (OpenSSL verify)
    staging       → SSH tunnel through edge CDN container
    prod          → WireGuard VPN (wg-quick / wg show)
    unknown       → Markupware proxy envelope (fallback)

Context signals evaluated in order:
    1. SINGINE_ENV env var (dev / staging / prod)
    2. Hostname suffix (.local → dev, *.internal / *.compute → staging)
    3. Docker socket presence (suggests edge-local)
    4. WireGuard interface presence (suggests prod tunnel)
    5. SSH_AUTH_SOCK (SSH agent available → staging tunnel capable)

Environment variables:
    SINGINE_ENV          dev | staging | prod
    SINGINE_EDGE_HOST    Hostname of the edge CDN container
    SSH_AUTH_SOCK        Set by ssh-agent (used for staging tunnel detection)
    MARKUPWARE_SECRET_KEY  HMAC key (see notify.py)
"""
from __future__ import annotations

import os
import socket
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ── Context dataclass ─────────────────────────────────────────────────────────

@dataclass
class SecureContext:
    env: str                    # dev | staging | prod | unknown
    device: str                 # hostname
    transport: str              # direct-tls | ssh-tunnel | wireguard | markupware-proxy
    docker_available: bool
    wireguard_available: bool
    ssh_agent_available: bool
    notes: list = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "env": self.env,
            "device": self.device,
            "transport": self.transport,
            "docker_available": self.docker_available,
            "wireguard_available": self.wireguard_available,
            "ssh_agent_available": self.ssh_agent_available,
            "notes": self.notes,
        }


# ── Internal helpers ──────────────────────────────────────────────────────────

def _run(cmd: list) -> tuple:
    """Run *cmd*, return (returncode, stdout, stderr). Never raises."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return 1, "", ""


# ── Context detection ─────────────────────────────────────────────────────────

def detect_context() -> SecureContext:
    """Inspect the runtime environment and return a SecureContext."""
    notes: list = []
    env = os.environ.get("SINGINE_ENV", "").lower()
    hostname = socket.gethostname()

    if not env:
        if hostname.endswith(".local") or hostname in ("localhost", "127.0.0.1"):
            env = "dev"
            notes.append(f"env=dev inferred from hostname '{hostname}'")
        elif ".internal" in hostname or ".compute" in hostname or ".ec2" in hostname:
            env = "staging"
            notes.append(f"env=staging inferred from hostname '{hostname}'")
        else:
            env = "unknown"
            notes.append("SINGINE_ENV not set; defaulting to unknown")

    docker_available = Path("/var/run/docker.sock").exists()
    if docker_available:
        notes.append("Docker socket found at /var/run/docker.sock")

    wg_rc, _, _ = _run(["which", "wg"])
    wg_ifaces_rc, wg_out, _ = _run(["wg", "show", "interfaces"])
    wireguard_available = wg_rc == 0 and wg_ifaces_rc == 0 and bool(wg_out.strip())
    if wireguard_available:
        notes.append(f"WireGuard interfaces: {wg_out.strip()}")

    ssh_agent_available = bool(os.environ.get("SSH_AUTH_SOCK"))

    # Transport selection logic
    if env == "prod":
        if wireguard_available:
            transport = "wireguard"
        else:
            transport = "markupware-proxy"
            notes.append("prod env but no WireGuard — falling back to markupware-proxy")
    elif env == "staging":
        if ssh_agent_available:
            transport = "ssh-tunnel"
        else:
            transport = "markupware-proxy"
            notes.append("staging env but SSH_AUTH_SOCK not set — falling back to markupware-proxy")
    elif env == "dev":
        transport = "direct-tls"
    else:
        transport = "markupware-proxy"
        notes.append("unknown env — using markupware-proxy as safe default")

    return SecureContext(
        env=env,
        device=hostname,
        transport=transport,
        docker_available=docker_available,
        wireguard_available=wireguard_available,
        ssh_agent_available=ssh_agent_available,
        notes=notes,
    )


# ── TLS / OpenSSL ─────────────────────────────────────────────────────────────

def openssl_cert_info(host: str, port: int = 443) -> dict:
    """Probe TLS certificate details for *host:port* via openssl s_client."""
    target = f"{host}:{port}"

    # Get brief connection info
    rc, out, _ = _run([
        "openssl", "s_client", "-connect", target,
        "-brief", "-verify_quiet",
    ])

    # Get cert subject / dates (pipe /dev/null to avoid blocking on stdin)
    rc2, cert_out, _ = _run([
        "openssl", "s_client", "-connect", target,
        "-servername", host, "-showcerts",
    ])

    all_lines = (out + "\n" + cert_out).splitlines()
    subject = next((ln for ln in all_lines if "subject" in ln.lower()), "")
    issuer = next((ln for ln in all_lines if "issuer" in ln.lower()), "")
    expiry = next(
        (ln for ln in all_lines if "notafter" in ln.lower() or "expire" in ln.lower()), ""
    )

    return {
        "ok": rc == 0 or rc2 == 0,
        "host": host,
        "port": port,
        "subject": subject.strip(),
        "issuer": issuer.strip(),
        "expiry": expiry.strip(),
    }


# ── SSH tunnel ────────────────────────────────────────────────────────────────

def ssh_tunnel_start(
    remote_host: str,
    local_port: int = 8026,
    remote_port: int = 8026,
    remote_user: str = "",
    identity_file: str = "",
) -> dict:
    """Start a background SSH tunnel: localhost:*local_port* → *remote_host*:*remote_port*."""
    pid_file = Path(f"/tmp/singine-tunnel-{local_port}.pid")
    user_at = f"{remote_user}@{remote_host}" if remote_user else remote_host

    cmd = ["ssh", "-f", "-N", "-o", "StrictHostKeyChecking=accept-new",
           "-L", f"{local_port}:127.0.0.1:{remote_port}"]
    if identity_file:
        cmd += ["-i", identity_file]
    cmd.append(user_at)

    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    time.sleep(0.8)  # allow SSH to daemonise
    rc = proc.poll()
    if rc is not None and rc != 0:
        _, err = proc.communicate(timeout=2)
        return {"ok": False, "error": err.decode().strip() if err else "ssh exited early"}

    # ssh -f forks; record the shell PID as best-effort
    pid_file.write_text(str(proc.pid))
    return {
        "ok": True,
        "local_port": local_port,
        "remote_host": remote_host,
        "remote_port": remote_port,
        "pid_file": str(pid_file),
    }


def ssh_tunnel_stop(local_port: int = 8026) -> dict:
    """Stop an SSH tunnel by killing the PID recorded in /tmp."""
    pid_file = Path(f"/tmp/singine-tunnel-{local_port}.pid")
    if not pid_file.exists():
        return {"ok": False, "error": f"No PID file: {pid_file}"}
    try:
        pid = int(pid_file.read_text().strip())
    except ValueError:
        return {"ok": False, "error": "PID file unreadable"}
    rc, _, err = _run(["kill", str(pid)])
    pid_file.unlink(missing_ok=True)
    return {"ok": rc == 0, "pid": pid, "error": err or None}


def ssh_tunnel_status(local_port: int = 8026) -> dict:
    """Check whether an SSH tunnel on *local_port* is active."""
    pid_file = Path(f"/tmp/singine-tunnel-{local_port}.pid")
    if not pid_file.exists():
        return {"ok": True, "active": False, "local_port": local_port}
    try:
        pid = int(pid_file.read_text().strip())
    except ValueError:
        return {"ok": False, "error": "PID file unreadable"}
    rc, _, _ = _run(["kill", "-0", str(pid)])
    return {"ok": True, "active": rc == 0, "pid": pid, "local_port": local_port}


# ── WireGuard VPN ─────────────────────────────────────────────────────────────

def vpn_status() -> dict:
    """Return WireGuard interface status."""
    rc, out, err = _run(["wg", "show"])
    if rc != 0:
        return {"ok": False, "error": err or "wg not found or no interfaces active"}
    ifaces = [ln.split(":", 1)[1].strip() for ln in out.splitlines() if ln.startswith("interface:")]
    peers = sum(1 for ln in out.splitlines() if ln.strip().startswith("peer:"))
    return {"ok": True, "interfaces": ifaces, "peers": peers, "raw": out}


def vpn_up(config: str) -> dict:
    """Bring up a WireGuard interface via wg-quick."""
    rc, out, err = _run(["wg-quick", "up", config])
    return {"ok": rc == 0, "config": config, "output": out, "error": err or None}


def vpn_down(config: str) -> dict:
    """Bring down a WireGuard interface via wg-quick."""
    rc, out, err = _run(["wg-quick", "down", config])
    return {"ok": rc == 0, "config": config, "output": out, "error": err or None}
