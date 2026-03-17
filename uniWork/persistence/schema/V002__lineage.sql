-- V002__lineage.sql — Lineage by design: commit, entity, LDAP tree

-- ── Lineage records ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS lineage (
  gen_id       TEXT NOT NULL PRIMARY KEY,
  commit_sha   TEXT NOT NULL,
  branch       TEXT NOT NULL,
  repo         TEXT NOT NULL,
  author       TEXT NOT NULL,
  message      TEXT,
  phase        TEXT NOT NULL DEFAULT 'raw'
                    CHECK(phase IN ('raw','base','master')),
  parent_id    TEXT REFERENCES lineage(gen_id),  -- chain
  created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  urn          TEXT,                             -- e.g. urn:singine:lineage:<gen_id>
  meta         TEXT                              -- JSON blob
);

-- ── LDAP tree: org entities ───────────────────────────────────────────────────
-- Stores dc/ou/cn hierarchy conforming to RFC 4512 DN structure.
CREATE TABLE IF NOT EXISTS ldap_entities (
  gen_id       TEXT NOT NULL PRIMARY KEY,
  dn           TEXT NOT NULL UNIQUE,             -- Distinguished Name
  entity_type  TEXT NOT NULL                     -- dc, ou, cn, uid
                    CHECK(entity_type IN ('dc','ou','cn','uid','o')),
  parent_dn    TEXT REFERENCES ldap_entities(dn),
  common_name  TEXT NOT NULL,
  org_unit     TEXT,
  description  TEXT,
  foaf_uri     TEXT,                             -- http://xmlns.com/foaf/0.1/
  doap_uri     TEXT,                             -- http://usefulinc.com/ns/doap#
  created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  meta         TEXT
);

-- Seed base LDAP tree: dc=singine,dc=io
INSERT OR IGNORE INTO ldap_entities (gen_id, dn, entity_type, common_name)
VALUES
  ('ent-dc-singine', 'dc=singine,dc=io',           'dc', 'singine'),
  ('ent-ou-projects','ou=Projects,dc=singine,dc=io','ou', 'Projects'),
  ('ent-ou-services','ou=Services,dc=singine,dc=io','ou', 'Services'),
  ('ent-ou-users',   'ou=Users,dc=singine,dc=io',   'ou', 'Users'),
  ('ent-cn-smtp',    'cn=smtpAgent,ou=Services,dc=singine,dc=io','cn','smtpAgent'),
  ('ent-cn-persist', 'cn=persistence,ou=Services,dc=singine,dc=io','cn','persistence');

-- ── RSS feed entries ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS rss_feed (
  gen_id       TEXT NOT NULL PRIMARY KEY,
  title        TEXT NOT NULL,
  link         TEXT NOT NULL,
  description  TEXT,
  pub_date     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  category     TEXT,
  lineage_id   TEXT REFERENCES lineage(gen_id),
  source       TEXT DEFAULT 'singine-commit-analyzer'
);

-- ── ODB / database connections registry ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS db_connections (
  gen_id       TEXT NOT NULL PRIMARY KEY,
  alias        TEXT NOT NULL UNIQUE,
  driver       TEXT NOT NULL                     -- sqlite, mariadb, hive
                    CHECK(driver IN ('sqlite','mariadb','hive','postgres')),
  host         TEXT,
  port         INTEGER,
  database     TEXT NOT NULL,
  schema_ver   TEXT,
  active       INTEGER NOT NULL DEFAULT 1,
  created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

INSERT OR IGNORE INTO db_connections
  (gen_id, alias, driver, database)
VALUES
  ('conn-sqlite-dev', 'singine_sqlite_dev', 'sqlite', 'singine.db');

INSERT OR IGNORE INTO schema_migrations (version, description, checksum)
VALUES ('V002', 'Lineage: lineage, ldap_entities, rss_feed, db_connections',
        'sha256:placeholder_V002');
