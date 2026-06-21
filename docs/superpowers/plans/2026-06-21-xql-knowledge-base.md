# XQL Knowledge Base + Authoring Skill — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Onboard Phantom's XQL capability into Guardian — an `xql-examples` knowledge base, an agent-side `xql_examples_search` enrichment built-in, and the `cortex_xql_query_authoring` skill — curated and extended for incident investigation.

**Architecture:** Everything lands in the guardian-agent/MCP image (KB data + one built-in tool + one skill + UI/docs). The RAG+enrichment is agent-side (connectors are separate containers with no KB access). `xql_examples_search` = `knowledge_base().search(kb_name="xql-examples")` + pure-markdown enrichment from `xql_doc.md`/`dataset_fields.md`. No connector image changes.

**Tech Stack:** Python 3 (FastMCP runtime, `usecase/builtin_components`), SqliteKnowledgeBase + VertexEmbedder (text-embedding-004), Markdown+YAML-frontmatter KB entries, Next.js (skills UI), pytest.

## Global Constraints

- Work in the worktree `/tmp/gw.bxZaY3` (the repo under `~/Documents` is TCC-blocked). Branch: `main` (trunk-based; this repo releases from `main`).
- Phantom source (read-only, temporary) at `/tmp/phantom-src/.claude/worktrees/goofy-wozniak-d23459/` — referred to below as `$PH`. Do NOT delete it until the whole task is done.
- Built-in tools live in `bundles/spark/mcp/src/usecase/builtin_components/`; registered via the `_BUILTIN_LEGACY_TOOLS` tuple in `bundles/spark/mcp/src/usecase/connector_loader.py`.
- Built-in singleton accessors are called INSIDE the function at runtime (never imported at module load) so tests can wire them.
- KB entry frontmatter required fields: `id`, `title`, `category`. Missing any → the entry is SILENTLY skipped at load (v0.6.53). Category must be in the KB's `schema.json` enum.
- KB pre-baked embedding frontmatter: `embedding` (base64 little-endian float32), `embedding_model` (e.g. `text-embedding-004`), baked by `bundles/spark/kbs/_tools/kb_embed.py`.
- Connector import discipline does NOT apply here (this is agent-side `usecase` code, which may import `usecase.*`).
- pytest: tests in `bundles/spark/mcp/tests/test_*.py`, import `from usecase...`; run from `bundles/spark/mcp/` with `src/` on `sys.path` (most tests rely on the repo's `conftest`/pytest config). Use a venv with `pytest pyyaml httpx` if running ad hoc.
- Connector test venv already exists at `/tmp/xsoarvenv` (has pytest + pyyaml).

---

### Task 1: Port the XQL enrichment module + reference resources

**Files:**
- Create: `bundles/spark/mcp/src/usecase/builtin_components/_xql_enrichment.py`
- Create: `bundles/spark/mcp/src/usecase/builtin_components/xql_data/xql_doc.md` (copied)
- Create: `bundles/spark/mcp/src/usecase/builtin_components/xql_data/dataset_fields.md` (copied)
- Test: `bundles/spark/mcp/tests/test_xql_enrichment.py`

**Interfaces:**
- Produces: `extract_stage_names(query: str) -> set[str]`, `extract_dataset(query: str) -> str | None`, `collect_stage_docs(resources_dir: Path, stage_names: list[str]) -> list[dict[str,str]]` (each `{stage, snippet}`), `collect_dataset_fields(resources_dir: Path, datasets: list[str]) -> list[dict[str,Any]]` (each `{dataset, fields}`).

- [ ] **Step 1: Copy the two reference resources from Phantom (co-located with the module so resolution is trivial)**

```bash
cd /tmp/gw.bxZaY3
mkdir -p bundles/spark/mcp/src/usecase/builtin_components/xql_data
cp "/tmp/phantom-src/.claude/worktrees/goofy-wozniak-d23459/bundles/spark/mcp/resources/xql_doc.md" \
   bundles/spark/mcp/src/usecase/builtin_components/xql_data/xql_doc.md
cp "/tmp/phantom-src/.claude/worktrees/goofy-wozniak-d23459/bundles/spark/mcp/resources/dataset_fields.md" \
   bundles/spark/mcp/src/usecase/builtin_components/xql_data/dataset_fields.md
wc -l bundles/spark/mcp/src/usecase/builtin_components/xql_data/*.md   # expect ~8663 + ~749
```

- [ ] **Step 2: Write the failing test** — `bundles/spark/mcp/tests/test_xql_enrichment.py`

```python
from __future__ import annotations
from pathlib import Path
import pytest
from usecase.builtin_components import _xql_enrichment as xe

DATA = Path(xe.__file__).resolve().parent / "xql_data"

def test_extract_stage_names():
    q = "dataset = xdr_data\n| filter a = 1\n| alter b = 2\n| comp count() by b"
    assert xe.extract_stage_names(q) == {"filter", "alter", "comp"}

def test_extract_dataset():
    assert xe.extract_dataset("dataset = panw_ngfw_traffic_raw\n| filter x") == "panw_ngfw_traffic_raw"
    assert xe.extract_dataset("| filter x") is None

def test_collect_stage_docs_returns_snippets_for_known_stages():
    out = xe.collect_stage_docs(DATA, ["filter"])
    assert isinstance(out, list)
    assert any(d["stage"] == "filter" and d["snippet"] for d in out)

def test_collect_dataset_fields_shape():
    out = xe.collect_dataset_fields(DATA, ["nonexistent_dataset_xyz"])
    assert out == []   # unknown dataset → empty, never error
```

- [ ] **Step 3: Run it (fails — module missing)**

Run: `cd /tmp/gw.bxZaY3/bundles/spark/mcp && /tmp/xsoarvenv/bin/python -m pytest tests/test_xql_enrichment.py -q`
Expected: FAIL (`ModuleNotFoundError: usecase.builtin_components._xql_enrichment`) — if `usecase` import itself fails, add `PYTHONPATH=src`: `PYTHONPATH=src /tmp/xsoarvenv/bin/python -m pytest tests/test_xql_enrichment.py -q`.

- [ ] **Step 4: Create the module verbatim from Phantom** (pure stdlib; identical logic) — `bundles/spark/mcp/src/usecase/builtin_components/_xql_enrichment.py`

```python
"""XQL response enrichment helpers — markdown-only, no vector store.

Semantic search lives in the runtime's SqliteKnowledgeBase (the
`xql-examples` KB). This module adds the enrichment the agent wants on
top of raw matches:
  - stage_docs: for each pipeline stage in a match (`| filter`, `| comp`,
    ...), pull the relevant snippet from `xql_data/xql_doc.md`.
  - dataset_fields: for each `dataset = X` in a match, look up its field
    list from `xql_data/dataset_fields.md`.
Pure markdown parsing, module-level cached. Ported from Phantom's
bundles/spark/connectors/xsiam/src/_xql_enrichment.py.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_xql_doc_cache: dict[Path, str] = {}
_dataset_fields_cache: dict[Path, dict[str, list[str]]] = {}

_STAGE_RE = re.compile(r"\|\s*([a-zA-Z_][\w]*)")
_DATASET_RE = re.compile(r"\bdataset\s*=\s*([A-Za-z0-9_]+)")
_DATAMODEL_RE = re.compile(r"\bdatamodel\s+dataset\s*=\s*([A-Za-z0-9_]+)")


def extract_stage_names(query: str) -> set[str]:
    return {m.group(1).lower() for m in _STAGE_RE.finditer(query)}


def extract_dataset(query: str) -> str | None:
    m = _DATASET_RE.search(query) or _DATAMODEL_RE.search(query)
    return m.group(1) if m else None


def _load_xql_doc(resources_dir: Path) -> str:
    cached = _xql_doc_cache.get(resources_dir)
    if cached is not None:
        return cached
    path = resources_dir / "xql_doc.md"
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        text = ""
    _xql_doc_cache[resources_dir] = text
    return text


def _load_dataset_fields(resources_dir: Path) -> dict[str, list[str]]:
    cached = _dataset_fields_cache.get(resources_dir)
    if cached is not None:
        return cached
    mapping: dict[str, list[str]] = {}
    path = resources_dir / "dataset_fields.md"
    if path.is_file():
        current: str | None = None
        fields: list[str] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("## "):
                if current:
                    mapping[current] = fields
                current = line.removeprefix("## ").strip()
                fields = []
                continue
            if line.startswith("- "):
                fields.append(line.removeprefix("- ").strip())
        if current:
            mapping[current] = fields
    _dataset_fields_cache[resources_dir] = mapping
    return mapping


def _extract_doc_snippet(doc_text: str, stage_name: str, window: int = 360) -> str | None:
    if not doc_text:
        return None
    pattern = re.compile(
        rf"(.{{0,{window}}}\b{re.escape(stage_name)}\b.{{0,{window}}})",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(doc_text)
    if not match:
        return None
    return re.sub(r"\s+", " ", match.group(1)).strip()


def collect_stage_docs(resources_dir: Path, stage_names: list[str]) -> list[dict[str, str]]:
    if not stage_names:
        return []
    doc_text = _load_xql_doc(resources_dir)
    out: list[dict[str, str]] = []
    for name in stage_names:
        snippet = _extract_doc_snippet(doc_text, name)
        if snippet:
            out.append({"stage": name, "snippet": snippet})
    return out


def collect_dataset_fields(resources_dir: Path, datasets: list[str]) -> list[dict[str, Any]]:
    if not datasets:
        return []
    mapping = _load_dataset_fields(resources_dir)
    out: list[dict[str, Any]] = []
    for ds in datasets:
        fields = mapping.get(ds)
        if fields:
            out.append({"dataset": ds, "fields": fields})
    return out
```

- [ ] **Step 5: Run tests (pass)**

Run: `cd /tmp/gw.bxZaY3/bundles/spark/mcp && PYTHONPATH=src /tmp/xsoarvenv/bin/python -m pytest tests/test_xql_enrichment.py -q`
Expected: PASS (4 passed). If `test_collect_stage_docs` fails because "filter" isn't in xql_doc.md, replace the asserted stage with one present in the file (grep `xql_data/xql_doc.md` for a stage heading e.g. `comp`/`filter`/`alter`).

- [ ] **Step 6: Commit**

```bash
cd /tmp/gw.bxZaY3
git add bundles/spark/mcp/src/usecase/builtin_components/_xql_enrichment.py \
        bundles/spark/mcp/src/usecase/builtin_components/xql_data/ \
        bundles/spark/mcp/tests/test_xql_enrichment.py
git commit -m "feat(xql): port XQL enrichment helpers + reference resources"
```

---

### Task 2: `xql_examples_search` built-in tool + registration

**Files:**
- Modify: `bundles/spark/mcp/src/usecase/builtin_components/cognitive_tools.py` (add function near `knowledge_search`)
- Modify: `bundles/spark/mcp/src/usecase/connector_loader.py` (`_BUILTIN_LEGACY_TOOLS` tuple)
- Modify: `bundles/spark/manifest.yaml` (`tools.allow[]`)
- Test: `bundles/spark/mcp/tests/test_xql_examples_search.py`

**Interfaces:**
- Consumes: `usecase.kb_store.knowledge_base()` → `kb.search(intent, kb_name="xql-examples", limit=top_k)` returning `list[tuple[KbDocument, float]]` (KbDocument has `.doc_id, .title, .category, .content, .metadata`); `_xql_enrichment` from Task 1.
- Produces: `xql_examples_search(intent: str, top_k: int = 5) -> dict` returning `{status:"ok"|"error", intent, matches:[{id,title,query,dataset,category,score}], stage_docs, dataset_fields, count}` (or `{status:"error", message}`).

- [ ] **Step 1: Write the failing test** — `bundles/spark/mcp/tests/test_xql_examples_search.py`

```python
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
    def __init__(self, hits): self._hits = hits
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
        content="dataset = xdr_data\n| filter event_type = \"Login\"\n| comp count() by user",
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
```

- [ ] **Step 2: Run it (fails)**

Run: `cd /tmp/gw.bxZaY3/bundles/spark/mcp && PYTHONPATH=src /tmp/xsoarvenv/bin/python -m pytest tests/test_xql_examples_search.py -q`
Expected: FAIL (`AttributeError: module ... has no attribute 'xql_examples_search'`).

- [ ] **Step 3: Add the function to `cognitive_tools.py`** (place immediately AFTER `knowledge_search`/`knowledge_list`; it reuses the same `knowledge_base()` singleton)

```python
def xql_examples_search(intent: str, top_k: int = 5) -> dict[str, Any]:
    """Search the bundled `xql-examples` KB by natural-language intent and
    enrich each hit with XQL stage-syntax snippets + dataset field lists.

    The retrieval companion to the `cortex_xql_query_authoring` skill: returns
    idiomatic example queries (pattern prior) plus, for the stages/datasets
    those examples use, inline docs from the bundled XQL reference — so the
    agent can author a query without a round-trip per stage. For authoritative
    live syntax, pair with `cortex-docs/xql_lookup`.

    Args:
        intent: free-form analyst intent ("find C2 beaconing", "failed logon
            spikes by user", ...).
        top_k: max example matches (1-20). Default 5.

    Returns {status, intent, matches:[{id,title,query,dataset,category,score}],
    stage_docs:[{stage,snippet}], dataset_fields:[{dataset,fields}], count},
    or {status:"error", message}.
    """
    from pathlib import Path
    from usecase.kb_store import knowledge_base
    from usecase.builtin_components import _xql_enrichment as _xe

    if not (intent or "").strip():
        return {"status": "error", "message": "intent must not be empty"}
    kb = knowledge_base()
    if kb is None:
        return {"status": "error", "message": "knowledge base not initialized on this MCP runtime"}
    try:
        hits = kb.search(intent, kb_name="xql-examples", limit=max(1, min(int(top_k), 20)))
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "message": _friendly_embed_error(exc, "xql_examples_search")}

    matches: list[dict[str, Any]] = []
    stages: set[str] = set()
    datasets: set[str] = set()
    for doc, score in hits:
        ds = (doc.metadata or {}).get("dataset") or _xe.extract_dataset(doc.content)
        stages |= _xe.extract_stage_names(doc.content)
        if ds:
            datasets.add(ds)
        matches.append({
            "id": doc.doc_id,
            "title": doc.title,
            "query": doc.content,
            "dataset": ds,
            "category": doc.category,
            "score": score,
        })

    resources_dir = Path(_xe.__file__).resolve().parent / "xql_data"
    return {
        "status": "ok",
        "intent": intent,
        "matches": matches,
        "stage_docs": _xe.collect_stage_docs(resources_dir, sorted(stages)),
        "dataset_fields": _xe.collect_dataset_fields(resources_dir, sorted(datasets)),
        "count": len(matches),
    }
```

- [ ] **Step 4: Run the unit test (pass)**

Run: `cd /tmp/gw.bxZaY3/bundles/spark/mcp && PYTHONPATH=src /tmp/xsoarvenv/bin/python -m pytest tests/test_xql_examples_search.py -q`
Expected: PASS (3 passed). (Note: `_friendly_embed_error` already exists in cognitive_tools.py.)

- [ ] **Step 5: Register the tool** — in `bundles/spark/mcp/src/usecase/connector_loader.py`, in the `_BUILTIN_LEGACY_TOOLS` tuple, immediately after the `("knowledge_list", cognitive_tools.knowledge_list),` line, add:

```python
    # XQL example search — KB retrieval + stage/dataset enrichment for the
    # cortex_xql_query_authoring skill. Read-only (searches the xql-examples KB).
    ("xql_examples_search", cognitive_tools.xql_examples_search),
```

- [ ] **Step 6: Allow the tool** — in `bundles/spark/manifest.yaml`, under `tools.allow:`, after `- "knowledge_list"`, add:

```yaml
    - "xql_examples_search"
```

- [ ] **Step 7: Verify registration is well-formed**

Run: `cd /tmp/gw.bxZaY3 && python3 -c "import yaml; m=yaml.safe_load(open('bundles/spark/manifest.yaml')); assert 'xql_examples_search' in m['tools']['allow']; print('allow OK')"`
Run: `grep -n 'xql_examples_search' bundles/spark/mcp/src/usecase/connector_loader.py`
Expected: `allow OK` + the registration line present.

- [ ] **Step 8: Commit**

```bash
cd /tmp/gw.bxZaY3
git add bundles/spark/mcp/src/usecase/builtin_components/cognitive_tools.py \
        bundles/spark/mcp/src/usecase/connector_loader.py \
        bundles/spark/manifest.yaml bundles/spark/mcp/tests/test_xql_examples_search.py
git commit -m "feat(xql): xql_examples_search built-in (KB retrieval + enrichment) + register"
```

---

### Task 3: `xql-examples` KB — schema + ported/curated entries + manifest registration

**Files:**
- Create: `bundles/spark/kbs/xql-examples/schema.json`
- Create: `bundles/spark/kbs/xql-examples/entries/*.md` (ported + curated from `$PH`)
- Modify: `bundles/spark/manifest.yaml` (`knowledge.bundled[]`)
- Create: `bundles/spark/kbs/xql-examples/_curate.py` (one-shot copy+sanitize script, kept for reproducibility)
- Test: `bundles/spark/mcp/tests/test_xql_examples_kb.py`

**Interfaces:**
- Produces: a KB dir whose every entry validates against `schema.json` (required `id,title,category`; category ∈ enum).

- [ ] **Step 1: Write `schema.json`**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "XQL Example Knowledge Entry",
  "description": "One curated Cortex XSIAM XQL example, indexed for natural-language retrieval via knowledge_search / xql_examples_search.",
  "type": "object",
  "required": ["id", "title", "category"],
  "properties": {
    "id": {"type": "string"},
    "title": {"type": "string"},
    "category": {"type": "string", "enum": ["alert-mapping", "detection", "investigation", "general", "threat-hunting"]},
    "dataset": {"type": "string"},
    "ecosystem": {"type": "string"},
    "tags": {"type": "array", "items": {"type": "string"}},
    "attack": {"type": "array", "items": {"type": "string"}}
  },
  "additionalProperties": true
}
```

- [ ] **Step 2: Write the curate+sanitize script** — `bundles/spark/kbs/xql-examples/_curate.py` (copies the 161 Phantom entries, sanitizes tags to the canonical XQL stage set, sets `ecosystem: xsiam`, and drops pure near-duplicate "Troy" demo-widget entries keeping one representative per title)

```python
"""One-shot: port + curate Phantom xql-examples entries into Guardian.
Run once from the repo root: python bundles/spark/kbs/xql-examples/_curate.py
Idempotent: rewrites entries/ from the Phantom source each run."""
from __future__ import annotations
import re, sys
from pathlib import Path
import yaml

