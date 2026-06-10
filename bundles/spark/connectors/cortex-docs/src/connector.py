"""cortex-docs connector — aggregator + MCP tool surface.

Wraps the four upstream scripts (`_search.py`, `_fetch_topic.py`,
`_xql_lookup.py`, `_research_planner.py`) with `cortex_*`-prefixed tool
functions. Tool names auto-namespace as `cortex-docs/<bare_name>` per
the embedded MCP's connector loader; `connector.yaml`'s
`runtimeMapping.functionPrefix=cortex_` strips the prefix at dispatch
time, so the agent sees `cortex-docs/search`, `cortex-docs/xql_lookup`,
etc.

# Why the wrappers exist
The upstream scripts were authored as standalone CLIs and call
`sys.exit(1)` on HTTP errors (HTTPError, URLError). Inside a long-
running connector process that would terminate phantom-agent — an
unrecoverable failure for one transient docs-site blip. Each wrapper
below catches `SystemExit` at the boundary and converts it to a
structured `{"ok": false, "error": "..."}` return so:
  - The agent sees a tool-call failure, not a container crash.
  - The operator sees a clear error string in the chat surface.
  - Other concurrent tool calls keep working.

Both forms (success dict and failure dict) carry an `ok` boolean so
the agent's downstream tooling can branch cleanly.

# Why the originals are kept unchanged
The user spent significant time tuning these scripts; modifying the
copies in lockstep with future upstream updates would be high-friction.
Keeping the upstream scripts as `_*.py` modules and exposing thin
wrappers here means upstream re-syncs are a `cp -f` away.

# Tool catalog (alphabetical)
  cortex_deep_research  full multi-section research planner (heavyweight)
  cortex_fetch_toc      table of contents for a publication
  cortex_fetch_topic    full topic content
  cortex_search         full-text search across Cortex docs
  cortex_suggest        autocomplete suggestions for partial queries
  cortex_xql_lookup     focused XQL stage/function lookup
"""
from __future__ import annotations

import io
import json
import sys
from contextlib import contextmanager, redirect_stdout
from typing import Any, Iterator, Optional

# Import the upstream scripts as internal modules. Their logic stays
# verbatim; we wrap only at the public-tool boundary. The original file
# names (search.py, fetch_topic.py, xql_lookup.py, research_planner.py)
# are preserved unchanged because xql_lookup.py and research_planner.py
# do `from fetch_topic import …` / `from search import …` at module top —
# renaming would force changes inside the upstream files we promised to
# keep verbatim.
from . import fetch_topic as _fetch_topic
from . import research_planner as _research_planner
from . import search as _search
from . import xql_lookup as _xql_lookup


@contextmanager
def _shielded() -> Iterator[None]:
    """Catch SystemExit raised by the upstream scripts' `sys.exit(1)`
    error paths. Anything else propagates normally. This is the
    process-survival guard that lets a transient HTTP error from the
    docs API surface as a returned error dict instead of crashing
    phantom-agent.

    Use as a context manager around any call into _search / _fetch_topic
    / _xql_lookup that hits the network — the public scripts call
    `sys.exit(1)` from `_post_json` / `_get` on HTTPError or URLError.
    """
    try:
        yield
    except SystemExit as exc:
        # Re-raise as a non-fatal exception the wrapper functions
        # below catch and translate to error dicts.
        raise RuntimeError(
            f"cortex-docs API call failed (upstream sys.exit({exc.code}))"
        ) from exc


def _err(message: str, **extra: Any) -> dict:
    """Standard error envelope. Agents branch on `ok=false`."""
    payload = {"ok": False, "error": message}
    payload.update(extra)
    return payload


def _ok(payload: dict) -> dict:
    """Standard success envelope. Tools that already return rich
    payloads pass through; we just stamp `ok=true` so downstream
    branching is uniform.
    """
    if not isinstance(payload, dict):
        payload = {"value": payload}
    if "ok" not in payload:
        payload = {"ok": True, **payload}
    return payload


