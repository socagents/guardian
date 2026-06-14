"""v0.2.23 — passive per-turn KB injection stays in-ecosystem.

At 6-KB scale the specialist matrices (ICS/Mobile/ATLAS) leaked into IT
investigations' passive context — an IT ransomware turn pulled an ICS technique
above the correct Enterprise one (measured). The ContextAssembler now drops
specialist-ecosystem docs from the PASSIVE injection; they stay reachable via
the agent's ACTIVE knowledge_search.
"""
from __future__ import annotations

from pathlib import Path

from usecase.context_assembler import ContextAssembler
from usecase.kb_store import SqliteKnowledgeBase, set_knowledge_base
from usecase.memory_store import TextHashEmbedder


def _seed(tmp_path: Path) -> SqliteKnowledgeBase:
    kb = SqliteKnowledgeBase(data_root=tmp_path, embedder=TextHashEmbedder(dims=128))
    # three docs that all match the query; differ only by ecosystem
    kb.upsert(kb_name="ent", doc_id="T1486", content="ransomware encrypts files for impact on the host",
              metadata={"ecosystem": "IT"}, source_hash="a")
    kb.upsert(kb_name="ics", doc_id="T0809", content="ransomware encrypts files for impact in the ICS OT environment",
              metadata={"ecosystem": "OT"}, source_hash="b")
    kb.upsert(kb_name="atlas", doc_id="AML.T0031", content="ransomware encrypts files impacting an AI model pipeline",
              metadata={"ecosystem": "AI"}, source_hash="c")
    kb.upsert(kb_name="guides", doc_id="pb-ransomware", content="how to investigate when ransomware encrypts files",
              metadata={}, source_hash="d")  # no ecosystem → always kept
    return kb


def test_passive_injection_excludes_specialist_ecosystems(tmp_path: Path) -> None:
    set_knowledge_base(_seed(tmp_path))
    try:
        asm = ContextAssembler(strategy="kb_only", kb_k=3)
        ctx = asm.assemble(query="ransomware encrypts files")
        got = {(r["kb_name"], r["doc_id"]) for r in ctx.knowledge}
        assert ("ics", "T0809") not in got, f"OT doc leaked into passive context: {got}"
        assert ("atlas", "AML.T0031") not in got, f"AI doc leaked: {got}"
        assert ("ent", "T1486") in got, f"IT doc missing: {got}"
        assert ("guides", "pb-ransomware") in got, f"no-ecosystem doc missing: {got}"
    finally:
        set_knowledge_base(None)


def test_passive_exclusion_is_configurable(tmp_path: Path) -> None:
    """An OT-focused deployment can re-enable specialist KBs by passing an
    empty exclude set."""
    set_knowledge_base(_seed(tmp_path))
    try:
        asm = ContextAssembler(strategy="kb_only", kb_k=4, kb_passive_exclude_ecosystems=())
        ctx = asm.assemble(query="ransomware encrypts files")
        got = {(r["kb_name"], r["doc_id"]) for r in ctx.knowledge}
        assert ("ics", "T0809") in got, f"empty exclude set should keep OT: {got}"
    finally:
        set_knowledge_base(None)
