"""v0.2.20 — kb_doc_tags label-filter substrate.

Arbitrary frontmatter tags (tactic, platform, product, investigation-type, …)
become a normalized, AND-filterable index so the UI can offer filter chips and
the agent/REST can scope list/search by label — not just `category`.
"""
from __future__ import annotations

from pathlib import Path

from usecase.kb_store import SqliteKnowledgeBase
from usecase.memory_store import TextHashEmbedder


def _kb(tmp_path: Path) -> SqliteKnowledgeBase:
    return SqliteKnowledgeBase(data_root=tmp_path, embedder=TextHashEmbedder(dims=64))


def _put(kb, doc_id, content, tags, *, category="attack-technique", hash_=None):
    kb.upsert(
        kb_name="k", doc_id=doc_id, content=content, category=category,
        metadata={"tags": tags, "category": category},
        source_hash=hash_ or doc_id,
    )


def test_upsert_syncs_tags_and_kb_tags_counts(tmp_path: Path) -> None:
    kb = _kb(tmp_path)
    _put(kb, "T1", "powershell execution", ["execution", "windows"])
    _put(kb, "T2", "scheduled task", ["execution", "windows", "persistence"])
    _put(kb, "T3", "linux cron", ["persistence", "linux"])

    tags = {t["tag"]: t["count"] for t in kb.kb_tags("k")}
    assert tags == {"execution": 2, "windows": 2, "persistence": 2, "linux": 1}


def test_list_docs_tags_and_filter(tmp_path: Path) -> None:
    kb = _kb(tmp_path)
    _put(kb, "T1", "a", ["execution", "windows"])
    _put(kb, "T2", "b", ["execution", "windows", "persistence"])
    _put(kb, "T3", "c", ["persistence", "linux"])

    # single tag
    ids = sorted(d.doc_id for d in kb.list_docs("k", tags=["execution"]))
    assert ids == ["T1", "T2"]
    # AND of two tags → only docs carrying BOTH
    ids = sorted(d.doc_id for d in kb.list_docs("k", tags=["execution", "persistence"]))
    assert ids == ["T2"]
    # case-insensitive
    ids = sorted(d.doc_id for d in kb.list_docs("k", tags=["LINUX"]))
    assert ids == ["T3"]
    # count_docs respects the same filter
    assert kb.count_docs("k", tags=["execution"]) == 2


def test_search_tags_filter(tmp_path: Path) -> None:
    kb = _kb(tmp_path)
    _put(kb, "T1", "credential dumping lsass", ["credential-access", "windows"])
    _put(kb, "T2", "credential dumping linux shadow", ["credential-access", "linux"])
    hits = kb.search("credential dumping", kb_name="k", tags=["windows"], limit=10)
    assert [d.doc_id for d, _ in hits] == ["T1"], "tag filter must exclude the linux doc"


def test_unchanged_path_backfills_tags(tmp_path: Path) -> None:
    """The migration case: a doc indexed before kb_doc_tags existed comes back
    as 'unchanged' (same source_hash) on reboot — its tags must still sync."""
    kb = _kb(tmp_path)
    _put(kb, "T1", "x", ["execution"], hash_="h1")
    # wipe the tag rows to simulate a pre-v0.2.20 kb.db, then re-upsert with the
    # SAME hash (→ "unchanged" path).
    with kb._conn() as c:  # noqa: SLF001
        c.execute("DELETE FROM kb_doc_tags")
    _, action = kb.upsert(
        kb_name="k", doc_id="T1", content="x", metadata={"tags": ["execution"]},
        source_hash="h1",
    )
    assert action == "unchanged"
    assert kb.count_docs("k", tags=["execution"]) == 1, "unchanged path must re-sync tags"


def test_remove_deletes_tags(tmp_path: Path) -> None:
    kb = _kb(tmp_path)
    _put(kb, "T1", "x", ["execution"])
    assert kb.kb_tags("k")
    kb.remove("k", "T1")
    assert kb.kb_tags("k") == []


def test_retag_on_content_change(tmp_path: Path) -> None:
    kb = _kb(tmp_path)
    _put(kb, "T1", "v1", ["execution"], hash_="h1")
    _put(kb, "T1", "v2 changed", ["persistence"], hash_="h2")  # new hash → update
    tags = {t["tag"] for t in kb.kb_tags("k")}
    assert tags == {"persistence"}, "stale tag must be dropped on update"


def test_search_offset_paginates(tmp_path: Path) -> None:
    kb = _kb(tmp_path)
    for i in range(5):
        _put(kb, f"T{i}", f"shared keyword doc number {i}", ["x"])
    page1 = kb.search("shared keyword", kb_name="k", limit=2, offset=0)
    page2 = kb.search("shared keyword", kb_name="k", limit=2, offset=2)
    ids1 = {d.doc_id for d, _ in page1}
    ids2 = {d.doc_id for d, _ in page2}
    assert len(ids1) == 2 and len(ids2) == 2
    assert ids1.isdisjoint(ids2), "offset must return a different page"
