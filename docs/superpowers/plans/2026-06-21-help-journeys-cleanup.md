# Plan — User Journeys cleanup (`app/help/journeys/page.tsx` + `lib/journeys.ts`)

**Goal:** The journeys catalog shows **all** current operator click-paths, no hidden categories, no version markers. Journey definitions live in `lib/journeys.ts`; the page renders them.

**Scope:** Audit found the page nearly clean (**1 version-marker comment**) but with one real **completeness bug**: the category filter hardcodes 6 of 7 categories, hiding 24 journeys.

## Tasks

1. **Fix the hidden-categories bug** (`page.tsx`, the `CATEGORIES` array): it hardcodes `["all","onboarding","chat","memory","validation","ops"]`, omitting **`auth` (9 journeys)** and **`connectors` (15 journeys)** — 24 journeys never appear in the catalog UI. Replace with a dynamic pull so it always reflects `lib/journeys.ts`:
   ```ts
   const CATEGORIES: ("all" | JourneyCategory)[] = [
     "all",
     ...(Object.keys(CATEGORY_META) as JourneyCategory[]),
   ];
   ```
   (Confirm `CATEGORY_META` is imported / in scope; verify the Authentication + Connectors tabs then render with counts 9 and 15.)

2. **Delete the retired-tabs version comment** (the `// [guardian v0.1.0] Retired tabs: log-generation + red-team …` block) — the CATEGORIES/CATEGORY_META are self-documenting.

3. **Completeness check against current product** (in `lib/journeys.ts`): confirm journeys exist for the newer operator flows surfaced by this session's work — the investigation Issue detail **Assessment / Report / Campaign** tabs, **Export STIX** download, **Approvals** resolve flow, **case rollup**. Add concise journey entries for any that have an operator click-path but no journey. (Keep these version-free.)

4. **Leave legitimate internal notes** (pre-hydration flicker note, component-chip navigation note) — these are implementation comments, not customer-facing version history.

## Verification
- `grep -nE '\(v[0-9]|guardian v0' app/help/journeys/page.tsx lib/journeys.ts` → 0.
- `/help/journeys` shows all 7 category tabs (onboarding, chat, memory, validation, ops, auth, connectors) with correct counts; filtering each works.
- `npx tsc --noEmit` + eslint clean.