PH = Path("/tmp/phantom-src/.claude/worktrees/goofy-wozniak-d23459/bundles/spark/kbs/xql-examples/entries")
OUT = Path(__file__).resolve().parent / "entries"
CANON_STAGES = {
    "filter","alter","comp","sort","dedup","bin","fields","join","arrayexpand",
    "call","config","view","limit","union","windowcomp","iploc","timestamp_diff",
    "transaction","tabletoxql","replaceex",
}

def canon_tags(query: str, old_tags) -> list[str]:
    found = {m.group(1).lower() for m in re.finditer(r"\|\s*([a-zA-Z_][\w]*)", query)}
    tags = sorted(found & CANON_STAGES)
    # keep any old tags that are real stages too
    for t in (old_tags or []):
        if isinstance(t, str) and t.lower() in CANON_STAGES and t.lower() not in tags:
            tags.append(t.lower())
    return sorted(set(tags))

def main():
    if not PH.is_dir():
        print(f"ERROR: Phantom source not found: {PH}", file=sys.stderr); sys.exit(2)
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob("*.md"):
        f.unlink()
    seen_titles: dict[str, int] = {}
    kept = dropped = 0
    for src in sorted(PH.glob("*.md")):
        text = src.read_text(encoding="utf-8")
        m = re.match(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", text, re.DOTALL)
        if not m:
            continue
        meta = yaml.safe_load(m.group(1)) or {}
        body = m.group(2)
        title = str(meta.get("title", "")).strip()
        # Drop pure near-dup "Troy" demo dashboard widgets beyond the first per title.
        is_demo_widget = "troy" in title.lower() and "widget" in title.lower()
        if is_demo_widget:
            seen_titles[title] = seen_titles.get(title, 0) + 1
            if seen_titles[title] > 1:
                dropped += 1
                continue
        qmatch = re.search(r"```sql\n(.*?)```", body, re.DOTALL)
        query = qmatch.group(1) if qmatch else ""
        meta["tags"] = canon_tags(query, meta.get("tags"))
        meta.setdefault("ecosystem", "xsiam")
        fm = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).strip()
        (OUT / src.name).write_text(f"---\n{fm}\n---\n{body}", encoding="utf-8")
        kept += 1
    print(f"kept={kept} dropped_demo_dups={dropped}")

