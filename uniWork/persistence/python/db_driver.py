#!/usr/bin/env python3
"""
db_driver.py — Singine open.dbc multi-database connection manager
Supports: SQLite · MariaDB · Hive (Apache)
Reads config from config/open.dbc (INI format) or config/connections.edn.

This is the ODB (Open Database Connectivity) abstraction layer —
all database access in the Python layer goes through here.
"""

import configparser
import json
import os
import sqlite3
from contextlib import contextmanager
from typing import Generator, Optional


# ── DSN config reader ─────────────────────────────────────────────────────────

def read_odbc_config(path: str = "config/open.dbc") -> dict:
    """Parse open.dbc INI file into a dict of DSN → params."""
    cfg = configparser.ConfigParser()
    cfg.read(path)
    result = {}
    for section in cfg.sections():
        result[section] = dict(cfg[section])
    return result


# ── Driver registry ───────────────────────────────────────────────────────────

class Driver:
    """Base driver interface."""
    def connect(self): ...
    def execute(self, sql: str, params=()): ...
    def close(self): ...


class SQLiteDriver(Driver):
    def __init__(self, database: str, **kwargs):
        self._path = database
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self) -> "SQLiteDriver":
        self._conn = sqlite3.connect(self._path)
        self._conn.row_factory = sqlite3.Row
        return self

    def execute(self, sql: str, params=()):
        cur = self._conn.execute(sql, params)
        self._conn.commit()
        return cur.fetchall()

    def query(self, sql: str, params=()):
        return self._conn.execute(sql, params).fetchall()

    def close(self):
        if self._conn:
            self._conn.close()

    @property
    def raw(self) -> sqlite3.Connection:
        return self._conn


class MariaDBDriver(Driver):
    def __init__(self, host="localhost", port=3306, database="singine",
                 user=None, password=None, **kwargs):
        self._cfg = dict(
            host=host, port=int(port), database=database,
            user=user or os.environ.get("DB_USER", "singine"),
            password=password or os.environ.get("DB_PASS", ""),
        )
        self._conn = None

    def connect(self) -> "MariaDBDriver":
        import mysql.connector
        self._conn = mysql.connector.connect(**self._cfg)
        return self

    def execute(self, sql: str, params=()):
        cur = self._conn.cursor(dictionary=True)
        cur.execute(sql, params)
        self._conn.commit()
        return cur.fetchall()

    def query(self, sql: str, params=()):
        return self.execute(sql, params)

    def close(self):
        if self._conn:
            self._conn.close()


class HiveDriver(Driver):
    def __init__(self, host="localhost", port=10000, database="singine",
                 user=None, **kwargs):
        self._cfg = dict(
            host=host, port=int(port), database=database,
            username=user or os.environ.get("DB_USER", "singine"),
        )
        self._conn = None

    def connect(self) -> "HiveDriver":
        from pyhive import hive
        self._conn = hive.Connection(**self._cfg)
        return self

    def execute(self, sql: str, params=()):
        cur = self._conn.cursor()
        cur.execute(sql, params)
        return cur.fetchall()

    def query(self, sql: str, params=()):
        return self.execute(sql, params)

    def close(self):
        if self._conn:
            self._conn.close()


# ── Connection factory ────────────────────────────────────────────────────────

_DRIVER_MAP = {
    "sqlite":   SQLiteDriver,
    "mariadb":  MariaDBDriver,
    "mysql":    MariaDBDriver,
    "hive":     HiveDriver,
}

def get_driver(alias: str, config_path: str = "config/open.dbc") -> Driver:
    """Return a connected driver for the given DSN alias."""
    cfg = read_odbc_config(config_path)
    if alias not in cfg:
        raise KeyError(f"DSN '{alias}' not found in {config_path}")
    params = cfg[alias]
    driver_name = params.pop("driver", "sqlite").lower()
    cls = _DRIVER_MAP.get(driver_name)
    if not cls:
        raise ValueError(f"Unknown driver: {driver_name}")
    return cls(**params).connect()


@contextmanager
def open_connection(alias: str = "singine_sqlite_dev",
                    config_path: str = "config/open.dbc") -> Generator[Driver, None, None]:
    """Context manager for auto-close connections."""
    driver = get_driver(alias, config_path)
    try:
        yield driver
    finally:
        driver.close()


# ── Lineage helper ────────────────────────────────────────────────────────────

def insert_lineage(driver: Driver, gen_id: str, commit_sha: str,
                   branch: str, repo: str, author: str, message: str,
                   phase: str = "raw", parent_id: Optional[str] = None) -> str:
    urn = f"urn:singine:lin:{gen_id}"
    driver.execute(
        """INSERT OR IGNORE INTO lineage
           (gen_id, commit_sha, branch, repo, author, message, phase, parent_id, urn)
         VALUES (?,?,?,?,?,?,?,?,?)""",
        (gen_id, commit_sha, branch, repo, author, message, phase, parent_id, urn),
    )
    return urn


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Singine DB driver CLI")
    ap.add_argument("--alias",  default="singine_sqlite_dev")
    ap.add_argument("--config", default="config/open.dbc")
    ap.add_argument("--sql",    help="Raw SQL to execute")
    args = ap.parse_args()

    with open_connection(args.alias, args.config) as drv:
        if args.sql:
            rows = drv.query(args.sql)
            print(json.dumps([dict(r) for r in rows], default=str, indent=2))
        else:
            print(f"Connected to alias='{args.alias}' OK")
