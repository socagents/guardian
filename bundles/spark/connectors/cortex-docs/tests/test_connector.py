"""cortex-docs connector — unit tests.

These tests don't hit the live docs API. They mock the upstream
script entrypoints (`_search.search`, `_xql_lookup._first_fetchable_hit`,
etc.) and verify the wrapper layer's contract:

  1. SystemExit raised by upstream `sys.exit(1)` paths becomes a
     structured `{ok: false, error: ...}` return — does NOT propagate.
  2. Successful upstream returns flow through with an `ok: true`
     stamp and the documented payload shape.
  3. The kind/product inference + cleaning stays consistent with the
     CLI behaviour ported from xql_lookup.py.

Run live-API smoke separately with:
  python3 bundles/spark/connectors/cortex-docs/tests/smoke_live.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import pytest

# Make the connector package importable. Mirrors how the embedded MCP's
# connector_loader injects the bundle path at boot.
SRC_PARENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SRC_PARENT))

from src import connector  # noqa: E402


# ─── SystemExit translation ──────────────────────────────────────────


def test_search_translates_systemexit_to_error_dict():
    """Upstream search.py:_post_json() calls sys.exit(1) on HTTPError.
    The wrapper must catch that and return ok=false instead of letting
    SystemExit propagate (which would kill phantom-agent)."""
    with mock.patch.object(connector._search, "search", side_effect=SystemExit(1)):
        result = connector.cortex_search("anything")
    assert result["ok"] is False
    assert "error" in result
    assert "sys.exit" in result["error"]


def test_suggest_translates_systemexit():
    with mock.patch.object(connector._search, "suggest", side_effect=SystemExit(1)):
        result = connector.cortex_suggest("partial")
    assert result["ok"] is False
    assert "error" in result


def test_fetch_topic_translates_systemexit():
    with mock.patch.object(
        connector._fetch_topic, "fetch_topic_with_fallback",
        side_effect=SystemExit(1),
    ):
        result = connector.cortex_fetch_topic("map123", "topic456")
    assert result["ok"] is False
    assert "error" in result


def test_fetch_toc_translates_systemexit():
    with mock.patch.object(
        connector._fetch_topic, "fetch_toc",
        side_effect=SystemExit(1),
    ):
        result = connector.cortex_fetch_toc("map123")
    assert result["ok"] is False


def test_xql_lookup_translates_systemexit():
    with mock.patch.object(
        connector._xql_lookup, "_first_fetchable_hit",
        side_effect=SystemExit(1),
    ):
        result = connector.cortex_xql_lookup("dedup")
    assert result["ok"] is False


# ─── Success-path shape tests ────────────────────────────────────────


def test_search_success_payload_shape():
    fake_hits = [
        {
            "title": "filter (XQL Stage)",
            "topic_id": "t1",
            "map_id": "m1",
            "map_title": "Cortex XSIAM Documentation",
            "reader_url": "https://example/filter",
            "excerpt": "Filter rows matching a condition.",
        }
    ]
    fake_result = {
        "query": "filter",
        "total_hits": 1,
        "scope": ["Cortex XSIAM"],
        "facets": {"Product": ["Cortex XSIAM"]},
        "hits": fake_hits,
    }
    with mock.patch.object(connector._search, "search", return_value=fake_result):
        result = connector.cortex_search("filter", product="xsiam")

    assert result["ok"] is True
    assert result["query"] == "filter"
    assert result["total_hits"] == 1
    assert result["hits"][0]["title"] == "filter (XQL Stage)"
    assert result["facets"] == {"Product": ["Cortex XSIAM"]}


def test_xql_lookup_success_when_found():
    fake_hit = {
        "title": "dedup",
        "topic_id": "t1",
        "map_id": "m1",
        "map_title": "Cortex AgentiX Documentation",
        "reader_url": "https://example/dedup",
        "excerpt": "Dedup removes duplicate rows.",
    }
    fake_topic = {
        "title": "dedup",
        "map_title": "Cortex AgentiX Documentation",
        "reader_url": "https://example/dedup",
        "content": "The dedup stage removes duplicate rows from the result set.\n\nSyntax: dedup <field> [by <key>].",
    }
    with mock.patch.object(
        connector._xql_lookup, "_first_fetchable_hit",
        return_value=(fake_hit, fake_topic),
    ):
        result = connector.cortex_xql_lookup("dedup", kind="stage")

    assert result["ok"] is True
    assert result["found"] is True
    assert result["title"] == "dedup"
    assert result["publication"] == "Cortex AgentiX Documentation"
    assert "dedup" in result["summary_content"].lower()
    assert "AgentiX" in result["source"]
    # scope_note populated when product=='xql' (default)
    assert result["scope_note"]
    assert result["product"] == "xql"


def test_xql_lookup_success_when_not_found():
    """When no hit is fetchable, _first_fetchable_hit returns (empty
    dict, info dict). The wrapper packages that as found: false."""
    with mock.patch.object(
        connector._xql_lookup, "_first_fetchable_hit",
        return_value=({}, {"fetch_errors": ["topic 1: timeout"]}),
    ):
        result = connector.cortex_xql_lookup("totallymadeup")

    assert result["ok"] is True  # tool itself didn't fail
    assert result["found"] is False
    assert result["fetch_errors"] == ["topic 1: timeout"]


def test_xql_lookup_kind_inference():
    """kind='auto' should map known stages → 'stage' and unknown
    terms → 'function'. We only verify the wrapper preserves the
    upstream's _infer_kind behaviour, not re-test the inference logic."""
    with mock.patch.object(
        connector._xql_lookup, "_first_fetchable_hit",
        return_value=({}, {}),
    ) as m:
        connector.cortex_xql_lookup("dedup")
        # Upstream takes (term, kind, product, per_page); kind should
        # have been inferred to "stage" because dedup is in STAGES.
        args, _kwargs = m.call_args
        assert args[1] == "stage", f"expected kind=stage for 'dedup', got {args[1]}"


