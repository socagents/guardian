#!/usr/bin/env python3
"""Focused Cortex XQL lookup helper.

Use this for stage/function questions where the full deep-research planner is
too heavy. It searches Cortex docs, fetches the top topic, and emits a compact
answer-ready payload.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from fetch_topic import fetch_topic_with_fallback  # noqa: E402
from search import search, suggest  # noqa: E402


XQL_SCOPE_NOTE = (
    "Searched XQL across Cortex XDR, Cortex XSIAM, Cortex AgentiX, and Cortex Cloud. "
    "Use --product xdr|xsiam|agentix|cloud when the question names a product."
)

STAGES = {
    "alter",
    "arrayexpand",
    "bin",
    "call",
    "comp",
    "config",
    "dedup",
    "fields",
    "filter",
    "sort",
}


def _normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9_]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _clean_term(term: str) -> str:
    term = term.strip()
    term = re.sub(r"\b(stage|function|xql|cortex query language)\b", "", term, flags=re.I)
    return re.sub(r"\s+", " ", term).strip()


def _infer_kind(term: str, explicit: str) -> str:
    if explicit != "auto":
        return explicit
    cleaned = _clean_term(term).lower()
    return "stage" if cleaned in STAGES else "function"


def _queries(term: str, kind: str) -> list[str]:
    cleaned = _clean_term(term)
    if not cleaned:
        cleaned = term.strip()
    if kind == "stage":
        return [
            f"Cortex Query Language {cleaned}",
            f"{cleaned} stage",
            cleaned,
        ]
    return [
        cleaned,
        f"{cleaned} XQL",
        f"Cortex Query Language {cleaned}",
    ]


def _score_hit(hit: dict, cleaned: str, kind: str, query_index: int, hit_index: int) -> float:
    title = _normalize(str(hit.get("title", "")))
    map_title = _normalize(str(hit.get("map_title", "")))
    excerpt = _normalize(str(hit.get("excerpt", "")))
    reader_url = _normalize(str(hit.get("reader_url", "")))
    term = _normalize(cleaned)
    haystack = f"{title} {map_title} {excerpt} {reader_url}"

    score = 0.0
    if title == term:
        score += 220
    elif title.startswith(f"{term} "):
        score += 90
    elif term in title:
        score += 45

    if kind == "stage":
        if title == term and term in STAGES:
            score += 35
        if f"{term} stage" in haystack or f"{term} stages" in haystack:
            score += 55
        if "syntax" in haystack:
            score += 15
        if title == "stages":
            score += 12
    else:
        if "function" in haystack or "functions" in haystack:
            score += 45
        if title == "functions":
            score += 10

    if "documentation" in map_title:
        score += 18
    if "reference guide" in map_title:
        score += 18
    if "release notes" in map_title:
        score -= 140

    # Preserve search engine ordering as a tie-breaker without letting broad
    # overview pages beat exact stage/function topics.
    score -= query_index * 3
    score -= hit_index * 0.2
    return score


def _first_fetchable_hit(term: str, kind: str, product: str, per_page: int) -> tuple[dict, dict]:
    cleaned = _clean_term(term) or term.strip()
    seen: set[str] = set()
    last_result: dict = {}
    candidates: list[tuple[float, dict]] = []
    fetch_errors: list[str] = []

    for query_index, query in enumerate(_queries(term, kind)):
        result = search(query=query, product=product, per_page=per_page)
        last_result = result
        for hit_index, hit in enumerate(result.get("hits", [])):
            key = f"{hit.get('map_id', '')}::{hit.get('topic_id', '')}"
            if key in seen:
                continue
            seen.add(key)
            map_id = str(hit.get("map_id", ""))
            topic_id = str(hit.get("topic_id", ""))
            if not map_id or not topic_id:
                continue
            candidates.append((_score_hit(hit, cleaned, kind, query_index, hit_index), hit))

    for _score, hit in sorted(candidates, key=lambda item: item[0], reverse=True):
        try:
            topic = fetch_topic_with_fallback(
                map_id=str(hit.get("map_id", "")),
                topic_id=str(hit.get("topic_id", "")),
                max_chars=12000,
                max_children=3,
                min_content_chars=120,
            )
        except (OSError, TimeoutError, json.JSONDecodeError, SystemExit) as exc:
            fetch_errors.append(f"{hit.get('title', 'unknown')}: {exc}")
            continue
        if str(topic.get("content", "")).strip():
            return hit, topic
    return {}, {"search_result": last_result, "fetch_errors": fetch_errors[:5]}


def _summarize_content(content: str, max_chars: int = 2200) -> str:
    content = re.sub(r"\n{3,}", "\n\n", content.strip())
    if len(content) <= max_chars:
        return content
    return content[:max_chars].rsplit("\n", 1)[0].strip() + "\n\n[truncated]"


def main() -> int:
    parser = argparse.ArgumentParser(description="Look up Cortex XQL stage/function docs.")
    parser.add_argument("term", help='Stage or function name, e.g. "dedup" or "arrayindexof"')
    parser.add_argument("--kind", choices=["auto", "stage", "function"], default="auto")
    parser.add_argument(
        "--product",
        default="xql",
        help="Product scope: xql, xdr, xsiam, cloud, agentix. Default xql searches all XQL-capable Cortex docs.",
    )
    parser.add_argument("--per-page", type=int, default=8)
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of markdown.")
    parser.add_argument("--suggest", action="store_true", help="Show autocomplete suggestions first.")
    args = parser.parse_args()

    kind = _infer_kind(args.term, args.kind)
    suggestions = (suggest(_clean_term(args.term) or args.term, product=args.product)[:8] if args.suggest else [])
    hit, topic = _first_fetchable_hit(args.term, kind, args.product, args.per_page)
    if not hit:
        payload = {
            "term": args.term,
            "kind": kind,
            "product": args.product,
            "found": False,
            "fetch_errors": topic.get("fetch_errors", []),
            "suggestions": suggestions,
        }
        print(json.dumps(payload, indent=2) if args.json else f"No XQL documentation found for {args.term!r}.")
        return 1

    content = str(topic.get("content", ""))
    payload = {
        "term": args.term,
        "kind": kind,
        "product": args.product,
        "found": True,
        "title": topic.get("title") or hit.get("title"),
        "publication": topic.get("map_title") or hit.get("map_title"),
        "reader_url": hit.get("reader_url") or topic.get("reader_url"),
        "summary_content": _summarize_content(content),
        "source": f"docs-cortex.paloaltonetworks.com - {topic.get('title') or hit.get('title')} ({topic.get('map_title') or hit.get('map_title')})",
        "scope_note": XQL_SCOPE_NOTE if args.product.strip().lower() == "xql" else "",
        "suggestions": suggestions,
    }

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    print(f"# {payload['title']}")
    print()
    print(payload["summary_content"])
    print()
    print(f"Source: {payload['source']}")
    if payload["reader_url"]:
        print(f"URL: {payload['reader_url']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
