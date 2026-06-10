#!/usr/bin/env python3
"""Fetch full topic content, table of contents, or publication metadata
from the Palo Alto Cortex documentation (public Fluid Topics API).

Usage:
    python3 fetch_topic.py topic  <map_id> <topic_id> [--max-chars 48000] [--auto-children 3] [--json]
    python3 fetch_topic.py toc    <map_id> [--json]
    python3 fetch_topic.py map    <map_id>

Auto-children fallback (enabled by default):
    Some topics in this docs site are DITA container nodes — they have a title and
    TOC entry but no body text. When a topic returns empty or stub content (below
    --min-content-chars, default 150), the script automatically finds its direct
    children in the TOC and fetches those instead.
    Use --auto-children 0 to disable this behaviour entirely.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE_URL = "https://docs-cortex.paloaltonetworks.com"

_HEADERS = {
    "accept": "*/*",
    "user-agent": "cortex-docs-skill/1.0",
    "ft-calling-app": "ft/turnkey-portal",
}


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _get(url: str) -> str:
    """GET a URL and return response body as text."""
    req = Request(url, method="GET", headers=_HEADERS)
    try:
        with urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8")
    except HTTPError as exc:
        print(f"HTTP {exc.code}: {exc.reason}  [{url}]", file=sys.stderr)
        sys.exit(1)
    except URLError as exc:
        print(f"Connection error: {exc.reason}  [{url}]", file=sys.stderr)
        sys.exit(1)


def _get_json(url: str) -> dict | list:
    return json.loads(_get(url))


# ---------------------------------------------------------------------------
# API calls
# ---------------------------------------------------------------------------

def get_map_info(map_id: str) -> dict:
    """Return publication-level metadata (title, lang, lastEdition, readerUrl, etc.)."""
    return _get_json(f"{BASE_URL}/api/khub/maps/{map_id}")  # type: ignore[return-value]


def get_toc(map_id: str) -> dict:
    """Return the full paginated table of contents for a publication."""
    return _get_json(f"{BASE_URL}/api/khub/maps/{map_id}/pages")  # type: ignore[return-value]


def get_topic_metadata(map_id: str, topic_id: str) -> dict:
    """Return topic-level metadata (title, contentApiEndpoint, metadata fields)."""
    return _get_json(f"{BASE_URL}/api/khub/maps/{map_id}/topics/{topic_id}")  # type: ignore[return-value]


def get_topic_html(map_id: str, topic_id: str) -> str:
    """Return the raw rendered HTML content for a topic."""
    url = (
        f"{BASE_URL}/api/khub/maps/{map_id}/topics/{topic_id}"
        "/content?target=DESIGNED_READER"
    )
    return _get(url)


# ---------------------------------------------------------------------------
# HTML → plain text conversion
# ---------------------------------------------------------------------------

def html_to_text(html: str) -> str:
    """Convert Fluid Topics rendered HTML to readable plain text.

    Preserves code blocks (wrapped in ``` fences), headings (with # prefix),
    list items (with - prefix), and paragraph spacing.
    """
    # Drop script/style content entirely
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)

    # Headings → markdown-style prefix
    for lvl in range(1, 7):
        prefix = "#" * lvl

        def _heading_repl(m: re.Match, p: str = prefix) -> str:
            return f"\n{p} {_strip_inline_tags(m.group(1))}\n"

        html = re.sub(
            rf"<h{lvl}[^>]*>(.*?)</h{lvl}>",
            _heading_repl,
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )

    # Code/pre blocks → fenced code
    html = re.sub(
        r"<(pre|code)[^>]*>(.*?)</(pre|code)>",
        lambda m: f"\n```\n{_decode_entities(re.sub(r'<[^>]+>', '', m.group(2)))}\n```\n",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # List items → dash prefix
    html = re.sub(r"<li[^>]*>", "\n- ", html, flags=re.IGNORECASE)
    html = re.sub(r"</li>", "", html, flags=re.IGNORECASE)

    # Block-level elements → newlines
    html = re.sub(
        r"<(p|div|br|tr|section|article|aside|blockquote)[^>]*/?>",
        "\n",
        html,
        flags=re.IGNORECASE,
    )
    html = re.sub(
        r"</(p|div|tr|section|article|aside|blockquote)>",
        "\n",
        html,
        flags=re.IGNORECASE,
    )

    # Strip all remaining tags
    html = re.sub(r"<[^>]+>", "", html)

    # Decode HTML entities
    html = _decode_entities(html)

    # Normalise whitespace: collapse spaces on each line, keep intentional blank lines
    lines = [line.strip() for line in html.split("\n")]
    cleaned: list[str] = []
    prev_blank = False
    for line in lines:
        if not line:
            if not prev_blank:
                cleaned.append("")
            prev_blank = True
        else:
            cleaned.append(line)
            prev_blank = False

    return "\n".join(cleaned).strip()


def _strip_inline_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html).strip()


def _decode_entities(text: str) -> str:
    return (
        text.replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&amp;", "&")
            .replace("&nbsp;", " ")
            .replace("&#39;", "'")
            .replace("&quot;", '"')
            .replace("&apos;", "'")
    )


# ---------------------------------------------------------------------------
# TOC helpers
# ---------------------------------------------------------------------------

def _flatten_toc(nodes: list[dict], depth: int = 0) -> list[dict]:
    """Recursively flatten a nested TOC tree into a flat list."""
    result: list[dict] = []
    for node in nodes:
        result.append(
            {
                "depth": depth,
                "title": node.get("title", ""),
                "topic_id": (node.get("contentId") or node.get("tocId") or "").strip(),
                "url": node.get("prettyUrl", ""),
            }
        )
        for child in node.get("children", []):
            result.extend(_flatten_toc([child], depth + 1))
    return result


def _find_children_in_toc(nodes: list[dict], target_topic_id: str) -> list[dict] | None:
    """Walk the TOC tree and return direct children of the node matching target_topic_id.

    Returns:
        List of child node dicts if the target was found (may be empty if no children).
        None if target_topic_id was not found anywhere in the tree.
    """
    for node in nodes:
        node_id = (node.get("contentId") or node.get("tocId") or "").strip()
        if node_id == target_topic_id:
            return node.get("children", [])
        # Recurse into children
        found = _find_children_in_toc(node.get("children", []), target_topic_id)
        if found is not None:
            return found
    return None


# ---------------------------------------------------------------------------
# High-level fetch helpers
# ---------------------------------------------------------------------------

def _fetch_topic_content(map_id: str, topic_id: str, max_chars: int = 48000) -> dict:
    """Fetch metadata + full plain-text content for a single topic.

    Internal helper (single caller: ``fetch_topic_with_fallback`` below).
    Named with a leading underscore so it does NOT collide with the
    ``fetch_topic`` *tool* — the tool's dispatched entry point is
    ``connector.cortex_fetch_topic`` (in ``connector.py``'s ``__all__``),
    which wraps ``fetch_topic_with_fallback`` and carries the full flat
    arg set (map_id, topic_id, max_chars, max_children, min_content_chars,
    max_depth) advertised in ``connector.yaml``. Keeping this helper
    private avoids a name-shadow that made the connector-tool-args
    validator resolve the tool to this thin 3-arg helper instead of the
    real 6-arg dispatched function (issue #111 / v0.17.114).

    Returns:
        Dict with: title, map_title, map_id, topic_id, last_edition,
                   reader_url, content (plain text, truncated to max_chars).
    """
    meta = get_topic_metadata(map_id, topic_id)
    map_info = get_map_info(map_id)
    html = get_topic_html(map_id, topic_id)
    text = html_to_text(html)

    reader_path = map_info.get("readerUrl", "")
    return {
        "title": meta.get("title", "").strip(),
        "map_title": map_info.get("title", "").strip(),
        "map_id": map_id,
        "topic_id": topic_id,
        "last_edition": map_info.get("lastEdition", ""),
        "reader_url": f"{BASE_URL}{reader_path}".rstrip("/"),
        "content": text[:max_chars],
        "content_truncated": len(text) > max_chars,
    }


def fetch_toc(map_id: str) -> list[dict]:
    """Return a flat list of all topics in a publication's TOC."""
    data = get_toc(map_id)
    all_nodes: list[dict] = []
    for page in data.get("paginatedToc", []):
        all_nodes.extend(page.get("pageToc", []))
    return _flatten_toc(all_nodes)


def fetch_topic_with_fallback(
    map_id: str,
    topic_id: str,
    max_chars: int = 48000,
    max_children: int = 3,
    min_content_chars: int = 300,
    max_depth: int = 2,
    _depth: int = 0,
    _toc_data: dict | None = None,
) -> dict:
    """Fetch a topic; if it is a stub or empty container, fetch its children instead.

    Some Fluid Topics pages are DITA container nodes — they have a title in the
    TOC but either no body text at all, or only a short abstract stub (a sentence
    or two that does not actually answer a question). This function transparently
    falls back to fetching direct child topics when content length is below
    min_content_chars.

    v0.5.69: Added **multi-level descent** (max_depth parameter). When a fetched
    child is ITSELF a stub/container, we recurse into ITS children, up to
    max_depth levels. Pre-v0.5.69 the descent was single-level only — the
    operator's dogfooding session against the Cortex XDR API Reference topic
    discovered the case where the top-level reference is a thin container, its
    sole direct child ("APIs Overview") is a short prose intro, and the actual
    per-endpoint reference pages live one level deeper. Multi-level descent
    surfaces those naturally.

    Args:
        map_id:            Publication map ID.
        topic_id:          Topic (contentId) to fetch.
        max_chars:         Total character budget across all returned content.
        max_children:      Maximum number of direct child topics to fetch per
                           descent level. Set to 0 to disable the fallback
                           entirely. Default 3.
        min_content_chars: Minimum content length (chars) to consider a topic
                           substantive. Topics shorter than this are treated as
                           stubs and trigger the children fallback (default 300).
        max_depth:         Maximum recursion depth for descending into children-
                           of-children when a child is itself a stub. Default 2
                           (= top level + 2 deeper levels = up to 3 levels of
                           nesting walked). Set to 1 to restore pre-v0.5.69
                           single-level behavior.
        _depth:            Internal recursion counter. Callers should leave at 0.
        _toc_data:         Internal: cached TOC dict to avoid re-fetching at
                           deeper recursion levels. Callers should leave None.

    Returns:
        Same shape as _fetch_topic_content(), plus:
          - is_container (bool): True when the fallback was triggered.
          - children_fetched (list[str]): Titles of children fetched on fallback
            (collected across all descent levels).
          - descent_depth (int, top-level only): Maximum depth reached during
            the fallback. 0 = no fallback needed. 1 = single-level descent
            (pre-v0.5.69 behavior). 2+ = multi-level descent fired.
    """
    result = _fetch_topic_content(map_id, topic_id, max_chars=max_chars)
    result["is_container"] = False
    result["children_fetched"] = []
    if _depth == 0:
        result["descent_depth"] = 0

    content_len = len(result["content"])
    # At top level (_depth=0): use the operator-supplied min_content_chars.
    # At recursion levels (_depth>0): use a much tighter 50-char threshold —
    # the goal of recursion is enrichment, not replacement. If a child has
    # thin-but-real content (e.g. 200 chars of meaningful prose), we want to
    # KEEP it rather than aggressively descend further and possibly lose it
    # to children that turn out to be even thinner. 50 chars = essentially
    # empty (a sentence fragment); anything above is preserved at recursion
    # levels.
    threshold = min_content_chars if _depth == 0 else 50
    is_stub = content_len < threshold

    # Stop conditions: not a stub, fallback disabled, or hit max depth
    if not is_stub or max_children == 0 or _depth >= max_depth:
        return result

    # Stub or empty content — locate direct children in the TOC and fetch them.
    result["is_container"] = True
    if _depth == 0:
        result["descent_depth"] = 1

    # Remember the bare-fetch content. If descent fails (no parts), we keep
    # this so callers don't lose thin-but-real content to a placeholder.
    bare_content = result["content"]

    # Cache the TOC fetch — re-fetching at each recursion level is wasteful.
    if _toc_data is None:
        _toc_data = get_toc(map_id)
    all_nodes: list[dict] = []
    for page in _toc_data.get("paginatedToc", []):
        all_nodes.extend(page.get("pageToc", []))

    child_nodes = _find_children_in_toc(all_nodes, topic_id) or []
    child_ids = [
        (c.get("contentId") or c.get("tocId") or "").strip()
        for c in child_nodes
        if (c.get("contentId") or c.get("tocId") or "").strip()
    ][:max_children]

    if not child_ids:
        result["content"] = "[Container topic — no child topics found in TOC]"
        return result

    # Fetch each child; split the char budget evenly across children.
    per_child_budget = max(1000, max_chars // len(child_ids))
    parts: list[str] = []
    children_fetched: list[str] = []

    for cid in child_ids:
        try:
            # v0.5.69: recursive call instead of bare fetch_topic. If the child
            # is itself a stub, descend further (up to max_depth). Pass the
            # cached _toc_data so each level doesn't re-fetch the TOC.
            child = fetch_topic_with_fallback(
                map_id,
                cid,
                max_chars=per_child_budget,
                max_children=max_children,
                min_content_chars=min_content_chars,
                max_depth=max_depth,
                _depth=_depth + 1,
                _toc_data=_toc_data,
            )
            if child["content"] and not child["content"].startswith("[Container topic"):
                parts.append(f"## {child['title']}\n\n{child['content']}")
                children_fetched.append(child["title"])
                # Collect titles fetched recursively from deeper levels too
                children_fetched.extend(child.get("children_fetched", []))
                # Track the deepest level reached for the top-level result
                if _depth == 0 and child.get("is_container"):
                    # Child was also a container; we descended one more level
                    result["descent_depth"] = max(
                        result.get("descent_depth", 1),
                        2 + _depth,  # at least one more level than this call
                    )
        except SystemExit:
            pass  # skip children that return HTTP errors

    result["children_fetched"] = children_fetched

    if parts:
        combined = "\n\n---\n\n".join(parts)
        # If we had bare content too, prepend it so the caller gets both
        # the (thin) container's own prose AND the enriched children.
        if bare_content:
            combined = bare_content + "\n\n---\n\n" + combined
        result["content"] = combined[:max_chars]
        result["content_truncated"] = len(combined) > max_chars
    elif bare_content:
        # Descent yielded no enrichable content but bare fetch had something.
        # Keep the bare content + note that descent was tried.
        result["content"] = (
            bare_content
            + f"\n\n[Note: this is a container topic — descended into "
            f"{len(child_ids)} child(ren) at depth {_depth} but they "
            f"returned no enriching content. Try cortex-docs/fetch_toc "
            f"to enumerate the publication for sibling/cousin topics.]"
        )
    else:
        result["content"] = (
            f"[Container topic — {len(child_ids)} child(ren) found at depth {_depth} but all returned empty content (max_depth={max_depth} reached without surfacing content)]"
        )

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_topic(result: dict) -> None:
    print(f"# {result['title']}")
    print(f"Publication : {result['map_title']}")
    print(f"Last updated: {result['last_edition']}")
    print(f"URL         : {result['reader_url']}")
    print(f"map_id      : {result['map_id']}")
    print(f"topic_id    : {result['topic_id']}")
    if result.get("is_container"):
        children = result.get("children_fetched") or []
        print(f"[Container topic — fetched {len(children)} child(ren): {', '.join(children) or 'none'}]")
    if result.get("content_truncated"):
        print("[Content truncated — use --max-chars to increase limit]")
    print("\n" + "─" * 60 + "\n")
    print(result["content"])


def _print_toc(items: list[dict]) -> None:
    for item in items:
        indent = "  " * item["depth"]
        print(f"{indent}- {item['title']}")
        print(f"{indent}  topic_id : {item['topic_id']}")
        print(f"{indent}  url      : {item['url']}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch Cortex documentation content (public API)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch topic (auto-fetches children if topic is an empty container)
  %(prog)s topic 2iKvnhFnGXeKYHSA2AFcVw IykutIp5DU_1VHx_mvyQFA

  # Limit content size to save context
  %(prog)s topic 2iKvnhFnGXeKYHSA2AFcVw IykutIp5DU_1VHx_mvyQFA --max-chars 4000

  # Fetch up to 5 children when container is detected
  %(prog)s topic 2iKvnhFnGXeKYHSA2AFcVw IykutIp5DU_1VHx_mvyQFA --auto-children 5

  # Disable fallback (return empty content as-is)
  %(prog)s topic 2iKvnhFnGXeKYHSA2AFcVw IykutIp5DU_1VHx_mvyQFA --auto-children 0

  # Get full topic as JSON
  %(prog)s topic 2iKvnhFnGXeKYHSA2AFcVw IykutIp5DU_1VHx_mvyQFA --json

  # Browse the table of contents
  %(prog)s toc 2iKvnhFnGXeKYHSA2AFcVw

  # Get publication metadata
  %(prog)s map 2iKvnhFnGXeKYHSA2AFcVw
        """,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # --- topic ---
    topic_p = sub.add_parser("topic", help="Fetch full content of a specific topic")
    topic_p.add_argument("map_id", help="Publication map ID")
    topic_p.add_argument("topic_id", help="Topic ID")
    topic_p.add_argument(
        "--max-chars", type=int, default=48000, metavar="N",
        help="Truncate content to N characters (default: 48000)",
    )
    topic_p.add_argument(
        "--auto-children", type=int, default=3, metavar="N",
        help=(
            "When a topic is a stub/container, automatically fetch up to N direct "
            "child topics instead. Set to 0 to disable (default: 3)."
        ),
    )
    topic_p.add_argument(
        "--min-content-chars", type=int, default=300, metavar="N",
        help=(
            "Minimum character count for topic content to be considered substantive. "
            "Topics shorter than this are treated as stubs and trigger the "
            "auto-children fallback (default: 300)."
        ),
    )
    topic_p.add_argument(
        "--json", dest="as_json", action="store_true",
        help="Output raw JSON",
    )

    # --- toc ---
    toc_p = sub.add_parser("toc", help="Show the table of contents for a publication")
    toc_p.add_argument("map_id", help="Publication map ID")
    toc_p.add_argument(
        "--json", dest="as_json", action="store_true",
        help="Output raw JSON",
    )

    # --- map ---
    map_p = sub.add_parser("map", help="Get publication metadata")
    map_p.add_argument("map_id", help="Publication map ID")

    args = parser.parse_args()

    if args.cmd == "topic":
        result = fetch_topic_with_fallback(
            args.map_id,
            args.topic_id,
            max_chars=args.max_chars,
            max_children=args.auto_children,
            min_content_chars=args.min_content_chars,
        )
        if args.as_json:
            print(json.dumps(result, indent=2))
        else:
            _print_topic(result)

    elif args.cmd == "toc":
        items = fetch_toc(args.map_id)
        if args.as_json:
            print(json.dumps(items, indent=2))
        else:
            _print_toc(items)

    elif args.cmd == "map":
        info = get_map_info(args.map_id)
        print(json.dumps(info, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
