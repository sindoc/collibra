//! shortest_path.rs — Singine shortest-path engine
//!
//! Algorithm:
//!   1. Load similarity_edges from SQLite → Vec<Edge>           (raw data)
//!   2. Quicksort the edge Vec by weight (ascending)            (list→vector transform)
//!   3. Build an adjacency map (HashMap<NodeId, Vec<(NodeId, f64)>>)
//!   4. Run Dijkstra over the sorted adjacency structure         (shortest path)
//!   5. Persist result to path_results table
//!
//! The quicksort-then-Dijkstra combination gives O(E log E) sort + O((V+E) log V)
//! query — efficient for sparse governance graphs.

use rusqlite::{Connection, Result as SqlResult};
use serde::{Deserialize, Serialize};
use std::collections::{BinaryHeap, HashMap};
use std::cmp::Ordering;

use crate::id_gen;

// ── Data types ─────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Edge {
    pub gen_id:    String,
    pub src_id:    String,
    pub dst_id:    String,
    pub weight:    f64,
    pub edge_type: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PathResult {
    pub src_id:       String,
    pub dst_id:       String,
    pub path:         Vec<String>,
    pub total_weight: f64,
    pub algorithm:    String,
}

// Dijkstra node state — min-heap by cost
#[derive(Clone, PartialEq)]
struct State {
    cost:    f64,
    node:    String,
    history: Vec<String>,
}

