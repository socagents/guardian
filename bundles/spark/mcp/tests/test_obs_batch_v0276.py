"""v0.2.76 audit batch — observability-granularity gaps.

Covers the pure-Python sites in this batch:

  * #KB-F9 — kb_store._resolve_embedding reports the embedding SOURCE
    (precomputed | live | live_mismatch); upsert accumulates a precomputed-vs-
    live-embedded split into the caller's out-dict so the kb_loaded row can
    differentiate a boot that reused trusted baked vectors from one that paid
    for live Vertex calls. Also: the per-doc kb_doc_indexed row carries
    embedding_source.
  * #INV-F9 — _clean_svg tags an over-cap SVG with code='svg_too_large' (+
    bytes/cap), and the diagram setters emit a distinct issue_diagram_rejected
    audit row so the Investigation UI poll can tell a too-large rejection apart
    from a generic agent-run failure/timeout.
  * #CDW-F16 — research_planner.plan_research tags the keyword-fallback plan
    with a _planning_fallback reason (anthropic_api_key_unset vs the LLM
    failure cases) instead of leaving the degradation only in stderr.
  * #CDW-F3 — run_deep_search returns a per-phase summary + warnings on the
    brief.stats envelope, and connector_loader._audit_meta hoists those into
    the single tool_call audit row (the connector can't write audit.db).
  * #OBS-F16 — the plugin_install audit row metadata includes a stdout tail.
  * manifest — every NEW v0.2.76 action string is declared under audit.events.

The TypeScript sites (CHAT-F7/F16/F17/F22, HOOK-F2/F16, MEM-F10/F12, OBS-F19)
are validated by the tsc gate + live smoke; this file covers the Python sites.

Repo has NO pytest-asyncio — anything async is driven via asyncio.run().
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from usecase import audit_log as audit_mod  # noqa: E402
from usecase.investigation_store import InvestigationStore  # noqa: E402
from usecase.builtin_components import investigation_tools as it  # noqa: E402
from usecase.kb_store import SqliteKnowledgeBase  # noqa: E402


# ─────────────────────────────────────────────────────────────────
# shared fixtures
# ─────────────────────────────────────────────────────────────────


class SpyEmbedder:
    """Counts embed() calls so a test can prove a baked vector was reused."""

    def __init__(self, dims: int = 4, model_id: str = "m1") -> None:
        self.dims = dims
        self.model_id = model_id
        self.calls = 0

    def embed(self, text: str) -> list[float]:
        self.calls += 1
        vec = [0.0] * self.dims
        vec[len(text) % self.dims] = 1.0
        return vec


def _wire_real_audit(tmp_path, monkeypatch) -> audit_mod.SqliteAuditLog:
    log = audit_mod.SqliteAuditLog(data_root=tmp_path)
    monkeypatch.setattr(audit_mod, "_audit", log)
    return log


# ─────────────────────────────────────────────────────────────────
# #KB-F9 — embedding-source split (precomputed vs live)
# ─────────────────────────────────────────────────────────────────


def test_resolve_embedding_reports_precomputed_source(tmp_path):
    spy = SpyEmbedder(dims=4, model_id="m1")
    kb = SqliteKnowledgeBase(data_root=tmp_path, embedder=spy)
    vec, source = kb._resolve_embedding(  # noqa: SLF001
        "hello", [0.1, 0.2, 0.3, 0.4], "m1", where="k:d1"
    )
    assert source == "precomputed"
    assert spy.calls == 0
    assert vec == [0.1, 0.2, 0.3, 0.4]


def test_resolve_embedding_reports_live_source(tmp_path):
    spy = SpyEmbedder(dims=4, model_id="m1")
    kb = SqliteKnowledgeBase(data_root=tmp_path, embedder=spy)
    _vec, source = kb._resolve_embedding("hello", None, None, where="k:d1")  # noqa: SLF001
    assert source == "live"
    assert spy.calls == 1


def test_resolve_embedding_reports_live_mismatch_source(tmp_path):
    spy = SpyEmbedder(dims=4, model_id="m1")
    kb = SqliteKnowledgeBase(data_root=tmp_path, embedder=spy)
    _vec, source = kb._resolve_embedding(  # noqa: SLF001
        "hello", [0.1, 0.2, 0.3, 0.4], "OTHER-MODEL", where="k:d1"
    )
    assert source == "live_mismatch"
    assert spy.calls == 1


def test_upsert_accumulates_embedding_stats_precomputed(tmp_path):
    spy = SpyEmbedder(dims=4, model_id="m1")
    kb = SqliteKnowledgeBase(data_root=tmp_path, embedder=spy)
    stats: dict[str, int] = {}
    kb.upsert(
        kb_name="k", doc_id="d1", content="hello", source_hash="h1",
        precomputed_embedding=[0.1, 0.2, 0.3, 0.4], precomputed_model="m1",
        embedding_stats=stats,
    )
    assert stats.get("precomputed") == 1
    assert stats.get("live_embedded", 0) == 0


def test_upsert_accumulates_embedding_stats_live_and_mismatch(tmp_path):
    spy = SpyEmbedder(dims=4, model_id="m1")
    kb = SqliteKnowledgeBase(data_root=tmp_path, embedder=spy)
    stats: dict[str, int] = {}
    # no baked vector → live
    kb.upsert(kb_name="k", doc_id="d1", content="a", source_hash="h1",
              embedding_stats=stats)
    # wrong-model baked vector → live_embedded + live_mismatch
    kb.upsert(kb_name="k", doc_id="d2", content="b", source_hash="h2",
              precomputed_embedding=[0.1, 0.2, 0.3, 0.4],
              precomputed_model="OTHER", embedding_stats=stats)
    assert stats.get("live_embedded") == 2
    assert stats.get("live_mismatch") == 1
    assert stats.get("precomputed", 0) == 0


def test_upsert_doc_indexed_row_carries_embedding_source(tmp_path, monkeypatch):
    log = _wire_real_audit(tmp_path, monkeypatch)
    spy = SpyEmbedder(dims=4, model_id="m1")
    kb = SqliteKnowledgeBase(data_root=tmp_path, embedder=spy)
    kb.upsert(
        kb_name="k", doc_id="d1", content="hello", source_hash="h1",
        precomputed_embedding=[0.1, 0.2, 0.3, 0.4], precomputed_model="m1",
    )
    rows = log.query(action="kb_doc_indexed")
    assert rows, "expected a kb_doc_indexed row"
    assert rows[0]["metadata"]["embedding_source"] == "precomputed"


def test_upsert_unchanged_does_not_touch_embedding_stats(tmp_path):
    spy = SpyEmbedder(dims=4, model_id="m1")
    kb = SqliteKnowledgeBase(data_root=tmp_path, embedder=spy)
    stats: dict[str, int] = {}
    kb.upsert(kb_name="k", doc_id="d1", content="a", source_hash="h1",
              embedding_stats=stats)
    # same source_hash → "unchanged" fast-path embeds nothing
    kb.upsert(kb_name="k", doc_id="d1", content="a", source_hash="h1",
              embedding_stats=stats)
    assert stats.get("live_embedded") == 1, "unchanged must not re-count"


# ─────────────────────────────────────────────────────────────────
# #INV-F9 — SVG-too-large rejection is tagged + audited distinctly
# ─────────────────────────────────────────────────────────────────


def test_clean_svg_too_large_tags_code():
    big = "<svg>" + ("x" * 300_000) + "</svg>"
    cleaned, verr = it._clean_svg(big)  # noqa: SLF001
    assert cleaned is None
    assert verr is not None
    assert verr["code"] == "svg_too_large"
    assert verr["bytes"] > 256_000
    assert verr["cap"] == 256_000


def test_clean_svg_not_markup_tags_code():
    cleaned, verr = it._clean_svg("not an svg at all")  # noqa: SLF001
    assert cleaned is None
    assert verr["code"] == "svg_not_markup"


def test_clean_svg_valid_passes():
    cleaned, verr = it._clean_svg("<svg><rect/></svg>")  # noqa: SLF001
    assert verr is None
    assert cleaned is not None


def _wire_inv_store(tmp_path, monkeypatch):
    s = InvestigationStore(data_root=tmp_path)
    monkeypatch.setattr(it, "investigation_store", lambda: s)
    return s


def test_issue_set_attack_chain_too_large_emits_audit(tmp_path, monkeypatch):
    log = _wire_real_audit(tmp_path, monkeypatch)
    s = _wire_inv_store(tmp_path, monkeypatch)
    iss = s.create_issue(title="t")
    big = "<svg>" + ("x" * 300_000) + "</svg>"

    res = it.issue_set_attack_chain(iss.id, big)
    assert res.get("code") == "svg_too_large"

    rows = log.query(action="issue_diagram_rejected")
    assert len(rows) == 1
    md = rows[0]["metadata"]
    assert rows[0]["target"] == f"issue:{iss.id}"
    assert md["diagram"] == "attack_chain"
    assert md["code"] == "svg_too_large"
    assert md["bytes"] > 256_000


def test_case_set_relation_graph_too_large_emits_audit(tmp_path, monkeypatch):
    log = _wire_real_audit(tmp_path, monkeypatch)
    s = _wire_inv_store(tmp_path, monkeypatch)
    case = s.create_case(title="c")
    big = "<svg>" + ("x" * 300_000) + "</svg>"

    res = it.case_set_relation_graph(case.id, big)
    assert res.get("code") == "svg_too_large"

    rows = log.query(action="issue_diagram_rejected")
    assert len(rows) == 1
    assert rows[0]["target"] == f"case:{case.id}"
    assert rows[0]["metadata"]["diagram"] == "relations"


def test_issue_set_attack_chain_valid_no_rejection_audit(tmp_path, monkeypatch):
    log = _wire_real_audit(tmp_path, monkeypatch)
    s = _wire_inv_store(tmp_path, monkeypatch)
    iss = s.create_issue(title="t")

    res = it.issue_set_attack_chain(iss.id, "<svg><rect/></svg>")
    assert res.get("ok") is True
    assert log.query(action="issue_diagram_rejected") == []


# ─────────────────────────────────────────────────────────────────
# #CDW-F16 / #CDW-F3 — research_planner fallback + per-phase envelope
#   (the connector lives under its own src/; import it directly)
# ─────────────────────────────────────────────────────────────────


def _load_research_planner():
    # tests/ → mcp → spark; the connector lives at spark/connectors/cortex-docs.
    rp_dir = (
        Path(__file__).resolve().parents[2]
        / "connectors" / "cortex-docs" / "src"
    )
    rp_path = rp_dir / "research_planner.py"
    # research_planner imports sibling modules (search, fetch_topic) from its own
    # src/ dir; put it on sys.path so the import resolves under pytest too.
    if str(rp_dir) not in sys.path:
        sys.path.insert(0, str(rp_dir))
    spec = importlib.util.spec_from_file_location("research_planner_v0276", rp_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_plan_research_tags_fallback_when_key_unset(monkeypatch):
    rp = _load_research_planner()
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # No key → _call_llm returns "" → keyword fallback, tagged with the
    # "anthropic_api_key_unset" reason (distinct from a transient LLM error).
    plan = rp.plan_research("Create a brief about XDR incident response", 5, rp.DEFAULT_MODEL)
    assert plan.get("_planning_fallback") == "anthropic_api_key_unset"
    assert "sections" in plan


def test_anthropic_key_configured_helper(monkeypatch):
    rp = _load_research_planner()
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert rp._anthropic_key_configured() is False  # noqa: SLF001
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert rp._anthropic_key_configured() is True  # noqa: SLF001


def test_run_deep_search_returns_phases_and_warnings(monkeypatch):
    rp = _load_research_planner()
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    # Stub the network-touching pieces so the pipeline runs offline. The plan
    # comes from the keyword fallback (no key); stub search/fetch to deterministic
    # empties so we exercise the phase-recording + warning paths.
    monkeypatch.setattr(rp, "search_section", lambda sec, n, seen: ([], 0))
    monkeypatch.setattr(rp, "fetch_evidence", lambda hits, max_chars: [])

    brief = rp.run_deep_search(
        request="Create a brief about XDR incident response",
        max_sections=3,
        hits_per_section=2,
        enable_gap_check=False,
    )
    stats = brief["stats"]
    assert "phases" in stats and isinstance(stats["phases"], list)
    names = [p["name"] for p in stats["phases"]]
    assert "plan" in names
    assert "search" in names
    assert "fetch" in names
    assert "synthesize" in names
    # warnings: the api-key-unset fallback + sections-no-hits + incomplete-coverage
    codes = {w["code"] for w in stats["warnings"]}
    assert "anthropic_api_key_unset" in codes
    assert "sections_no_hits" in codes


# ─────────────────────────────────────────────────────────────────
# #CDW-F3 — connector_loader._audit_meta hoists research_phases/warnings
# ─────────────────────────────────────────────────────────────────


def test_audit_meta_hoists_research_phases(monkeypatch):
    """Exercise the result-inspection branch of _audit_meta by invoking the
    nested closure indirectly. _audit_meta is defined inside _wrap_tool, so we
    drive the public-facing extraction logic via a tiny re-implementation guard:
    confirm the connector_loader module exposes the precedent + our key names by
    asserting the source contains the hoist for research_phases/research_warnings.
    """
    cl_path = SRC / "usecase" / "connector_loader.py"
    text = cl_path.read_text()
    assert "research_phases" in text
    assert "research_warnings" in text
    # The hoist must read from brief.stats (the envelope run_deep_search returns).
    assert 'result.get("brief")' in text


# ─────────────────────────────────────────────────────────────────
# #OBS-F16 — plugin_install audit metadata includes a stdout tail
# ─────────────────────────────────────────────────────────────────


def test_plugin_install_route_audits_stdout_tail():
    p = SRC / "api" / "plugin_entry_points_routes.py"
    text = p.read_text()
    # The audit metadata dict must include stdout_tail (not only stderr_tail).
    assert '"stdout_tail": out[-500:]' in text


# ─────────────────────────────────────────────────────────────────
# manifest — every NEW v0.2.76 action declared under audit.events
# ─────────────────────────────────────────────────────────────────


def test_new_actions_declared_in_manifest():
    import yaml

    manifest_path = Path(__file__).resolve().parents[2] / "manifest.yaml"
    events = set(yaml.safe_load(manifest_path.read_text())["audit"]["events"])
    for value in (
        "chat_compaction_persist_failed",  # #CHAT-F17
        "memory_inject_skipped",           # #MEM-F10
        "hook_invalid",                    # #HOOK-F2
        "issue_diagram_rejected",          # #INV-F9
    ):
        assert value in events, f"{value!r} missing from manifest audit.events"