if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run the curate script**

Run: `cd /tmp/gw.bxZaY3 && /tmp/xsoarvenv/bin/python bundles/spark/kbs/xql-examples/_curate.py`
Expected: prints `kept=N dropped_demo_dups=M` (N ≈ 130-150, M ≈ 10-30); `ls bundles/spark/kbs/xql-examples/entries | wc -l` matches `kept`.

- [ ] **Step 4: Register the KB** — in `bundles/spark/manifest.yaml`, under `knowledge.bundled:`, add (after the last existing entry):

```yaml
    - name: "xql-examples"
      path: "./kbs/xql-examples/"
      schema: "./kbs/xql-examples/schema.json"
```

- [ ] **Step 5: Write the validation test** — `bundles/spark/mcp/tests/test_xql_examples_kb.py`

```python
from __future__ import annotations
import json, re
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
```

- [ ] **Step 6: Run the validation test (pass)**

Run: `cd /tmp/gw.bxZaY3/bundles/spark/mcp && PYTHONPATH=src /tmp/xsoarvenv/bin/python -m pytest tests/test_xql_examples_kb.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
cd /tmp/gw.bxZaY3
git add bundles/spark/kbs/xql-examples/ bundles/spark/manifest.yaml \
        bundles/spark/mcp/tests/test_xql_examples_kb.py
git commit -m "feat(xql): xql-examples KB — schema + curated ported entries + register"
```

