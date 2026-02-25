-- V003__categories.sql — Multi-dimensional categories + similarity + shortest-path graph

-- ── Category taxonomy ─────────────────────────────────────────────────────────
-- Each category carries: dimension (main/primary/secondary/n-linear/relational/boolean),
-- parent for hierarchical constraint, and a boolean algebra expression.
CREATE TABLE IF NOT EXISTS categories (
  gen_id       TEXT NOT NULL PRIMARY KEY,
  name         TEXT NOT NULL,
  urn          TEXT NOT NULL UNIQUE,             -- urn:singine:cat:<name>
  dimension    TEXT NOT NULL
                    CHECK(dimension IN
                      ('main','primary','secondary','n_linear',
                       'relational','boolean','temporal')),
  parent_id    TEXT REFERENCES categories(gen_id),  -- hierarchical constraint
  bool_expr    TEXT,  -- Boolean algebra: e.g. "(main AND primary) OR NOT secondary"
  weight       REAL   NOT NULL DEFAULT 1.0,
  validated    INTEGER NOT NULL DEFAULT 0,       -- 1 = validated algorithm applied
  created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  meta         TEXT
);

-- Seed base ontology
INSERT OR IGNORE INTO categories (gen_id, name, urn, dimension, validated) VALUES
  ('cat-main',       'Main',        'urn:singine:cat:main',       'main',       1),
  ('cat-primary',    'Primary',     'urn:singine:cat:primary',    'primary',    1),
  ('cat-secondary',  'Secondary',   'urn:singine:cat:secondary',  'secondary',  1),
  ('cat-nlinear',    'NLinear',     'urn:singine:cat:n_linear',   'n_linear',   0),
  ('cat-relational', 'Relational',  'urn:singine:cat:relational', 'relational', 1),
  ('cat-boolean',    'Boolean',     'urn:singine:cat:boolean',    'boolean',    1),
  ('cat-temporal',   'Temporal',    'urn:singine:cat:temporal',   'temporal',   0);

-- ── Entity-category membership (reification) ─────────────────────────────────
CREATE TABLE IF NOT EXISTS entity_categories (
  gen_id       TEXT NOT NULL PRIMARY KEY,
  entity_id    TEXT NOT NULL,                    -- references any gen_id
  entity_type  TEXT NOT NULL,                    -- lineage, ldap_entity, pipeline_run
  category_id  TEXT NOT NULL REFERENCES categories(gen_id),
  score        REAL NOT NULL DEFAULT 1.0,        -- similarity score 0..1
  algorithm    TEXT NOT NULL DEFAULT 'hierarchical',
  validated    INTEGER NOT NULL DEFAULT 0,
  assigned_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- ── Similarity edges (for shortest-path graph) ────────────────────────────────
-- Edge list: (src, dst, weight) where weight = 1 - cosine_similarity
-- Rust quicksort engine reads this table to build the adjacency vector.
CREATE TABLE IF NOT EXISTS similarity_edges (
  gen_id       TEXT NOT NULL PRIMARY KEY,
  src_id       TEXT NOT NULL,
  dst_id       TEXT NOT NULL,
  weight       REAL NOT NULL CHECK(weight >= 0),
  edge_type    TEXT NOT NULL DEFAULT 'similarity'
                    CHECK(edge_type IN
                      ('similarity','lineage','category','ldap_parent')),
  created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- ── Shortest-path results ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS path_results (
  gen_id       TEXT NOT NULL PRIMARY KEY,
  src_id       TEXT NOT NULL,
  dst_id       TEXT NOT NULL,
  path_json    TEXT NOT NULL,                    -- ordered list of gen_ids
  total_weight REAL NOT NULL,
  algorithm    TEXT NOT NULL DEFAULT 'dijkstra+quicksort',
  computed_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  run_id       TEXT REFERENCES pipeline_runs(gen_id)
);

-- ── FOAF/DOAP semantic records ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS semantic_records (
  gen_id       TEXT NOT NULL PRIMARY KEY,
  subject_uri  TEXT NOT NULL,
  vocab        TEXT NOT NULL CHECK(vocab IN ('foaf','doap','skos','dc','rss')),
  predicate    TEXT NOT NULL,
  object_val   TEXT NOT NULL,
  object_type  TEXT NOT NULL DEFAULT 'literal'
                    CHECK(object_type IN ('literal','uri','blank')),
  lineage_id   TEXT REFERENCES lineage(gen_id),
  created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

INSERT OR IGNORE INTO schema_migrations (version, description, checksum)
VALUES ('V003', 'Categories: categories, entity_categories, similarity_edges, path_results, semantic_records',
        'sha256:placeholder_V003');
