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

## 1. ORIENT — pick ONE focus (first match wins)
a. **An open finding** in `state.json.open_findings` not yet resolved.
b. **`next_focus`** from state, if still valid.
c. **A self-heal scan** — run these audits and take the FIRST real issue found.
   **Repo-only audits (ALWAYS available):**
   - **Doc-sync:** sidebar nav vs pages — `find mcp/agent/app -maxdepth 3 -name page.tsx | xargs dirname | sort` vs `href:` entries in `mcp/agent/components/sidebar.tsx`. Architecture-page service list vs the `services:` block in `docker-compose.yml`. CHANGELOG.md newest entry vs `mcp/agent/lib/release-notes.ts` newest entry.
   - **Bug-family audit:** `grep -rn "from usecase\." bundles/spark/connectors */src 2>/dev/null` (import-style regression, see connectors/CLAUDE.md); connector.yaml `spec.tools[].name` bare vs prefixed Python functions; hardcoded-data drift in `mcp/agent/app/api/` (e.g. marketplace `toolCount`).
   - **Spec-drift:** "Implementation gap" bullets in `mcp/agent/app/help/architecture/page.tsx`.
   **Live-stack audits (ONLY if the launch prompt said a tunnel is up):**
   - **Observe:** `curl -sk -H "Authorization: Bearer $GUARDIAN_API_KEY" $GUARDIAN_BASE/api/agent/jobs`; scan the `/observability` surfaces for errors. If no tunnel this pass, SKIP — do not block on stack access.
d. **Nothing to do** → skip to step 6 and record a clean `no-op` cycle, set a
   sensible `next_focus`, do NOT push, exit.

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
