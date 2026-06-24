"""v0.2.78 validation-guard batch — input-validation / guard gaps.

Covers the pure-Python guards in this batch. Each guard rejects bad input
early with a clear error (fail-closed) instead of failing late/silently:

  * #SKILL-F11 — skills_crud._resolve_skill_path rejects path traversal
    (../../etc/passwd) and absolute paths, keeping skill ops inside
    SKILLS_DIR; a good relative path resolves cleanly.
  * #KB-F14 — knowledge_list rejects an unknown kb_name with a structured
    error + valid_kbs list (was: silent [] / count:0), mirroring the REST
    _kb_exists_or_404 helper.
  * #MEM-F15 — memory_store wraps a non-ValueError (embedding) failure with
    _friendly_embed_error instead of letting the raw exception propagate.
  * #INV-F4 — _stix._issue_objects now connects relationship edges whose
    target is an attack-pattern (target_type=attack-pattern, target_value=
    technique_id), instead of silently dropping them.
  * #MEM-F7 — _personality_rank_kwargs translates the personality blob's
    memoryMmrLambda / memoryTemporalDecayLambda into search() rank kwargs
    (and yields {} when absent/malformed so search keeps its defaults).

Modules needing heavy deps are imported with light stubs:
  * skills_crud imports `mcp` → stubbed.
connector_probes (httpx), connector_loader (pydantic), and the job_scheduler
auto-disable path (croniter) are CI-only; #XSIAM-F8/#XSIAM-F12/#XSOAR-F5/
#JOBS-F9/#OBS-F21 are validated by the tsc/py_compile gate + live smoke.

Repo has NO pytest-asyncio — nothing here is async.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


# ─────────────────────────────────────────────────────────────────
# light stub for the `mcp` package so skills_crud imports dep-free
# ─────────────────────────────────────────────────────────────────
def _stub_mcp() -> None:
    if "mcp" in sys.modules:
        return
    mcp_mod = types.ModuleType("mcp")
    mcp_types = types.ModuleType("mcp.types")

    class _Tool:  # minimal stand-in
        def __init__(self, *a, **k):
            pass

    mcp_types.Tool = _Tool
    mcp_mod.types = mcp_types
    sys.modules["mcp"] = mcp_mod
    sys.modules["mcp.types"] = mcp_types


# ─────────────────────────────────────────────────────────────────
# #SKILL-F11 — path-traversal guard
# ─────────────────────────────────────────────────────────────────
def test_skill_path_rejects_traversal():
    _stub_mcp()
    from usecase.builtin_components import skills_crud as s
    path, err = s._resolve_skill_path("../../etc/passwd")
    assert path is None
    assert err and "Invalid skill path" in err


def test_skill_path_rejects_absolute():
    _stub_mcp()
    from usecase.builtin_components import skills_crud as s
    path, err = s._resolve_skill_path("/etc/passwd")
    assert path is None
    assert err and "Invalid skill path" in err


def test_skill_path_rejects_empty():
    _stub_mcp()
    from usecase.builtin_components import skills_crud as s
    path, err = s._resolve_skill_path("   ")
    assert path is None
    assert err == "file_path is required"


def test_skill_path_accepts_relative_inside_dir():
    _stub_mcp()
    from usecase.builtin_components import skills_crud as s
    path, err = s._resolve_skill_path("workflows/example.md")
    assert err is None
    assert path is not None
    # Stays inside SKILLS_DIR.
    assert str(path).startswith(str(s.SKILLS_DIR.resolve()))


def test_skill_read_rejects_traversal_end_to_end():
    _stub_mcp()
    from usecase.builtin_components import skills_crud as s
    result = s.read_skill("../../etc/passwd")
    assert result["success"] is False
    assert "Invalid skill path" in result["error"]


# ─────────────────────────────────────────────────────────────────
# #KB-F14 — knowledge_list rejects unknown kb_name
# ─────────────────────────────────────────────────────────────────
class _FakeKb:
    def __init__(self, names):
        self._names = list(names)

    def kb_summary(self):
        return {n: {"count": 1} for n in self._names}

    def list_docs(self, kb_name, limit=20):
        return []  # mimics SQL returning no rows for an unknown name


def test_knowledge_list_rejects_unknown_kb(monkeypatch=None):
    from usecase.builtin_components import cognitive_tools as ct
    import usecase.kb_store as kb_store

    fake = _FakeKb(["cortex-docs", "soc-investigation"])
    orig = kb_store.knowledge_base
    kb_store.knowledge_base = lambda: fake
    try:
        out = ct.knowledge_list("ghost-kb")
        assert "error" in out
        assert "unknown knowledge base" in out["error"]
        assert out["valid_kbs"] == ["cortex-docs", "soc-investigation"]
    finally:
        kb_store.knowledge_base = orig


def test_knowledge_list_accepts_known_kb():
    from usecase.builtin_components import cognitive_tools as ct
    import usecase.kb_store as kb_store

    fake = _FakeKb(["cortex-docs"])
    orig = kb_store.knowledge_base
    kb_store.knowledge_base = lambda: fake
    try:
        out = ct.knowledge_list("cortex-docs")
        # No error key on success; returns the listing shape.
        assert "error" not in out
        assert out["kb_name"] == "cortex-docs"
    finally:
        kb_store.knowledge_base = orig


# ─────────────────────────────────────────────────────────────────
# #MEM-F15 — memory_store wraps embedding failures
# ─────────────────────────────────────────────────────────────────
class _FakeMemStoreEmbedFail:
    def store(self, *, key, value, scope, ttl_seconds):
        raise RuntimeError("vertex embed: 404 not found")


class _FakeMem:
    def to_dict(self):
        return {"key": "k", "value": "v"}


class _FakeMemStoreOK:
    def store(self, *, key, value, scope, ttl_seconds):
        return _FakeMem()


def test_memory_store_wraps_embed_error():
    from usecase.builtin_components import cognitive_tools as ct
    import usecase.memory_store as mem_store

    orig = mem_store.memory_store
    mem_store.memory_store = lambda: _FakeMemStoreEmbedFail()
    try:
        out = ct.memory_store(key="k", value="v")
        assert "error" in out
        # Routed through _friendly_embed_error (names the Vertex 404 cause).
        assert "memory_store failed" in out["error"]
        assert "Vertex" in out["error"]
    finally:
        mem_store.memory_store = orig


def test_memory_store_accepts_good_input():
    from usecase.builtin_components import cognitive_tools as ct
    import usecase.memory_store as mem_store

    orig = mem_store.memory_store
    mem_store.memory_store = lambda: _FakeMemStoreOK()
    try:
        out = ct.memory_store(key="k", value="v")
        assert out == {"key": "k", "value": "v"}
    finally:
        mem_store.memory_store = orig


# ─────────────────────────────────────────────────────────────────
# #INV-F4 — STIX export connects attack-pattern relationship edges
# ─────────────────────────────────────────────────────────────────
class _Ind:
    def __init__(self, value, itype="ip"):
        self.value = value
        self.type = itype
        self.created_at = None
        self.updated_at = None
        self.first_seen = None


class _Tech:
    def __init__(self, tid, tactic=None):
        self.technique_id = tid
        self.tactic = tactic


class _Issue:
    id = "issue-1"
    title = "T"
    summary = "s"
    conclusions = ""
    created_at = None
    updated_at = None


class _FakeInvStore:
    def __init__(self, rels):
        self._rels = rels
        self._ind = _Ind("1.2.3.4")

    def list_indicators_for_issue(self, _id):
        return [self._ind]

    def list_technique_mappings(self, _id):
        return [_Tech("T1071.004", "command-and-control")]

    def list_relationships(self):
        return self._rels

    def get_indicator(self, _id):
        return {"value": "1.2.3.4"}


def test_stix_connects_attack_pattern_edge():
    from usecase.builtin_components import _stix

    # An edge from the indicator to an attack-pattern technique.
    rels = [{
        "source_id": "ind-1",
        "target_value": "T1071.004",
        "target_type": "attack-pattern",
        "relationship_type": "uses",
    }]
    store = _FakeInvStore(rels)
    _incident, objs = _stix._issue_objects(store, _Issue())
    rel_objs = [o for o in objs if o["type"] == "relationship"]
    # The attack-pattern edge must be present (was silently dropped pre-fix).
    ap_id = _stix._sid("attack-pattern", "T1071.004")
    connected = [
        r for r in rel_objs
        if r["target_ref"] == ap_id and r["relationship_type"] == "uses"
    ]
    assert len(connected) == 1


def test_stix_still_drops_edge_to_absent_target():
    from usecase.builtin_components import _stix

    # An edge to a technique that has NO attack-pattern SDO in the bundle
    # must still be skipped (fail-closed: no dangling target_ref).
    rels = [{
        "source_id": "ind-1",
        "target_value": "T9999",  # not in technique mappings
        "target_type": "attack-pattern",
        "relationship_type": "uses",
    }]
    store = _FakeInvStore(rels)
    _incident, objs = _stix._issue_objects(store, _Issue())
    rel_objs = [o for o in objs if o["type"] == "relationship"]
    missing_id = _stix._sid("attack-pattern", "T9999")
    assert not any(r["target_ref"] == missing_id for r in rel_objs)


# ─────────────────────────────────────────────────────────────────
# #MEM-F7 — personality rank-knob plumbing
# ─────────────────────────────────────────────────────────────────
class _Persona:
    def __init__(self, blob):
        self.blob = blob


class _FakePersonaStore:
    def __init__(self, blob):
        self._p = _Persona(blob)

    def get_or_default(self):
        return self._p


def test_personality_rank_kwargs_translates_blob():
    import usecase.context_assembler as ca
    import usecase.personality_store as ps

    orig = ps.personality_store
    ps.personality_store = lambda: _FakePersonaStore(
        {"memoryMmrLambda": 0.4, "memoryTemporalDecayLambda": 0.05}
    )
    try:
        out = ca._personality_rank_kwargs()
        assert out == {"mmr_lambda": 0.4, "temporal_decay_lambda": 0.05}
    finally:
        ps.personality_store = orig


def test_personality_rank_kwargs_empty_when_absent():
    import usecase.context_assembler as ca
    import usecase.personality_store as ps

    orig = ps.personality_store
    ps.personality_store = lambda: _FakePersonaStore({})  # no knobs set
    try:
        assert ca._personality_rank_kwargs() == {}
    finally:
        ps.personality_store = orig


def test_personality_rank_kwargs_empty_on_no_store():
    import usecase.context_assembler as ca
    import usecase.personality_store as ps

    orig = ps.personality_store
    ps.personality_store = lambda: None
    try:
        assert ca._personality_rank_kwargs() == {}
    finally:
        ps.personality_store = orig
