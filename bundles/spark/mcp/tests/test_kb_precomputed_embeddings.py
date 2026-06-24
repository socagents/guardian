"""v0.2.17 keystone — pre-computed embeddings shipped in a KB bundle.

The expansion arc (full ATT&CK Enterprise ~691 docs, ATLAS, SOAR playbooks)
makes boot-time embedding prohibitive: one Vertex round-trip per doc, ~16 min
on a fresh-volume install. These tests pin the contract that lets a bundle ship
the vector baked in and skip the Vertex call — but ONLY when it's trustworthy.
"""
from __future__ import annotations

import base64
import importlib.util
import json
import struct
from pathlib import Path

from usecase.kb_loader import (
    _extract_precomputed_embedding,
    load_bundled_knowledge,
)
from usecase.kb_store import SqliteKnowledgeBase
from usecase.memory_store import TextHashEmbedder


class SpyEmbedder:
    """Embedder that counts embed() calls so a test can prove a baked vector
    was used (calls == 0) vs a live embed (calls >= 1)."""

    def __init__(self, dims: int = 768, model_id: str = "text-embedding-004") -> None:
        self.dims = dims
        self.model_id = model_id
        self.calls = 0

    def embed(self, text: str) -> list[float]:
        self.calls += 1
        vec = [0.0] * self.dims
        vec[len(text) % self.dims] = 1.0
        return vec


def _b64(vec: list[float]) -> str:
    return base64.b64encode(struct.pack(f"<{len(vec)}f", *vec)).decode("ascii")


def _read_embedding(kb: SqliteKnowledgeBase, kb_name: str, doc_id: str, dims: int) -> list[float]:
    with kb._conn() as c:  # noqa: SLF001 — test reaches into storage on purpose
        row = c.execute(
            "SELECT embedding FROM kb_documents WHERE kb_name = ? AND doc_id = ?",
            (kb_name, doc_id),
        ).fetchone()
    return list(struct.unpack(f"{dims}f", row["embedding"]))


# ── kb_store.upsert trust logic ──────────────────────────────────────────


def test_upsert_uses_precomputed_when_model_and_dims_match(tmp_path: Path) -> None:
    spy = SpyEmbedder(dims=4, model_id="m1")
    kb = SqliteKnowledgeBase(data_root=tmp_path, embedder=spy)
    pre = [0.1, 0.2, 0.3, 0.4]

    kb.upsert(
        kb_name="k", doc_id="d1", content="hello", source_hash="h1",
        precomputed_embedding=pre, precomputed_model="m1",
    )

    assert spy.calls == 0, "a trusted pre-computed vector must skip embed()"
    stored = _read_embedding(kb, "k", "d1", 4)
    assert all(abs(a - b) < 1e-6 for a, b in zip(stored, pre)), stored


def test_upsert_falls_back_on_model_mismatch(tmp_path: Path) -> None:
    spy = SpyEmbedder(dims=4, model_id="m1")
    kb = SqliteKnowledgeBase(data_root=tmp_path, embedder=spy)
    kb.upsert(
        kb_name="k", doc_id="d1", content="hello", source_hash="h1",
        precomputed_embedding=[0.1, 0.2, 0.3, 0.4], precomputed_model="OTHER-MODEL",
    )
    assert spy.calls == 1, "wrong model must NOT be trusted — re-embed live"


def test_upsert_falls_back_on_dims_mismatch(tmp_path: Path) -> None:
    spy = SpyEmbedder(dims=4, model_id="m1")
    kb = SqliteKnowledgeBase(data_root=tmp_path, embedder=spy)
    kb.upsert(
        kb_name="k", doc_id="d1", content="hello", source_hash="h1",
        precomputed_embedding=[0.1, 0.2], precomputed_model="m1",  # 2 dims, expected 4
    )
    assert spy.calls == 1, "wrong dims must NOT be trusted — re-embed live"


