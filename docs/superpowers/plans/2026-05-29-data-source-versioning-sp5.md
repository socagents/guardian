# SP-5 — Data Source Version History + Rollback — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax. Repo root `/Users/ayman/Documents/Coding/phantom`; `.venv` python for pytest.

**Goal:** Surface the version history built in SP-4 — let an operator (UI) or the agent (MCP tools) **list** a data source's versions, **view** any prior version's content, and **roll back** to any version (non-destructively: rollback copies the target forward as a new current; history is preserved).

**Architecture:** The store layer already exists (`data_source_versions_store.py` — `list_versions`, `get_version`, `rollback` all built + unit-tested in SP-4 T1). SP-5 adds: 3 REST endpoints (`versions`, `versions/{n}`, `rollback`), 2 catalog-side agent tools (`data_sources_list_versions`, `data_sources_rollback`), 3 Next.js proxies, and a drawer **Version history** panel (list versions, view one, roll back a non-current one).

**Tech Stack:** Python (FastMCP, sqlite3), Next.js 15 / React 19 (TS), Material 3 tokens.

**Version:** v0.17.100 (patch bump per CHANGELOG convention). Mid-arc; ships to dev cycle, no customer tag.

---

## Reference (read before starting)
- Spec: `docs/superpowers/specs/2026-05-29-data-source-versioning-design.md` (§Flows, §Surfaces, §Error handling).
- SP-4 plan (done): `docs/superpowers/plans/2026-05-29-data-source-versioning-sp4.md`.
- Store (DONE, SP-4 T1): `bundles/spark/mcp/src/usecase/data_source_versions_store.py` — `list_versions(ds_id)`, `get_version(ds_id, n)`, `rollback(ds_id, k)`, `get_current(ds_id)`, `has_versions(ds_id)`.
- REST + tools + `_apply_edit`: `bundles/spark/mcp/src/api/data_sources.py` (`compose_data_source_id`, `require_bearer`, `_json_body`, `set_current_actor`/`reset_current_actor`, the `PUT …/edit` route at `edit_data_source`, the `data_sources_edit` tool).
- Tool registration: `bundles/spark/mcp/src/main.py` (the `mcp.tool()(data_sources.*)` block).
- Next.js proxy precedent: `mcp/agent/app/api/agent/data-sources/[pack]/[rule]/[dataset]/edit/route.ts`.
- UI drawer: `mcp/agent/app/data-sources/page.tsx` — `DetailDrawer` (footer Edit-guidance button + `EditDataSourceModal` from SP-4 T6).
- Pre-deploy gate (root CLAUDE.md): `cd mcp/agent && npx tsc --noEmit && npm run lint && npm run build && (cd ../../bundles/spark/mcp && PYTHONPATH=$PWD/src /Users/ayman/Documents/Coding/phantom/.venv/bin/python -m pytest tests/ -k data_source -q)`.

---

## File structure

