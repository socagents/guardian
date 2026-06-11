# Guardian self-learning loop — operator runbook

The loop is a durable, unattended self-improvement cycle that runs on the
**operator's local Mac** (NOT guardian-vm). Design:
[`2026-06-11-self-learning-loop-design.md`](2026-06-11-self-learning-loop-design.md).
Phase-1 procedure: [`PLAYBOOK.md`](PLAYBOOK.md).

## What it does (Phase 1)
A nightly **launchd** LaunchAgent runs one "trainer pass" of headless Claude
Code that finds + fixes one self-healing unit (doc-sync, bug-family, spec-drift,
and — when a best-effort IAP tunnel is up — live-stack observe), runs the full
gate + an adversarial checker, and pushes to `main` (which triggers the normal
CI build + auto-deploy on the VM runner). No XSOAR seeding yet (Phase 2).

## Where things live
| Thing | Path |
|---|---|
| Dedicated clone | `~/guardian-loop` (OUTSIDE `~/Documents`; NOT the working repo) |
| Secrets/config (gitignored, 0600) | `~/guardian-loop/scripts/loop/loop.env` |
| VM coords for the tunnel (gitignored) | `~/guardian-loop/.env.vm` (copied during provisioning) |
| Machine state (tracked) | `.guardian-loop/state.json` |
| Human state mirror | `docs/loop/state.md` |
| Per-cycle transcripts (gitignored) | `.guardian-loop/logs/cycle-*.log` + `launchd.{out,err}.log` |
| LaunchAgent plist | `deploy/loop/com.guardian.loop.plist` → `~/Library/LaunchAgents/` |

## Provisioning (one time — see Task 9 of the plan for the exact commands)
1. `git clone` into `~/guardian-loop` (claude + git are already installed/authed locally).
2. `cp scripts/loop/loop.env.example scripts/loop/loop.env`, fill it, `chmod 600`.
3. Copy `.env.vm` into the clone (for the best-effort tunnel) — gitignored.
4. `scripts/loop/loop_bootstrap.sh` (npm ci + .venv + deps + gate smoke).
5. Install the LaunchAgent: copy the plist to `~/Library/LaunchAgents/` and
   `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.guardian.loop.plist`.

## Operate it
- **Status:** `launchctl print gui/$(id -u)/com.guardian.loop | grep -E 'state|runs'`
- **Run one pass now:** `launchctl kickstart -k gui/$(id -u)/com.guardian.loop` then
  tail the newest `~/guardian-loop/.guardian-loop/logs/cycle-*.log`.
- **Dry run (no claude):** `DRY_RUN=1 ~/guardian-loop/scripts/loop/guardian_loop.sh`
- **Pause:** `launchctl bootout gui/$(id -u)/com.guardian.loop`
- **Read what it's done:** `~/guardian-loop/docs/loop/state.md`.

## Unattended auth (login-backed, by design)
- **`claude`** runs on this laptop's **logged-in Claude Code session** (your subscription) — **no Anthropic API key, by design** (the loop runs locally, so it's the same `claude` you use interactively). Caveat: the login creds live in the macOS **login keychain**, unlocked only while you're logged in; a reboot/logout before the 02:30 fire locks them and that night's run skips — an accepted tradeoff (subscription over an API key). No `--max-budget-usd` either (subscription isn't $-billed; the wall-clock `LOOP_MAX_SECONDS` watchdog bounds each run).
- **`git push`** uses `gh`'s **active account, which must stay `thekite-dev`** — the only account with access to `kite-production/guardian` (`ayman-m` 404s). The active-account credential IS the push auth (no per-clone PAT). If the active account drifts back to `ayman-m`, the nightly push fails; `gh auth switch --user thekite-dev` restores it.
- **`gcloud`** (best-effort tunnel, only when `LOOP_USE_TUNNEL=1` + `.env.vm` present) uses your SSO account whose token expires on a corporate cadence; when it lapses the tunnel degrades to repo-only audits (Phase 1's default). A dedicated service account + ADC is the proper unattended fix (Phase 2+).

## Guardrails
The loop auto-pushes to `main` with **no PR**. Its only guardrails are the full
gate (`scripts/loop/run_gate.sh`) and an adversarial checker subagent — both
must pass before any push. The wrapper refuses to run in the primary working
repo or under `~/Documents`. It never touches credentials and never tags a
release (operator-only). To stop it entirely, `launchctl bootout` the agent.
