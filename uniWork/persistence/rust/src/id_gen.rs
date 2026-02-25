//! id_gen.rs — Singine inode-style ID generator
//!
//! Each gen_id is:  <namespace>-<uuid_v4_short>
//! Each URN is:     urn:singine:<namespace>:<gen_id>
//! Each inode is:   a monotonically increasing u64 persisted in SQLite
//!
//! The "code gen key method" resolves the namespace from the URN map
//! (schema/urn_map.json) so every generated ID is URN-addressable.

use rusqlite::{Connection, Result as SqlResult};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GenId {
    pub gen_id: String,
    pub urn:    String,
    pub inode:  u64,
}

/// Generate a new inode-style ID, persist the inode counter in SQLite.
pub fn generate(conn: &Connection, namespace: &str, hint: Option<&str>) -> SqlResult<GenId> {
    // Ensure inode counter table exists
    conn.execute_batch(
        "CREATE TABLE IF NOT EXISTS inode_counter (
           namespace TEXT NOT NULL PRIMARY KEY,
           next_inode INTEGER NOT NULL DEFAULT 1
         );",
    )?;

    // Atomically increment inode for this namespace
    conn.execute(
        "INSERT INTO inode_counter (namespace, next_inode) VALUES (?1, 2)
         ON CONFLICT(namespace) DO UPDATE SET next_inode = next_inode + 1",
        [namespace],
    )?;

    let inode: u64 = conn.query_row(
        "SELECT next_inode - 1 FROM inode_counter WHERE namespace = ?1",
        [namespace],
        |r| r.get::<_, i64>(0),
    )? as u64;

    // Build gen_id: <namespace>-<uuid_short>[_hint]
    let short_uuid = &Uuid::new_v4().to_string()[..8];
    let gen_id = match hint {
        Some(h) if !h.is_empty() => {
            let safe: String = h
                .chars()
                .map(|c| if c.is_alphanumeric() || c == '-' { c } else { '_' })
                .take(16)
                .collect();
            format!("{}-{}-{}", namespace, short_uuid, safe)
        }
        _ => format!("{}-{}", namespace, short_uuid),
    };

    let urn = format!("urn:singine:{}:{}", namespace, gen_id);

    tracing::debug!(gen_id = %gen_id, urn = %urn, inode = inode, "generated ID");

    Ok(GenId { gen_id, urn, inode })
}

/// Resolve a URN back to its gen_id component.
pub fn resolve_urn(urn: &str) -> Option<String> {
    // urn:singine:<namespace>:<gen_id>
    let parts: Vec<&str> = urn.splitn(4, ':').collect();
    if parts.len() == 4 && parts[0] == "urn" && parts[1] == "singine" {
        Some(parts[3].to_string())
    } else {
        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use rusqlite::Connection;

    #[test]
    fn test_generate_increments_inode() {
        let conn = Connection::open_in_memory().unwrap();
        let a = generate(&conn, "lineage", None).unwrap();
        let b = generate(&conn, "lineage", None).unwrap();
        assert_eq!(a.inode + 1, b.inode);
        assert!(a.gen_id.starts_with("lineage-"));
        assert!(a.urn.starts_with("urn:singine:lineage:"));
    }

    #[test]
    fn test_resolve_urn() {
        let urn = "urn:singine:cat:cat-abc12345";
        let id = resolve_urn(urn).unwrap();
        assert_eq!(id, "cat-abc12345");
    }
}
