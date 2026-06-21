from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import pytest
from usecase.builtin_components import cognitive_tools as ct


@dataclass(frozen=True)
class _Doc:
    doc_id: str
    title: str | None
    category: str | None
    content: str
    metadata: dict[str, Any]


class _FakeKB:
    def __init__(self, hits):
        self._hits = hits

    def search(self, query, *, kb_name=None, category=None, tags=None, limit=5, **kw):
        assert kb_name == "xql-examples"
        return self._hits[:limit]


def _wire(monkeypatch, kb):
    import usecase.kb_store as kb_store
    monkeypatch.setattr(kb_store, "_kb", kb, raising=False)
    monkeypatch.setattr(kb_store, "knowledge_base", lambda: kb)


def test_empty_intent_errors(monkeypatch):
    _wire(monkeypatch, _FakeKB([]))
    out = ct.xql_examples_search("")
    assert out["status"] == "error"


def test_kb_uninitialised_errors(monkeypatch):
    import usecase.kb_store as kb_store
    monkeypatch.setattr(kb_store, "knowledge_base", lambda: None)
    out = ct.xql_examples_search("find logins")
    assert out["status"] == "error"


def test_returns_matches_and_enrichment(monkeypatch):
    doc = _Doc(
        doc_id="XQL-001", title="Login spike", category="investigation",
        content='dataset = xdr_data\n| filter event_type = "Login"\n| comp count() by user',
        metadata={"dataset": "xdr_data"},
    )
    _wire(monkeypatch, _FakeKB([(doc, 0.91)]))
    out = ct.xql_examples_search("brute force logins", top_k=5)
    assert out["status"] == "ok"
    assert out["count"] == 1
    m = out["matches"][0]
    assert m["id"] == "XQL-001" and m["dataset"] == "xdr_data" and m["category"] == "investigation"
    assert m["score"] == pytest.approx(0.91)
    assert isinstance(out["stage_docs"], list) and isinstance(out["dataset_fields"], list)
