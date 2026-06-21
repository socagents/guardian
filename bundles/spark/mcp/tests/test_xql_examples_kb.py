from __future__ import annotations
import json
import re
from pathlib import Path
import yaml

KB = Path(__file__).resolve().parents[2] / "kbs" / "xql-examples"


def _load_schema():
    return json.loads((KB / "schema.json").read_text("utf-8"))


def test_all_entries_valid_against_schema():
    schema = _load_schema()
    required = set(schema["required"])
    enum = set(schema["properties"]["category"]["enum"])
    entries = list((KB / "entries").glob("*.md"))
    assert len(entries) >= 100, f"expected a substantial KB, got {len(entries)}"
    seen_ids = set()
    for f in entries:
        text = f.read_text("utf-8")
        m = re.match(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", text, re.DOTALL)
        assert m, f"{f.name}: no frontmatter"
        meta = yaml.safe_load(m.group(1)) or {}
        missing = required - set(meta)
        assert not missing, f"{f.name}: missing required {missing}"
        assert meta["category"] in enum, f"{f.name}: bad category {meta['category']}"
        assert meta["id"] not in seen_ids, f"{f.name}: duplicate id {meta['id']}"
        seen_ids.add(meta["id"])
