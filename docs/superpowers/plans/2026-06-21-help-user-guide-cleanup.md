# Plan — User Guide cleanup (`app/help/user/page.tsx`)

**Goal:** The operator user guide describes only the **current, final** product, in plain present tense, with **zero internal version markers**. Version history lives only in the About-modal release notes / CHANGELOG.

**Scope:** 5,667-line guide, 7 groups / 33 sections. Audit found **50 version markers** and a set of retired-feature comment blocks. No missing operator-visible features (coverage is complete); this is a *clean-up*, not an *add*, pass.

## Policy (applies to every edit)
- Strip every `(v0.X.Y)` / `(v0.X.Y+)` stamp from SubSection titles and inline prose — **keep the feature description, drop the marker**, rewriting to present tense ("Guardian hides automated sessions by default" not "… (v0.2.40)").
- Delete every `{/* [guardian vX.Y.Z] Retired: … */}` developer comment (non-rendered, but pollutes the source and the "final state" intent).
- No "redesigned in", "reintroduced", "RESTORED", "keystone", "Phase N" narration.

## Tasks

1. **Delete retired-feature comment blocks** (no rendered change): SECTIONS array (data-sources / log-destinations-ux retired notes), the retired v0.3.0 breaking-change + upgrade-from-v0.2 walkthrough comments, the guardian-soc / xql-examples KB reintroduction comments, the Caldera password comment, the Plugins + Notifications + Backup&Restore retired-step comments. ~8 blocks.

2. **Strip version stamps from SubSection titles** (~17): Automated sessions; each Bundled KB (SOC Investigation, ATT&CK Enterprise, ATLAS, SOAR Playbooks, ICS+Mobile); XQL query authoring; Deploy + test-run; Indicators; Relations & attribution; Per-issue-type layouts; Cortex XSIAM connector; Running multiple instances; XSOAR command tools & playground_id; Evidence on XSOAR 6 vs 8; Emulated services; Guardian IR built-ins.

3. **Strip inline version stamps from paragraph bodies** (~25): the Investigation section is densest — Investigation-area intro, "redesigned in v0.1.7", the two verdict-line stamps, structured-outcome `(v0.2.45)`, Report term, Activity sort, Attack-chain term, Relations term, Multi-source depth, Case-level diagrams, Campaign rollup, Export & handoff; plus KB tag-chips/pagination/keystone/soar-playbooks, Version-aware fields, form-feedback, list_integrations, integration-status tools, playbook-state error, Hooks page, hook verdict ref, separator-insensitive glob.

4. **Fix the one version-pinned copy-paste command** (line ~848): `gh release download v0.1.0 …` → `gh release download <version> …` (or the `latest`/current-tag form the installer actually documents). This is the only place a version string is functional, not decorative — make it not go stale.

## Verification
- `grep -nE '\(v[0-9]+\.[0-9]+' app/help/user/page.tsx` → 0 results.
- `grep -n 'guardian v0' app/help/user/page.tsx` → 0 results.
- `grep -niE 'retired|reintroduced|redesigned in|keystone|phase [0-9]' app/help/user/page.tsx` → only legitimate product copy, no dev narration.
- `npx tsc --noEmit` + `npx eslint app/help/user/page.tsx` clean.
- Spot-read the Investigation + Connectors + Knowledge sections: each reads as "here's what Guardian does," no release archaeology.
