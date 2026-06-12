# Guardian Self-Learning Loop — PLAYBOOK (Phase 1: harness + self-healing)

You are Claude Code running an **unattended scheduled trainer pass** on the
operator's local machine, started by `scripts/loop/guardian_loop.sh`. The clone
is already reset to clean `origin/main`. Do **exactly one coherent unit** this
pass, then verify, check, ship, and record. Then stop.

The wrapper's launch prompt tells you whether a **live-stack IAP tunnel** is up
this pass. If it is NOT, skip every live-stack audit below and use the
repo-only audits — those are always available and are the bulk of Phase 1.

Phase 1 has **no incident seeding and no new tools** — the job is to *harden
Guardian and keep it consistent*. (Seeding + judging investigations is Phase 2.)

## Ground rules (non-negotiable, every pass)
- **Never push on a red gate or a checker rejection.** Revert and record instead.
- **One unit per pass.** A focused, coherent change — not a grab-bag.
- **Honor every contract in CLAUDE.md.** Spec-driven workflow, contained-release
  discipline, documentation discipline, the credential guardrail.
- **Credential guardrail:** never read/write SecretStore values; never commit
  secrets. You edit code/docs only.
- This pass **auto-pushes to `main`**, which triggers CI build + auto-deploy.
  That is the intended delivery path. Do not tag a release (that is operator-only).

## 0. Preflight
1. `git rev-parse --short HEAD` — note the starting commit.
2. Read the loop's memory: `docs/loop/state.md` and `.guardian-loop/state.json`.
   Note `next_focus` and any `open_findings`.
3. Record the start time (UTC ISO-8601) for the state entry at the end.

## 1. ORIENT — continue or open ONE unit (narrow by default)
First check the loop's memory: `python3 scripts/loop/loop_state.py --repo . render` already
refreshed `state.md` from `state.json`. Read `.guardian-loop/state.json`.

a. **If an `active_unit` exists** (status `active`): CONTINUE it.
   - `mode: narrow` → take the NEXT slice from its `remaining_scope` (one file / small group).
   - `mode: wide` → if a carry patch exists at `.guardian-loop/carry/<active_unit.id>.patch`,
     `git apply` it first, then extend it (see CHECK / the carry-forward note).
b. **Else open a NEW unit** from the first real issue an audit finds (the §1c audits below).
   - Give it a stable `id` (kebab slug), a `title`, and a `scope` (the mapped files/hits).
   - **Scope it NARROW:** the smallest coherent slice that passes the gate on its own. If the
     issue is a WIDE bug-family across many files, decide:
       - **Splittable** (slices ship independently) → `mode: narrow`; fix ONE slice this cycle;
         record the rest as `remaining_scope`.
       - **Atomic-but-wide** (all-or-nothing for the gate, e.g. a rename) → `mode: wide`.
     Open it: `python3 scripts/loop/loop_state.py --repo . open-unit --id <slug> --title "..." --scope "..." --mode <narrow|wide>`
     and, when splitting, `... set-remaining --slices "<slice2>" "<slice3>" ...`.
   - **NEVER open a unit whose id is already in `state.json.deferred[]`** — those are human-owned.
c. **Self-heal audits** (run to FIND a new unit only when there is no active unit) — unchanged
   from Phase 1: doc-sync, bug-family, spec-drift; live-stack audits if the tunnel is up. When an
   audit re-surfaces an already-`deferred` issue, SKIP it.
   **Repo-only audits (ALWAYS available):**
   - **Doc-sync:** sidebar nav vs pages — `find mcp/agent/app -maxdepth 3 -name page.tsx | xargs dirname | sort` vs `href:` entries in `mcp/agent/components/sidebar.tsx`. Architecture-page service list vs the `services:` block in `docker-compose.yml`. CHANGELOG.md newest entry vs `mcp/agent/lib/release-notes.ts` newest entry.
   - **Bug-family audit:** `grep -rn "from usecase\." bundles/spark/connectors */src 2>/dev/null` (import-style regression, see connectors/CLAUDE.md); connector.yaml `spec.tools[].name` bare vs prefixed Python functions; hardcoded-data drift in `mcp/agent/app/api/` (e.g. marketplace `toolCount`).
   - **Spec-drift:** "Implementation gap" bullets in `mcp/agent/app/help/architecture/page.tsx`.
   **Live-stack audits (ONLY if the launch prompt said a tunnel is up):**
   - **Observe:** `curl -sk -H "Authorization: Bearer $GUARDIAN_API_KEY" $GUARDIAN_BASE/api/agent/jobs`; scan the `/observability` surfaces for errors. If no tunnel this pass, SKIP — do not block on stack access.
d. **Nothing to do** → record a clean `no-op` cycle and exit (no active unit to continue, no new
   issue found).

## 2. SCOPE the unit
- If the fix is **non-trivial** (new behavior / operator-visible / API change),
  open or find a GitHub issue first (`gh issue create --template release.md`),
  apply the mechanical labels, and reference it (`Refs #N`/`Closes #N`) — per
  CLAUDE.md spec-driven workflow. **Trivial** self-heal (doc-sync, bug-family,
  prose) is `scenario:trivial` / auto-closable.