---

### Task 4: Add IR / threat-hunting XQL entries (≥40, ATT&CK-aligned)

**Files:**
- Create: `bundles/spark/kbs/xql-examples/entries/2NN-<slug>.md` (≥40 new entries)

**Interfaces:**
- Consumes: the schema + validation test from Task 3 (every new entry must pass it).

- [ ] **Step 1: Author the IR/threat-hunting entries.** Number them `201-…`.md upward so they never collide with the ported `001-1xx` set. Each follows the exact entry format below. Cover at minimum these techniques (one entry each; add variants to reach ≥40): failed-logon / brute-force spike (T1110), successful logon after many failures, new local admin / group change (T1136/T1098), suspicious/encoded PowerShell (T1059.001), LOLBin execution (T1218), scheduled task creation (T1053), service creation (T1543), C2 beaconing by connection regularity (T1071), rare external destination / new domain (T1071), DNS tunneling / high-entropy subdomains (T1071.004), large outbound transfer / exfil (T1048), RDP lateral movement (T1021.001), SMB/admin-share lateral movement (T1021.002), impossible travel / concurrent geo logons (T1078), disabled security tooling (T1562), clearing event logs (T1070.001), credential dumping process access (T1003), new persistence via Run key (T1547), mass file rename / ransomware canary (T1486), privilege escalation token use (T1134). Use realistic XSIAM datasets (`xdr_data`, `endpoint_raw`, `network_story`, `incidents`, `panw_ngfw_traffic_raw`, `panw_ngfw_threat_raw`, `xdr_dns`).

  Entry template (fill per technique — this is the exact format, not a placeholder; produce a real query per entry):

