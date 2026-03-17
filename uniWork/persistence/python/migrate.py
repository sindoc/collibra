#!/usr/bin/env python3
"""
migrate.py — Singine schema migration runner
Applies versioned SQL migrations (V001, V002, ...) to SQLite / MariaDB / Hive.
raw → base migration step in the chain of command.

Usage:
  python3 migrate.py --db singine.db --migrations schema/ --env dev
"""

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"sha256:{h}"


def get_connection(driver: str, db_path: str, **kwargs):
    if driver == "sqlite":
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    elif driver == "mariadb":
        import mysql.connector
        return mysql.connector.connect(
            host=kwargs.get("host", "localhost"),
            port=kwargs.get("port", 3306),
            user=kwargs.get("user", os.environ.get("DB_USER", "singine")),
            password=kwargs.get("password", os.environ.get("DB_PASS", "")),
            database=kwargs.get("database", "singine"),
        )
    elif driver == "hive":
        from pyhive import hive
        return hive.Connection(
            host=kwargs.get("host", "localhost"),
            port=kwargs.get("port", 10000),
            username=kwargs.get("user", os.environ.get("DB_USER", "singine")),
            database=kwargs.get("database", "singine"),
        )
    raise ValueError(f"Unknown driver: {driver}")


def find_migrations(migrations_dir: Path) -> list[Path]:
    """Return V*.sql files in ascending version order."""
    files = sorted(
        migrations_dir.glob("V*.sql"),
        key=lambda p: int(re.search(r"V(\d+)", p.name).group(1)),
    )
    return files


def already_applied(conn, version: str) -> bool:
    try:
        cur = conn.execute(
            "SELECT 1 FROM schema_migrations WHERE version = ?", (version,)
        )
        return cur.fetchone() is not None
    except Exception:
        return False


def apply_migration(conn, path: Path, env: str) -> dict:
    version = re.search(r"(V\d+)", path.name).group(1)
    checksum = sha256_file(path)

    if already_applied(conn, version):
        print(f"  [skip] {path.name} — already applied")
        return {"version": version, "status": "skipped"}

    sql = path.read_text(encoding="utf-8")

    # Split on ; for multi-statement files (SQLite doesn't support executescript + params)
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    print(f"  [apply] {path.name} ({len(statements)} statements)...")

    for stmt in statements:
        if stmt:
            try:
                conn.execute(stmt)
            except Exception as e:
                # Some statements may fail on dialect difference — log and continue
                print(f"    [warn] {e}", file=sys.stderr)

    # Update checksum in schema_migrations (may already be inserted by the SQL itself)
    try:
        conn.execute(
            "UPDATE schema_migrations SET checksum = ? WHERE version = ?",
            (checksum, version),
        )
    except Exception:
        pass

    conn.commit()
    print(f"  [done] {version}")
    return {"version": version, "status": "applied", "checksum": checksum}


def record_env_migration(conn, from_env: str, to_env: str, schema_ver: str, gen_id: str):
    """Insert an env_migrations record after successful migration."""
    try:
        conn.execute(
            """INSERT OR IGNORE INTO env_migrations
               (gen_id, from_env, to_env, lang, schema_ver, status, inode_path, dir_path)
             VALUES (?,?,?,?,?,?,?,?)""",
            (
                gen_id,
                from_env,
                to_env,
                "python",
                schema_ver,
                "applied",
                f"/var/singine/{to_env}",
                f"uniWork/persistence/schema",
            ),
        )
        conn.commit()
    except Exception as e:
        print(f"[warn] env_migration record: {e}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description="Singine schema migration runner")
    ap.add_argument("--db",         default="singine.db")
    ap.add_argument("--driver",     default="sqlite",
                    choices=["sqlite", "mariadb", "hive"])
    ap.add_argument("--migrations", default="schema")
    ap.add_argument("--env",        default="dev")
    args = ap.parse_args()

    migrations_dir = Path(args.migrations)
    if not migrations_dir.exists():
        print(f"Error: migrations dir not found: {migrations_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"[migrate] env={args.env} driver={args.driver} db={args.db}")
    conn = get_connection(args.driver, args.db)

    migration_files = find_migrations(migrations_dir)
    if not migration_files:
        print("[migrate] No migration files found.", file=sys.stderr)
        sys.exit(0)

    results = []
    for mf in migration_files:
        result = apply_migration(conn, mf, args.env)
        results.append(result)

    # Determine current schema version
    last_ver = results[-1]["version"] if results else "V000"

    # Record env transition raw → base
    import uuid
    gen_id = f"envmig-{str(uuid.uuid4())[:8]}"
    record_env_migration(conn, "raw", args.env, last_ver, gen_id)

    summary = {
        "timestamp":     utc_now(),
        "env":           args.env,
        "driver":        args.driver,
        "db":            args.db,
        "schema_ver":    last_ver,
        "migrations":    results,
        "env_migration": gen_id,
    }
    print(json.dumps(summary, indent=2))
    conn.close()


if __name__ == "__main__":
    main()
