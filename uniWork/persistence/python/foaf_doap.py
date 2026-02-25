#!/usr/bin/env python3
"""
foaf_doap.py — Singine semantic web generator
Outputs FOAF, DOAP, RSS, and silkpage/lutino.io records
from the persistence DB for each commit/lineage event.

Formats: Turtle (.ttl), RSS 2.0 XML, JSON-LD
"""

import argparse
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path


LUTINO_BASE = "https://lutino.io/singine/"
REPO_URL    = "https://github.com/sindoc/collibra"
RSS_LINK    = f"{LUTINO_BASE}feed.rss"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def rfc822_now() -> str:
    return datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")


# ── FOAF + DOAP Turtle ────────────────────────────────────────────────────────

def build_turtle(commit_sha: str, author: str, branch: str, repo: str) -> str:
    short = commit_sha[:8]
    commit_uri = f"{LUTINO_BASE}commit/{commit_sha}"
    project_uri = f"{LUTINO_BASE}project/smtpAgent"
    person_uri  = f"{LUTINO_BASE}people/{author}"

    return f"""\
@prefix foaf:   <http://xmlns.com/foaf/0.1/> .
@prefix doap:   <http://usefulinc.com/ns/doap#> .
@prefix dc:     <http://purl.org/dc/elements/1.1/> .
@prefix singine:<{LUTINO_BASE}> .
@prefix rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix xsd:    <http://www.w3.org/2001/XMLSchema#> .

# ── Project (DOAP) ───────────────────────────────────────────────────────────
<{project_uri}>
  rdf:type           doap:Project ;
  doap:name          "Singine smtpAgent" ;
  doap:homepage      <{REPO_URL}> ;
  doap:description   "Multi-layer SMTP agent: C TCP + Clojure JVM + Python web" ;
  doap:license       <https://opensource.org/licenses/MIT> ;
  doap:repository    [
    rdf:type       doap:GitRepository ;
    doap:location  <{REPO_URL}.git>
  ] ;
  doap:release [
    rdf:type       doap:Version ;
    doap:revision  "{short}" ;
    doap:created   "{utc_now()}"^^xsd:dateTime ;
    doap:branch    "{branch}"
  ] .

# ── Commit (singine lineage) ──────────────────────────────────────────────────
<{commit_uri}>
  rdf:type           singine:Commit ;
  dc:identifier      "{commit_sha}" ;
  dc:date            "{utc_now()}"^^xsd:dateTime ;
  dc:source          <{REPO_URL}> ;
  singine:branch     "{branch}" ;
  singine:author     <{person_uri}> ;
  singine:phase      "master" .

# ── Author (FOAF) ─────────────────────────────────────────────────────────────
<{person_uri}>
  rdf:type  foaf:Person ;
  foaf:nick "{author}" ;
  foaf:account [
    rdf:type          foaf:OnlineAccount ;
    foaf:accountServiceHomepage <https://github.com> ;
    foaf:accountName  "{author}"
  ] .
"""


# ── RSS 2.0 feed ──────────────────────────────────────────────────────────────

def build_rss(items: list[dict]) -> str:
    items_xml = ""
    for item in items:
        items_xml += f"""
    <item>
      <title><![CDATA[{item['title']}]]></title>
      <link>{item['link']}</link>
      <description><![CDATA[{item['description']}]]></description>
      <pubDate>{item['pub_date']}</pubDate>
      <guid isPermaLink="false">{item['guid']}</guid>
      <category>{item.get('category','commit')}</category>
    </item>"""

    return f"""\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:dc="http://purl.org/dc/elements/1.1/"
     xmlns:doap="http://usefulinc.com/ns/doap#"
     xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Singine smtpAgent — Commit Feed</title>
    <link>{REPO_URL}</link>
    <description>Auto-generated RSS feed from Singine chain-of-command pipeline</description>
    <language>en-us</language>
    <atom:link href="{RSS_LINK}" rel="self" type="application/rss+xml"/>
    <lastBuildDate>{rfc822_now()}</lastBuildDate>
    <generator>Singine foaf_doap.py</generator>{items_xml}
  </channel>
</rss>
"""


# ── JSON-LD ───────────────────────────────────────────────────────────────────