```markdown
---
id: XQL-IR-201-bruteforce-logon-spike
title: Brute-force logon spike by source IP (T1110)
category: threat-hunting
dataset: xdr_data
ecosystem: xsiam
tags: [filter, comp, sort]
attack: [T1110]
---

# Brute-force logon spike by source IP (T1110)

**Dataset**: `xdr_data`

Hunt for sources generating many failed authentications in a short window — a brute-force / password-spray signal. Tune the `> 50` threshold and the `bin` window to the environment.

```sql
dataset = xdr_data
| filter event_type = ENUM.AUTHENTICATION and action_result = "FAILURE"
| alter ts_10m = bin(_time, 10m)
| comp count() as failures by actor_remote_ip, ts_10m
| filter failures > 50
| sort desc failures
```
```

- [ ] **Step 2: Validate all new entries against the schema**

Run: `cd /tmp/gw.bxZaY3/bundles/spark/mcp && PYTHONPATH=src /tmp/xsoarvenv/bin/python -m pytest tests/test_xql_examples_kb.py -q`
Expected: PASS. Then confirm count + categories: `grep -rl 'category: threat-hunting' /tmp/gw.bxZaY3/bundles/spark/kbs/xql-examples/entries | wc -l` ≥ 30 and total entries grew by ≥40.