# ─── cortex_search ───────────────────────────────────────────────────


def cortex_search(
    query: str,
    product: Optional[str] = None,
    per_page: int = 20,
    page: int = 1,
) -> dict:
    """Full-text search across the Palo Alto Networks Cortex public
    documentation (docs-cortex.paloaltonetworks.com).

    Args:
        query:    Free-text search string. Use Cortex product
                  vocabulary (e.g. "Cortex Query Language filter
                  stage") for best recall.
        product:  Optional product scope. One of: agentix, xdr, xsiam,
                  xsoar, xql, cloud, dspm, cspm, ciem, xpanse. When
                  omitted, the connector auto-detects product mentions
                  in the query string.
        per_page: Results per page (1–100; default 20).
        page:     1-based page number.

    Returns:
        On success: {ok: true, query, total_hits, scope, facets, hits}.
        Each hit carries title, topic_id, map_id, map_title,
        reader_url, excerpt — enough to chain into cortex_fetch_topic
        without a second search call.
        On failure: {ok: false, error}.
    """
    try:
        with _shielded():
            result = _search.search(
                query=query,
                per_page=per_page,
                product=product,
                page=page,
            )
        return _ok(result)
    except RuntimeError as exc:
        return _err(str(exc))
    except Exception as exc:  # pragma: no cover — defensive
        return _err(f"cortex_search unexpected error: {exc}")


# ─── cortex_suggest ──────────────────────────────────────────────────


def cortex_suggest(
    input_text: str,
    product: Optional[str] = None,
) -> dict:
    """Autocomplete suggestions for a partial Cortex docs query.

    Args:
        input_text: Partial search text (e.g. "filter st").
        product:    Optional product scope (same vocabulary as
                    cortex_search).

    Returns:
        On success: {ok: true, suggestions: [...]}. List may be empty
        if the docs API has no matches.
        On failure: {ok: false, error}.
    """
    try:
        with _shielded():
            suggestions = _search.suggest(input_text, product=product)
        return _ok({"suggestions": suggestions})
    except RuntimeError as exc:
        return _err(str(exc))
    except Exception as exc:  # pragma: no cover
        return _err(f"cortex_suggest unexpected error: {exc}")


# ─── cortex_xql_lookup ───────────────────────────────────────────────


def cortex_xql_lookup(
    term: str,
    kind: str = "auto",
    product: str = "xql",
    per_page: int = 8,
    suggest: bool = False,
) -> dict:
    """Focused lookup for an XQL stage or function. Searches Cortex
    docs, ranks the result set against stage/function quality
    heuristics, fetches the top-ranked topic, and returns a compact
    answer-ready payload.

    Use this instead of cortex_search when the question is "how do I
    use the `dedup` stage?" or "what does `arrayindexof` do?". For
    multi-topic syntheses use cortex_deep_research.

    Args:
        term:      Stage or function name (e.g. "dedup",
                   "arrayindexof"). Phantom strips a leading
                   "stage"/"function"/"xql"/"cortex query language"
                   noise prefix automatically.
        kind:      "auto" (default; inferred from name), "stage", or
                   "function". Affects the search-query expansion and
                   ranking.
        product:   Product scope. Default "xql" searches all
                   XQL-capable Cortex products. Narrow to "xdr",
                   "xsiam", "agentix", or "cloud" when the question
                   carries explicit product context.
        per_page:  Search-result page size (default 8).
        suggest:   If true, also include autocomplete suggestions for
                   the cleaned term.

    Returns:
        On success when found:
          {ok, found: true, term, kind, product, title, publication,
           reader_url, summary_content, source, scope_note,
           suggestions}.
        On success when not found:
          {ok, found: false, term, kind, product, fetch_errors,
           suggestions}.
        On failure: {ok: false, error}.
    """
    try:
        kind_resolved = _xql_lookup._infer_kind(term, kind)
        cleaned = _xql_lookup._clean_term(term) or term.strip()
        suggestions: list[str] = []
        if suggest:
            with _shielded():
                suggestions = _search.suggest(cleaned, product=product)[:8]
        with _shielded():
            hit, topic = _xql_lookup._first_fetchable_hit(
                term, kind_resolved, product, per_page
            )
        if not hit:
            return _ok({
                "found": False,
                "term": term,
                "kind": kind_resolved,
                "product": product,
                "fetch_errors": topic.get("fetch_errors", []),
                "suggestions": suggestions,
            })

        content = str(topic.get("content", ""))
        return _ok({
            "found": True,
            "term": term,
            "kind": kind_resolved,
            "product": product,
            "title": topic.get("title") or hit.get("title"),
            "publication": topic.get("map_title") or hit.get("map_title"),
            "reader_url": hit.get("reader_url") or topic.get("reader_url"),
            "summary_content": _xql_lookup._summarize_content(content),
            "source": (
                f"docs-cortex.paloaltonetworks.com - "
                f"{topic.get('title') or hit.get('title')} "
                f"({topic.get('map_title') or hit.get('map_title')})"
            ),
            "scope_note": (
                _xql_lookup.XQL_SCOPE_NOTE
                if product.strip().lower() == "xql"
                else ""
            ),
            "suggestions": suggestions,
        })
    except RuntimeError as exc:
        return _err(str(exc))
    except Exception as exc:  # pragma: no cover
        return _err(f"cortex_xql_lookup unexpected error: {exc}")


