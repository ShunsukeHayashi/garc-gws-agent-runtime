#!/usr/bin/env python3
"""
GARC KG Query — Safe query/show interface for the knowledge graph cache file.
Arguments are passed via argv (no shell interpolation).
"""

import argparse
import json
import sys
from pathlib import Path


def load_kg(cache_path: str) -> dict:
    p = Path(cache_path)
    if not p.exists():
        print(f"❌ Knowledge graph cache not found: {cache_path}", file=sys.stderr)
        print("   Run: garc kg build", file=sys.stderr)
        sys.exit(1)
    try:
        with open(p) as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Failed to load KG cache: {e}", file=sys.stderr)
        sys.exit(1)


def kg_query(cache_path: str, query: str, max_results: int = 10):
    """Search nodes by keyword in title or content_preview."""
    kg = load_kg(cache_path)
    nodes = kg.get("nodes", [])
    query_lower = query.lower()

    matches = []
    for node in nodes:
        title = node.get("title", "").lower()
        content = node.get("content_preview", "").lower()
        if query_lower in title or query_lower in content:
            matches.append(node)

    built_at = kg.get("built_at", "?")[:10]
    print(f"Knowledge graph — built: {built_at}  nodes: {len(nodes)}")
    print()

    if not matches:
        print(f"No results for: \"{query}\"")
        return

    limit = min(max_results, len(matches))
    print(f"Results for \"{query}\" ({len(matches)} match{'es' if len(matches) != 1 else ''}, showing {limit}):")
    print()
    for m in matches[:limit]:
        doc_id = m.get("doc_id", "")
        title = m.get("title", "")
        link = m.get("web_link", "")
        links_count = len(m.get("links", []))
        preview = m.get("content_preview", "")[:120].replace("\n", " ")
        print(f"  [{doc_id[:16]}] {title}")
        if preview:
            print(f"    {preview}...")
        if links_count:
            print(f"    ↳ {links_count} linked doc(s)")
        if link:
            print(f"    🔗 {link}")
        print()


def kg_show(cache_path: str, doc_id: str):
    """Show full details for a specific doc."""
    kg = load_kg(cache_path)
    nodes = kg.get("nodes", [])

    for node in nodes:
        if node.get("doc_id") == doc_id:
            print(f"Title    : {node.get('title', '')}")
            print(f"Doc ID   : {doc_id}")
            print(f"MIME     : {node.get('mime_type', '')}")
            print(f"Modified : {node.get('modified_time', '')[:19]}")
            link = node.get("web_link", "")
            if link:
                print(f"URL      : {link}")
            print()
            preview = node.get("content_preview", "")
            if preview:
                print("Content preview:")
                print(preview[:800])
                print()
            links = node.get("links", [])
            if links:
                print(f"Linked documents ({len(links)}):")
                for lnk in links:
                    print(f"  → {lnk}")
            return

    print(f"Document '{doc_id}' not found in knowledge graph.")
    print(f"Run 'garc kg build' to refresh the index.")


def main():
    parser = argparse.ArgumentParser(description="GARC KG Query")
    sub = parser.add_subparsers(dest="command")

    qp = sub.add_parser("query", help="Search the knowledge graph")
    qp.add_argument("--cache", required=True, help="Path to knowledge-graph.json")
    qp.add_argument("--query", required=True, help="Search keyword")
    qp.add_argument("--max", type=int, default=10, help="Max results")

    sp = sub.add_parser("show", help="Show a specific doc")
    sp.add_argument("--cache", required=True, help="Path to knowledge-graph.json")
    sp.add_argument("--doc-id", required=True, help="Document ID")

    args = parser.parse_args()

    if args.command == "query":
        kg_query(args.cache, args.query, args.max)
    elif args.command == "show":
        kg_show(args.cache, args.doc_id)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