def test_fetch_topic_success_passthrough():
    fake_topic = {
        "title": "Filter Stage",
        "map_title": "Cortex XSIAM Documentation",
        "reader_url": "https://example/filter",
        "content": "The filter stage keeps rows matching a condition.",
    }
    with mock.patch.object(
        connector._fetch_topic, "fetch_topic_with_fallback",
        return_value=fake_topic,
    ):
        result = connector.cortex_fetch_topic("m1", "t1")

    assert result["ok"] is True
    assert result["title"] == "Filter Stage"
    assert result["content"].startswith("The filter stage")


def test_suggest_success():
    with mock.patch.object(
        connector._search, "suggest",
        return_value=["filter stage", "filter syntax"],
    ):
        result = connector.cortex_suggest("filter")

    assert result["ok"] is True
    assert result["suggestions"] == ["filter stage", "filter syntax"]


def test_fetch_toc_success_wraps_in_items():
    fake_items = [
        {"topic_id": "t1", "title": "Overview", "depth": 0, "parent_id": None},
        {"topic_id": "t2", "title": "Stages", "depth": 1, "parent_id": "t1"},
    ]
    with mock.patch.object(
        connector._fetch_topic, "fetch_toc",
        return_value=fake_items,
    ):
        result = connector.cortex_fetch_toc("m1")

    assert result["ok"] is True
    assert result["items"] == fake_items


# ─── deep_research smoke ─────────────────────────────────────────────


def test_deep_research_success_wraps_in_brief():
    fake_brief = {
        "request": "test",
        "deliverable_type": "brief",
        "audience": "operator",
        "sections": [],
        "citations": [],
        "coverage": {},
        "stats": {},
    }
    with mock.patch.object(
        connector._research_planner, "run_deep_search",
        return_value=fake_brief,
    ):
        result = connector.cortex_deep_research("test request", max_sections=3)

    assert result["ok"] is True
    assert "brief" in result
    assert result["brief"]["deliverable_type"] == "brief"


def test_deep_research_translates_systemexit():
    with mock.patch.object(
        connector._research_planner, "run_deep_search",
        side_effect=SystemExit(1),
    ):
        result = connector.cortex_deep_research("test")
    assert result["ok"] is False


# ─── Public surface check ────────────────────────────────────────────


def test_all_exported_tools_are_callable():
    """connector.__all__ should match the callable cortex_* surface
    in the module — no stragglers, no missing entries."""
    expected = {
        "cortex_search",
        "cortex_suggest",
        "cortex_xql_lookup",
        "cortex_fetch_topic",
        "cortex_fetch_toc",
        "cortex_deep_research",
    }
    assert set(connector.__all__) == expected
    for name in expected:
        assert callable(getattr(connector, name)), f"{name} not callable"
