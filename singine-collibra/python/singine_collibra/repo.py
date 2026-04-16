"""Repository discovery and scheduled daily commit.

Commands surface:
    singine collibra repo find          -- scan local filesystem for git repos
    singine collibra repo remote        -- list remote repos via REST API
    singine collibra repo status        -- summarise dirty/clean state of repos
    singine collibra repo daily-commit  -- stage and commit all repos in scope
    singine collibra repo schedule      -- manage cron entry for daily-commit
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


_DEFAULT_SEARCH_ROOTS = [Path.home() / "ws", Path.home()]
_MAX_DEPTH = 4
_CRON_TAG = "# singine-collibra-daily-commit"
_SCRIPT_NAME = "singine-collibra-daily-commit.sh"


# ── Data types ────────────────────────────────────────────────────────────────

@dataclass
class RepoInfo:
    path: str
    branch: str
    dirty: bool
    ahead: int
    untracked: int
    last_commit: str

    def as_dict(self) -> dict:
        return {
            "path": self.path,
            "branch": self.branch,
            "dirty": self.dirty,
            "ahead": self.ahead,
            "untracked": self.untracked,
            "last_commit": self.last_commit,
        }


# ── Internal helpers ──────────────────────────────────────────────────────────

def _run(cmd: list, cwd: Optional[str] = None) -> tuple:
    """Run *cmd*, return (returncode, stdout, stderr). Never raises."""
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=15
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return 1, "", str(exc)


def _is_git_repo(path: Path) -> bool:
    return (path / ".git").exists() or (path / ".git").is_file()


# ── Local repo discovery ──────────────────────────────────────────────────────

def find_local_repos(root: Path, depth: int = _MAX_DEPTH) -> list:
    """Walk *root* up to *depth* levels deep and return git repo paths."""
    found: list = []

    def _walk(p: Path, remaining: int) -> None:
        if remaining < 0:
            return
        if _is_git_repo(p):
            found.append(p)
            return  # don't recurse into sub-repos
        try:
            for child in sorted(p.iterdir()):
                if child.is_dir() and not child.name.startswith("."):
                    _walk(child, remaining - 1)
        except PermissionError:
            pass

    _walk(root, depth)
    return found


def repo_info(path: Path) -> RepoInfo:
    """Return a snapshot of *path*'s current git state."""
    cwd = str(path)
    _, branch, _ = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd)
    _, status_out, _ = _run(["git", "status", "--porcelain"], cwd)
    _, ahead_out, _ = _run(["git", "rev-list", "--count", "@{u}..HEAD"], cwd)
    _, last_commit, _ = _run(
        ["git", "log", "-1", "--pretty=format:%h %s", "--no-walk"], cwd
    )

    lines = [ln for ln in status_out.splitlines() if ln.strip()]
    dirty = any(not ln.startswith("?? ") for ln in lines)
    untracked = sum(1 for ln in lines if ln.startswith("?? "))
    try:
        ahead = int(ahead_out)
    except ValueError:
        ahead = 0

    return RepoInfo(
        path=str(path),
        branch=branch or "unknown",
        dirty=dirty,
        ahead=ahead,
        untracked=untracked,
        last_commit=last_commit or "(empty repo)",
    )


# ── Remote repo listing ───────────────────────────────────────────────────────

def find_remote_repos(
    provider: str = "github",
    org: str = "",
    token: str = "",
) -> dict:
    """Query remote repo listing via REST (stdlib urllib, no extra deps)."""
    import urllib.request
    import urllib.error

    tok = token or os.environ.get("GITHUB_TOKEN", "")

    if provider == "github":
        base = "https://api.github.com"
        path = f"/orgs/{org}/repos" if org else "/user/repos"
        url = f"{base}{path}?per_page=100&type=all"
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "singine-collibra"}
        if tok:
            headers["Authorization"] = f"Bearer {tok}"
    elif provider == "gitlab":
        base = os.environ.get("GITLAB_URL", "https://gitlab.com")
        ns = f"groups/{org}/projects" if org else "projects"
        url = f"{base}/api/v4/{ns}?per_page=100&membership=true"
        headers = {"User-Agent": "singine-collibra"}
        if tok:
            headers["PRIVATE-TOKEN"] = tok
    else:
        return {"ok": False, "error": f"Unsupported provider: {provider}"}

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        if isinstance(data, list):
            repos = [
                {
                    "name": r.get("name") or r.get("path", ""),
                    "full_name": r.get("full_name") or r.get("path_with_namespace", ""),
                    "url": r.get("html_url") or r.get("web_url", ""),
                    "default_branch": r.get("default_branch", "main"),
                    "private": r.get("private", False) or r.get("visibility", "") != "public",
                }
                for r in data
            ]
            return {"ok": True, "provider": provider, "repos": repos, "count": len(repos)}
        return {"ok": False, "error": "Unexpected API response shape", "data": data}
    except urllib.error.URLError as exc:
        return {"ok": False, "error": str(exc)}