def test_upsert_embeds_when_no_precomputed(tmp_path: Path) -> None:
    spy = SpyEmbedder(dims=4, model_id="m1")
    kb = SqliteKnowledgeBase(data_root=tmp_path, embedder=spy)
    kb.upsert(kb_name="k", doc_id="d1", content="hello", source_hash="h1")
    assert spy.calls == 1, "no pre-computed vector → embed-on-boot (unchanged behavior)"


# ── loader decode ────────────────────────────────────────────────────────


def test_extract_precomputed_embedding_roundtrip() -> None:
    vec = [0.5, -0.25, 1.0]
    meta = {"id": "d1", "embedding": _b64(vec), "embedding_model": "text-embedding-004"}
    out, model = _extract_precomputed_embedding(meta)
    assert model == "text-embedding-004"
    assert out is not None and all(abs(a - b) < 1e-6 for a, b in zip(out, vec))
    # fields are POPPED so the base64 blob never lands in metadata_json
    assert "embedding" not in meta and "embedding_model" not in meta


def test_extract_precomputed_embedding_malformed_is_none() -> None:
    out, model = _extract_precomputed_embedding({"embedding": "!!!not-base64!!!"})
    assert out is None and model is None


def _write_kb(tmp_path: Path, content: str, baked_model: str | None) -> Path:
    """Create a one-doc KB dir; bake an embedding when baked_model is given."""
    kbdir = tmp_path / "mykb" / "entries"
    kbdir.mkdir(parents=True)
    fm = ["---", "id: d1", "title: Test Doc", "category: ref"]
    if baked_model is not None:
        vec = TextHashEmbedder(dims=768).embed(content)
        fm += [f"embedding_model: {baked_model}", f"embedding: {_b64(vec)}"]
    fm += ["---", "", content, ""]
    (kbdir / "d1.md").write_text("\n".join(fm), "utf-8")
    (tmp_path / "mykb" / "schema.json").write_text(json.dumps({
        "type": "object", "required": ["id", "title", "category"],
        "additionalProperties": True,
    }))
    return tmp_path


def test_loader_uses_baked_embedding_with_zero_vertex_calls(tmp_path: Path) -> None:
    stub_model = TextHashEmbedder(dims=768).model_id
    bundle_root = _write_kb(tmp_path, "dns tunneling exfiltration over c2", baked_model=stub_model)
    spy = SpyEmbedder(dims=768, model_id=stub_model)
    kb = SqliteKnowledgeBase(data_root=tmp_path / "db", embedder=spy)

    counts = load_bundled_knowledge(
        kb=kb, bundle_root=bundle_root,
        bundled=[{"name": "mykb", "path": "./mykb/", "schema": "./mykb/schema.json"}],
    )
    assert counts["mykb"]["insert"] == 1
    assert spy.calls == 0, "a fully-baked KB must boot with ZERO embed() calls"
    # the baked doc is real + searchable
    hits = kb.search("dns tunneling", kb_name="mykb", limit=1)
    assert hits and hits[0][0].doc_id == "d1"


def test_loader_embeds_when_no_baked_embedding(tmp_path: Path) -> None:
    bundle_root = _write_kb(tmp_path, "plain doc, no baked vector", baked_model=None)
    spy = SpyEmbedder(dims=768, model_id="text-embedding-004")
    kb = SqliteKnowledgeBase(data_root=tmp_path / "db", embedder=spy)
    load_bundled_knowledge(
        kb=kb, bundle_root=bundle_root,
        bundled=[{"name": "mykb", "path": "./mykb/", "schema": "./mykb/schema.json"}],
    )
    assert spy.calls == 1, "unbaked doc → embed-on-boot (back-compat preserved)"


# ── kb_embed authoring tool round-trip ───────────────────────────────────