# ─── cortex_fetch_topic ──────────────────────────────────────────────


def cortex_fetch_topic(
    map_id: str,
    topic_id: str,
    max_chars: int = 12000,
    max_children: int = 3,
    min_content_chars: int = 120,
    max_depth: int = 2,
) -> dict:
    """Fetch full topic content from the Cortex public docs given a
    publication map_id + topic_id pair (typically obtained from a
    prior cortex_search call).

    Some docs topics are DITA container nodes — title + TOC entry but
    no body text. The fallback fetcher detects empty/stub content and
    descends into direct children automatically.

    v0.5.69 adds **multi-level descent** (`max_depth` arg, default 2).
    When a fetched child is ITSELF a stub/container, the fetcher
    recurses into ITS children, up to max_depth levels. Discovered
    via dogfooding the Cortex XDR API Reference topic: the top-level
    reference is a thin container, its sole direct child is a short
    intro, and the actual per-endpoint reference pages live one level
    deeper. Multi-level descent surfaces them naturally.

    Args:
        map_id:            Publication ID (from search hit `map_id`).
        topic_id:          Topic ID within that publication
                           (`topic_id` from the search hit).
        max_chars:         Truncation ceiling for the returned
                           content (default 12000).
        max_children:      Max direct-child topics to recursively
                           fetch when the parent is a stub (default
                           3). Set 0 to disable child descent.
        min_content_chars: Below this, treat the topic as a stub and
                           trigger child descent.
        max_depth:         Max recursion depth when children are
                           also stubs (default 2 = top + 2 deeper
                           levels; set 1 to restore single-level
                           descent behavior).

    Returns:
        On success: {ok, title, content, map_title, reader_url,
                     is_container, children_fetched, descent_depth, ...}.
        On failure: {ok: false, error}.
    """
    try:
        with _shielded():
            topic = _fetch_topic.fetch_topic_with_fallback(
                map_id=map_id,
                topic_id=topic_id,
                max_chars=max_chars,
                max_children=max_children,
                min_content_chars=min_content_chars,
                max_depth=max_depth,
            )
        return _ok(topic)
    except RuntimeError as exc:
        return _err(str(exc))
    except Exception as exc:  # pragma: no cover
        return _err(f"cortex_fetch_topic unexpected error: {exc}")


# ─── cortex_fetch_toc ────────────────────────────────────────────────


