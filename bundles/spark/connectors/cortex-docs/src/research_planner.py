#!/usr/bin/env python3
"""Deep research planner for Cortex documentation.

Decomposes a document/presentation creation request into a multi-section
research plan, executes multiple search rounds against the Fluid Topics API,
fetches full topic content, checks for coverage gaps, and produces a
structured research brief.

Usage:
    python3 research_planner.py \\
      --request "Create a PPT for MSSP partners on XDR IR" \\
      --max-sections 10 \\
      --hits-per-section 4 \\
      --enable-gap-check \\
      --json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# ---------------------------------------------------------------------------
# Import search.py and fetch_topic.py from the same scripts/ directory
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))

from search import search, suggest, PRODUCT_NAMES  # noqa: E402
from fetch_topic import fetch_topic_with_fallback   # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Anthropic API for planning LLM calls (2 calls max: plan + gap check)
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-haiku-4-5-20251001"

# Limits
MAX_SEARCH_HITS_PER_QUERY = 10
MAX_TOTAL_CONTENT_CHARS = 500_000  # safety cap for total output
FETCH_MAX_CHARS = 48_000
FETCH_AUTO_CHILDREN = 3
FETCH_MIN_CONTENT = 300

# Coverage thresholds
COVERAGE_STRONG = 3
COVERAGE_ADEQUATE = 2


# ---------------------------------------------------------------------------
# LLM helper — uses Anthropic Messages API via urllib (no external deps)
# ---------------------------------------------------------------------------

def _call_llm(
    system_prompt: str,
    user_prompt: str,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> str:
    """Call Anthropic Messages API and return the assistant message text."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("Warning: ANTHROPIC_API_KEY not set, using fallback planning", file=sys.stderr)
        return ""

    payload = {
        "model": model,
        "system": system_prompt,
        "messages": [
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
    }

    req = Request(
        ANTHROPIC_API_URL,
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
    )

    try:
        with urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["content"][0]["text"].strip()
    except (HTTPError, URLError, KeyError, IndexError) as exc:
        print(f"LLM call failed: {exc}", file=sys.stderr)
        return ""


def _parse_json_from_llm(text: str) -> dict:
    """Extract JSON from LLM response, handling markdown fences."""
    # Strip markdown code fences
    text = re.sub(r"^```(?:json)?\s*\n?", "", text.strip())
    text = re.sub(r"\n?```\s*$", "", text.strip())
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return {}


# ---------------------------------------------------------------------------
# Planning prompt templates
# ---------------------------------------------------------------------------

PLAN_SYSTEM_PROMPT = """You are a research planner for Palo Alto Networks Cortex product documentation.
You decompose document creation requests into structured research outlines."""

PLAN_USER_TEMPLATE = """Given a document creation request, decompose it into a structured research outline
that will guide multiple independent KB searches.

REQUEST: {request}

Produce a JSON object with this exact structure:
{{
  "deliverable_type": "<presentation|report|whitepaper|brief|comparison>",
  "audience": "<who the deliverable is for, or 'general' if not specified>",
  "sections": [
    {{
      "title": "<Short section title, 3-6 words>",
      "description": "<What information this section needs, 1-2 sentences>",
      "queries": [
        "<search query 1>",
        "<search query 2>"
      ],
      "product_scope": "<xdr|xsiam|xsoar|agentix|cloud|xpanse|>",
      "priority": "<high|medium|low>"
    }}
  ]
}}

QUERY RULES — critical for search quality:
- Use Palo Alto documentation vocabulary, NOT user language:
  * "set up" not "deploy" or "install"
  * "configure" not "enable" or "turn on"
  * "manage" not "govern" or "administer"
  * "isolate" not "wipe" or "disconnect"
  * "quarantine" not "sandbox" or "block file"
  * "terminate process" not "kill process"
- 3-5 keywords per query, strip filler words entirely
- Do NOT expand acronyms: XDR, XQL, XSIAM, XSOAR are product names
- Do NOT include question words: "how", "what", "why", "can I"
- Each query should target a specific doc title or concept
- Use suggest-style phrases that match doc titles (e.g., "Incident Response Overview")

PRODUCT SCOPE:
- xdr: Cortex XDR agent, EDR, prevention profiles, broker VM, live terminal, forensics
- xsiam: Alert triage, BIOC, correlation rules, analytics, SIEM, ingestion
- xsoar: Playbooks, automation, cases, incident response workflows, war rooms
- agentix: XQL query language, dashboards, widgets, datasets
- cloud: Cloud onboarding, DSPM, CSPM, CIEM, cloud posture
- xpanse: Attack surface, exposure management
- "" (empty string): Cross-product or uncertain scope

SECTION RULES:
- Maximum {max_sections} sections
- Order sections in logical presentation/document flow
- High priority: core thesis topics (typically 3-4 sections)
- Medium priority: supporting context (2-3 sections)
- Low priority: nice-to-have extras (1-2 sections)
- Each section needs 2-4 search queries approaching the topic from different angles
- If audience is specified, include at least one section for audience-specific framing

Return ONLY valid JSON, no markdown fencing, no commentary."""

GAP_SYSTEM_PROMPT = """You are reviewing research coverage for a document about Palo Alto Cortex products.
Suggest alternative search queries for under-covered sections."""

GAP_USER_TEMPLATE = """Review research coverage for this document creation task.

ORIGINAL REQUEST: {request}

RESEARCH PLAN SECTIONS:
{plan_summary}

CURRENT COVERAGE:
{per_section_status}

For each section marked "weak" (0-1 evidence pieces) or "none" (0 evidence pieces),
suggest 1-2 alternative search queries that might find relevant content.

QUERY RULES:
- Use Palo Alto documentation vocabulary
- Try synonyms: if "incident response" found nothing, try "investigate alerts"
- Try broader terms: if "MSSP multi-tenant" found nothing, try "multi-tenant"
- Try related concepts: if direct feature search failed, try the parent category

Return ONLY valid JSON:
{{"retry_queries": [{{"section_index": 0, "section_title": "...", "queries": ["...", "..."]}}]}}
If all sections have adequate coverage (2+ evidence pieces), return:
{{"retry_queries": []}}

Return ONLY valid JSON, no markdown fencing, no commentary."""


# ---------------------------------------------------------------------------
# Fallback planning (when no API key)
# ---------------------------------------------------------------------------

def _fallback_plan(request: str, max_sections: int) -> dict:
    """Simple keyword-based plan when LLM is unavailable."""
    # Extract product mentions
    req_lower = request.lower()
    products = []
    for key in PRODUCT_NAMES:
        if key in req_lower and key not in ("cloud",):  # skip generic "cloud"
            products.append(key)

    # Use the first detected product, or empty for cross-product
    product_scope = products[0] if products else ""

    # Extract key nouns (simple heuristic)
    stop_words = {
        "create", "build", "make", "write", "develop", "prepare",
        "a", "an", "the", "for", "on", "about", "how", "to", "and",
        "or", "with", "our", "their", "its", "this", "that", "of",
        "in", "is", "we", "can", "use", "presentation", "report",
        "document", "whitepaper", "brief", "briefing", "ppt",
        "powerpoint", "slide", "slides",
    }
    words = re.findall(r"\b\w+\b", req_lower)
    keywords = [w for w in words if w not in stop_words and len(w) > 2][:8]

    # Build 3-5 sections from keywords
    sections = []
    chunk_size = max(1, len(keywords) // min(max_sections, 5))
    for i in range(0, len(keywords), chunk_size):
        chunk = keywords[i : i + chunk_size]
        if not chunk:
            continue
        title = " ".join(chunk[:3]).title()
        queries = [" ".join(chunk)]
        if len(chunk) > 1:
            queries.append(chunk[0])  # broader query
        sections.append({
            "title": title,
            "description": f"Research about {' '.join(chunk)}",
            "queries": queries,
            "product_scope": product_scope,
            "priority": "high" if i == 0 else "medium",
        })
        if len(sections) >= max_sections:
            break

    return {
        "deliverable_type": "document",
        "audience": "general",
        "sections": sections[:max_sections],
    }


# ---------------------------------------------------------------------------
# Phase 1: Plan research
# ---------------------------------------------------------------------------

def plan_research(request: str, max_sections: int, model: str) -> dict:
    """Use LLM to decompose request into a structured research plan."""
    prompt = PLAN_USER_TEMPLATE.format(
        request=request,
        max_sections=max_sections,
    )

    response = _call_llm(PLAN_SYSTEM_PROMPT, prompt, model=model)
    if not response:
        print("LLM planning failed, using fallback keyword planner", file=sys.stderr)
        return _fallback_plan(request, max_sections)

    plan = _parse_json_from_llm(response)
    if not plan or "sections" not in plan:
        print("LLM returned invalid plan, using fallback", file=sys.stderr)
        return _fallback_plan(request, max_sections)

    # Validate and cap sections
    plan["sections"] = plan["sections"][:max_sections]

    # Ensure required fields
    plan.setdefault("deliverable_type", "document")
    plan.setdefault("audience", "general")

    for sec in plan["sections"]:
        sec.setdefault("queries", [])
        sec.setdefault("product_scope", "")
        sec.setdefault("priority", "medium")
        # Cap queries per section
        sec["queries"] = sec["queries"][:4]

    return plan


# ---------------------------------------------------------------------------
# Phase 2: Search per section
# ---------------------------------------------------------------------------

def search_section(
    section: dict,
    hits_per_section: int,
    global_seen: set[str],
) -> tuple[list[dict], int]:
    """Execute all queries for a section, deduplicate, return top hits.

    Args:
        section: Section dict with queries and product_scope.
        hits_per_section: Max hits to keep per section.
        global_seen: Set of "map_id::topic_id" keys already seen across sections.

    Returns:
        (top_hits, total_raw_hits) — deduped and capped list + raw count.
    """
    all_hits: list[dict] = []
    seen_in_section: set[str] = set()
    total_raw = 0

    product = section.get("product_scope", "") or None

    for query in section.get("queries", []):
        if not query.strip():
            continue
        try:
            result = search(
                query=query.strip(),
                per_page=MAX_SEARCH_HITS_PER_QUERY,
                product=product if product else None,
            )
            raw_hits = result.get("hits", [])
            total_raw += len(raw_hits)

            for hit in raw_hits:
                key = f"{hit.get('map_id', '')}::{hit.get('topic_id', '')}"
                if key in seen_in_section or key in global_seen:
                    continue
                seen_in_section.add(key)
                global_seen.add(key)
                all_hits.append(hit)

        except SystemExit:
            # search.py calls sys.exit on HTTP errors — catch and continue
            print(f"  Search failed for query: {query}", file=sys.stderr)
            continue

    # Return top N hits (search results are already relevance-ordered)
    return all_hits[:hits_per_section], total_raw


# ---------------------------------------------------------------------------
# Phase 3: Fetch evidence
# ---------------------------------------------------------------------------

def fetch_evidence(
    hits: list[dict],
    max_chars: int = FETCH_MAX_CHARS,
) -> list[dict]:
    """Fetch full topic content for a list of search hits.

    Returns list of evidence dicts with content and metadata.
    """
    evidence: list[dict] = []

    for hit in hits:
        map_id = hit.get("map_id", "")
        topic_id = hit.get("topic_id", "")
        if not map_id or not topic_id:
            continue

        try:
            topic = fetch_topic_with_fallback(
                map_id=map_id,
                topic_id=topic_id,
                max_chars=max_chars,
                max_children=FETCH_AUTO_CHILDREN,
                min_content_chars=FETCH_MIN_CONTENT,
            )

            content = topic.get("content", "")
            if len(content) < FETCH_MIN_CONTENT:
                continue

            evidence.append({
                "topic_title": topic.get("title", hit.get("title", "")),
                "map_title": topic.get("map_title", hit.get("map_title", "")),
                "map_id": map_id,
                "topic_id": topic_id,
                "reader_url": topic.get("reader_url", hit.get("reader_url", "")),
                "content": content,
                "content_chars": len(content),
                "is_container": topic.get("is_container", False),
                "children_fetched": topic.get("children_fetched", []),
            })

        except SystemExit:
            # fetch_topic.py calls sys.exit on HTTP errors — catch and continue
            print(f"  Fetch failed for {map_id}/{topic_id}", file=sys.stderr)
            continue

    return evidence


# ---------------------------------------------------------------------------
# Phase 4: Gap check
# ---------------------------------------------------------------------------

def check_gaps(
    request: str,
    plan: dict,
    section_evidence: dict[int, list[dict]],
    model: str,
) -> list[dict]:
    """Review coverage and suggest retry queries for weak sections.

    Returns list of {"section_index": int, "queries": [str]} dicts.
    """
    # Build coverage summary
    plan_lines = []
    status_lines = []

    for i, sec in enumerate(plan.get("sections", [])):
        ev_count = len(section_evidence.get(i, []))
        plan_lines.append(f"  [{i}] {sec['title']} ({sec['priority']})")

        if ev_count >= COVERAGE_ADEQUATE:
            status_lines.append(f"  [{i}] {sec['title']}: adequate ({ev_count} evidence pieces)")
        elif ev_count == 1:
            status_lines.append(f"  [{i}] {sec['title']}: weak (1 evidence piece)")
        else:
            status_lines.append(f"  [{i}] {sec['title']}: none (0 evidence pieces)")

    # If all sections are adequate, skip the LLM call
    weak_count = sum(
        1 for i in range(len(plan.get("sections", [])))
        if len(section_evidence.get(i, [])) < COVERAGE_ADEQUATE
    )
    if weak_count == 0:
        return []

    prompt = GAP_USER_TEMPLATE.format(
        request=request,
        plan_summary="\n".join(plan_lines),
        per_section_status="\n".join(status_lines),
    )

    response = _call_llm(GAP_SYSTEM_PROMPT, prompt, model=model)
    if not response:
        return []

    result = _parse_json_from_llm(response)
    return result.get("retry_queries", [])


# ---------------------------------------------------------------------------
# Phase 5: Synthesize brief
# ---------------------------------------------------------------------------

def _coverage_label(count: int) -> str:
    if count >= COVERAGE_STRONG:
        return "strong"
    elif count >= COVERAGE_ADEQUATE:
        return "adequate"
    elif count >= 1:
        return "weak"
    return "none"


def synthesize_brief(
    request: str,
    plan: dict,
    section_evidence: dict[int, list[dict]],
    stats: dict,
) -> dict:
    """Assemble the final research brief from plan + evidence."""
    sections_out = []
    all_citations: list[str] = []
    seen_citations: set[str] = set()

    for i, sec in enumerate(plan.get("sections", [])):
        evidence = section_evidence.get(i, [])
        section_out = {
            "title": sec.get("title", f"Section {i+1}"),
            "description": sec.get("description", ""),
            "priority": sec.get("priority", "medium"),
            "queries_used": sec.get("queries", []),
            "evidence": evidence,
            "coverage": _coverage_label(len(evidence)),
            "hit_count": sec.get("_hit_count", 0),
            "fetched_count": len(evidence),
        }
        sections_out.append(section_out)

        # Collect citations
        for ev in evidence:
            citation = (
                f"docs-cortex.paloaltonetworks.com — "
                f"{ev.get('topic_title', 'Unknown')} "
                f"({ev.get('map_title', 'Unknown')})"
            )
            if citation not in seen_citations:
                seen_citations.add(citation)
                all_citations.append(citation)

    return {
        "request": request,
        "deliverable_type": plan.get("deliverable_type", "document"),
        "audience": plan.get("audience", "general"),
        "sections": sections_out,
        "citations": all_citations,
        "stats": stats,
    }


# ---------------------------------------------------------------------------
# Text output formatter
# ---------------------------------------------------------------------------

def format_text_output(brief: dict) -> str:
    """Format research brief as human-readable text."""
    lines = []
    stats = brief.get("stats", {})

    lines.append("=== Deep Search Research Brief ===")
    lines.append(f"Request: {brief['request']}")
    lines.append(
        f"Type: {brief['deliverable_type']} | "
        f"Audience: {brief['audience']}"
    )
    lines.append(
        f"Sections: {stats.get('sections_planned', 0)} planned, "
        f"{stats.get('sections_with_evidence', 0)} with evidence | "
        f"Topics fetched: {stats.get('topics_fetched', 0)}"
    )
    lines.append("")

    for i, sec in enumerate(brief.get("sections", []), 1):
        priority = sec.get("priority", "medium").upper()
        coverage = sec.get("coverage", "none")
        fetched = sec.get("fetched_count", 0)
        lines.append(
            f"--- Section {i}: {sec['title']} ({priority}) ---"
        )
        lines.append(f"Coverage: {coverage} ({fetched} topics)")
        lines.append(f"Queries: {', '.join(repr(q) for q in sec.get('queries_used', []))}")
        lines.append("")

        for j, ev in enumerate(sec.get("evidence", []), 1):
            lines.append(
                f"  [{j}] {ev.get('topic_title', 'Unknown')} "
                f"({ev.get('map_title', '')})"
            )
            lines.append(f"      {ev.get('reader_url', '')}")
            lines.append(f"      {ev.get('content_chars', 0):,} chars")
            lines.append("")

    lines.append("=== Citations ===")
    for c in brief.get("citations", []):
        lines.append(f"- {c}")
    lines.append("")

    lines.append("=== Stats ===")
    lines.append(
        f"Sections: {stats.get('sections_planned', 0)} planned, "
        f"{stats.get('sections_with_evidence', 0)} covered"
    )
    lines.append(
        f"Queries: {stats.get('total_queries', 0)} total, "
        f"{stats.get('total_search_hits', 0)} hits"
    )
    lines.append(
        f"Topics: {stats.get('topics_fetched', 0)} fetched, "
        f"{stats.get('total_content_chars', 0):,} chars"
    )
    lines.append(
        f"Gap check: {'enabled' if stats.get('gap_check_enabled') else 'disabled'}, "
        f"{stats.get('gap_check_retries', 0)} retries"
    )
    lines.append(f"Time: {stats.get('execution_time_seconds', 0):.1f}s")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def run_deep_search(
    request: str,
    max_sections: int = 10,
    hits_per_section: int = 4,
    max_chars_per_topic: int = FETCH_MAX_CHARS,
    enable_gap_check: bool = False,
    model: str = DEFAULT_MODEL,
    output_json: bool = False,
) -> dict:
    """Execute the full deep search pipeline.

    Returns the research brief dict.
    """
    start_time = time.time()
    total_queries = 0
    total_search_hits = 0
    total_content_chars = 0
    gap_retries = 0

    # ── Phase 1: Plan ──────────────────────────────────────────────
    print("Phase 1: Planning research outline...", file=sys.stderr)
    plan = plan_research(request, max_sections, model)
    sections = plan.get("sections", [])
    print(
        f"  → {len(sections)} sections planned "
        f"(type={plan.get('deliverable_type')}, audience={plan.get('audience')})",
        file=sys.stderr,
    )

    if not sections:
        print("  No sections generated, aborting", file=sys.stderr)
        return synthesize_brief(request, plan, {}, {
            "sections_planned": 0,
            "sections_with_evidence": 0,
            "total_queries": 0,
            "total_search_hits": 0,
            "topics_fetched": 0,
            "total_content_chars": 0,
            "gap_check_enabled": enable_gap_check,
            "gap_check_retries": 0,
            "execution_time_seconds": time.time() - start_time,
        })

    # ── Phase 2: Search per section ────────────────────────────────
    print("Phase 2: Searching per section...", file=sys.stderr)
    global_seen: set[str] = set()
    section_hits: dict[int, list[dict]] = {}

    for i, sec in enumerate(sections):
        queries = sec.get("queries", [])
        total_queries += len(queries)
        print(
            f"  Section {i+1}/{len(sections)}: {sec.get('title', '?')} "
            f"({len(queries)} queries, scope={sec.get('product_scope', 'global')})",
            file=sys.stderr,
        )

        hits, raw_count = search_section(sec, hits_per_section, global_seen)
        total_search_hits += raw_count
        section_hits[i] = hits
        sec["_hit_count"] = raw_count

        print(f"    → {len(hits)} unique hits (from {raw_count} raw)", file=sys.stderr)

    # ── Phase 3: Fetch evidence ────────────────────────────────────
    print("Phase 3: Fetching full topic content...", file=sys.stderr)
    section_evidence: dict[int, list[dict]] = {}

    for i, hits in section_hits.items():
        if not hits:
            section_evidence[i] = []
            continue

        print(
            f"  Section {i+1}: fetching {len(hits)} topics...",
            file=sys.stderr,
        )
        evidence = fetch_evidence(hits, max_chars=max_chars_per_topic)
        section_evidence[i] = evidence
        chars = sum(e.get("content_chars", 0) for e in evidence)
        total_content_chars += chars
        print(
            f"    → {len(evidence)} topics, {chars:,} chars",
            file=sys.stderr,
        )

    # ── Phase 4: Gap check (optional) ─────────────────────────────
    if enable_gap_check:
        print("Phase 4: Checking coverage gaps...", file=sys.stderr)
        retries = check_gaps(request, plan, section_evidence, model)

        if retries:
            print(
                f"  → {len(retries)} sections need retry queries",
                file=sys.stderr,
            )
            for retry in retries:
                idx = retry.get("section_index", -1)
                if idx < 0 or idx >= len(sections):
                    continue

                retry_queries = retry.get("queries", [])
                total_queries += len(retry_queries)
                gap_retries += len(retry_queries)

                print(
                    f"  Retrying section {idx+1} with {len(retry_queries)} queries",
                    file=sys.stderr,
                )

                # Add retry queries to the section for tracking
                sections[idx].setdefault("queries", []).extend(retry_queries)

                # Search with retry queries
                retry_sec = {
                    "queries": retry_queries,
                    "product_scope": sections[idx].get("product_scope", ""),
                }
                retry_hits, retry_raw = search_section(
                    retry_sec, hits_per_section, global_seen
                )
                total_search_hits += retry_raw

                if retry_hits:
                    retry_evidence = fetch_evidence(
                        retry_hits, max_chars=max_chars_per_topic
                    )
                    section_evidence[idx].extend(retry_evidence)
                    chars = sum(e.get("content_chars", 0) for e in retry_evidence)
                    total_content_chars += chars
                    print(
                        f"    → {len(retry_evidence)} new topics, {chars:,} chars",
                        file=sys.stderr,
                    )
        else:
            print("  → All sections have adequate coverage", file=sys.stderr)

    # ── Phase 5: Synthesize ────────────────────────────────────────
    print("Phase 5: Synthesizing research brief...", file=sys.stderr)

    topics_fetched = sum(len(ev) for ev in section_evidence.values())
    sections_with_evidence = sum(
        1 for ev in section_evidence.values() if ev
    )

    stats = {
        "sections_planned": len(sections),
        "sections_with_evidence": sections_with_evidence,
        "total_queries": total_queries,
        "total_search_hits": total_search_hits,
        "topics_fetched": topics_fetched,
        "total_content_chars": total_content_chars,
        "gap_check_enabled": enable_gap_check,
        "gap_check_retries": gap_retries,
        "execution_time_seconds": round(time.time() - start_time, 1),
    }

    brief = synthesize_brief(request, plan, section_evidence, stats)

    print(
        f"Done: {sections_with_evidence}/{len(sections)} sections covered, "
        f"{topics_fetched} topics, {total_content_chars:,} chars, "
        f"{stats['execution_time_seconds']}s",
        file=sys.stderr,
    )

    return brief


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Deep research planner for Cortex documentation"
    )
    parser.add_argument(
        "--request",
        required=True,
        help="The document creation request to research",
    )
    parser.add_argument(
        "--max-sections",
        type=int,
        default=10,
        help="Maximum sections in research plan (default: 10)",
    )
    parser.add_argument(
        "--hits-per-section",
        type=int,
        default=4,
        help="Top hits to fetch per section (default: 4)",
    )
    parser.add_argument(
        "--max-chars-per-topic",
        type=int,
        default=FETCH_MAX_CHARS,
        help=f"Content budget per topic (default: {FETCH_MAX_CHARS})",
    )
    parser.add_argument(
        "--enable-gap-check",
        action="store_true",
        help="Enable gap analysis with retry round",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Anthropic model for planning (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Output raw JSON instead of formatted text",
    )

    args = parser.parse_args()

    brief = run_deep_search(
        request=args.request,
        max_sections=args.max_sections,
        hits_per_section=args.hits_per_section,
        max_chars_per_topic=args.max_chars_per_topic,
        enable_gap_check=args.enable_gap_check,
        model=args.model,
        output_json=args.output_json,
    )

    if args.output_json:
        json.dump(brief, sys.stdout, ensure_ascii=False, indent=2)
        print()  # trailing newline
    else:
        print(format_text_output(brief))


if __name__ == "__main__":
    main()
