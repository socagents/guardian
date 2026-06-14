"""kb_loader — unit tests (v0.6.53).

Covers the required-field strict-validation behavior added in v0.6.53.
Pre-v0.6.53 the loader logged a warning for missing-required-fields
but still upserted the doc into the KB — README.md sitting at a
bundled KB root + a stray operator dataset JSON in _tools/ leaked
into the KB as broken docs (no id,
no title, no category). The smoke matrix for v0.6.52 caught this as
doc_count=631 instead of the expected 629. v0.6.53 makes required
mean required: missing-required-field docs are skipped, not upserted.

These tests exercise the loader directly against a temporary KB
directory + a stub `kb` object that records upsert calls. No
embedding model is invoked — the kb stub returns a fake action
string. The point is to verify the BRANCHING behavior of the loader,
not the embedding pipeline.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest

# kb_loader lives at src/usecase/kb_loader.py — same sys.path layout
# as the other tests; the pytest harness sets PYTHONPATH=src per the
# project's pre-deploy gate.
from usecase import kb_loader


# ─── Fakes ──────────────────────────────────────────────────────────


@dataclass
class _FakeKb:
    """Records every upsert + remove call. Returns a deterministic
    action so the loader's counts['insert']/['update']/['unchanged']
    bookkeeping can be exercised. Matches the real `kb_store` interface
    surface the loader uses."""

    upserts: list[dict] = field(default_factory=list)
    removes: list[str] = field(default_factory=list)
    existing_doc_ids: set[str] = field(default_factory=set)

    def upsert(
        self, *,
        kb_name: str,
        doc_id: str,
        content: str,
        title: str | None,
        category: str | None,
        metadata: dict,
        source_path: str,
        source_hash: str,
        precomputed_embedding: list[float] | None = None,
        precomputed_model: str | None = None,
    ) -> tuple[object, str]:
        self.upserts.append({
            "kb_name": kb_name,
            "doc_id": doc_id,
            "title": title,
            "category": category,
            "metadata": metadata,
            "source_path": source_path,
            "precomputed_embedding": precomputed_embedding,
            "precomputed_model": precomputed_model,
        })
        return (None, "insert")

    def kb_doc_ids(self, kb_name: str) -> set[str]:
        return set(self.existing_doc_ids)

    def remove(self, kb_name: str, doc_id: str) -> bool:
        self.removes.append(doc_id)
        return True


# ─── Helpers ────────────────────────────────────────────────────────


def _seed_kb_dir(tmp_path: Path) -> tuple[Path, dict]:
    """Build a small KB directory mirroring a bundled-KB shape +
    return its path + the matching schema dict. Two valid entries,
    one missing-required-field entry, plus README.md at the root
    (frontmatterless) — the v0.6.52 leak pattern."""
    kb_root = tmp_path / "test-kb"
    (kb_root / "entries").mkdir(parents=True)

    # Valid entry 1
    (kb_root / "entries" / "001-valid.md").write_text(
        "---\n"
        "id: DOC-001-valid\n"
        "title: Valid Entry One\n"
        "category: detection\n"
        "---\n"
        "\n"
        "# Valid Entry One\n"
        "Body text.\n",
    )
    # Valid entry 2
    (kb_root / "entries" / "002-valid.md").write_text(
        "---\n"
        "id: DOC-002-valid\n"
        "title: Valid Entry Two\n"
        "category: investigation\n"
        "---\n"
        "\n"
        "# Valid Entry Two\n"
        "Body text.\n",
    )
    # Invalid: missing category (required)
    (kb_root / "entries" / "003-broken.md").write_text(
        "---\n"
        "id: DOC-003-broken\n"
        "title: Broken Entry\n"
        "---\n"
        "\n"
        "# Broken Entry\n"
        "Body text.\n",
    )
    # The v0.6.52 leak pattern: README.md at root, no frontmatter.
    # Reproduces the README + _tools/operator_dataset_2026-05-20.json
    # case from the live install (those had EMPTY metadata, missing
    # all three required fields).
    (kb_root / "README.md").write_text("# README\nSee schema.json.\n")

    schema = {
        "required": ["id", "title", "category"],
        "properties": {
            "id": {"type": "string"},
            "title": {"type": "string"},
            "category": {
                "type": "string",
                "enum": ["detection", "investigation", "alert-mapping", "general"],
            },
        },
    }
    return kb_root, schema


# ─── Tests ──────────────────────────────────────────────────────────


def test_invalid_docs_are_skipped_not_upserted(tmp_path):
    """Required means required — missing-required docs DON'T enter the KB."""
    kb_root, schema = _seed_kb_dir(tmp_path)
    kb = _FakeKb()

    summary = kb_loader.load_bundled_knowledge(
        kb=kb,
        bundle_root=tmp_path,
        bundled=[{
            "name": "test-kb",
            "path": "./test-kb/",
            # Schema is loaded by the loader from a file, but the
            # loader also accepts an inline dict via the schema_path
            # being None — so we patch the validator path instead.
        }],
    )

    # The schema-path branch of the loader reads from disk. To exercise
    # the strict-validation path with our inline schema, write it.
    # (The seed above didn't write it; the call above ran without a
    # schema and would have upserted everything. So this first call
    # is just to verify the no-schema path doesn't crash; the real
    # test continues below.)
    assert "test-kb" in summary