- **Modify** `bundles/spark/mcp/src/usecase/data_source_versions_store.py` — parametrize `rollback(..., author="operator")` so agent rollbacks record `author="agent"`.
- **Modify** `bundles/spark/mcp/src/api/data_sources.py` — 3 REST routes + 2 agent tool fns + a shared `_apply_rollback` helper.
- **Modify** `bundles/spark/mcp/tests/test_data_sources_api.py` — endpoint + tool tests.
- **Modify** `bundles/spark/mcp/tests/test_data_source_versions_store.py` — rollback-author test.
- **Modify** `bundles/spark/mcp/src/main.py` — register `data_sources_list_versions` + `data_sources_rollback`.
- **Create** `mcp/agent/app/api/agent/data-sources/[pack]/[rule]/[dataset]/versions/route.ts` — GET list proxy.
- **Create** `mcp/agent/app/api/agent/data-sources/[pack]/[rule]/[dataset]/versions/[version]/route.ts` — GET one-version proxy.
- **Create** `mcp/agent/app/api/agent/data-sources/[pack]/[rule]/[dataset]/rollback/route.ts` — POST rollback proxy.
- **Modify** `mcp/agent/app/data-sources/page.tsx` — Version-history panel in the drawer (list, view one, roll back).
- **Modify docs:** architecture (#data-sources versioning subsection — add lifecycle/rollback), user guide, `lib/journeys.ts` ("roll back a data source"), `CHANGELOG.md`, `lib/release-notes.ts`.

---

## Task 1: Store — parametrize rollback author

**Files:** Modify `data_source_versions_store.py`; Test `test_data_source_versions_store.py`

- [ ] **Step 1 — failing test** (append):
```python
def test_rollback_records_author(store):
    store.snapshot(DS, "v1", author="bundle-baseline")
    store.snapshot(DS, "v2", author="operator")
    new = store.rollback(DS, 1, author="agent")
    assert new["author"] == "agent" and new["version"] == 3
```
- [ ] **Step 2 — run, verify fail** (TypeError: unexpected kwarg `author`).
- [ ] **Step 3 — implement.** Change `def rollback(self, ds_id, version)` → `def rollback(self, ds_id, version, *, author="operator")`; pass `author=author` into the `self.snapshot(...)` call (keep `note=f"rolled back to v{version}"`).
- [ ] **Step 4 — run, verify pass** (`pytest tests/test_data_source_versions_store.py -q`).
- [ ] **Step 5 — commit.** `feat(data-sources): rollback records author (SP-5 T1) Refs #NN`

---

## Task 2: REST endpoints + `_apply_rollback` helper

**Files:** Modify `api/data_sources.py`; Test `test_data_sources_api.py`

- [ ] **Step 1 — failing tests** (append; reuse the `vstore` fixture from SP-4):
```python
def test_apply_rollback_non_destructive(vstore):
    ds_api._apply_edit("ServiceNow","ServiceNow","servicenow_servicenow_raw", how_to_use="E1", author="operator")
    ds_api._apply_edit("ServiceNow","ServiceNow","servicenow_servicenow_raw", how_to_use="E2", author="operator")
    out = ds_api._apply_rollback("ServiceNow","ServiceNow","servicenow_servicenow_raw", version=1, author="operator")
    assert out["ok"] and out["version"] == 4  # v1 base, v2 E1, v3 E2, v4 = rollback-to-v1
    versions = vstore.list_versions(SN)
    assert [v["version"] for v in versions] == [1,2,3,4]  # history preserved

def test_apply_rollback_unknown_version(vstore):
    ds_api._apply_edit("ServiceNow","ServiceNow","servicenow_servicenow_raw", how_to_use="E1", author="operator")
    out = ds_api._apply_rollback("ServiceNow","ServiceNow","servicenow_servicenow_raw", version=99, author="operator")
    assert out["ok"] is False and "not found" in out["error"].lower()

def test_apply_rollback_no_versions(vstore):
    out = ds_api._apply_rollback("ServiceNow","ServiceNow","servicenow_servicenow_raw", version=1, author="operator")
    assert out["ok"] is False  # nothing to roll back to
```
- [ ] **Step 2 — run, verify fail.**
- [ ] **Step 3 — implement** `_apply_rollback(pack, rule, dataset, *, version, author) -> dict`:
```python
def _apply_rollback(pack_name, rule_name, dataset_name, *, version, author):
    from usecase.data_source_versions_store import get_data_source_versions_store
    from usecase.data_sources_yaml_loader import get_data_sources_yaml_loader
    store = get_data_source_versions_store()
    if store is None:
        return {"ok": False, "error": "version store not initialized"}
    ds_id = compose_data_source_id(pack_name, rule_name, dataset_name)
    if not store.has_versions(ds_id):
        return {"ok": False, "error": f"no versions to roll back for {ds_id}"}
    try:
        new = store.rollback(ds_id, int(version), author=author)
    except ValueError as e:
        return {"ok": False, "error": str(e)}  # "version N not found ..."
    get_data_sources_yaml_loader().invalidate()
    return {"ok": True, "version": new["version"], "data_source_id": ds_id}
```
  Then 3 routes (mirror `edit_data_source`'s bearer + actor pattern):
  - `GET …/{pack}/{rule}/{dataset}/versions` → `store.list_versions(compose_data_source_id(...))`; return `{ "ok": True, "versions": [{version, author, note, created_at, is_current}], "data_source_id": id }` (omit `yaml_snapshot` from the list to keep it light). If store None/empty → `{"ok": True, "versions": []}`.
  - `GET …/{pack}/{rule}/{dataset}/versions/{version}` → `store.get_version(id, int(version))`; 404 if None; else `{ "ok": True, "version": {…full row incl yaml_snapshot…} }`.
  - `POST …/{pack}/{rule}/{dataset}/rollback` → parse body `{version}`; `set_current_actor("user:operator")`; `_apply_rollback(..., author="operator")`; 200/400 (400 when `ok` false).
- [ ] **Step 4 — run, verify pass.**
- [ ] **Step 5 — commit.**

---

## Task 3: Agent tools `data_sources_list_versions` + `data_sources_rollback`

**Files:** Modify `api/data_sources.py` (tool fns) + `main.py` (register); Test `test_data_sources_api.py`

- [ ] **Step 1 — failing tests** (append):
```python
def test_list_versions_tool(vstore):
    ds_api._apply_edit("ServiceNow","ServiceNow","servicenow_servicenow_raw", how_to_use="E1", author="operator")
    out = asyncio.run(ds_api.data_sources_list_versions(pack_name="ServiceNow", rule_name="ServiceNow", dataset_name="servicenow_servicenow_raw"))
    assert out["ok"] and [v["version"] for v in out["versions"]] == [1,2]
    assert out["versions"][0]["author"] == "bundle-baseline"

def test_rollback_tool_records_agent(vstore):
    ds_api._apply_edit("ServiceNow","ServiceNow","servicenow_servicenow_raw", how_to_use="E1", author="operator")
    out = asyncio.run(ds_api.data_sources_rollback(pack_name="ServiceNow", rule_name="ServiceNow", dataset_name="servicenow_servicenow_raw", version=1))
    assert out["ok"] and out["version"] == 3
    assert vstore.list_versions(SN)[-1]["author"] == "agent"
```
- [ ] **Step 2 — run, verify fail.**
- [ ] **Step 3 — implement** two async tools (docstrings with Args + example payload + the system-source note):
  - `data_sources_list_versions(pack_name, rule_name, dataset_name)` → returns `{ok, versions:[{version,author,note,created_at,is_current}]}` (reuse the store directly; no yaml_snapshot in the list). Docstring: "Inspect a data source's edit history — every saved version with author + note + timestamp, newest marked current. Pair with data_sources_rollback to revert."
  - `data_sources_rollback(pack_name, rule_name, dataset_name, version)` → `_apply_rollback(..., author="agent")`. Docstring: "Roll a data source back to a prior version. Non-destructive — the target is copied forward as a NEW current version; history is preserved (you can roll forward again). Use data_sources_list_versions first to pick the version number."
  - Register both in `main.py` next to `data_sources_edit`: `mcp.tool()(data_sources_list_versions)`, `mcp.tool()(data_sources_rollback)`.
- [ ] **Step 4 — run, verify pass** + `pytest tests/ -k data_source -q`.
- [ ] **Step 5 — commit.**

---

## Task 4: Next.js proxies

**Files:** Create 3 routes under `mcp/agent/app/api/agent/data-sources/[pack]/[rule]/[dataset]/`

- [ ] **Step 1** — `versions/route.ts` (GET), `versions/[version]/route.ts` (GET), `rollback/route.ts` (POST). Mirror the SP-4 `edit/route.ts` proxy exactly (`resolveMcp()`, bearer, forward to `${r.base}/api/v1/data-sources/${pack}/${rule}/${dataset}/<suffix>`, return JSON verbatim with upstream status). The rollback POST forwards the JSON body; the two GETs forward no body.
- [ ] **Step 2** — `cd mcp/agent && npx tsc --noEmit` → clean.
- [ ] **Step 3 — commit.**

---

## Task 5: UI — Version-history panel + rollback

**Files:** Modify `mcp/agent/app/data-sources/page.tsx`

- [ ] **Step 1 — implement** a `VersionHistoryModal` (mirror `EditDataSourceModal`'s shell): props `{ source, onClose, onChanged }`. On open, `GET /api/agent/data-sources/{pack}/{rule}/{dataset}/versions`. Render a list (newest first): `v{n} · {author} · {created_at}` + note; the current version tagged "Current". Each non-current row: a **View** action (GET `.../versions/{n}` → show its `how_to_use` read-only in an expandable block) + a **Roll back to this version** button (POST `.../rollback` `{version:n}` → on ok, `onChanged()` refetches the drawer + closes). Empty history → "No versions yet — this source hasn't been edited."
- [ ] **Step 2 — wire** a **History** button into the DetailDrawer footer next to "Edit guidance" (show whenever the source could have versions — i.e. always; the modal handles the empty case). Add `editingSource`-style state `historySource` + render the modal.
- [ ] **Step 3 — gate:** `npx tsc --noEmit && npm run lint && npm run build` → clean.
- [ ] **Step 4 — commit.**

---

## Task 6: Docs

**Files:** architecture `#data-sources` (extend the SP-4 "Versioning overlay" subsection with the rollback lifecycle + the 3 endpoints + 2 tools), user guide (add the "view history / roll back" steps to the SP-4 edit subsection), `lib/journeys.ts` ("roll-back-data-source" journey), `CHANGELOG.md` + `lib/release-notes.ts` (v0.17.100).

- [ ] **Step 1** — write all updates (version-tag v0.17.100; note SP-5 completes the "edit + roll back" capability; SP-6 export-version still pending). **Step 2 — commit.**

---

## Task 7: Gate, push, deploy, smoke

- [ ] **Step 1 — full gate** (tsc + lint + build + pytest -k data_source).
- [ ] **Step 2 — push**; background-watch Build agent → Build dev installer.
- [ ] **Step 3 — deploy verify:** `PHANTOM_VERSION` on phantom-vm == HEAD short sha.
- [ ] **Step 4 — smoke (deployed, via `docker exec -i phantom_agent`):** edit a source twice → `GET …/versions` shows v1(baseline)/v2/v3 → `GET …/versions/2` returns v2 content → `POST …/rollback {version:1}` → v4 current == v1 content, history still [1,2,3,4] → `GET …/schema` reflects the rolled-back content → agent tools `data_sources_list_versions` + `data_sources_rollback` advertised in tools/list. Restore to a clean state at the end. Extend `scripts/maintainer/_sp4_smoke.py` or add `_sp5_smoke.py`.
- [ ] **Step 5** — post smoke matrix to the issue + `status:dev-built` + `status:ready-for-testing`; closure note in chat (no tag).

---

## Self-review (against the spec)
- **Spec coverage:** `versions` + `versions/{n}` + `rollback` endpoints (T2) ✓; `data_sources_list_versions` + `data_sources_rollback` agent tools (T3) ✓; drawer version dropdown + view + non-destructive rollback (T5) ✓; non-destructive rollback (T1 author param + store.rollback copy-forward, already built) ✓; error handling — rollback unknown version → 4xx, no-versions → 4xx (T2) ✓; docs (T6) ✓. **Export-version is SP-6** (out of scope).
- **Placeholders:** none — every step has code or a precise instruction.
- **Type consistency:** `_apply_rollback(..., version, author)` shared by REST (operator) + tool (agent); `compose_data_source_id` is the id everywhere; store methods reused (`list_versions`/`get_version`/`rollback`) — no new store method beyond the `author` kwarg.
- **`#NN`** = the SP-5 issue number (opened at T7 Step or earlier); replace in commit footers. (Arc issue #101 may be reused, or a fresh SP-5 issue opened — decide at issue step.)