def _load_kb_embed_tool():
    tool_path = (
        Path(__file__).resolve().parents[2] / "kbs" / "_tools" / "kb_embed.py"
    )
    spec = importlib.util.spec_from_file_location("kb_embed", tool_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_kb_embed_author_then_load_zero_calls(tmp_path: Path) -> None:
    """Full author→load round-trip: bake a KB with the tool, then prove it
    boots with zero embed() calls."""
    kb_embed = _load_kb_embed_tool()
    kbdir = tmp_path / "gen" / "entries"
    kbdir.mkdir(parents=True)
    content = "kerberoasting service account ticket request"
    (kbdir / "d1.md").write_text(
        f"---\nid: d1\ntitle: Gen Doc\ncategory: ref\n---\n\n{content}\n", "utf-8"
    )
    (tmp_path / "gen" / "schema.json").write_text(json.dumps({
        "type": "object", "required": ["id", "title", "category"],
        "additionalProperties": True,
    }))

    # Author: bake the embedding with the deterministic stub embedder.
    author_embedder = TextHashEmbedder(dims=768)
    action = kb_embed._embed_markdown(kbdir / "d1.md", author_embedder, force=False)
    assert action == "embedded"
    assert "embedding_model:" in (kbdir / "d1.md").read_text()

    # Load: a runtime embedder with the SAME model id must make zero calls.
    spy = SpyEmbedder(dims=768, model_id=author_embedder.model_id)
    kb = SqliteKnowledgeBase(data_root=tmp_path / "db", embedder=spy)
    counts = load_bundled_knowledge(
        kb=kb, bundle_root=tmp_path,
        bundled=[{"name": "gen", "path": "./gen/", "schema": "./gen/schema.json"}],
    )
    assert counts["gen"]["insert"] == 1
    assert spy.calls == 0


# ── #KB-F10 — embedding-model drift is observable ─────────────────────────


def test_embed_mismatch_increments_counter_and_audits_once(tmp_path: Path) -> None:
    """A baked-model/runtime-model mismatch forces a live re-embed on EVERY
    doc and EVERY boot (recurring Vertex cost). KB-F10 makes that drift
    observable: a cumulative counter (per re-embed) + ONE audit row per
    process (guarded — a per-doc row would flood audit.db with ~700 lines)."""
    from usecase.metrics_registry import MetricsRegistry, metrics_registry, set_metrics_registry
    from usecase import audit_log as audit_mod

    captured: list[tuple[str, dict]] = []

    class _Audit:
        def record(self, action, **kw):
            captured.append((action, kw))

    prev_reg = metrics_registry()
    prev_audit = audit_mod._audit  # noqa: SLF001 — test swaps the singleton
    set_metrics_registry(MetricsRegistry())
    audit_mod.set_audit_log(_Audit())
    try:
        spy = SpyEmbedder(dims=4, model_id="m1")
        kb = SqliteKnowledgeBase(data_root=tmp_path, embedder=spy)
        # Two docs whose baked vectors declare the WRONG model → both re-embed.
        for doc_id in ("d1", "d2"):
            kb.upsert(
                kb_name="k", doc_id=doc_id, content=f"body {doc_id}", source_hash=doc_id,
                precomputed_embedding=[0.1, 0.2, 0.3, 0.4], precomputed_model="OTHER-MODEL",
            )
        assert spy.calls == 2, "both wrong-model vectors must re-embed live"

        counter = metrics_registry().get("guardian_kb_embed_mismatch_total")
        assert counter is not None
        # No labels → the counter's value lives under the empty-tuple key.
        assert counter._values.get((), 0.0) == 2.0  # noqa: SLF001

        rows = [kw for action, kw in captured if action == "kb_embed_mismatch"]
        assert len(rows) == 1, "audit row must fire ONCE per process, not per doc"
        assert rows[0]["metadata"]["doc_model"] == "OTHER-MODEL"
        assert rows[0]["metadata"]["runtime_model"] == "m1"
    finally:
        set_metrics_registry(prev_reg)
        audit_mod.set_audit_log(prev_audit)
