"""#MEM-F6 — the /memory Advanced sliders (mmr_lambda / temporal_decay_lambda)
must actually affect ranking.

The store's search() implements temporal decay + MMR; the bug was the REST
route dropping the two params so the sliders had zero effect (fixed in
api/cognitive.py:search_memories). This pins the store-level contract the
route now exposes: a higher temporal_decay_lambda demotes older memories.
Two rows with identical text (→ identical embedding, identical cosine to any
query) differ only by age, so decay alone decides the order.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from usecase.memory_store import SqliteMemoryStore  # noqa: E402


def _backdate(db_path: Path, key: str, iso: str) -> None:
    with sqlite3.connect(db_path) as c:
        c.execute("UPDATE memories SET updated_at = ? WHERE key = ?", (iso, key))
        c.commit()


def test_temporal_decay_lambda_changes_ranking(tmp_path):
    store = SqliteMemoryStore(data_root=tmp_path)
    # Identical value text → identical embedding → identical cosine.
    store.store(key="old_fact", value="phishing campaign indicators", scope="agent")
    store.store(key="new_fact", value="phishing campaign indicators", scope="agent")
    # Backdate the "old" row ~200 days; leave "new" at now.
    _backdate(store.db_path, "old_fact", "2025-12-01T00:00:00+00:00")

    # No decay → both score equally (tie); the param is inert here.
    flat = store.search("phishing campaign indicators", limit=2, temporal_decay_lambda=0.0)
    flat_scores = {m.key: s for m, s in flat}
    assert set(flat_scores) == {"old_fact", "new_fact"}
    assert abs(flat_scores["old_fact"] - flat_scores["new_fact"]) < 1e-9

    # Strong decay → the old row is demoted; the recent one ranks first
    # and outscores it. Proves temporal_decay_lambda has real effect.
    decayed = store.search(
        "phishing campaign indicators", limit=2, temporal_decay_lambda=0.5
    )
    assert decayed[0][0].key == "new_fact"
    decayed_scores = {m.key: s for m, s in decayed}
    assert decayed_scores["new_fact"] > decayed_scores["old_fact"]


def test_mmr_lambda_accepted_and_bounds_results(tmp_path):
    # Lighter guard: mmr_lambda flows through and the result count is
    # bounded by limit regardless of the diversity weight.
    store = SqliteMemoryStore(data_root=tmp_path)
    for i in range(5):
        store.store(key=f"k{i}", value=f"lateral movement note {i}", scope="agent")
    relevance_heavy = store.search("lateral movement", limit=3, mmr_lambda=1.0)
    diversity_heavy = store.search("lateral movement", limit=3, mmr_lambda=0.0)
    assert len(relevance_heavy) <= 3
    assert len(diversity_heavy) <= 3
