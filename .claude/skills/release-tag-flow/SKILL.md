---
name: release-tag-flow
description: >-
  Use when preparing a customer release tag (v0.X.Y). Walks the use-case
  completion gate, the approval phrasing, the pre-tag docs checklist, the tag
  ceremony, and the post-tag closure report. Prevents the common mistake of
  tagging mid-arc commits or skipping the closure deliverable.
paths:
  - CHANGELOG.md
  - mcp/agent/lib/release-notes.ts
---

# Customer release tag flow

Activates when you're editing `CHANGELOG.md` or `mcp/agent/lib/release-notes.ts`. Customer-release tags fire `.github/workflows/release.yml` which builds + tags + pushes ALL 11 customer images at the same `vX.Y.Z` digest.

## Pre-tag: use-case completion gate (MANDATORY — root § Release-readiness gate)

A customer release tag is appropriate **only when the user-facing capability the release is meant to deliver is working end-to-end on the deployed install** — not when individual commits' smoke bullets pass.

**Mid-arc commits NEVER get tagged.** Asking "approve v0.6.52?" mid-arc is a category error. The tag fires at arc completion. Multi-release arcs:

1. Each commit goes through pre-deploy gate → push → CI build → auto-deploy → agent-side smoke → fix-and-push next iteration. **No operator approval between iterations.**
2. Mid-arc commits get CHANGELOG entries naming the prerequisite role: *"v0.6.5M is a prerequisite for the `<capability>` arc; the capability ships in v0.6.5N."*
3. Arc declaration goes in the FIRST commit's CHANGELOG entry with a "Capability acceptance criteria" section.
4. Tag only when ALL bullets pass end-to-end AND docs reflect the capability.

## Pre-tag docs checklist (root § Documentation discipline)

Before tagging any `vX.Y.Z`, every backend feature merged since the last release MUST have:

1. **Architecture page reflects reality** — `mcp/agent/app/help/architecture/page.tsx`. Services match `docker compose ps -a`. New services have a section with container name, source path, runtime, host ports, role, **explicit inter-service connections**.
2. **User guide reflects every operator-visible feature** — `mcp/agent/app/help/user/page.tsx`. Tag new content with the introducing version.
3. **User journeys cover every documented flow** — `mcp/agent/lib/journeys.ts`.
4. **Observability surfaces reflect runtime reality** — `mcp/agent/app/observability/`.
5. **Skills page in sync with on-disk skills** — `mcp/agent/app/skills/page.tsx`.
6. **No backend feature without a UI surface (or documented deferral).** No new UI page without a sidebar nav entry in the SAME release.
7. **Release notes describe user-visible deltas — in BOTH places.** `CHANGELOG.md` (long-form) + `mcp/agent/lib/release-notes.ts` (3-7 highlights, ~10-15 words each, **newest first**).
8. **Spec drift fixed in the same PR**, not deferred.
9. **MCP tool docstrings in lockstep with UI forms.**

## Approval phrasing (MANDATORY — root § Approval phrasing)

When ready to release at the END of a multi-release arc, ask plainly:

> "v0.X.Y completes the `<capability>` arc. End-state acceptance check passed on the deployed install: `<one-line summary of what the operator can now do>`. **Approve release of vX.Y.Z?**"

Then wait. Do not proceed on silence, on a thumbs-up emoji on a previous message, or on inferred consent from earlier "go ahead" instructions about implementation work.

## The tag ceremony

Only AFTER explicit operator chat-approval:

```bash
git tag -a vX.Y.Z -m "vX.Y.Z — <capability> customer release

<one-paragraph description>

Scenario <1|2|3> upgrade."
git push origin vX.Y.Z
```

The tag push fires `release.yml`. Watch with:

```bash
gh run watch <run-id> --exit-status
```

## After release.yml succeeds: post-tag closure deliverable (MANDATORY)

1. **Edit release notes** with the v0.X.Y CHANGELOG section:

```bash
# Extract the v0.X.Y section from CHANGELOG.md
awk '/^## \[v0\.X\.Y\]/{flag=1} /^## \[v0\.Z\.W\]/{flag=0} flag' CHANGELOG.md > /tmp/notes.md
gh release edit vX.Y.Z --notes-file /tmp/notes.md
```

2. **Apply `status:released` label** to every issue referenced in the release.

3. **Produce the 5-section closure report in chat** (root § Release closure report template):
   - Help docs landed
   - Journeys landed
   - Release notes landed
   - Image digests published (with REBUILT vs RETAGGED status from manifest diff)
   - Operator review checklist

Source of truth: `git diff vX.Y.Z-1..vX.Y.Z -- mcp/agent/app/help mcp/agent/lib/journeys.ts CHANGELOG.md mcp/agent/lib/release-notes.ts`.

## Forbidden

- Asking "approve tag?" between arc iterations.
- Deferring a smoke-uncovered arc-blocking bug.
- Tagging mid-arc commits as if standalone.
- Skipping CHANGELOG entries for mid-arc commits.
- Skipping the closure report because "the release was small."
- Populating closure report from imagination without opening docs to confirm.
- Treating closure report as customer-facing (it's an internal review aid).
