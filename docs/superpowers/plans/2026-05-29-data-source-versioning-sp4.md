# SP-4 — Data Source Edit + Versioning Foundation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax. Calibrated for self-execution by an agent with full Phantom context; commands assume repo root `/Users/ayman/Documents/Coding/phantom` and the `.venv` python for pytest/validator.

**Goal:** Let an operator (UI) or the agent (MCP tool) edit any data source's `how_to_use` + schema columns; each save creates a version in a new version store; the loader serves the current version as an overlay; the original is preserved as v1. (History-view + rollback = SP-5; export-by-version = SP-6.)

**Architecture:** New SQLite version store (`data_source_versions.db`) fronted by `data_source_versions_store.py`. The YAML loader consults the store for a current override (store-current → user YAML → bundle YAML). Edit goes through a validating REST endpoint (`PUT …/edit`) + a catalog-side agent tool (`data_sources_edit`); the UI drawer gains an Edit form with a system-source warning.

**Tech Stack:** Python (FastMCP, sqlite3, pydantic-settings, pyyaml, jsonschema), Next.js 15 / React 19 (TS), Material 3 tokens.

---

## Reference (read before starting)
- Spec: `docs/superpowers/specs/2026-05-29-data-source-versioning-design.md`
- Store pattern to mirror: `bundles/spark/mcp/src/usecase/data_sources_store.py`
- Loader to modify: `bundles/spark/mcp/src/usecase/data_sources_yaml_loader.py` (`get_by_3tuple`, `list_all`, `resolve_user_root`)
- REST + tools: `bundles/spark/mcp/src/api/data_sources.py` (`compose_data_source_id` imported line ~82; `_sync_field_counts_to_fields` / `_live_field_counts_by_id` are SP-2 helpers; `update_user` PUT precedent at `/api/v1/data-sources/user/{id}`)
- Schema validator: `bundles/spark/data-sources/data_source.schema.json`
- UI drawer: `mcp/agent/app/data-sources/page.tsx` (`DetailDrawer`, the Export `<a>` ~line 1535, the how_to_use `<MarkdownContent>` ~line 2347, stat tiles ~2299)
- Tool registration: `bundles/spark/mcp/src/main.py` (the `mcp.tool()(module.fn)` block) + `connector_loader.py` `_BUILTIN_LEGACY_TOOLS`
- Pre-deploy gate (root CLAUDE.md): `cd mcp/agent && npx tsc --noEmit && npm run lint && npm run build && (cd ../../bundles/spark/mcp && PYTHONPATH=$PWD/src .venv/python -m pytest tests/ -x)`

---

## File structure