- [ ] **Step 3: Commit**

```bash
cd /tmp/gw.bxZaY3
git add bundles/spark/kbs/xql-examples/entries/
git commit -m "feat(xql): add ATT&CK-aligned IR/threat-hunting XQL examples"
```

---

### Task 5: Pre-bake KB embeddings

**Files:**
- Modify: `bundles/spark/kbs/xql-examples/entries/*.md` (adds `embedding` + `embedding_model` frontmatter)

- [ ] **Step 1: Bake embeddings.** Prefer a real Vertex bake (matches the mitre KBs, text-embedding-004) when credentials are available; otherwise the KB self-heals by embedding on boot on the VM (which has Vertex), so this step is an optimization, not a blocker.

```bash
cd /tmp/gw.bxZaY3/bundles/spark/kbs/_tools
# Real bake (preferred) — requires a GCP service-account JSON with Vertex access:
python kb_embed.py ../xql-examples/ --embedder vertex \
    --sa-json /path/to/sa.json --project <gcp-project> --region us-central1
# If no creds at authoring time, SKIP the bake (loader embeds on boot). Do NOT
# use --embedder stub for the shipped KB (stub vectors give poor search; the
# loader rejects a stub bake whose model id != the runtime embedder anyway).
```

- [ ] **Step 2: Verify (only if baked)**

Run: `grep -c '^embedding_model:' /tmp/gw.bxZaY3/bundles/spark/kbs/xql-examples/entries/*.md | grep -vc ':0'`
Expected: equals the entry count (every entry baked). Re-run the Task 3 validation test to confirm entries still parse.

- [ ] **Step 3: Commit (only if baked)**

```bash
cd /tmp/gw.bxZaY3
git add bundles/spark/kbs/xql-examples/entries/
git commit -m "chore(xql): pre-bake Vertex embeddings for xql-examples KB"
```

---

### Task 6: `cortex_xql_query_authoring` skill + UI registration

**Files:**
- Create: `bundles/spark/mcp/skills/foundation/cortex_xql_query_authoring.md`
- Modify: `mcp/agent/app/skills/page.tsx` (`SKILLS[]` array)

- [ ] **Step 1: Create the skill** by copying Phantom's verbatim, then applying the adaptations below.

```bash
cp "/tmp/phantom-src/.claude/worktrees/goofy-wozniak-d23459/bundles/spark/mcp/skills/foundation/cortex_xql_query_authoring.md" \
   /tmp/gw.bxZaY3/bundles/spark/mcp/skills/foundation/cortex_xql_query_authoring.md
```

