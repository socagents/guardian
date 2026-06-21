# Stage A — Structured Investigation Record + Report

**Status:** approved (design) — 2026-06-21 · Arc: [structured-investigation-model-arc](2026-06-21-structured-investigation-model-arc.md) · **Keystone**
**Goal:** Replace prose-only investigation outcomes with a structured, queryable record — explicit verdict + confidence, blast-radius, a queryable issue↔ATT&CK technique table — and a one-call investigation report. Back-compatible with today's `VERDICT:` convention.

## Why
Today an investigation's outcome lives as free text (`Issue.summary` starting `VERDICT: …`, techniques cited in `conclusions` prose). You can't query "all true positives" or "incidents using T1566", the judge scores prose, and there's no exportable closure artifact. Stage A makes the outcome structured so it's queryable, defensibly scored, reportable — and so B/C/D have a typed foundation.

## Schema changes (`bundles/spark/mcp/src/usecase/investigation_store.py`)

All additive + backward-safe (existing `PRAGMA table_info` → `ALTER TABLE … ADD COLUMN` boot-migration pattern; new table via `CREATE TABLE IF NOT EXISTS`).

**`issues` — new columns:**
- `verdict TEXT` — enum: `TRUE_POSITIVE | FALSE_POSITIVE | BENIGN | NEEDS_ESCALATION | INCONCLUSIVE` (nullable until resolved).
- `verdict_confidence REAL` — 0.0–1.0 (nullable).
- `blast_radius TEXT` — JSON: `{ "hosts": [...], "accounts": [...], "related_issue_ids": [...], "summary": "…" }` (nullable).
- `report TEXT` — the rendered closure report (markdown), set by `generate_investigation_report` (nullable).

Add the four to the `Issue` dataclass (after `next_steps`, before `created_at`) + the row→Issue mapping + `create_issue`/`update_issue` field handling. `update_issue(**fields)` already takes arbitrary fields — extend its allowed-column set.

**New table `technique_mappings`** (queryable issue↔ATT&CK):
```sql
CREATE TABLE IF NOT EXISTS technique_mappings (
    id            TEXT PRIMARY KEY,
    issue_id      TEXT NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
    technique_id  TEXT NOT NULL,              -- e.g. T1566.001
    tactic        TEXT,                       -- e.g. initial-access
    manifestation TEXT,                       -- how it showed up in this incident
    evidence_ref  TEXT,                       -- indicator id / event id / war-room entry id
    confidence    REAL,                       -- 0..1 (confirmed vs suspected)
    created_at    TEXT NOT NULL,
    UNIQUE(issue_id, technique_id)
);
CREATE INDEX IF NOT EXISTS idx_techmap_issue ON technique_mappings(issue_id);
CREATE INDEX IF NOT EXISTS idx_techmap_tech  ON technique_mappings(technique_id);
```
Dataclass `TechniqueMapping`; store methods `add_technique_mapping(...)`, `list_technique_mappings(issue_id)`, `list_issues_by_technique(technique_id)`.

## MCP tools (`builtin_components/investigation_tools.py`, registered in `connector_loader._BUILTIN_LEGACY_TOOLS`)

- `issue_set_verdict(issue_id, verdict, confidence=None, blast_radius=None)` — sets the structured fields; validates `verdict` against the enum; `blast_radius` accepts a dict (serialized) or pre-serialized JSON. Returns the updated issue.
- `issue_add_technique(issue_id, technique_id, tactic=None, manifestation=None, evidence_ref=None, confidence=None)` — upsert into `technique_mappings`.
- `incidents_by_technique(technique_id)` — returns issues mapped to a technique (the inverse query; foundation for B/C dashboards).
- `generate_investigation_report(issue_id)` — assembles a structured report from existing data (issue fields + verdict/confidence/blast_radius + events timeline + indicators + technique_mappings + relationships), stores the markdown in `issues.report`, and returns `{ markdown, json }`. Pure read+assemble (no new external calls).

All catalog-side (no approval gate). Add each name to `_BUILTIN_LEGACY_TOOLS` and `manifest.yaml tools.allow`.

## REST (`api/investigation.py`)
- `GET /api/v1/issues/{id}` — include `verdict, verdict_confidence, blast_radius, report, techniques[]` in the detail payload.
- `GET /api/v1/issues/{id}/report` — return stored `report` (404 if not generated).
- `GET /api/v1/techniques/{technique_id}/issues` — inverse query.
(Keep existing routes; additive only.)

## UI (`mcp/agent/app/investigation/...` + `components/investigation/ui.tsx`)
- Issue detail **Assessment tab**: render the structured `verdict` as the banner (prefer the structured field; fall back to `splitVerdict(summary)` for legacy issues), with a confidence meter; render `blast_radius` (hosts/accounts/related counts + lists); render the **technique chips** (id + tactic, linking to a technique→incidents view) from `technique_mappings`.
- Add a **Report tab** (or section) showing the generated `report` markdown with a "Regenerate" action (one-shot job firing `generate_investigation_report`, same pattern as SVG regen).
- `lib/api/investigation.ts`: extend `IssueDetail` type with the new fields + `techniques`.
- Keep `splitVerdict`/`verdictTone` for back-compat; map the structured enum → the same tones.

## Skill + judge
- **`xsoar_case_investigation.md`** (the lifecycle skill): in the document/resolve steps, instruct the agent to ALSO call `issue_set_verdict` (structured) + `issue_add_technique` for each ATT&CK technique it mapped, and `generate_investigation_report` at resolve. Keep writing the `VERDICT:` prose line (back-compat) AND set the structured verdict. Preserve the 6-step lifecycle (the judge is trained on it).
- **Judge job** (`PATCH /api/agent/jobs/guardian-investigation-judge`): extend the rubric to score the structured fields (verdict set? confidence present? ≥1 technique mapped with evidence? blast_radius enumerated? report generated?).

## Back-compat / migration safety
- Existing issues (no structured verdict) still render via the legacy `splitVerdict(summary)` path.
- New columns default NULL; pre-migration DBs upgrade on boot (covered by a "pre-migration db gets columns" test).
- The `block-close-without-verdict` hook keeps working (it checks the `VERDICT:` line, which the skill still writes).

## Testing
- **pytest** (`test_investigation_store.py` + a new `test_investigation_structured.py`): new columns round-trip; `technique_mappings` CRUD + `list_issues_by_technique`; pre-migration DB (create issues table without the new cols, then init store → columns added, existing rows intact); `generate_investigation_report` assembles expected sections; `issue_set_verdict` enum validation.
- **tool tests**: `issue_set_verdict` / `issue_add_technique` / `incidents_by_technique` / `generate_investigation_report` via the singleton (mock/seed store).
- **tsc** clean for the UI changes.
- **Live smoke**: create a test issue via tools → set verdict + 2 techniques → generate report → `GET /api/v1/issues/{id}` shows structured fields + techniques + report; `incidents_by_technique(T1566.001)` returns it; headless `/api/chat` "investigate then structure the verdict" confirms the skill sets structured outputs.

## Deploy
Agent-image-only. Gate → push → agent build/deploy → live smoke → tag (next patch version) → release.