# ── Daily commit ──────────────────────────────────────────────────────────────

def daily_commit(
    paths: list,
    message: str = "chore: scheduled daily commit [singine-collibra]",
    dry_run: bool = False,
    push: bool = False,
) -> dict:
    """Stage all changes and commit in each repo.

    Args:
        paths:    List of Path objects pointing to git repos.
        message:  Commit message.
        dry_run:  When True, report what would happen without making changes.
        push:     When True, git push after each successful commit.
    """
    results = []
    for p in paths:
        p = Path(p)
        info = repo_info(p)
        if not info.dirty and info.untracked == 0:
            results.append({"path": str(p), "status": "clean", "committed": False})
            continue

        if dry_run:
            results.append({
                "path": str(p),
                "status": "would-commit",
                "dirty": info.dirty,
                "untracked": info.untracked,
            })
            continue

        rc, _, err = _run(["git", "add", "-A"], str(p))
        if rc != 0:
            results.append({"path": str(p), "status": "error", "stage": err})
            continue

        rc, out, err = _run(["git", "commit", "-m", message], str(p))
        if rc != 0:
            results.append({"path": str(p), "status": "error", "commit": err})
            continue

        entry: dict = {
            "path": str(p),
            "status": "committed",
            "output": out.splitlines()[0] if out else "",
        }

        if push:
            rc2, push_out, push_err = _run(["git", "push"], str(p))
            entry["pushed"] = rc2 == 0
            if rc2 != 0:
                entry["push_error"] = push_err

        results.append(entry)

    return {
        "ok": True,
        "dry_run": dry_run,
        "push": push,
        "results": results,
        "committed": sum(1 for r in results if r.get("status") == "committed"),
        "clean": sum(1 for r in results if r.get("status") == "clean"),
        "errors": sum(1 for r in results if r.get("status") == "error"),
    }


# ── Cron schedule ─────────────────────────────────────────────────────────────

def _script_path() -> Path:
    return Path.home() / ".local" / "bin" / _SCRIPT_NAME


def _write_daily_script(root: str, notify_email: str, push: bool) -> Path:
    script = _script_path()
    script.parent.mkdir(parents=True, exist_ok=True)
    exe = sys.executable
    push_flag = " --push" if push else ""
    notify_lines = []
    if notify_email:
        notify_lines = [
            f'  | {exe} -m singine collibra notify email \\',
            f'    --to "{notify_email}" \\',
            f'    --subject "daily-commit $(hostname) $(date +%F)" \\',
            f'    --stdin',
        ]

    body_lines = [
        "#!/usr/bin/env bash",
        "# Generated by: singine collibra repo schedule install",
        "set -euo pipefail",
        f'{exe} -m singine collibra repo daily-commit \\',
        f'  --root "{root}"{push_flag} --json \\',
    ] + notify_lines

    script.write_text("\n".join(body_lines) + "\n")
    script.chmod(0o755)
    return script


def schedule_install(
    root: str,
    hour: int = 23,
    notify_email: str = "",
    push: bool = False,
) -> dict:
    """Install a crontab entry to run daily-commit at *hour* UTC each day."""
    script = _write_daily_script(root, notify_email, push)
    cron_line = f"0 {hour} * * * {script}  {_CRON_TAG}"

    rc, existing, _ = _run(["crontab", "-l"])
    lines = existing.splitlines() if rc == 0 else []
    lines = [ln for ln in lines if _CRON_TAG not in ln]
    lines.append(cron_line)
    new_cron = "\n".join(lines) + "\n"

    proc = subprocess.run(["crontab", "-"], input=new_cron, text=True, capture_output=True)
    if proc.returncode != 0:
        return {"ok": False, "error": proc.stderr.strip()}
    return {
        "ok": True,
        "cron_line": cron_line,
        "script": str(script),
        "hour": hour,
        "notify_email": notify_email,
    }


def schedule_remove() -> dict:
    """Remove the singine-collibra daily-commit crontab entry."""
    rc, existing, _ = _run(["crontab", "-l"])
    if rc != 0:
        return {"ok": True, "message": "No crontab found — nothing to remove"}
    lines = [ln for ln in existing.splitlines() if _CRON_TAG not in ln]
    new_cron = "\n".join(lines) + "\n"
    proc = subprocess.run(["crontab", "-"], input=new_cron, text=True, capture_output=True)
    if proc.returncode != 0:
        return {"ok": False, "error": proc.stderr.strip()}
    return {"ok": True, "message": "Removed singine-collibra-daily-commit crontab entry"}


def schedule_status() -> dict:
    """Return current cron schedule status."""
    rc, existing, _ = _run(["crontab", "-l"])
    entries = []
    if rc == 0:
        entries = [ln for ln in existing.splitlines() if _CRON_TAG in ln]
    script = _script_path()
    return {
        "ok": True,
        "installed": bool(entries),
        "entries": entries,
        "script": str(script),
        "script_exists": script.exists(),
    }
