"""Backfill `## When to use`, `## Variations`, `## Source` sections into the
old KB entries (1-166 range) that pre-date the v0.6.51 schema convention.

Pre-v0.6.51, the seed corpus from `xql_examples.md` only emitted a frontmatter
block + title + dataset line + SQL block. v0.6.51's operator-dataset bulk
import standardized on a richer body — `## When to use` (the intent text the
embedding model picks up), `## Variations` (curation slot), `## Source`
(provenance). The two halves of the corpus diverged: 463 new entries with
the full schema, 166 old entries without.

This tool walks the old half, parses what's there, and adds the three new
sections using the SAME heuristic generators as the importer
(`import_operator_dataset.py`). Output is identical in shape to what the
importer would produce. Idempotent — running twice is a no-op (entries
that already have `## When to use` are skipped).

Why this matters beyond aesthetics: the embedding model embeds the entire
body text. With the old entries missing the intent section, their embedding
vectors live in a different subspace than the new entries'. Similarity
search would systematically prefer new entries even when an old one is the
better match. Schema uniformity is an embedding-quality issue, not just
a stylistic one.

Run from repo root:
    python3 bundles/spark/kbs/xql-examples/_tools/backfill_old_entries.py
"""

from __future__ import annotations

import re
from pathlib import Path

# Resolve paths relative to this script so it works from any CWD.
SCRIPT_DIR = Path(__file__).resolve().parent
ENTRIES_DIR = SCRIPT_DIR.parent / "entries"


# ─── Heuristic generators (shape-matched to import_operator_dataset.py) ────


def extract_stages(query_text: str) -> list[str]:
    """Extract pipeline stage names (the bit after `|`) preserving order."""
    seen = set()
    out: list[str] = []
    for m in re.finditer(r"\|\s*(\w+)", query_text):
        stage = m.group(1)
        if stage not in seen:
            seen.add(stage)
            out.append(stage)
    return out


def detect_source_kind(query_text: str) -> str:
    """Identify whether the query opens with `preset = `, `dataset = `, or
    `datamodel ...`. Falls back to `unknown`."""
    head = query_text.lstrip()[:200]
    if re.match(r"preset\s*=", head):
        return "preset"
    if re.match(r"dataset\s*=", head):
        return "dataset"
    if re.match(r"datamodel\b", head):
        return "datamodel"
    return "unknown"


def generate_description(
    title: str, query_text: str, dataset: str, source_kind: str, stages: list[str]
) -> str:
    """Compose a 1-3 sentence intent description.

    Same shape as the importer's `generate_description` — title becomes the
    lead clause, then "queries the X preset/dataset directly" + first filter
    clause + stage signature. The text is what the embedding model sees;
    provenance disclaimers live in the Source section, NOT here.
    """
    # First filter clause for "filtered on X" context.
    first_filter = ""
    m = re.search(r"\|\s*filter\s+(.+?)(?:\n|\||$)", query_text, re.DOTALL)
    if m:
        first_filter = m.group(1).strip()
        first_filter = re.sub(r"\s+", " ", first_filter)[:140]

    if source_kind == "preset":
        lead = f"{title}. Queries the `{dataset}` preset"
    elif source_kind == "dataset":
        lead = f"{title}. Queries the `{dataset}` dataset directly"
    elif source_kind == "datamodel":
        lead = f"{title}. XDM-normalized query over `{dataset}`"
    else:
        lead = f"{title}. XQL pattern"

    if first_filter:
        lead += f", filtered on `{first_filter}`"
    lead += "."

    detail = ""
    if stages:
        detail = "Uses stages: " + ", ".join(f"`{s}`" for s in stages[:6]) + "."

    return (lead + " " + detail).strip()


# ─── Old-entry parser ─────────────────────────────────────────────────────


FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
SQL_BLOCK_RE = re.compile(r"```sql\s*\n(.*?)\n```", re.DOTALL)
DATASET_LINE_RE = re.compile(r"\*\*Dataset\*\*:\s*`([^`]+)`")
TITLE_HEADING_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


def parse_old_entry(text: str) -> dict:
    """Pull frontmatter, title, dataset, and SQL out of an old entry."""
    fm_match = FRONTMATTER_RE.match(text)
    if not fm_match:
        raise ValueError("no frontmatter")
    frontmatter = fm_match.group(0)  # full `---\n...\n---\n`
    body = text[fm_match.end() :]

    title_match = TITLE_HEADING_RE.search(body)
    title = title_match.group(1).strip() if title_match else "Untitled"

    ds_match = DATASET_LINE_RE.search(body)
    dataset = ds_match.group(1) if ds_match else ""

    sql_match = SQL_BLOCK_RE.search(body)
    query_text = sql_match.group(1).strip() if sql_match else ""

    return {
        "frontmatter": frontmatter,
        "title": title,
        "dataset": dataset,
        "query_text": query_text,
    }


# ─── Renderer ─────────────────────────────────────────────────────────────


SOURCE_LINE = (
    "Backfilled from the pre-v0.6.51 KB seed corpus (`bundles/spark/kbs/"
    "xql-examples/seed/xql_examples.md`). The `When to use` description "
    "above was auto-generated by the backfill heuristic — operator-"
    "curation pass pending. The query body is the authoritative version "
    "regardless of description quality. Schema-uniformity backfill landed "
    "in v0.6.52."
)


def render_backfilled(parsed: dict) -> str:
    """Build the new entry body, preserving the original frontmatter +
    title + dataset line + SQL block."""
    title = parsed["title"]
    dataset = parsed["dataset"] or "(none)"
    query_text = parsed["query_text"]

    stages = extract_stages(query_text)
    source_kind = detect_source_kind(query_text)
    description = generate_description(title, query_text, dataset, source_kind, stages)

    body_lines = [
        "",
        f"# {title}",
        "",
        f"**Dataset**: `{dataset}`",
        "",
        "```sql",
        query_text,
        "```",
        "",
        "## When to use",
        "",
        description,
        "",
        "## Variations",
        "",
        "_(Backfilled — variations not yet authored. The operator's curation pass adds these.)_",
        "",
        "## Source",
        "",
        SOURCE_LINE,
        "",
    ]
    return parsed["frontmatter"] + "\n".join(body_lines)


# ─── Main ─────────────────────────────────────────────────────────────────


def main() -> None:
    files = sorted(ENTRIES_DIR.glob("*.md"))
    stats = {"total": len(files), "backfilled": 0, "skipped_already_ok": 0, "skipped_unparseable": 0}

    for f in files:
        text = f.read_text(encoding="utf-8")

        # Idempotent: skip entries that already have the new schema.
        if "## When to use" in text:
            stats["skipped_already_ok"] += 1
            continue

        try:
            parsed = parse_old_entry(text)
        except ValueError:
            stats["skipped_unparseable"] += 1
            print(f"WARN: unparseable, skipping: {f.name}")
            continue

        new_text = render_backfilled(parsed)
        f.write_text(new_text, encoding="utf-8")
        stats["backfilled"] += 1

    print("\nBackfill complete:")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
