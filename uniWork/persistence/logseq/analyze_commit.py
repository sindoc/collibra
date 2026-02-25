#!/usr/bin/env python3
"""
logseq/analyze_commit.py — Singine commit analyzer
Implements the raw → base → master pipeline for each git commit.

Stages:
  raw    — capture raw git data (sha, diff stats, files changed)
  base   — normalize to schema (lineage record, env_migration)
  master — finalize lineage, update phase, record pipeline_run

Persists to SQLite; the final DB is the Logseq knowledge graph source.
"""

import argparse
import json
import os
import sqlite3
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def gen_id(namespace: str) -> str:
    return f"{namespace}-{str(uuid.uuid4())[:8]}"


# ── Git helpers ───────────────────────────────────────────────────────────────

def git(*args) -> str:
    try:
        return subprocess.check_output(
            ["git"] + list(args), stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return ""


def get_commit_data(sha: str) -> dict:
    """Extract raw commit data from git."""
    return {
        "sha":        sha,
        "author":     git("log", "-1", "--format=%aN", sha) or "unknown",
        "email":      git("log", "-1", "--format=%aE", sha) or "",
        "message":    git("log", "-1", "--format=%s",  sha) or "",
        "timestamp":  git("log", "-1", "--format=%aI", sha) or utc_now(),
        "files":      git("diff-tree", "--no-commit-id", "-r", "--name-only", sha)
                          .splitlines(),
        "insertions": _stat(sha, "insertions"),
        "deletions":  _stat(sha, "deletions"),
    }


def _stat(sha: str, kind: str) -> int:
    out = git("show", "--stat", "--oneline", sha)
    for line in out.splitlines():
        if kind in line:
            try:
                return int(line.strip().split()[0])
            except (ValueError, IndexError):
                pass
    return 0


# ── Pipeline phases ───────────────────────────────────────────────────────────

def phase_raw(conn: sqlite3.Connection, sha: str, branch: str,
              author: str, repo: str) -> dict:
    """Phase 1 — raw: capture and persist raw commit data."""
    raw_data = get_commit_data(sha)
    raw_data["author"] = raw_data["author"] or author

    run_id  = gen_id("run")
    lin_id  = gen_id("lin")
    urn     = f"urn:singine:lin:{lin_id}"

    # pipeline_runs record
    conn.execute(
        """INSERT OR IGNORE INTO pipeline_runs
           (gen_id, phase, status, env, started_at, meta)
         VALUES (?,?,?,?,?,?)""",
        (run_id, "raw", "running", "ci", utc_now(),
         json.dumps({"commit": sha, "branch": branch})),
    )

    # lineage record — phase=raw
    conn.execute(
        """INSERT OR IGNORE INTO lineage
           (gen_id, commit_sha, branch, repo, author, message, phase, urn)
         VALUES (?,?,?,?,?,?,?,?)""",
        (lin_id, sha, branch, repo,
         raw_data["author"], raw_data["message"], "raw", urn),
    )
    conn.commit()
    print(f"  [raw]  lineage_id={lin_id} urn={urn}")
    return {"run_id": run_id, "lineage_id": lin_id, "raw": raw_data}


def phase_base(conn: sqlite3.Connection, ctx: dict, env: str = "dev") -> dict:
    """Phase 2 — base: normalize, link env_migration, advance to base."""
    lin_id = ctx["lineage_id"]
    run_id = ctx["run_id"]
    env_id = gen_id("envmig")

    # Advance lineage phase
    conn.execute(
        "UPDATE lineage SET phase='base' WHERE gen_id=?", (lin_id,)
    )

    # env_migrations record: raw → base
    conn.execute(
        """INSERT OR IGNORE INTO env_migrations
           (gen_id, from_env, to_env, lang, schema_ver, status, inode_path, dir_path, meta)
         VALUES (?,?,?,?,?,?,?,?,?)""",
        (env_id, "raw", "base", "python", "V003", "applied",
         f"/var/singine/{env}", "uniWork/persistence",
         json.dumps({"lineage_id": lin_id, "files": ctx["raw"]["files"]})),
    )

    # Update pipeline_run
    conn.execute(
        "UPDATE pipeline_runs SET phase='base', status='running' WHERE gen_id=?",
        (run_id,),
    )
    conn.commit()
    print(f"  [base] env_migration_id={env_id} phase=base")
    return {**ctx, "env_id": env_id, "phase": "base"}


def phase_master(conn: sqlite3.Connection, ctx: dict) -> dict:
    """Phase 3 — master: finalize, insert RSS entry, close pipeline_run."""
    lin_id = ctx["lineage_id"]
    run_id = ctx["run_id"]
    sha    = ctx["raw"]["sha"]

    # Advance to master
    conn.execute(
        "UPDATE lineage SET phase='master' WHERE gen_id=?", (lin_id,)
    )

    # RSS entry
    rss_id = gen_id("rss")
    conn.execute(
        """INSERT OR IGNORE INTO rss_feed
           (gen_id, title, link, description, lineage_id, source)
         VALUES (?,?,?,?,?,?)""",
        (rss_id,
         f"Commit {sha[:8]} merged to master lineage",
         f"https://github.com/{ctx['raw'].get('repo','sindoc/collibra')}/commit/{sha}",
         ctx["raw"]["message"],
         lin_id,
         "singine-commit-analyzer"),
    )

    # Close pipeline_run
    conn.execute(
        """UPDATE pipeline_runs
           SET phase='master', status='success', finished_at=?,
               meta=json_patch(COALESCE(meta,'{}'), ?)
         WHERE gen_id=?""",
        (utc_now(),
         json.dumps({"lineage_id": lin_id, "rss_id": rss_id}),
         run_id),
    )
    conn.commit()
    print(f"  [master] lineage_id={lin_id} rss_id={rss_id} status=success")
    return {**ctx, "phase": "master", "rss_id": rss_id}


# ── inode dir path logger ─────────────────────────────────────────────────────

def log_inode_paths(conn: sqlite3.Connection, files: list[str], lineage_id: str):
    """Record each changed file as an env_migration dir/inode path."""
    for f in files:
        path  = Path(f)
        inode = gen_id("inode")
        conn.execute(
            """INSERT OR IGNORE INTO env_migrations
               (gen_id, from_env, to_env, lang, schema_ver, status,
                inode_path, dir_path, folder, meta)
             VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (inode, "raw", "master", "auto", "V003", "file-tracked",
             str(path),                     # inode_path
             str(path.parent),              # dir_path
             path.parts[0] if path.parts else ".",  # folder
             json.dumps({"lineage_id": lineage_id, "file": f})),
        )
    conn.commit()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Singine commit analyzer")
    ap.add_argument("--db",     default="singine.db")
    ap.add_argument("--commit", required=True)
    ap.add_argument("--branch", default="main")
    ap.add_argument("--author", default="singine-bot")
    ap.add_argument("--repo",   default="sindoc/collibra")
    ap.add_argument("--env",    default="dev")
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    conn.execute("PRAGMA journal_mode=WAL")   # safe concurrent access

    print(f"[analyze] commit={args.commit[:8]} branch={args.branch}")

    ctx = phase_raw(conn, args.commit, args.branch, args.author, args.repo)
    ctx["raw"]["repo"] = args.repo
    log_inode_paths(conn, ctx["raw"]["files"], ctx["lineage_id"])

    ctx = phase_base(conn, ctx, args.env)
    ctx = phase_master(conn, ctx)

    # Emit output for GitHub Actions GITHUB_OUTPUT
    output = {
        "lineage_id": ctx["lineage_id"],
        "run_id":     ctx["run_id"],
        "phase":      ctx["phase"],
        "rss_id":     ctx.get("rss_id"),
    }
    print(json.dumps(output, indent=2))

    # Write lineage_id for downstream steps
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"lineage_id={ctx['lineage_id']}\n")

    conn.close()


if __name__ == "__main__":
    main()
