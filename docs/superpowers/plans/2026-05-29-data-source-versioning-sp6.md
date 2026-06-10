# SP-6 — Data Source Export-by-Version — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`). Repo root `/Users/ayman/Documents/Coding/phantom`; `.venv` python for pytest.

**Goal:** Let an operator export *any* version of a data source's YAML — not just the file on disk. Extend the existing export endpoint with an optional `?version=n` (default = the current version), and add an **Export** action to each row of the SP-5 version-history panel.

**Architecture:** The version store already holds every version's `yaml_snapshot` (SP-4 T1). SP-6 adds a `_resolve_export_content` helper (version-store-aware) behind the existing export route, threads `?version=` through the Next.js proxy, and adds a per-version Export action in `VersionHistoryModal`. This also fixes a latent inconsistency: today's export reads the pristine file even after an edit; default export now returns the current overlay content (matching the drawer).

**Tech Stack:** Python (FastMCP, sqlite3, pyyaml), Next.js 15 / React 19 (TS).

**Version:** v0.17.101 (patch bump). **Completes the versioning arc** (SP-4/5/6). Ships to dev cycle; no customer tag.

---

## Reference (read before starting)
- Spec: `docs/superpowers/specs/2026-05-29-data-source-versioning-design.md` (§Flows "Export", §Surfaces, SP-6 in §Sub-release decomposition).
- Export route (to modify): `bundles/spark/mcp/src/api/data_sources.py` — `export_data_source_yaml` (reads `yaml_ds._source_path.read_text()` today; filename `{dataset}.yaml`).
- Store (DONE): `data_source_versions_store.py` — `get_current(id)`, `get_version(id, n)`, `has_versions(id)`.
- `compose_data_source_id`, `require_bearer` in `api/data_sources.py`.
- Export proxy (to modify): `mcp/agent/app/api/agent/data-sources/[pack]/[rule]/[dataset]/export/route.ts` — currently does NOT forward query params.
- UI: `mcp/agent/app/data-sources/page.tsx` — `VersionHistoryModal` (SP-5; lists versions, View + Roll back per row).
- Pre-deploy gate (root CLAUDE.md).

---