def build_jsonld(commit_sha: str, author: str, branch: str) -> dict:
    return {
        "@context": {
            "foaf": "http://xmlns.com/foaf/0.1/",
            "doap": "http://usefulinc.com/ns/doap#",
            "dc":   "http://purl.org/dc/elements/1.1/",
            "singine": LUTINO_BASE,
        },
        "@graph": [
            {
                "@id":   f"{LUTINO_BASE}commit/{commit_sha}",
                "@type": "singine:Commit",
                "dc:identifier": commit_sha,
                "singine:branch": branch,
                "singine:phase":  "master",
                "singine:author": {
                    "@id":      f"{LUTINO_BASE}people/{author}",
                    "@type":    "foaf:Person",
                    "foaf:nick": author,
                },
            }
        ],
    }


# ── DB persistence ────────────────────────────────────────────────────────────

def persist_semantic(conn: sqlite3.Connection, commit_sha: str,
                     lineage_id: str, records: list[dict]):
    for rec in records:
        gen_id = f"sem-{str(uuid.uuid4())[:8]}"
        try:
            conn.execute(
                """INSERT OR IGNORE INTO semantic_records
                   (gen_id, subject_uri, vocab, predicate, object_val,
                    object_type, lineage_id)
                 VALUES (?,?,?,?,?,?,?)""",
                (gen_id, rec["subject"], rec["vocab"], rec["predicate"],
                 rec["object"], rec.get("type", "literal"), lineage_id),
            )
        except Exception:
            pass
    conn.commit()


def persist_rss(conn: sqlite3.Connection, commit_sha: str,
                lineage_id: str, title: str, link: str, desc: str):
    gen_id = f"rss-{str(uuid.uuid4())[:8]}"
    try:
        conn.execute(
            """INSERT OR IGNORE INTO rss_feed
               (gen_id, title, link, description, lineage_id, source)
             VALUES (?,?,?,?,?,?)""",
            (gen_id, title, link, desc, lineage_id, "singine-foaf-doap"),
        )
        conn.commit()
    except Exception:
        pass


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Singine FOAF/DOAP/RSS generator")
    ap.add_argument("--db",     default="singine.db")
    ap.add_argument("--commit", required=True)
    ap.add_argument("--branch", default="main")
    ap.add_argument("--author", default="singine-bot")
    ap.add_argument("--repo",   default=REPO_URL)
    ap.add_argument("--output", default="semantic-web")
    args = ap.parse_args()

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(args.db)

    # Fetch lineage_id for this commit
    row = conn.execute(
        "SELECT gen_id FROM lineage WHERE commit_sha=? LIMIT 1", (args.commit,)
    ).fetchone()
    lineage_id = row[0] if row else f"lin-unknown-{args.commit[:8]}"

    # Generate outputs
    turtle = build_turtle(args.commit, args.author, args.branch, args.repo)
    rss_items = [{
        "title":       f"Commit {args.commit[:8]} on {args.branch}",
        "link":        f"{args.repo}/commit/{args.commit}",
        "description": f"Singine pipeline completed for {args.commit[:8]}",
        "pub_date":    rfc822_now(),
        "guid":        f"urn:singine:commit:{args.commit}",
        "category":    "commit",
    }]
    rss = build_rss(rss_items)
    jsonld = build_jsonld(args.commit, args.author, args.branch)

    (out_dir / "project.ttl").write_text(turtle, encoding="utf-8")
    (out_dir / "feed.rss").write_text(rss, encoding="utf-8")
    (out_dir / "commit.jsonld").write_text(
        json.dumps(jsonld, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"[foaf_doap] Written to {out_dir}/")

    # Persist into semantic_records and rss_feed tables
    persist_semantic(conn, args.commit, lineage_id, [
        {"subject": f"{LUTINO_BASE}commit/{args.commit}",
         "vocab": "doap", "predicate": "revision",
         "object": args.commit[:8], "type": "literal"},
        {"subject": f"{LUTINO_BASE}commit/{args.commit}",
         "vocab": "foaf", "predicate": "maker",
         "object": f"{LUTINO_BASE}people/{args.author}", "type": "uri"},
    ])
    persist_rss(conn, args.commit, lineage_id,
                rss_items[0]["title"], rss_items[0]["link"], rss_items[0]["description"])

    conn.close()


if __name__ == "__main__":
    main()