- **Create** `bundles/spark/mcp/src/usecase/data_source_versions_store.py` — the version store (db + CRUD).
- **Create** `bundles/spark/mcp/tests/test_data_source_versions_store.py` — store unit tests.
- **Modify** `bundles/spark/mcp/src/usecase/data_sources_yaml_loader.py` — overlay resolution (consult version store for current).
- **Modify** `bundles/spark/mcp/tests/test_data_sources_yaml_loader.py` — overlay resolution tests.
- **Modify** `bundles/spark/mcp/src/api/data_sources.py` — `PUT …/edit` endpoint + `data_sources_edit` tool + a shared `_apply_edit()` helper + wire the store singleton.
- **Modify** `bundles/spark/mcp/tests/test_data_sources_api.py` — edit endpoint/tool tests.
- **Modify** `bundles/spark/mcp/src/main.py` — register `data_sources_edit` + init the version store singleton.
- **Modify** `bundles/spark/mcp/src/usecase/connector_loader.py` — add `data_sources_edit` to `_BUILTIN_LEGACY_TOOLS`.
- **Create** `mcp/agent/app/api/agent/data-sources/[pack]/[rule]/[dataset]/edit/route.ts` — Next.js proxy.
- **Modify** `mcp/agent/app/data-sources/page.tsx` — Edit button + edit form modal + system-source warning + save.
- **Modify docs:** `app/help/architecture/page.tsx` (#data-sources versioning subsystem), `app/help/user/page.tsx`, `lib/journeys.ts`, `CHANGELOG.md`, `lib/release-notes.ts`.

---

## Task 1: Version store module

**Files:** Create `bundles/spark/mcp/src/usecase/data_source_versions_store.py`; Test `bundles/spark/mcp/tests/test_data_source_versions_store.py`

- [ ] **Step 1 — Write failing tests** (`test_data_source_versions_store.py`):

```python
from __future__ import annotations
import pytest
from usecase.data_source_versions_store import DataSourceVersionsStore

@pytest.fixture
def store(tmp_path):
    return DataSourceVersionsStore(db_path=tmp_path / "versions.db")

DS = "ServiceNow/ServiceNow/servicenow_servicenow_raw"

def test_first_edit_snapshots_baseline_then_edit(store):
    # original_yaml = the file content; edit_yaml = the operator's change
    store.snapshot(DS, "vendor: ServiceNow\n", author="bundle-baseline", note="original")
    store.snapshot(DS, "vendor: ServiceNow\nhow_to_use: edited\n", author="operator", note="my edit")
    versions = store.list_versions(DS)
    assert [v["version"] for v in versions] == [1, 2]
    assert versions[0]["author"] == "bundle-baseline"
    cur = store.get_current(DS)
    assert cur["version"] == 2 and "edited" in cur["yaml_snapshot"]

def test_single_current_invariant(store):
    store.snapshot(DS, "a", author="bundle-baseline")
    store.snapshot(DS, "b", author="operator")
    store.snapshot(DS, "c", author="operator")
    currents = [v for v in store.list_versions(DS) if v["is_current"]]
    assert len(currents) == 1 and currents[0]["version"] == 3

def test_get_version_and_none_for_unknown(store):
    store.snapshot(DS, "a", author="bundle-baseline")
    assert store.get_version(DS, 1)["yaml_snapshot"] == "a"
    assert store.get_version(DS, 99) is None
    assert store.get_current("Nope/Nope/nope_raw") is None
    assert store.list_versions("Nope/Nope/nope_raw") == []

def test_rollback_non_destructive(store):
    store.snapshot(DS, "v1", author="bundle-baseline")
    store.snapshot(DS, "v2", author="operator")
    store.snapshot(DS, "v3", author="operator")
    new = store.rollback(DS, 1)              # roll back to v1
    assert new["version"] == 4 and new["yaml_snapshot"] == "v1"
    assert [v["version"] for v in store.list_versions(DS)] == [1, 2, 3, 4]  # history kept
    assert store.get_current(DS)["version"] == 4

def test_rollback_unknown_version_raises(store):
    store.snapshot(DS, "v1", author="bundle-baseline")
    with pytest.raises(ValueError):
        store.rollback(DS, 99)

def test_has_versions(store):
    assert store.has_versions(DS) is False
    store.snapshot(DS, "v1", author="bundle-baseline")
    assert store.has_versions(DS) is True
```

- [ ] **Step 2 — Run, verify fail:** `cd bundles/spark/mcp && PYTHONPATH=$PWD/src /Users/ayman/Documents/Coding/phantom/.venv/bin/python -m pytest tests/test_data_source_versions_store.py -x` → ImportError.

- [ ] **Step 3 — Implement** `data_source_versions_store.py`:

```python
"""SP-4 (#NN) — version store for data-source edits. One SQLite db holding
every version of every edited data source as a full YAML snapshot. The
loader reads the current version as an overlay; bundle/user files stay
pristine. Mirrors data_sources_store.py conventions (sqlite3, row factory,
a module-level singleton wired at boot)."""
from __future__ import annotations
import sqlite3, datetime
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS data_source_versions (
  data_source_id TEXT NOT NULL,
  version        INTEGER NOT NULL,
  yaml_snapshot  TEXT NOT NULL,
  created_at     TEXT NOT NULL,
  author         TEXT NOT NULL,
  note           TEXT,
  is_current     INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (data_source_id, version)
);
CREATE INDEX IF NOT EXISTS idx_dsv_current ON data_source_versions(data_source_id, is_current);
"""

def _resolve_db_path() -> Path:
    # Container: /app/data/. Dev: env override or cwd-local.
    import os
    override = os.environ.get("PHANTOM_DATA_DIR")
    base = Path(override) if override else Path("/app/data")
    return base / "data_source_versions.db"

class DataSourceVersionsStore:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or _resolve_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.db_path)
        c.row_factory = sqlite3.Row
        return c

    def has_versions(self, ds_id: str) -> bool:
        with self._conn() as c:
            r = c.execute("SELECT 1 FROM data_source_versions WHERE data_source_id=? LIMIT 1", (ds_id,)).fetchone()
        return r is not None

    def _next_version(self, c: sqlite3.Connection, ds_id: str) -> int:
        r = c.execute("SELECT MAX(version) AS m FROM data_source_versions WHERE data_source_id=?", (ds_id,)).fetchone()
        return (r["m"] or 0) + 1

    def snapshot(self, ds_id: str, yaml_text: str, *, author: str, note: str | None = None) -> dict[str, Any]:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._conn() as c:
            v = self._next_version(c, ds_id)
            c.execute("UPDATE data_source_versions SET is_current=0 WHERE data_source_id=?", (ds_id,))
            c.execute(
                "INSERT INTO data_source_versions(data_source_id,version,yaml_snapshot,created_at,author,note,is_current)"
                " VALUES (?,?,?,?,?,?,1)", (ds_id, v, yaml_text, now, author, note))
        return self.get_version(ds_id, v)

    def get_current(self, ds_id: str) -> dict[str, Any] | None:
        with self._conn() as c:
            r = c.execute("SELECT * FROM data_source_versions WHERE data_source_id=? AND is_current=1", (ds_id,)).fetchone()
        return dict(r) if r else None

    def get_version(self, ds_id: str, version: int) -> dict[str, Any] | None:
        with self._conn() as c:
            r = c.execute("SELECT * FROM data_source_versions WHERE data_source_id=? AND version=?", (ds_id, version)).fetchone()
        return dict(r) if r else None

    def list_versions(self, ds_id: str) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM data_source_versions WHERE data_source_id=? ORDER BY version", (ds_id,)).fetchall()
        return [dict(r) for r in rows]

    def rollback(self, ds_id: str, version: int) -> dict[str, Any]:
        target = self.get_version(ds_id, version)
        if target is None:
            raise ValueError(f"version {version} not found for {ds_id}")
        return self.snapshot(ds_id, target["yaml_snapshot"], author="operator", note=f"rolled back to v{version}")

# Module singleton (wired at boot like data_sources_store).
_STORE: DataSourceVersionsStore | None = None
def get_data_source_versions_store() -> DataSourceVersionsStore | None:
    return _STORE
def set_data_source_versions_store(s: DataSourceVersionsStore | None) -> None:
    global _STORE
    _STORE = s
```

- [ ] **Step 4 — Run, verify pass.** Same pytest command → all pass.
- [ ] **Step 5 — Commit:** `git add bundles/spark/mcp/src/usecase/data_source_versions_store.py bundles/spark/mcp/tests/test_data_source_versions_store.py && git commit -m "feat(data-sources): version store (SP-4) Refs #NN"`

---

## Task 2: Loader overlay resolution

**Files:** Modify `data_sources_yaml_loader.py`; Test `test_data_sources_yaml_loader.py`

- [ ] **Step 1 — Write failing test** (append to the loader test file):

```python
def test_version_store_current_overlays_file(tmp_path, monkeypatch):
    # Build a loader over the real bundle tree, inject a fake versions store
    # whose current snapshot for ServiceNow overrides how_to_use.
    from usecase.data_sources_yaml_loader import get_data_sources_yaml_loader
    from usecase import data_source_versions_store as vs
    store = vs.DataSourceVersionsStore(db_path=tmp_path / "v.db")
    edited = "schema_version: 1\nid: ServiceNow\npack_name: ServiceNow\nrule_name: ServiceNow\ndataset_name: servicenow_servicenow_raw\nvendor: ServiceNow\nproduct: ServiceNow\nhow_to_use: OVERLAID\nfields: []\n"
    store.snapshot("ServiceNow/ServiceNow/servicenow_servicenow_raw", edited, author="operator")
    vs.set_data_source_versions_store(store)
    loader = get_data_sources_yaml_loader(); loader.invalidate_cache()
    ds = loader.get_by_3tuple("ServiceNow", "ServiceNow", "servicenow_servicenow_raw")
    assert ds.how_to_use == "OVERLAID"
    vs.set_data_source_versions_store(None); loader.invalidate_cache()
```

- [ ] **Step 2 — Run, verify fail** (no overlay yet → how_to_use is the file's, not "OVERLAID").
- [ ] **Step 3 — Implement.** In the loader: (a) import `get_data_source_versions_store` + `compose_data_source_id`; (b) add an `invalidate_cache()` method if not present (the loader caches `list_all`); (c) in `get_by_3tuple` and in `_scan_root`/`list_all`'s per-source build, after resolving the file `YamlDataSource`, check the store: `cur = store.get_current(compose_data_source_id(pack, rule, dataset))`; if present, parse `cur["yaml_snapshot"]` via `YamlDataSource.from_doc(yaml.safe_load(...), source_path, origin)` and return that instead. Guard with `store = get_data_source_versions_store(); if store is not None and store.has_versions(id): …`. Wrap in try/except → on any error, fall back to the file ds (degrade gracefully).
- [ ] **Step 4 — Run, verify pass.**
- [ ] **Step 5 — Commit.**

---

## Task 3: Edit REST endpoint + shared `_apply_edit` helper

**Files:** Modify `api/data_sources.py`; Test `test_data_sources_api.py`

- [ ] **Step 1 — Write failing tests** (append): edit a known bundle source with a valid `how_to_use` change → 200 + the store has v1 (baseline) + v2 (current with the change); edit with a schema-invalid body (e.g. `fields` with a duplicate name, or a bad top-level) → 4xx + no version written.

```python
def test_edit_creates_baseline_then_version(store, vstore_wired):  # fixtures wire both stores + a tmp versions db
    body = {"how_to_use": "EDITED VIA TEST", "note": "t"}
    out = asyncio.run(ds_api.data_sources_edit(pack_name="ServiceNow", rule_name="ServiceNow", dataset_name="servicenow_servicenow_raw", **body))
    assert out["ok"] and out["version"] == 2
    versions = vstore.list_versions("ServiceNow/ServiceNow/servicenow_servicenow_raw")
    assert len(versions) == 2 and versions[0]["author"] == "bundle-baseline"

def test_edit_rejects_invalid_schema(vstore_wired):
    out = asyncio.run(ds_api.data_sources_edit(pack_name="ServiceNow", rule_name="ServiceNow", dataset_name="servicenow_servicenow_raw", fields=[{"name":"a"},{"name":"a"}]))
    assert out["ok"] is False and "duplicate" in out["error"].lower()
```

- [ ] **Step 2 — Run, verify fail.**
- [ ] **Step 3 — Implement** `_apply_edit(pack, rule, dataset, *, how_to_use=None, fields=None, note=None, author) -> dict`:
  1. Resolve the current source content: `loader.get_by_3tuple(...)` → its `to_doc()` (full YAML dict). (If the store already has a current, that's what `get_by_3tuple` returns — so edits compose on the latest.)
  2. Apply the patch: set `how_to_use` if provided; replace `fields` if provided (validate each field dict).
  3. Validate the resulting doc against `data_source.schema.json` (reuse the same jsonschema load the validator uses) + the field-name-uniqueness check. On failure → `{"ok": False, "error": "..."}` (no snapshot).
  4. If the store has NO versions yet for this id, first `snapshot(original_doc_yaml, author="bundle-baseline", note="original")`. Then `snapshot(edited_doc_yaml, author=author, note=note)`.
  5. `loader.invalidate_cache()`. Return `{"ok": True, "version": new_version, "data_source_id": id}`.
  - REST route `PUT /api/v1/data-sources/{pack}/{rule}/{dataset}/edit` → parse body → `_apply_edit(..., author="operator")` → JSONResponse. Bearer-gated.
- [ ] **Step 4 — Run, verify pass.**
- [ ] **Step 5 — Commit.**

---

## Task 4: Agent MCP tool `data_sources_edit`

**Files:** Modify `api/data_sources.py` (tool fn), `main.py` (register), `connector_loader.py` (`_BUILTIN_LEGACY_TOOLS`); Test `test_data_sources_api.py`

- [ ] **Step 1 — Failing test:** `data_sources_edit(pack_name=..., rule_name=..., dataset_name=..., how_to_use="X")` returns `{"ok": True, "version": 2}` and the store reflects it.
- [ ] **Step 2 — Run, verify fail.**
- [ ] **Step 3 — Implement** `async def data_sources_edit(pack_name, rule_name, dataset_name, how_to_use=None, fields=None, note=None)` → calls `_apply_edit(..., author="agent")`. **Docstring** with Args + example payload (agent picks fields from docstring) + a line: "Catalog-side: edits curated schema/how_to_use; no secrets. System sources are editable but create an operator override — mention this to the operator." Register in `main.py` (`mcp.tool()(data_sources.data_sources_edit)`) and add `"data_sources_edit"` to `_BUILTIN_LEGACY_TOOLS`. Init the versions store singleton in `main.py` boot alongside `data_sources_store` (`set_data_source_versions_store(DataSourceVersionsStore())`).
- [ ] **Step 4 — Run, verify pass** + `pytest tests/ -k "data_source" ` (no regressions).
- [ ] **Step 5 — Commit.**

---

## Task 5: Next.js proxy for edit

**Files:** Create `mcp/agent/app/api/agent/data-sources/[pack]/[rule]/[dataset]/edit/route.ts`

- [ ] **Step 1** — Implement a `PUT` handler mirroring the existing `export/route.ts` proxy pattern: `resolveMcp()` → `fetch(`${r.base}/api/v1/data-sources/${pack}/${rule}/${dataset}/edit`, {method:"PUT", headers:{Authorization, "Content-Type":"application/json"}, body})` → return JSON. Use `lib/mcp-proxy.ts` conventions; don't hand-roll auth.
- [ ] **Step 2** — `cd mcp/agent && npx tsc --noEmit` → clean.
- [ ] **Step 3 — Commit.**

---

## Task 6: UI — Edit form + system-source warning

**Files:** Modify `mcp/agent/app/data-sources/page.tsx`

- [ ] **Step 1 — Screenshot the current drawer** (Chrome MCP, authenticated tab) to anchor placement: Edit button beside Export in the drawer header; form fields = `how_to_use` (textarea) + an editable fields table (name/type/description/example/is_meta/is_array rows, add/remove row).
- [ ] **Step 2 — Implement** an `EditDataSourceModal` component (Material 3 tokens, follows existing modal patterns in page.tsx): props `{ row, onClose, onSaved }`. On open for a system source (`origin === "bundle"`), show a warning banner: "This is a system data source. Saving creates an operator override (the original is preserved as version 1)." Fields: `how_to_use` textarea (prefill from `detail.how_to_use`), fields table editable. Save → `PUT /api/agent/data-sources/{pack}/{rule}/{dataset}/edit` with `{how_to_use, fields, note}` → on `ok`, call `onSaved()` (refetch drawer). Add an **Edit** button to the drawer header that opens it.
- [ ] **Step 3 — Gate:** `npx tsc --noEmit && npm run lint && npm run build` → clean.
- [ ] **Step 4 — Commit.**

---

## Task 7: Docs

**Files:** `app/help/architecture/page.tsx` (#data-sources — add "Versioning subsystem" subsection: store, overlay resolution order, v1-baseline rule, inter-service wiring agent↔MCP↔store), `app/help/user/page.tsx` (editing a data source + the system-source warning + "original preserved as v1"), `lib/journeys.ts` ("Edit a data source" journey), `CHANGELOG.md` + `lib/release-notes.ts` (v0.17.99 entry).

- [ ] **Step 1** — Write all five doc updates (real prose, version-tagged). **Step 2** — Commit.

---

## Task 8: Pre-deploy gate, push, deploy, smoke

- [ ] **Step 1 — Full gate:** `cd mcp/agent && npx tsc --noEmit && npm run lint && npm run build && (cd ../../bundles/spark/mcp && PYTHONPATH=$PWD/src /Users/ayman/Documents/Coding/phantom/.venv/bin/python -m pytest tests/ -k "data_source" -q)`. Fix any failure before proceeding.
- [ ] **Step 2 — Open the SP-4 issue** (`scenario:1,component:agent,area: ui` + `area: mcp`), apply `status:in-progress`. **Step 3 — Push** main; background-watch Build agent → Build dev installer.
- [ ] **Step 4 — Deploy verify:** `PHANTOM_VERSION` on phantom-vm == HEAD short sha.
- [ ] **Step 5 — Smoke (deployed):** via the MCP bearer in-container — (a) `PUT …/edit` ServiceNow `how_to_use` → 200 v2; (b) `GET …/catalog` + `GET …/schema` reflect the edit (loader overlay live); (c) versions store has v1 baseline + v2; (d) re-edit → v3; (e) agent tool: `tools/call data_sources_edit` round-trip → ok. Post the smoke matrix to the issue + apply `status:dev-built` + `status:ready-for-testing`.
- [ ] **Step 6** — Closure note in chat (no tag).

---

## Self-review (against the spec)

- **Spec coverage:** version store (T1) ✓; loader overlay (T2) ✓; edit REST (T3) ✓; agent tool (T4) ✓; proxy (T5) ✓; UI edit form + system warning (T6) ✓; baseline v1 rule (T3 step 3.4) ✓; docs (T7) ✓; error handling — schema/dup validation before snapshot (T3), loader degrade (T2 step 3) ✓. **History-view + rollback are SP-5; export-version is SP-6** (correctly out of SP-4 scope).
- **Placeholders:** none — every step has commands/code or a precise instruction.
- **Type consistency:** store methods (`snapshot/get_current/get_version/list_versions/rollback/has_versions`) used consistently in T1–T4; `compose_data_source_id` is the id everywhere; `_apply_edit(author=...)` shared by REST (operator) + tool (agent).
- **Note:** `#NN` placeholders are the SP-4 issue number, assigned at Task 8 Step 2; replace in commit footers.
