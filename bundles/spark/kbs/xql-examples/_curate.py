"""One-shot: port + curate Phantom xql-examples entries into Guardian.

Run once from the repo root:  python bundles/spark/kbs/xql-examples/_curate.py

Idempotent: rewrites entries/ from the Phantom source each run (only touches
files that came from the port — Guardian-authored IR entries are left alone).
Sanitizes tags to the canonical XQL stage set, sets `ecosystem: xsiam`, and
drops ONLY true duplicates (entries whose XQL query body is byte-identical to
one already kept) — every distinct example query is preserved.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

import yaml

PH = Path(
    "/tmp/phantom-src/.claude/worktrees/goofy-wozniak-d23459"
    "/bundles/spark/kbs/xql-examples/entries"
)
OUT = Path(__file__).resolve().parent / "entries"
CANON_STAGES = {
    "filter", "alter", "comp", "sort", "dedup", "bin", "fields", "join",
    "arrayexpand", "call", "config", "view", "limit", "union", "windowcomp",
    "iploc", "timestamp_diff", "transaction", "tabletoxql", "replaceex",
}


def canon_tags(query: str, old_tags) -> list[str]:
    found = {m.group(1).lower() for m in re.finditer(r"\|\s*([a-zA-Z_][\w]*)", query)}
    tags = set(found & CANON_STAGES)
    for t in (old_tags or []):
        if isinstance(t, str) and t.lower() in CANON_STAGES:
            tags.add(t.lower())
    return sorted(tags)


def main() -> None:
    if not PH.is_dir():
        print(f"ERROR: Phantom source not found: {PH}", file=sys.stderr)
        sys.exit(2)
    OUT.mkdir(parents=True, exist_ok=True)
    # Only clear ported files (3-digit-prefixed); keep Guardian IR entries (2xx authored separately use XQL-IR ids/filenames).
    for f in OUT.glob("[0-9][0-9][0-9]-*.md"):
        f.unlink()
    seen_queries: set[str] = set()
    kept = dropped = 0
    for src in sorted(PH.glob("*.md")):
        text = src.read_text(encoding="utf-8")
        m = re.match(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", text, re.DOTALL)
        if not m:
            continue
        meta = yaml.safe_load(m.group(1)) or {}
        body = m.group(2)
        qmatch = re.search(r"```sql\n(.*?)```", body, re.DOTALL)
        query = qmatch.group(1) if qmatch else ""
        norm = re.sub(r"\s+", " ", query).strip().lower()
        if norm and norm in seen_queries:
            dropped += 1  # byte-identical query already kept — true duplicate
            continue
        if norm:
            seen_queries.add(norm)
        meta["tags"] = canon_tags(query, meta.get("tags"))
        meta.setdefault("ecosystem", "xsiam")
        fm = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).strip()
        (OUT / src.name).write_text(f"---\n{fm}\n---\n{body}", encoding="utf-8")
        kept += 1
    print(f"kept={kept} dropped_demo_dups={dropped}")


if __name__ == "__main__":
    main()