Then edit the copy:
1. **Step 2 of the workflow** ("Find ~5 similar examples"): change the retrieval instruction to prefer the enriched built-in — *"Call `xql_examples_search(intent=..., top_k=5)` — it returns matches PLUS `stage_docs` (XQL stage syntax) and `dataset_fields` (columns you can filter on). Fall back to `knowledge_search(kb_name='xql-examples')` for plain matches."*
2. **Failure-handling table:** remove the `xsiam_get_xql_doc` row (that tool doesn't exist in Guardian). Keep the cortex-docs-unreachable + xsiam-not-configured rows but rename the XSIAM tool refs to Guardian's: `xsiam_get_datasets`, `xsiam_run_xql_query`.
3. **Add an "## Incident-investigation use" section** after Step 6:

```markdown
## Incident-investigation use (Guardian)

XQL authoring isn't only ad-hoc — during an investigation, use it to SCOPE an
incident. Given a case's indicators (host, user, IP, hash, time window):

1. Pull the case context (e.g. `xsoar_get_incident` / the investigation tools).
2. `xql_examples_search` for the relevant hunt pattern (e.g. "lateral movement
   from host", "process tree for hash") to get an idiomatic starting query.
3. Bind the case's indicators into the query's `filter` clause and narrow the
   time window to the incident's span.
4. Confirm stage syntax with `cortex-docs/xql_lookup` for anything unfamiliar.
5. Run it with `xsiam_run_xql_query` to enumerate affected assets / sessions,
   then feed findings back into the case (notes, evidence, related indicators).

This turns the example KB + live docs into a blast-radius / threat-hunting
loop anchored to the incident under investigation.
```

4. Leave the rest (cortex-docs tool table, citation format) unchanged — Guardian's `cortex-docs` tool names already match.

- [ ] **Step 2: Verify the skill frontmatter parses + name matches**

Run: `cd /tmp/gw.bxZaY3 && python3 -c "import re,yaml; t=open('bundles/spark/mcp/skills/foundation/cortex_xql_query_authoring.md').read(); m=re.match(r'\A---\s*\n(.*?)\n---', t, re.DOTALL); d=yaml.safe_load(m.group(1)); assert d['name']=='cortex_xql_query_authoring' and d['category']=='foundation'; print('skill frontmatter OK:', d['displayName'])"`
Expected: `skill frontmatter OK: ...`.

- [ ] **Step 3: Register in the UI SKILLS[] array** — in `mcp/agent/app/skills/page.tsx`, add this object to the `SKILLS` array next to the other `foundation` entries (matches the `SkillDef` interface):

```ts
{
  id: "foundation-cortex-xql-query-authoring",
  name: "cortex_xql_query_authoring",
  displayName: "Cortex XQL query authoring",
  category: "foundation",
  description:
    "Compose Cortex XSIAM XQL queries by chaining the bundled xql-examples KB (via xql_examples_search) with live Palo Alto Cortex docs (cortex-docs/xql_lookup): find ~5 idiomatic examples, extract their stages/functions, confirm syntax in the docs, then author the query — and, mid-investigation, scope an incident's blast radius and run it with xsiam_run_xql_query.",
  icon: "query_stats",
  source: "platform",
  loadingMode: "on-demand",
  enabled: true,
  locked: false,
  agentCount: 1,
  calls7d: 0,
  content: "See bundles/spark/mcp/skills/foundation/cortex_xql_query_authoring.md",
  charCount: 0,
  tokenCount: 0,
  maxConcurrentAgents: 0,
  eligibleAgents: "guardian-agent",
  analytics: { calls24h: 0, calls7d: 0, calls30d: 0, avgContextTokens: 0, activeAgents: 1, topAgents: [{ name: "guardian", color: "#1f7bff" }] },
},
```

- [ ] **Step 4: Typecheck the UI change**

Run: `cd /tmp/gw.bxZaY3/mcp/agent && npx tsc --noEmit 2>&1 | head -20`
Expected: no errors referencing `app/skills/page.tsx`. (If `tsc` isn't set up for direct invocation, run `npm run build` per repo convention and confirm it compiles.)

- [ ] **Step 5: Commit**

```bash
cd /tmp/gw.bxZaY3
git add bundles/spark/mcp/skills/foundation/cortex_xql_query_authoring.md \
        mcp/agent/app/skills/page.tsx
git commit -m "feat(xql): cortex_xql_query_authoring skill (IR-reframed) + UI entry"
```

---

### Task 7: Docs — architecture, user, CHANGELOG, release-notes

**Files:**
- Modify: `mcp/agent/app/help/architecture/page.tsx`
- Modify: `mcp/agent/app/help/user/page.tsx`
- Modify: `CHANGELOG.md`
- Modify: `mcp/agent/lib/release-notes.ts`

- [ ] **Step 1: Architecture page** — add a subsection under the knowledge-base section documenting the `xql-examples` KB + the `xql_examples_search` built-in and its data flow (agent runtime → SqliteKnowledgeBase + local `xql_data/` resources; pairs with `cortex-docs/xql_lookup`). Follow the existing `Section`/`SubSection` component pattern in that file; one new anchor `#xql-knowledge-base`.

- [ ] **Step 2: User page** — add an entry describing the XQL authoring capability (the skill + `xql_examples_search`), tagged with the introducing version. Follow the existing pattern in `help/user/page.tsx`.

- [ ] **Step 3: CHANGELOG** — add a `## [v0.2.44] (<date>) — *XQL knowledge base + authoring skill*` section above the latest, in operator language: new `xql-examples` KB (N curated + IR/threat-hunting examples), `xql_examples_search` built-in (matches + stage docs + dataset fields), `cortex_xql_query_authoring` skill (incident-investigation reframed).

- [ ] **Step 4: release-notes.ts** — prepend a `{version:"0.2.44", date:"<date>", title:..., highlights:[...]}` entry (bare semver, newest first), per the file's authoring contract.

- [ ] **Step 5: Verify docs build**

Run: `cd /tmp/gw.bxZaY3/mcp/agent && npx tsc --noEmit 2>&1 | head -20`
Expected: no new errors in the edited files.

- [ ] **Step 6: Commit**

```bash
cd /tmp/gw.bxZaY3
git add mcp/agent/app/help/architecture/page.tsx mcp/agent/app/help/user/page.tsx \
        CHANGELOG.md mcp/agent/lib/release-notes.ts
git commit -m "docs(xql): architecture + user + changelog + release-notes for XQL KB/skill"
```

---

### Task 8: Gate, deploy, live smoke, release v0.2.44

**Files:** none (CI/CD + live verification)

- [ ] **Step 1: Full local gate** — run the MCP test suite (incl. the 3 new test files) and confirm green:

```bash
cd /tmp/gw.bxZaY3/bundles/spark/mcp && PYTHONPATH=src /tmp/xsoarvenv/bin/python -m pytest tests/test_xql_enrichment.py tests/test_xql_examples_search.py tests/test_xql_examples_kb.py -q
```
Expected: all pass. Also run any repo gate script if present (`grep -l 'pytest' /tmp/gw.bxZaY3/*.sh scripts/*.sh` then run it).

- [ ] **Step 2: Push to main + watch the agent build** (agent-image-only; no connector rebuild). Use the deploy-watch pattern from this session (watch `Build agent` → `build-dev-installer`; auto-rerun on the GHCR flake). Confirm `/api/agent/version` advances after deploy.

- [ ] **Step 3: Live smoke (in-container MCP, guardian-agent).** Restart `guardian_updater` only if needed; the KB + skill + built-in are in the agent image. Verify:
  - The `xql-examples` KB loaded: `GET /api/v1/kbs` lists it with the expected doc count.
  - `knowledge_search(kb_name="xql-examples", query="brute force logons")` returns hits.
  - `xql_examples_search(intent="lateral movement RDP", top_k=5)` returns `status:ok` with `matches` + non-empty `stage_docs`.
  - The skill is discoverable: `skills_list_all` includes `cortex_xql_query_authoring`; `/skills` UI shows the card.
  - End-to-end: drive a chat prompt ("write an XQL query to find failed-logon spikes") and confirm the agent loads the skill, calls `xql_examples_search` + `cortex-docs/xql_lookup`, and authors a cited query.

- [ ] **Step 4: Tag + release v0.2.44** — commit any version bump, tag `v0.2.44`, watch `release.yml` (9 images + install kit; auto-rerun on flake), confirm the GitHub release publishes.

- [ ] **Step 5: Cleanup** — once the release is verified, delete the Phantom copy: `rm -rf /tmp/phantom-src` (operator-requested). Update memory with the outcome.

---

## Self-Review

**Spec coverage:**
- Component A (KB) → Tasks 3 (port+curate+schema+register) + 4 (IR additions) + 5 (embeddings). ✓
- Component B (enrichment + RAG built-in) → Tasks 1 (enrichment+resources) + 2 (`xql_examples_search` + register + allow). ✓
- Component C (skill) → Task 6 (skill + UI). ✓
- Component D (docs/UI) → Task 6 (skills UI) + Task 7 (architecture/user/changelog/release-notes); `/knowledge` auto-discovers (no task needed). ✓
- Skipped `bootstrap_dataset_fields` → not ported (kept `dataset_fields.md` as a resource in Task 1). ✓
- Data flow (xql_examples_search → cortex-docs/xql_lookup → xsiam_run_xql_query) → Task 6 skill body. ✓
- Testing (enrichment, built-in, schema validation, live smoke) → Tasks 1,2,3,8. ✓
- Deploy agent-image-only → Task 8. ✓

**Placeholder scan:** Enrichment + built-in + schema + tests + skill UI entry are shown in full. Bulk data (161 entries, xql_doc.md, dataset_fields.md) is copied from `$PH` via exact commands. IR entries (Task 4) give the exact format + the explicit technique list to author (real queries, not stubs). Docs tasks (Task 7) describe exact files + the component pattern to follow (the help-page-update skill governs the section shape).

**Type consistency:** `xql_examples_search(intent, top_k)` return shape (`status/matches/stage_docs/dataset_fields/count`) is consistent across Task 2 (impl + test) and Task 6 (skill instructions). `KbDocument` fields (`doc_id/title/category/content/metadata`) used in Task 2 match the extracted dataclass. Enrichment signatures used in Task 2 match Task 1's definitions. KB schema (required + category enum incl. `threat-hunting`) is consistent across Tasks 3, 4, and the validation test.
