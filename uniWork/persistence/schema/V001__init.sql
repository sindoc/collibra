-- V001__init.sql — Singine base schema
-- UTF-8, URN-addressable, inode-style gen_id primary keys
-- Compatible: SQLite · MariaDB · Hive (DDL comments mark dialect differences)

-- SQLite only: set UTF-8 encoding. MariaDB/Hive default to UTF-8 natively.
PRAGMA encoding = 'UTF-8';

-- ── Schema version registry ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS schema_migrations (
  version     TEXT        NOT NULL PRIMARY KEY,  -- e.g. "V001"
  description TEXT        NOT NULL,
  applied_at  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  checksum    TEXT        NOT NULL               -- SHA-256 of migration file
);

-- ── Pipeline run tracking ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pipeline_runs (
  gen_id      TEXT        NOT NULL PRIMARY KEY,  -- see id_gen.rs
  phase       TEXT        NOT NULL,
  status      TEXT        NOT NULL DEFAULT 'pending'
                          CHECK(status IN ('pending','running','success','failed')),
  env         TEXT        NOT NULL DEFAULT 'dev',
  started_at  TEXT,
  finished_at TEXT,
  meta        TEXT                               -- JSON blob
);

-- ── Environment migration map ─────────────────────────────────────────────────
-- Tracks every env/lang/schema version transition in the migration path.
CREATE TABLE IF NOT EXISTS env_migrations (
  gen_id       TEXT NOT NULL PRIMARY KEY,
  from_env     TEXT NOT NULL,                    -- e.g. raw, base, staging, prod
  to_env       TEXT NOT NULL,
  lang         TEXT NOT NULL,                    -- python, clj, rust, c, xml
  schema_ver   TEXT NOT NULL,
  status       TEXT NOT NULL DEFAULT 'pending',
  created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  inode_path   TEXT,                             -- unix inode-style dir path
  dir_path     TEXT,
  folder       TEXT,
  meta         TEXT                              -- JSON blob
);

-- Seed initial migration record
INSERT OR IGNORE INTO schema_migrations (version, description, checksum)
VALUES ('V001', 'Base init: pipeline_runs, env_migrations', 'sha256:placeholder_V001');
