---
name: Spec-driven release
about: Open one of these BEFORE starting work on a non-trivial change. The body becomes the CHANGELOG entry at release time.
title: '[spec] Short verb-phrase title (e.g. "Add foo to bar")'
labels: ['status:spec']
assignees: []
---

<!--
GUIDE
─────
This issue tracks ONE concept that will ship as ONE release
(per CLAUDE.md § Contained-release discipline). The body below
becomes the CHANGELOG / release-notes entry at release time —
write it like the final doc, not like a TODO list.

Add labels manually after creation:
  • component:* (one or more — agent / connectors /
                 installer / workflows / docs / help-pages / journeys)
  • scenario:* (exactly one — scenario:1 / scenario:2 / scenario:3 /
                scenario:docs-only / scenario:trivial)

The agent assigns status:* labels mechanically as work progresses
(in-progress, dev-built, released). You apply the human-decision
status:* labels (spec-approved, testing-complete, release-approved).

For TRIVIAL changes (typo, whitespace, comment-only): label as
scenario:trivial and skip the rest of the fields. The agent reads
this label and skips the smoke-test ceremony.

Full discipline: see docs/CICD.md § Spec-driven workflow.
-->

## Summary

<!-- One sentence. What does this release change? -->

## Scenario classification

<!-- Mark exactly ONE — the corresponding label will determine
     versioning (patch vs major) + customer experience + volume policy.
     See docs/CICD.md § Change scenarios for the full breakdown. -->

- [ ] **Scenario 1** — code-only, installer unchanged, backwards-compatible storage → patch bump, volumes preserved
- [ ] **Scenario 2** — code + installer change, backwards-compatible storage → patch bump, volumes preserved
- [ ] **Scenario 3** — backwards-incompatible storage schema → MAJOR bump, volumes wiped (with backup, after operator types `UPGRADE`)
- [ ] **Docs-only** — no code change; rides along with next code release
- [ ] **Trivial** — typo / whitespace / comment-only (skip the rest of this template)

## Why

<!-- The motivating problem. Operator-reported friction? Internal
     discipline gap? Customer feature request? Be specific —
     "improve auth" is too vague; "auth flow re-prompts customer for
     password twice on Step 4 in the v0.5.X installer" is concrete. -->

## What ships

<!-- The "What ships" section of the CHANGELOG entry that this
     release will produce. List the surfaces affected + the change
     per surface. Files in `installer/**`, `mcp/agent/**`, `docs/**`,
     `CLAUDE.md`, `.github/workflows/**`, etc.

     This is the contract: when the release lands, the CHANGELOG
     entry should match this section closely (with minor wording
     edits). If you can't write this section before starting work,
     the scope isn't clear enough yet. -->

## Smoke-test bullets (cumulative)

<!-- What the operator runs on guardian-vm after
     `sudo guardian-installer-dev` to verify this change works.
     5-15 bullets. Each bullet:
       • Names a specific UI action OR shell command
       • Names the surface to verify (UI page / log file / endpoint)
       • Has an unambiguous pass/fail signal (HTTP code, visible
         text, container state, etc.)

     The cumulative-scope rule (CLAUDE.md § Smoke-test bullet
     contract): these bullets cover ALL unreleased issues since the
     last customer vX.Y.Z release, not just this one. They grow
     monotonically until release approval. -->

1.
2.
3.

## Forbidden going forward

<!-- Once this lands, what patterns must NOT regress? What anti-
     patterns should the next change avoid?

     Mirrors the CHANGELOG's "Forbidden post-vX.Y.Z" section.
     Empty if nothing needs forbidding; non-empty if the change
     codifies a new discipline. -->

## Cross-references

<!-- Related issues / discussions: -->
- Refs: #
- Replaces / supersedes: #
- Docs surfaces to update in the same PR:
  - [ ] `docs/CICD.md` § (anchor)
  - [ ] `CLAUDE.md` § (section)
  - [ ] `mcp/agent/app/help/architecture` § (anchor)
  - [ ] `mcp/agent/app/help/user` § (anchor)
  - [ ] `mcp/agent/lib/journeys.ts` (new/retired journey)
  - [ ] `mcp/agent/lib/release-notes.ts` (the customer-readable entry)

---

<!-- DO NOT EDIT BELOW THIS LINE — labels track lifecycle state.

Lifecycle (label transitions):
  status:spec           ← (auto on issue creation via this template)
  status:spec-approved  ← you apply when scope is locked
  status:in-progress    ← agent applies when first commit lands
  status:dev-built      ← agent applies after build-dev-installer success
  status:testing-complete  ← you apply after manual smoke test passes
  status:release-approved  ← you apply after chat approval
  status:released       ← agent applies after release.yml success;
                          issue closes automatically
-->
