//! main.rs — Singine persistence engine entry point
//! Modes: shortest-path | gen-id | migrate-check | status
//!
//! Called by GitHub Actions Phase 4 and by the top-level Makefile.

mod id_gen;
mod shortest_path;

use clap::{Parser, ValueEnum};
use rusqlite::Connection;
use serde_json::json;
use std::path::PathBuf;
use tracing_subscriber::{fmt, EnvFilter};

#[derive(Debug, Clone, ValueEnum)]
enum Mode {
    ShortestPath,
    GenId,
    MigrateCheck,
    Status,
}

#[derive(Parser, Debug)]
#[command(name = "persistence", about = "Singine persistence engine")]
struct Args {
    #[arg(long, default_value = "singine.db")]
    db: PathBuf,

    #[arg(long, value_enum, default_value = "status")]
    mode: Mode,

    /// src node gen_id (for shortest-path mode)
    #[arg(long)]
    src: Option<String>,

    /// dst node gen_id (for shortest-path mode)
    #[arg(long)]
    dst: Option<String>,

    /// edge type filter (similarity | lineage | category | ldap_parent)
    #[arg(long)]
    edge_type: Option<String>,

    /// namespace for gen-id mode
    #[arg(long, default_value = "entity")]
    namespace: String,

    /// optional hint for gen-id mode
    #[arg(long)]
    hint: Option<String>,

    /// output JSON file path
    #[arg(long, default_value = "path-report.json")]
    output: PathBuf,

    /// run_id from pipeline_runs (for tracing)
    #[arg(long)]
    run_id: Option<String>,
}

fn main() -> anyhow::Result<()> {
    // Structured logging
    fmt()
        .with_env_filter(
            EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info")),
        )
        .json()
        .init();

    let args = Args::parse();

    tracing::info!(mode = ?args.mode, db = %args.db.display(), "Singine persistence engine start");

    let conn = Connection::open(&args.db)?;

    match args.mode {
        Mode::Status => {
            let count: i64 = conn
                .query_row("SELECT COUNT(*) FROM sqlite_master WHERE type='table'", [], |r| {
                    r.get(0)
                })
                .unwrap_or(0);
            let out = json!({
                "status": "ok",
                "db": args.db.to_string_lossy(),
                "tables": count,
                "engine": "singine-persistence-rust",
                "version": env!("CARGO_PKG_VERSION"),
            });
            println!("{}", serde_json::to_string_pretty(&out)?);
        }

        Mode::GenId => {
            let rec = id_gen::generate(&conn, &args.namespace, args.hint.as_deref())?;
            let out = json!({
                "gen_id": rec.gen_id,
                "urn":    rec.urn,
                "inode":  rec.inode,
            });
            println!("{}", serde_json::to_string_pretty(&out)?);
        }

        Mode::ShortestPath => {
            let src = args.src.as_deref().unwrap_or_else(|| {
                tracing::error!("--src required for shortest-path mode");
                std::process::exit(1);
            });
            let dst = args.dst.as_deref().unwrap_or_else(|| {
                tracing::error!("--dst required for shortest-path mode");
                std::process::exit(1);
            });

            match shortest_path::compute_and_persist(
                &conn,
                src,
                dst,
                args.edge_type.as_deref(),
                args.run_id.as_deref(),
            )? {
                Some(result) => {
                    let out = json!({
                        "ok":           true,
                        "src":          result.src_id,
                        "dst":          result.dst_id,
                        "path":         result.path,
                        "total_weight": result.total_weight,
                        "algorithm":    result.algorithm,
                    });
                    let json_str = serde_json::to_string_pretty(&out)?;
                    std::fs::write(&args.output, &json_str)?;
                    println!("{}", json_str);
                }
                None => {
                    let out = json!({"ok": false, "error": "No path found", "src": src, "dst": dst});
                    std::fs::write(&args.output, serde_json::to_string_pretty(&out)?)?;
                    std::process::exit(2);
                }
            }
        }

        Mode::MigrateCheck => {
            let ver: String = conn
                .query_row(
                    "SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1",
                    [],
                    |r| r.get(0),
                )
                .unwrap_or_else(|_| "none".to_string());
            let out = json!({"schema_version": ver, "db": args.db.to_string_lossy()});
            println!("{}", serde_json::to_string_pretty(&out)?);
        }
    }

    tracing::info!("Done");
    Ok(())
}