## 3. FIX — implement the one unit
- Standard architecture first; clean cohesive change; minimal-but-complete.
- If operator-visible, do the **full doc cycle** in the same change (architecture
  page, user guide, journeys, CHANGELOG.md, release-notes.ts) per CLAUDE.md.

## 4. VERIFY — the full gate
- Run `scripts/loop/run_gate.sh "$PWD/.guardian-loop/logs/gate-$(date +%H%M%S).log"`.
  Step 0 of the gate is a **deterministic secret-scan** of your diff — if it trips,
  you committed/staged a credential-like string; treat as a hard failure.
- **Red** → revert your working changes (`git reset --hard HEAD && git clean -fd`),
  record the cycle as `gate-failed` with a summary of what broke, set `next_focus`
  to the failure, do NOT push, exit.

## 5. CHECK — adversarial checker subagent (maker ≠ checker)
- Spawn a **fresh subagent** (the Agent tool) with the diff (`git diff` / `git
  diff --staged`) and instructions to **REFUTE** the change:
  - Does the gate genuinely pass (not papered over)? Is the fix correct, complete,
    and spec-consistent? Does it honor CLAUDE.md (credential guardrail, contained
    release, docs discipline)? Any regression risk? **Default to REJECT on doubt.**
  - The subagent returns a verdict: `approved` or `rejected` + reasons.
- **Rejected** → revert, record `checker-rejected` with the reasons, set
  `next_focus`, do NOT push, exit.
- **On a rejection, branch by mode (the convergence machinery):**
  - `record-rejection`: `python3 scripts/loop/loop_state.py --repo . record-rejection --reasons "<the checker's specific reasons>"`.
  - **`mode: wide`** → save the rejected diff for the next cycle to build on:
    `mkdir -p .guardian-loop/carry && git diff > ".guardian-loop/carry/$(python3 -c 'import json;print(json.load(open(".guardian-loop/state.json"))["active_unit"]["id"])').patch"`
    then revert the working tree (`git reset --hard HEAD && git clean -fd -e .guardian-loop`).
  - **`mode: narrow`** → just revert (no carry); the slice will be re-derived (it's small).
  - **DEFER check:** if `python3 scripts/loop/loop_state.py --repo . show-defer` prints `DEFER`
    (rejections ≥ K: 2 narrow / 3 wide), HAND OFF instead of retrying:
      1. File a GitHub issue: `gh issue create --title "loop deferred: <title>" --body "<scope + accumulated checker reasons>"` → capture the URL.
      2. `python3 scripts/loop/loop_state.py --repo . defer-unit --issue "<url>"` (moves it to `deferred[]`, clears the active unit).
      3. Record the cycle `--outcome checker-rejected`, set a fresh `--next-focus`, do NOT push the fix. Exit.

## 6. SHIP + STATE
Record the cycle into the loop's memory, then ship the fix **and** the state
update as ONE atomic commit — folding them avoids a second CI/auto-deploy
trigger and the state-loss race if a human pushes between two separate pushes.

1. Record + render (the module is the only writer; note tunnel availability in
   the summary so degraded live-stack access is visible):
   ```bash
   python3 scripts/loop/loop_state.py --repo . record \
     --started-at "<UTC ISO from preflight>" \
     --focus "<the focus>" \
     --outcome "<fixed|no-op|gate-failed|checker-rejected>" \
     --summary "<one line> (tunnel: <up|down>)" \
     --commit "" \
     --gate "<pass|fail|>" --checker "<approved|rejected|n/a>" \
     --next-focus "<what next pass should look at>"
   python3 scripts/loop/loop_state.py --repo . render
   ```
2. **fixed (approved + green)** — one commit (fix + state together), one push,
   with a bounded rebase-retry:
   ```bash
   git add -A
   git commit -m "<conventional message; Refs/Closes #N>

   Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
   for i in 1 2 3; do git pull --rebase origin main && git push origin main && break; sleep 5; done
   ```
   (The shipping commit *is* this one; git history is the source of truth for the
   SHA, so `--commit ""` in the record is fine.)
  - **Drain the unit:** if the active unit still has `remaining_scope`, pop the shipped slice
    (`... set-remaining --slices "<the rest>"`) so the next cycle continues it; if it's now empty,
    `python3 scripts/loop/loop_state.py --repo . complete-unit`. A `wide` unit that finally ships:
    delete its carry patch (`rm -f .guardian-loop/carry/<id>.patch`) and `complete-unit`.
3. **no-op** — you MAY commit + push the state-only update (same one-commit/
   one-push shape) so the nightly cadence stays visible.
4. **gate-failed / checker-rejected** — first revert the working changes
   (`git reset --hard HEAD && git clean -fd`), then record + render; optionally
   commit + push the state-only record so the failure is visible. NEVER push a
   fix that failed the gate or the checker.
- **Do NOT wait for CI** — the wrapper exits here. The next pass's ORIENT can
  verify the deploy landed (when the tunnel is up, version endpoint vs HEAD).

## Stop
One unit done (or a clean no-op). Exit. The launchd LaunchAgent fires the next pass.
