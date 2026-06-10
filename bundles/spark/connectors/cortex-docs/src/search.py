#!/usr/bin/env python3
"""Search Palo Alto Cortex documentation using the public Fluid Topics API.

Usage:
    python3 search.py search "XQL filter stage" [--product xsiam] [--per-page 20] [--json]
    python3 search.py suggest "dedup st"
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE_URL = "https://docs-cortex.paloaltonetworks.com"
SEARCH_API = f"{BASE_URL}/api/khub/clustered-search"
SUGGEST_API = f"{BASE_URL}/api/khub/suggest"

_HEADERS = {
    "accept": "*/*",
    "content-type": "application/json",
    "user-agent": "cortex-docs-skill/1.0",
    "ft-calling-app": "ft/turnkey-portal",
}

# Product → canonical "Product" metadata values used by the Fluid Topics API.
# These are the stable facet values returned by the docs site — scoping by
# product name is resilient to publication restructuring (map IDs can change;
# product names don't unless Palo Alto rebrands the product itself).
#
# Run: python3 search.py search "" --json  and inspect facets["Product"]
# to see the current full list of product values.
XQL_PRODUCT_NAMES: list[str] = [
    "Cortex XDR",
    "Cortex XDR Agent",
    "Cortex XSIAM",
    "Cortex AgentiX",
    "Cortex CLOUD",
    "Cortex Cloud Application Security",
    "Cortex Cloud Posture Management",
    "Cortex Cloud Runtime Security",
]

PRODUCT_NAMES: dict[str, list[str]] = {
    "agentix":               ["Cortex AgentiX"],
    "cortex agentix":        ["Cortex AgentiX"],
    "xql":                   XQL_PRODUCT_NAMES,
    "query language":        XQL_PRODUCT_NAMES,
    "cortex query language": XQL_PRODUCT_NAMES,
    "xdr":                   ["Cortex XDR", "Cortex XDR Agent"],
    "cortex xdr":            ["Cortex XDR", "Cortex XDR Agent"],
    "xsiam":                 ["Cortex XSIAM"],
    "cortex xsiam":          ["Cortex XSIAM"],
    "xsoar":                 ["Cortex XSOAR"],
    "cortex xsoar":          ["Cortex XSOAR"],
    "cloud":                 ["Cortex CLOUD", "Cortex Cloud Application Security", "Cortex Cloud Posture Management", "Cortex Cloud Runtime Security"],
    "cortex cloud":          ["Cortex CLOUD", "Cortex Cloud Application Security", "Cortex Cloud Posture Management", "Cortex Cloud Runtime Security"],
    "dspm":                  ["Cortex CLOUD", "Cortex Cloud Posture Management"],
    "cspm":                  ["Cortex CLOUD", "Cortex Cloud Posture Management"],
    "ciem":                  ["Cortex CLOUD", "Cortex Cloud Posture Management"],
    "xpanse":                ["Cortex XPANSE"],
    "cortex xpanse":         ["Cortex XPANSE"],
}


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _post_json(url: str, payload: dict) -> dict:
    req = Request(
        url,
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
        headers=_HEADERS,
    )
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        print(f"HTTP {exc.code}: {exc.reason}", file=sys.stderr)
        sys.exit(1)
    except URLError as exc:
        print(f"Connection error: {exc.reason}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strip_html(html: str, max_chars: int = 400) -> str:
    """Remove HTML tags, decode entities, normalise whitespace."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = text.replace("&nbsp;", " ").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def _build_product_filter(product_values: list[str]) -> list[dict]:
    """Return a metadataFilter scoped by Product facet values (not map IDs)."""
    return [
        {
            "key": "Product",
            "valueFilter": {"negative": False, "values": product_values},
        }
    ]