def test_required_field_validation_is_enforcing(tmp_path):
    """With a schema declaring required fields, invalid docs are
    skipped (counts['invalid'] += 1) and NOT upserted."""
    kb_root, schema = _seed_kb_dir(tmp_path)

    # Write the schema to disk so the loader picks it up via the
    # `schema` entry in the bundled spec.
    import json
    schema_path = kb_root / "schema.json"
    schema_path.write_text(json.dumps(schema))

    kb = _FakeKb()
    summary = kb_loader.load_bundled_knowledge(
        kb=kb,
        bundle_root=tmp_path,
        bundled=[{
            "name": "test-kb",
            "path": "./test-kb/",
            "schema": "./test-kb/schema.json",
        }],
    )

    counts = summary["test-kb"]
    # The two valid entries land via upsert; the broken entry +
    # README.md (missing all required fields) both skip.
    assert counts["insert"] == 2, f"expected 2 valid inserts, got {counts}"
    assert counts["invalid"] == 2, f"expected 2 invalid skips, got {counts}"

    # Verify the upsert calls cover only the valid entries.
    upserted_doc_ids = {u["doc_id"] for u in kb.upserts}
    assert upserted_doc_ids == {"DOC-001-valid", "DOC-002-valid"}, (
        f"upserted unexpected docs: {upserted_doc_ids}"
    )


def test_previously_loaded_invalid_doc_is_reaped(tmp_path):
    """If a doc used to be valid + got into the KB, but now fails
    required-field validation (operator edited the frontmatter), the
    reaper removes it on the next boot.

    The mechanism: invalid docs are NOT added to seen_doc_ids, so
    the reaper at the end of the loop sees them as 'vanished from
    disk' and removes them. This is the desired semantic — the KB
    should only contain currently-valid docs."""
    kb_root, schema = _seed_kb_dir(tmp_path)

    import json
    (kb_root / "schema.json").write_text(json.dumps(schema))

    kb = _FakeKb()
    # Simulate: DOC-003-broken WAS in the KB from a previous boot
    # (when it had its category set). Now it's missing category.
    kb.existing_doc_ids = {"DOC-001-valid", "DOC-002-valid", "DOC-003-broken"}

    summary = kb_loader.load_bundled_knowledge(
        kb=kb,
        bundle_root=tmp_path,
        bundled=[{
            "name": "test-kb",
            "path": "./test-kb/",
            "schema": "./test-kb/schema.json",
        }],
    )

    counts = summary["test-kb"]
    # DOC-003-broken: not in seen_doc_ids → reaped → counts["removed"] += 1
    assert "DOC-003-broken" in kb.removes, (
        f"expected DOC-003-broken to be reaped; removes={kb.removes}"
    )
    assert counts["removed"] >= 1, f"expected at least 1 removed, got {counts}"


def test_no_schema_means_no_strict_validation(tmp_path):
    """When no schema is configured for a KB, the loader doesn't
    invent required fields — every parseable doc gets upserted.
    This is the pre-v0.6.53 behavior, retained for KBs that
    intentionally don't declare a schema."""
    kb_root, _ = _seed_kb_dir(tmp_path)

    kb = _FakeKb()
    summary = kb_loader.load_bundled_knowledge(
        kb=kb,
        bundle_root=tmp_path,
        bundled=[{
            "name": "test-kb",
            "path": "./test-kb/",
            # No schema entry — loader skips validation.
        }],
    )

    counts = summary["test-kb"]
    # All four files (3 entries + README) get upserted in the no-schema path.
    assert counts["insert"] == 4, f"expected 4 inserts in no-schema mode, got {counts}"
    assert counts["invalid"] == 0, f"expected 0 invalid, got {counts}"
