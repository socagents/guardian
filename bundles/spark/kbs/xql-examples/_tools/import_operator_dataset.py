#!/usr/bin/env python3
"""Convert the operator's XQL queries export (~/Downloads/xql queries.rtf,
converted via textutil to /tmp/xql-work/queries.txt as JSON) into the
existing knowledge-base markdown schema at
bundles/spark/kbs/xql-examples/entries/.

The operator flagged these fields as irrelevant + to drop:
  created_by, created_by_pretty, created_at,
  modified_at, modified_by, modified_by_pretty,
  content_global_id, RELATIONS, error, is_private, labels

The operator's request for descriptions: the existing KB embeds
the entry's title + body via text-embedding-004; the "When to use"
prose section is what gives natural-language retrieval signal. We
generate a heuristic description per entry (intent inferred from
title + dataset + first filter clause). Descriptions are marked
as auto-generated in the Source line so a future curation pass
can replace them.

Idempotent: re-running produces identical output (same ids, same
content) so we can iterate the description heuristic without
churning the working tree unnecessarily.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

# ─── Inputs ────────────────────────────────────────────────────
# Resolve paths relative to this script's location so re-runs work
# regardless of cwd / CI / operator workstation.
HERE = Path(__file__).resolve().parent
SOURCE_JSON = HERE / "operator_dataset_2026-05-20.json"
OUTPUT_DIR = HERE.parent / "entries"
START_ID = 167  # next available after existing 166

# Existing KB entries — to skip duplicate names if any overlap
EXISTING_TITLES: set[str] = set()
for f in OUTPUT_DIR.iterdir():
    if not f.name.endswith(".md"):
        continue
    head = f.read_text(encoding="utf-8").splitlines()[:25]
    for line in head:
        if line.startswith("title:"):
            EXISTING_TITLES.add(line.split(":", 1)[1].strip())
            break

# ─── Helpers ───────────────────────────────────────────────────


def slugify(text: str, max_len: int = 60) -> str:
    """Filename-safe slug. Lowercase, hyphens, no leading/trailing dashes."""
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return s[:max_len].rstrip("-") or "entry"


def short_hash(text: str, n: int = 8) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:n]


# XQL stages we'll extract for the `tags` field. Pulled from query_text.
KNOWN_STAGES = {
    "filter", "alter", "comp", "fields", "sort", "limit", "dedup",
    "join", "transaction", "bin", "union", "stats", "iploc",
    "config", "arrayexpand", "windowcomp", "view", "datamodel",
    "preset",
}


def extract_stages(query_text: str) -> list[str]:
    """Pull pipeline stages from the query text. We look for tokens that
    appear AFTER a pipe `|` (or at the start) and match one of
    KNOWN_STAGES. Returns insertion-ordered unique stages."""
    stages: list[str] = []
    seen: set[str] = set()
    # Split on pipe; first segment may have `dataset =` / `preset =` / `datamodel ...`.
    for segment in query_text.split("|"):
        token_match = re.match(r"\s*([a-z_]+)\b", segment, re.IGNORECASE)
        if not token_match:
            continue
        token = token_match.group(1).lower()
        if token in KNOWN_STAGES and token not in seen:
            stages.append(token)
            seen.add(token)
    return stages


def extract_dataset(query_text: str, query_metadata: dict) -> tuple[str, str]:
    """Returns (dataset_name, source_kind) where source_kind is one of
    'preset' | 'dataset' | 'datamodel' | 'unknown'."""
    # 1) Look at query_metadata first (the operator's RTF carries this).
    presets = query_metadata.get("query_presets") or []
    if presets:
        return presets[0], "preset"
    if query_metadata.get("is_datamodel"):
        m = re.search(r"datamodel\s+dataset\s*=\s*([a-zA-Z0-9_]+)", query_text)
        if m:
            return m.group(1), "datamodel"
    # 2) Parse from the query text.
    m = re.search(r"^\s*dataset\s*=\s*([a-zA-Z0-9_]+)", query_text, re.MULTILINE)
    if m:
        return m.group(1), "dataset"
    m = re.search(r"^\s*preset\s*=\s*([a-zA-Z0-9_]+)", query_text, re.MULTILINE)
    if m:
        return m.group(1), "preset"
    m = re.search(r"^\s*config\b", query_text, re.MULTILINE)
    if m:
        # Some queries start with `config case_sensitive = false` then dataset.
        m2 = re.search(r"dataset\s*=\s*([a-zA-Z0-9_]+)", query_text)
        if m2:
            return m2.group(1), "dataset"
    return "", "unknown"


def categorize(name: str, query_text: str) -> str:
    """Map the operator's queries to one of {alert-mapping, detection,
    investigation, general}."""
    n = name.lower()
    # The operator uses `QR -` (quick response) and `QE -` (quick examine)
    # prefixes for hunting / detection examples.
    if n.startswith("qr -") or n.startswith("qr-") or "ransomware" in n:
        return "detection"
    if n.startswith("qe -") or n.startswith("qe-"):
        return "investigation"
    if "alert" in n and ("automatically generated" in n or "mapping" in n):
        return "alert-mapping"
    if any(k in n for k in ("hunt", "tracking", "monitor", "anomaly", "abnormal")):
        return "detection"
    if any(k in n for k in ("metric", "summary", "trend", "stats", "ingest")):
        return "general"
    # Default — these tend to be operator-authored investigation patterns.
    return "investigation"


def humanize_title(name: str) -> str:
    """Convert snake_case / kebab-case slugs to a more human-readable title.
    Keep camelCase + already-spaced names as-is."""
    if "_" in name and " " not in name:
        # snake_case → Title Case
        parts = name.split("_")
        return " ".join(p[:1].upper() + p[1:] for p in parts if p)
    return name


def extract_inline_metadata(query_text: str) -> dict[str, str]:
    """Extract operator-authored metadata from SQL comments.

    Many `QR -` queries follow a template:
        //Title: Procdump interacting with LSASS
        //Tags: EDR,Windows,HighFi,IRKO
        //Description: Query looks for instances of Procdump interacting with lsass.exe
        //Author: John Percival
        //Filters: Filtering for procdump execution with command lines that contain lsass

    Operator-written descriptions are MUCH higher quality than my
    heuristic ones — they describe analyst intent, not query mechanics.
    When present, prefer them as the entry's `When to use` body.

    Returns a dict with lowercase keys. Only keys present in the text
    appear in the output.
    """
    out: dict[str, str] = {}
    # Match `//Key: value`  OR `// Key: value` followed by everything to
    # the next newline. Case-insensitive keys.
    pattern = re.compile(
        r"^\s*//\s*([A-Za-z][A-Za-z _-]*?)\s*:\s*(.+?)\s*$", re.MULTILINE,
    )
    for m in pattern.finditer(query_text):
        key = m.group(1).strip().lower().replace(" ", "_").replace("-", "_")
        value = m.group(2).strip()
        if value and key not in out:
            out[key] = value
    return out


def generate_description(
    name: str, query_text: str, dataset: str, source_kind: str, stages: list[str]
) -> str:
    """Compose a 1-3 sentence intent description.

    Heuristic-based — this is the FIRST tier of the description. The
    operator's eventual review pass will rewrite individual entries
    with richer context (matching the operator-authored entries
    like XQL-166).

    The description's role: it's combined with `title` in the
    embedding's searchable content. So the description should be
    natural-language SOC-analyst phrasing — "find X" / "show Y" /
    "detect Z" — not implementation mechanics. Stages + filter
    clauses get appended as supporting detail; the LEAD sentence
    is the intent.

    Auto-import disclaimer is intentionally NOT in this string —
    it lives in the Source section so it doesn't pollute the
    embedding vector. Embedding signal stays clean; provenance
    stays in metadata.
    """
    # Pretty name: drop QR-/QE- prefixes + replace underscores so
    # the description reads naturally.
    bare = re.sub(r"^(QR|QE|QH)\s*-\s*", "", name).strip()
    bare_natural = bare.replace("_", " ")

    # First filter clause for "filtered on X" context.
    first_filter = ""
    m = re.search(r"\|\s*filter\s+(.+?)(?:\n|\||$)", query_text, re.DOTALL)
    if m:
        first_filter = m.group(1).strip()
        first_filter = re.sub(r"\s+", " ", first_filter)[:140]

    # Lead sentence — describe intent.
    if source_kind == "preset":
        lead = f"{bare_natural}. Queries the `{dataset}` preset"
    elif source_kind == "dataset":
        lead = f"{bare_natural}. Queries the `{dataset}` dataset directly"
    elif source_kind == "datamodel":
        lead = f"{bare_natural}. XDM-normalized query over `{dataset}`"
    else:
        lead = f"{bare_natural}. XQL pattern"

    if first_filter:
        lead += f", filtered on `{first_filter}`"

    lead += "."

    # Supporting detail — stage signature for retrieval boost.
    detail = ""
    if stages:
        detail = "Uses stages: " + ", ".join(f"`{s}`" for s in stages[:6]) + "."

    return (lead + " " + detail).strip()


def render_md(entry_id: str, title: str, category: str, dataset: str,
              tags: list[str], query_text: str, description: str,
              source_kind: str, when_created_ts: int | None,
              desc_source: str = "heuristic") -> str:
    """Render the markdown entry matching the existing KB schema."""
    # Frontmatter — schema.json requires id, title, category. dataset + tags optional.
    fm = [
        "---",
        f"id: {entry_id}",
        f"title: {title}",
        f"category: {category}",
    ]
    if dataset:
        fm.append(f"dataset: {dataset}")
    if tags:
        fm.append("tags:")
        for t in tags:
            fm.append(f"  - {t}")
    fm.append("---")

    # Body
    ds_label = dataset or "(none)"
    qbody = query_text.strip()

    source_line = (
        f"Operator-authored, exported from XSIAM tenant by "
        f"amahmoud@paloaltonetworks.com. Imported as part of the "
        f"v0.6.51 operator-dataset bulk import (see CHANGELOG)."
    )
    if desc_source == "inline-comment":
        source_line += (
            " The `When to use` description above was extracted "
            "verbatim from the operator's `//Description:` SQL comment "
            "in the query body."
        )
    elif desc_source == "rtf-field":
        source_line += (
            " The `When to use` description above was carried over "
            "from the operator's XSIAM-saved-query `description` field."
        )
    else:
        source_line += (
            " The `When to use` description above was auto-generated "
            "by the importer's heuristic — operator-curation pass "
            "pending. The query body is the operator's authoritative "
            "version regardless of description quality."
        )
    if when_created_ts:
        # Convert epoch seconds → ISO date.
        import datetime as dt
        ts = dt.datetime.fromtimestamp(when_created_ts, tz=dt.timezone.utc)
        source_line += f" Original creation: {ts.strftime('%Y-%m-%d')}."

    body = [
        "",
        f"# {title}",
        "",
        f"**Dataset**: `{ds_label}`",
        "",
        "```sql",
        qbody,
        "```",
        "",
        "## When to use",
        "",
        description,
        "",
        "## Variations",
        "",
        "_(Auto-imported — variations not yet authored. The operator's curation pass adds these.)_",
        "",
        "## Source",
        "",
        source_line,
        "",
    ]
    return "\n".join(fm) + "\n" + "\n".join(body)


# ─── Main ──────────────────────────────────────────────────────


def main() -> None:
    data = json.loads(SOURCE_JSON.read_text(encoding="utf-8"))
    queries = data.get("data", [])

    stats: dict[str, int] = {
        "total": 0,
        "skipped_invalid": 0,
        "skipped_empty_query": 0,
        "skipped_duplicate_title": 0,
        "written": 0,
    }
    by_category: dict[str, int] = {}
    by_desc_source: dict[str, int] = {}

    for i, q in enumerate(queries):
        stats["total"] += 1

        if not (q.get("query_text") or "").strip():
            stats["skipped_empty_query"] += 1
            continue
        if not q.get("query_metadata", {}).get("is_valid", True):
            stats["skipped_invalid"] += 1
            continue

        raw_name: str = q.get("name") or f"untitled-{q.get('id', i)}"
        title = humanize_title(raw_name)

        if title in EXISTING_TITLES:
            stats["skipped_duplicate_title"] += 1
            continue

        query_text = q["query_text"]
        meta = q.get("query_metadata") or {}
        dataset, source_kind = extract_dataset(query_text, meta)
        stages = extract_stages(query_text)
        category = categorize(raw_name, query_text)

        # Tags: stages + dataset + source-kind + provenance marker
        tags: list[str] = list(stages)
        if dataset:
            tags.append(dataset)
        tags.append(f"source:{source_kind}")
        tags.append("operator-authored")
        # The operator's labels list is empty in all samples we saw, but
        # respect it if non-empty.
        for lbl in q.get("labels") or []:
            if isinstance(lbl, str) and lbl not in tags:
                tags.append(lbl)

        # Description ("When to use"). Priority order:
        #   1. RTF-level `description` field (rare — only ~10% of
        #      entries had it populated in the export)
        #   2. Operator's inline `//Description:` comment in the SQL
        #      body (the `QR -` template uses this — high quality)
        #   3. Heuristic generation (fallback for entries without
        #      operator-authored intent text)
        inline_meta = extract_inline_metadata(query_text)
        rtf_desc = (q.get("description") or "").strip()
        inline_desc = inline_meta.get("description", "").strip()

        if rtf_desc:
            description = rtf_desc
            desc_source = "rtf-field"
        elif inline_desc:
            description = inline_desc
            # If the operator also wrote //Filters: , append it — it
            # explains WHY the filter is what it is, useful retrieval
            # signal.
            inline_filters = inline_meta.get("filters", "").strip()
            if inline_filters:
                description += f" Filter rationale: {inline_filters}"
            # And //Tags: hints at category / detection family.
            inline_tags = inline_meta.get("tags", "").strip()
            if inline_tags:
                # Add operator-tags as additional KB tags (after the
                # stage / dataset / source-kind ones we already added).
                for t in re.split(r"[,;\s]+", inline_tags):
                    t = t.strip().lower()
                    if t and t not in tags:
                        tags.append(t)
            desc_source = "inline-comment"
        else:
            description = generate_description(
                raw_name, query_text, dataset, source_kind, stages
            )
            desc_source = "heuristic"

        # Track for stats
        by_desc_source[desc_source] = by_desc_source.get(desc_source, 0) + 1

        # ID + filename — stable hash on the original query id.
        seq = START_ID + stats["written"]
        slug = slugify(title)
        # Suffix with a short hash of the original id so duplicates across
        # re-runs land in the same file (idempotent).
        hsh = short_hash(f"opdata-{q.get('id')}-{title}")
        entry_id = f"XQL-{seq:03d}-{hsh}"

        out_path = OUTPUT_DIR / f"{seq:03d}-{slug}.md"
        md = render_md(
            entry_id=entry_id,
            title=title,
            category=category,
            dataset=dataset,
            tags=tags,
            query_text=query_text,
            description=description,
            source_kind=source_kind,
            when_created_ts=q.get("created_at"),
            desc_source=desc_source,
        )
        out_path.write_text(md, encoding="utf-8")
        stats["written"] += 1
        by_category[category] = by_category.get(category, 0) + 1

    print("=== Import stats ===")
    for k, v in stats.items():
        print(f"  {k:32}: {v}")
    print()
    print("=== By category ===")
    for k, v in sorted(by_category.items()):
        print(f"  {k:20}: {v}")
    print()
    print("=== Description source ===")
    for k, v in sorted(by_desc_source.items()):
        print(f"  {k:20}: {v}")


if __name__ == "__main__":
    main()