def _infer_filters_from_query(query: str) -> list[dict]:
    """Auto-detect product mentions in the query and return product filters."""
    low = query.lower()
    names: list[str] = []
    for keyword, values in PRODUCT_NAMES.items():
        if keyword in low:
            for v in values:
                if v not in names:
                    names.append(v)
    return _build_product_filter(names) if names else []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def search(
    query: str,
    per_page: int = 20,
    product: str | None = None,
    page: int = 1,
) -> dict:
    """Run a full clustered search against the Cortex docs.

    Args:
        query:    Free-text search string.
        per_page: Number of results to return (1–100).
        product:  Optional product key to scope the search (e.g. "xsiam", "xdr").
                  Resolved to canonical Product metadata values — no map IDs needed.
        page:     Page number (1-based) for pagination.

    Returns:
        Dict with keys: query, total_hits, scope, facets, hits.
        Each hit has: title, topic_id, map_id, map_title, reader_url, excerpt.
    """
    if product:
        key = product.strip().lower()
        values = PRODUCT_NAMES.get(key, [])
        filters = _build_product_filter(values) if values else []
    else:
        filters = _infer_filters_from_query(query)

    payload = {
        "query": query,
        "clusterSortCriterions": [],
        "metadataFilters": filters,
        "facets": [
            {"id": "Product"},
            {"id": "Category"},
            {"id": "License"},
            {"id": "Version"},
            {"id": "Solution"},
        ],
        "sort": [],
        "sortId": None,
        "paging": {"page": page, "perPage": max(1, min(per_page, 100))},
        "keywordMatch": None,
        "contentLocale": "en-US",
        "otherQueryParams": {},
        "virtualField": "EVERYWHERE",
        "scope": "DEFAULT",
    }

    data = _post_json(SEARCH_API, payload)

    hits: list[dict] = []
    for cluster in data.get("results", []):
        if not isinstance(cluster, dict):
            continue
        for entry in cluster.get("entries", []):
            if not isinstance(entry, dict):
                continue
            topic = entry.get("topic") or {}
            map_obj = entry.get("map") or {}

            title = (topic.get("title") or map_obj.get("title") or "").strip()
            if not title:
                continue

            # contentId is the stable topic identifier used in fetch_topic.py
            topic_id = (topic.get("contentId") or topic.get("id") or topic.get("topicId") or "").strip()
            map_id = (topic.get("mapId") or map_obj.get("mapId") or map_obj.get("id") or "").strip()
            # readerUrl may be a full URL or a path — normalise to full URL
            reader_raw = topic.get("readerUrl") or map_obj.get("readerUrl") or ""
            if reader_raw.startswith("http"):
                reader_url = reader_raw.rstrip("/")
            else:
                reader_url = f"{BASE_URL}{reader_raw}".rstrip("/")

            hits.append(
                {
                    "title": title,
                    "topic_id": topic_id,
                    "map_id": map_id,
                    "map_title": (topic.get("mapTitle") or map_obj.get("title") or "").strip(),
                    "reader_url": reader_url,
                    "excerpt": _strip_html(topic.get("htmlExcerpt") or ""),
                }
            )
            if len(hits) >= per_page:
                break
        if len(hits) >= per_page:
            break

    # Summarise available facets for context
    facets: dict[str, list[str]] = {}
    for f in data.get("facets", []):
        fkey = f.get("key", "")
        values = [
            n["value"]
            for n in f.get("rootNodes", [])
            if isinstance(n, dict) and n.get("totalResultsCount", 0) > 0
        ]
        if values:
            facets[fkey] = values

    scope_label = (
        [v for f in filters for v in f["valueFilter"]["values"]]
        if filters
        else "global"
    )

    return {
        "query": query,
        "total_hits": len(hits),
        "scope": scope_label,
        "facets": facets,
        "hits": hits,
    }


def suggest(input_text: str, product: str | None = None) -> list[str]:
    """Return autocomplete suggestions for a partial query.

    Args:
        input_text: Partial search text.
        product:    Optional product key to scope suggestions (e.g. "xdr", "xsiam").

    Returns:
        List of suggestion strings.
    """
    filters: list[dict] = []
    if product:
        key = product.strip().lower()
        values = PRODUCT_NAMES.get(key, [])
        if values:
            filters = _build_product_filter(values)

    payload: dict = {
        "contentLocale": "en-US",
        "input": input_text,
        "metadataFilters": filters,
        "sort": [],
    }

    data = _post_json(SUGGEST_API, payload)
    return [s.get("value", "") for s in data.get("suggestions", []) if s.get("value")]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_results(result: dict) -> None:
    scope = result["scope"]
    scope_str = ", ".join(scope) if isinstance(scope, list) else scope
    print(f'Search: "{result["query"]}"  —  {result["total_hits"]} result(s)  [scope: {scope_str}]\n')

    for i, hit in enumerate(result["hits"], 1):
        print(f"{i}. {hit['title']}")
        print(f"   Publication : {hit['map_title']}")
        print(f"   map_id      : {hit['map_id']}")
        print(f"   topic_id    : {hit['topic_id']}")
        print(f"   URL         : {hit['reader_url']}")
        if hit["excerpt"]:
            print(f"   Excerpt     : {hit['excerpt']}")
        print()

    if result["facets"]:
        print("Available facets:")
        for key, values in result["facets"].items():
            print(f"  {key}: {', '.join(values[:8])}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Search Palo Alto Cortex documentation (public API)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s search "XQL filter stage"
  %(prog)s search "alert triage" --product xsiam --per-page 5
  %(prog)s search "dedup stage" --json
  %(prog)s suggest "filter st" --product agentix
        """,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # --- search subcommand ---
    search_p = sub.add_parser("search", help="Full-text search")
    search_p.add_argument("query", help='Search query, e.g. "XQL filter stage"')
    search_p.add_argument(
        "--per-page", type=int, default=20, metavar="N",
        help="Results per page, 1–100 (default: 20)",
    )
    search_p.add_argument(
        "--page", type=int, default=1, metavar="N",
        help="Page number for pagination (default: 1)",
    )
    search_p.add_argument(
        "--product", metavar="PRODUCT",
        help="Scope to product: agentix, xdr, xsiam, xsoar, xql, cloud, dspm, cspm, xpanse",
    )
    search_p.add_argument(
        "--json", dest="as_json", action="store_true",
        help="Output raw JSON",
    )

    # --- suggest subcommand ---
    suggest_p = sub.add_parser("suggest", help="Autocomplete suggestions")
    suggest_p.add_argument("input", help="Partial search text")
    suggest_p.add_argument(
        "--product", metavar="PRODUCT",
        help="Scope suggestions to a product (e.g. agentix, xdr, xsiam)",
    )

    args = parser.parse_args()

    if args.cmd == "search":
        result = search(
            query=args.query,
            per_page=args.per_page,
            page=args.page,
            product=args.product,
        )
        if args.as_json:
            print(json.dumps(result, indent=2))
        else:
            _print_results(result)

    elif args.cmd == "suggest":
        suggestions = suggest(args.input, product=getattr(args, "product", None))
        if suggestions:
            for s in suggestions:
                print(s)
        else:
            print("No suggestions returned.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