def cortex_fetch_toc(map_id: str) -> dict:
    """Fetch the full table of contents for a Cortex docs publication.

    Useful when you have a `map_id` from cortex_search and want to
    enumerate all topics in that publication (e.g. for browsing every
    XQL stage doc, or auditing coverage of a topic family).

    Args:
        map_id: Publication ID (from a cortex_search hit).

    Returns:
        On success: {ok, items: [{topic_id, title, depth, parent_id}]}
        — flat list of every topic in the TOC.
        On failure: {ok: false, error}.
    """
    try:
        with _shielded():
            items = _fetch_topic.fetch_toc(map_id)
        return _ok({"items": items})
    except RuntimeError as exc:
        return _err(str(exc))
    except Exception as exc:  # pragma: no cover
        return _err(f"cortex_fetch_toc unexpected error: {exc}")


# ─── cortex_deep_research ────────────────────────────────────────────


def cortex_deep_research(
    request: str,
    max_sections: int = 8,
    hits_per_section: int = 4,
    enable_gap_check: bool = False,
    model: Optional[str] = None,
) -> dict:
    """Run the full multi-section research planner against the Cortex
    docs. HEAVYWEIGHT — typically 1–3 minutes wall-clock — so reserve
    for actual multi-section deliverables (whitepapers, partner
    briefings, migration guides, comparisons). For single-topic
    answers use cortex_xql_lookup or cortex_search instead.

    The planner sequence:
      1. Plan: derive deliverable type, audience, product scope, and
         per-section query plans from `request`. Uses ANTHROPIC_API_KEY
         when available; falls back to a heuristic planner otherwise
         (no LLM dependency required).
      2. Search: per-section docs queries with deduped hits.
      3. Fetch: pull topic content for each hit.
      4. Gap check (optional): flag sections with weak coverage and
         retry with rephrased queries.
      5. Synthesize: emit a JSON brief with sections, evidence,
         coverage labels, citations, and stats.

    Args:
        request:          The user's research deliverable request
                          ("Create a partner briefing about Cortex
                          XDR incident response").
        max_sections:     Cap on planned sections (default 8).
        hits_per_section: Max docs hits to evaluate per section
                          (default 4).
        enable_gap_check: If true, run the gap-check + retry pass
                          (slower but better coverage).
        model:            LLM model id for the planner (defaults to
                          the upstream's DEFAULT_MODEL).

    Returns:
        On success: {ok, brief: {...}}. The `brief.coverage[i]` per-
        section labels are usually `strong | adequate | weak | none`;
        treat `weak`/`none` sections as needing a follow-up
        cortex_search call rather than synthesizing claims.
        On failure: {ok: false, error}.

    Note: this tool prints planner phase logs to stderr inside the
    upstream script. We capture stdout into a buffer so the JSON
    brief is what the caller receives, but stderr passes through —
    operators inspecting the agent's container logs will see "Phase 1:
    Planning..." progress lines, which is correct.
    """
    try:
        kwargs: dict[str, Any] = {
            "request": request,
            "max_sections": max_sections,
            "hits_per_section": hits_per_section,
            "enable_gap_check": enable_gap_check,
            "output_json": True,
        }
        if model:
            kwargs["model"] = model

        # The upstream run_deep_search prints progress to stderr only;
        # stdout is reserved for the brief itself in CLI mode but the
        # function we call returns the dict directly. Belt-and-braces
        # capture in case any future version starts using stdout.
        buf = io.StringIO()
        with _shielded():
            with redirect_stdout(buf):
                brief = _research_planner.run_deep_search(**kwargs)
        return _ok({"brief": brief})
    except RuntimeError as exc:
        return _err(str(exc))
    except Exception as exc:  # pragma: no cover
        return _err(f"cortex_deep_research unexpected error: {exc}")


__all__ = [
    "cortex_search",
    "cortex_suggest",
    "cortex_xql_lookup",
    "cortex_fetch_topic",
    "cortex_fetch_toc",
    "cortex_deep_research",
]