impl Eq for State {}
impl Ord for State {
    fn cmp(&self, other: &Self) -> Ordering {
        other.cost.partial_cmp(&self.cost).unwrap_or(Ordering::Equal)
    }
}
impl PartialOrd for State {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

// ── Quicksort ─────────────────────────────────────────────────────────────────

/// In-place quicksort on edges by weight (ascending).
/// Transforms the flat edge list into a vector sorted for efficient Dijkstra.
pub fn quicksort_edges(edges: &mut Vec<Edge>) {
    let n = edges.len();
    if n < 2 {
        return;
    }
    qs_partition(edges, 0, n - 1);
}

fn qs_partition(edges: &mut Vec<Edge>, lo: usize, hi: usize) {
    if lo >= hi {
        return;
    }
    let pivot_w = edges[hi].weight;
    let mut i = lo;
    for j in lo..hi {
        if edges[j].weight <= pivot_w {
            edges.swap(i, j);
            i += 1;
        }
    }
    edges.swap(i, hi);
    if i > 0 {
        qs_partition(edges, lo, i - 1);
    }
    qs_partition(edges, i + 1, hi);
}

// ── Graph builder ─────────────────────────────────────────────────────────────

fn build_adjacency(edges: &[Edge]) -> HashMap<String, Vec<(String, f64)>> {
    let mut adj: HashMap<String, Vec<(String, f64)>> = HashMap::new();
    for e in edges {
        adj.entry(e.src_id.clone())
           .or_default()
           .push((e.dst_id.clone(), e.weight));
        // undirected — add reverse
        adj.entry(e.dst_id.clone())
           .or_default()
           .push((e.src_id.clone(), e.weight));
    }
    adj
}

// ── Dijkstra ─────────────────────────────────────────────────────────────────

pub fn dijkstra(
    adj: &HashMap<String, Vec<(String, f64)>>,
    src: &str,
    dst: &str,
) -> Option<PathResult> {
    let mut dist: HashMap<String, f64> = HashMap::new();
    let mut heap = BinaryHeap::new();

    dist.insert(src.to_string(), 0.0);
    heap.push(State {
        cost:    0.0,
        node:    src.to_string(),
        history: vec![src.to_string()],
    });

    while let Some(State { cost, node, history }) = heap.pop() {
        if node == dst {
            return Some(PathResult {
                src_id:       src.to_string(),
                dst_id:       dst.to_string(),
                path:         history,
                total_weight: cost,
                algorithm:    "dijkstra+quicksort".to_string(),
            });
        }
        if let Some(&best) = dist.get(&node) {
            if cost > best + 1e-9 {
                continue;
            }
        }
        if let Some(neighbours) = adj.get(&node) {
            for (next, w) in neighbours {
                let next_cost = cost + w;
                let entry = dist.entry(next.clone()).or_insert(f64::INFINITY);
                if next_cost < *entry {
                    *entry = next_cost;
                    let mut new_hist = history.clone();
                    new_hist.push(next.clone());
                    heap.push(State {
                        cost:    next_cost,
                        node:    next.clone(),
                        history: new_hist,
                    });
                }
            }
        }
    }
    None
}

// ── DB interface ──────────────────────────────────────────────────────────────

pub fn load_edges(conn: &Connection, edge_type: Option<&str>) -> SqlResult<Vec<Edge>> {
    let sql = match edge_type {
        Some(t) => format!(
            "SELECT gen_id,src_id,dst_id,weight,edge_type FROM similarity_edges \
             WHERE edge_type='{}' ORDER BY weight",
            t
        ),
        None => "SELECT gen_id,src_id,dst_id,weight,edge_type \
                 FROM similarity_edges ORDER BY weight"
            .to_string(),
    };
    let mut stmt = conn.prepare(&sql)?;
    let edges = stmt
        .query_map([], |r| {
            Ok(Edge {
                gen_id:    r.get(0)?,
                src_id:    r.get(1)?,
                dst_id:    r.get(2)?,
                weight:    r.get(3)?,
                edge_type: r.get(4)?,
            })
        })?
        .collect::<SqlResult<Vec<_>>>()?;
    Ok(edges)
}

pub fn persist_path(
    conn: &Connection,
    result: &PathResult,
    run_id: Option<&str>,
) -> SqlResult<String> {
    let id_rec = id_gen::generate(conn, "path", None)?;
    let path_json = serde_json::to_string(&result.path).unwrap_or_default();
    conn.execute(
        "INSERT INTO path_results
           (gen_id, src_id, dst_id, path_json, total_weight, algorithm, run_id)
         VALUES (?1,?2,?3,?4,?5,?6,?7)",
        rusqlite::params![
            id_rec.gen_id,
            result.src_id,
            result.dst_id,
            path_json,
            result.total_weight,
            result.algorithm,
            run_id,
        ],
    )?;
    Ok(id_rec.gen_id)
}

// ── Public entry point ────────────────────────────────────────────────────────

pub fn compute_and_persist(
    conn: &Connection,
    src_id: &str,
    dst_id: &str,
    edge_type: Option<&str>,
    run_id: Option<&str>,
) -> SqlResult<Option<PathResult>> {
    let mut edges = load_edges(conn, edge_type)?;
    tracing::info!(edge_count = edges.len(), "Loaded edges, running quicksort");
    quicksort_edges(&mut edges);

    let adj = build_adjacency(&edges);
    match dijkstra(&adj, src_id, dst_id) {
        Some(result) => {
            let path_id = persist_path(conn, &result, run_id)?;
            tracing::info!(
                path_id = %path_id,
                total_weight = result.total_weight,
                hops = result.path.len(),
                "Shortest path found and persisted"
            );
            Ok(Some(result))
        }
        None => {
            tracing::warn!(src = %src_id, dst = %dst_id, "No path found");
            Ok(None)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_quicksort_ascending() {
        let mut edges = vec![
            Edge { gen_id: "3".into(), src_id: "a".into(), dst_id: "b".into(),
                   weight: 3.0, edge_type: "similarity".into() },
            Edge { gen_id: "1".into(), src_id: "b".into(), dst_id: "c".into(),
                   weight: 1.0, edge_type: "similarity".into() },
            Edge { gen_id: "2".into(), src_id: "a".into(), dst_id: "c".into(),
                   weight: 2.0, edge_type: "similarity".into() },
        ];
        quicksort_edges(&mut edges);
        assert_eq!(edges[0].weight, 1.0);
        assert_eq!(edges[1].weight, 2.0);
        assert_eq!(edges[2].weight, 3.0);
    }

    #[test]
    fn test_dijkstra_finds_shortest() {
        let edges = vec![
            Edge { gen_id: "e1".into(), src_id: "A".into(), dst_id: "B".into(),
                   weight: 1.0, edge_type: "sim".into() },
            Edge { gen_id: "e2".into(), src_id: "B".into(), dst_id: "C".into(),
                   weight: 2.0, edge_type: "sim".into() },
            Edge { gen_id: "e3".into(), src_id: "A".into(), dst_id: "C".into(),
                   weight: 10.0, edge_type: "sim".into() },
        ];
        let adj = build_adjacency(&edges);
        let result = dijkstra(&adj, "A", "C").unwrap();
        assert!(result.total_weight < 4.0); // A→B→C = 3, not A→C = 10
        assert_eq!(result.path, vec!["A", "B", "C"]);
    }
}