## File structure
- **Modify** `bundles/spark/mcp/src/api/data_sources.py` — `_resolve_export_content(pack, rule, dataset, *, version=None)` helper + wire the export route to use it + honor `?version=`.
- **Modify** `bundles/spark/mcp/tests/test_data_sources_api.py` — helper tests.
- **Modify** `mcp/agent/app/api/agent/data-sources/[pack]/[rule]/[dataset]/export/route.ts` — forward `?version=`.
- **Modify** `mcp/agent/app/data-sources/page.tsx` — per-version Export action in `VersionHistoryModal`.
- **Modify docs:** architecture (#data-sources export note), user guide, `lib/journeys.ts` (extend roll-back journey), `CHANGELOG.md`, `lib/release-notes.ts` (v0.17.101).

---

## Task 1: Backend — `_resolve_export_content` + `?version=`

**Files:** Modify `api/data_sources.py`; Test `test_data_sources_api.py`

- [ ] **Step 1 — failing tests** (append; reuse `vstore`):
```python
def test_export_content_current_after_edit(vstore):
    ds_api._apply_edit("ServiceNow","ServiceNow","servicenow_servicenow_raw", how_to_use="EXPORT-CUR", author="operator")
    content, fname, err = ds_api._resolve_export_content("ServiceNow","ServiceNow","servicenow_servicenow_raw", version=None)
    assert err is None and "EXPORT-CUR" in content and fname == "servicenow_servicenow_raw.yaml"

def test_export_content_specific_version(vstore):
    ds_api._apply_edit("ServiceNow","ServiceNow","servicenow_servicenow_raw", how_to_use="V2TEXT", author="operator")
    # v1 = baseline (original), v2 = the edit
    content, fname, err = ds_api._resolve_export_content("ServiceNow","ServiceNow","servicenow_servicenow_raw", version=1)
    assert err is None and "V2TEXT" not in content and fname == "servicenow_servicenow_raw.v1.yaml"

def test_export_content_unknown_version(vstore):
    ds_api._apply_edit("ServiceNow","ServiceNow","servicenow_servicenow_raw", how_to_use="X", author="operator")
    content, fname, err = ds_api._resolve_export_content("ServiceNow","ServiceNow","servicenow_servicenow_raw", version=99)
    assert content is None and err == "version_not_found"

def test_export_content_unedited_reads_file(vstore):
    content, fname, err = ds_api._resolve_export_content("ServiceNow","ServiceNow","servicenow_servicenow_raw", version=None)
    assert err is None and "ServiceNow" in content and fname == "servicenow_servicenow_raw.yaml"
```
- [ ] **Step 2 — run, verify fail.**
- [ ] **Step 3 — implement** `_resolve_export_content(pack, rule, dataset, *, version=None) -> tuple[str|None, str, str|None]` returning `(content, filename, error)`:
  1. `ds_id = compose_data_source_id(...)`; `store = get_data_source_versions_store()`.
  2. If `version is not None`: `row = store.get_version(ds_id, int(version))` (if store) → if None return `(None, "", "version_not_found")`; else `(row["yaml_snapshot"], f"{dataset}.v{version}.yaml", None)`.
  3. Else (current): if `store and store.has_versions(ds_id)`: `cur = store.get_current(ds_id)` → `(cur["yaml_snapshot"], f"{dataset}.yaml", None)`.
  4. Else (no versions): resolve the file via `loader.get_by_3tuple(...)._source_path.read_text()` (today's path) → `(content, f"{dataset}.yaml", None)`; if not found → `(None, "", "not_found")`; on read error → `(None, "", "read_failed")`.
  - Wire `export_data_source_yaml`: parse `version = request.query_params.get("version")`; call the helper; map `error` → 404 (`not_found`/`version_not_found`) or 500 (`read_failed`); else return the `Response(content, media_type=..., Content-Disposition=filename)`.
- [ ] **Step 4 — run, verify pass.**
- [ ] **Step 5 — commit.**

---

## Task 2: Next.js export proxy — forward `?version=`

**Files:** Modify `export/route.ts`

- [ ] **Step 1** — read `request.nextUrl.searchParams.get("version")`; if present, append `?version=<encoded>` to the upstream URL. Keep streaming the body + `Content-Disposition` through (the filename now carries `.vN.` for specific versions).
- [ ] **Step 2** — `npx tsc --noEmit` → clean.
- [ ] **Step 3 — commit.**

---

## Task 3: UI — per-version Export in `VersionHistoryModal`

**Files:** Modify `mcp/agent/app/data-sources/page.tsx`

- [ ] **Step 1** — in each version row of `VersionHistoryModal`, add an **Export** action (anchor or button) that downloads `/api/agent/data-sources/{pack}/{rule}/{dataset}/export?version={v.version}`. Use an `<a download href=...>` styled like the View/Roll-back pills (icon `download`). Place it before Roll back. The current version's Export omits the `?version` (downloads `{dataset}.yaml`); older versions download `{dataset}.v{n}.yaml`.
- [ ] **Step 2 — gate:** `npx tsc --noEmit && npm run lint && npm run build` → clean.
- [ ] **Step 3 — commit.**

---

## Task 4: Docs

**Files:** architecture (#data-sources — add `export?version=` to the endpoint list + a line that default export = current overlay), user guide (one line in the history paragraph: "Export any version from the History panel"), `lib/journeys.ts` (extend `roll-back-data-source` — add an Export-a-version step + the `export?version=` API), `CHANGELOG.md` + `lib/release-notes.ts` (v0.17.101 — completes the arc).

- [ ] **Step 1** — write all updates. **Step 2 — commit.**

---

## Task 5: Gate, push, deploy, smoke

- [ ] **Step 1 — full gate** (tsc + lint + build + pytest -k data_source).
- [ ] **Step 2 — open the SP-6 issue** (`scenario:1, component:agent, area: ui, area: mcp`, `status:in-progress`, `Refs #101`); **push**; background-watch Build agent → Build dev installer.
- [ ] **Step 3 — deploy verify:** `PHANTOM_VERSION` == HEAD short sha.
- [ ] **Step 4 — smoke (deployed, `_sp6_smoke.py`):** edit a source → `GET …/export` returns current (edited) content; `GET …/export?version=1` returns the pristine baseline (no edit marker) + `Content-Disposition` filename `*.v1.yaml`; `GET …/export?version=99999` → 404. Restore not needed (export is read-only).
- [ ] **Step 5** — post smoke matrix to the issue + `status:dev-built` + `status:ready-for-testing`; **arc-completion closure note in chat** (no tag) — present the consolidated tag-approval ask for v0.17.99 + v0.17.100 + v0.17.101.

---

## Self-review (against the spec)
- **Spec coverage:** `export?version=` (T1) ✓; default = current (T1 step 3.3) ✓; UI export picker — realized as per-version Export in the history panel (T3), the cohesive home for version actions ✓; export reads `yaml_snapshot` verbatim (T1) ✓; docs (T4) ✓. Arc complete (SP-4 edit, SP-5 history+rollback, SP-6 export-version).
- **Placeholders:** none.
- **Type consistency:** `_resolve_export_content(... , version=None) -> (content, filename, error)` used by the route; `compose_data_source_id` everywhere; filename convention `{dataset}.yaml` (current) / `{dataset}.v{n}.yaml` (specific).
- **Deviation note:** the spec sketched a "Current / Version…" dropdown on the Export control; SP-6 instead puts per-version Export in the SP-5 history panel (already lists every version) + keeps the existing Export button = current. Same capability, more cohesive, less UI surface.
