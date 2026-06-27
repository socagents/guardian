# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Lean-root principle (v0.10.0+)**: this file holds only **repo-wide agent-behavior contracts** + **critical gotchas**. Architecture detail per subsystem lives in subdirectory `CLAUDE.md` files — Claude loads them additively as you move into the relevant tree. The structural map lives in [`CODEBASE_MAP.md`](CODEBASE_MAP.md). The harness documentation lives in [`AI-LAYER.md`](AI-LAYER.md).

## Subdirectory CLAUDE.md files

For local conventions, read the directory's own `CLAUDE.md`:

- [`mcp/agent/CLAUDE.md`](mcp/agent/CLAUDE.md) — Next.js + embedded MCP host (the `guardian-agent` container)
- [`bundles/spark/mcp/CLAUDE.md`](bundles/spark/mcp/CLAUDE.md) — Python FastMCP server
- [`bundles/spark/connectors/CLAUDE.md`](bundles/spark/connectors/CLAUDE.md) — connector authoring conventions
<!-- [guardian v0.1.0] Retired: log-generation backend CLAUDE.md entry — that subsystem was removed when Guardian was carved out of the upstream platform -->
- [`installer/CLAUDE.md`](installer/CLAUDE.md) — customer installer template
- [`updater/CLAUDE.md`](updater/CLAUDE.md) — guardian-updater container-lifecycle daemon

For the structural map, read [`CODEBASE_MAP.md`](CODEBASE_MAP.md).
For the AI Layer (hooks, skills, MCP servers, subagents, plugin marketplace) read [`AI-LAYER.md`](AI-LAYER.md).

## What Guardian is

AI incident-response agent for Cortex XSIAM/XSOAR: evidence-grounded investigations, XQL hunts, case enrichment, and response orchestration over MCP. Ships as a Docker Compose stack — `guardian-agent` (Next.js UI + embedded Python FastMCP subprocess behind a TLS proxy), `guardian-browser` (headless-Chromium CDP sidecar), `guardian-updater` (container-lifecycle daemon), plus per-instance connector containers — see [`CODEBASE_MAP.md`](CODEBASE_MAP.md) for the topology.

## Operator communication context

**Operator messages are frequently voice-transcribed.** Expect occasional misspellings, dropped punctuation, words that obviously didn't transcribe right ("z four four four zero" → `v0.4.0`, "second store" → SecretStore, "Claude MD" → CLAUDE.md). Read for intent, not literal tokens. When a sentence reads strangely, infer the most coherent technical meaning before asking for clarification. Do not echo transcription artifacts back ("the SSDG diagram you mentioned"); silently normalize to the correct term ("the SVG diagram").

## Contained-release discipline (MANDATORY)

**One concept = one release.** Even when the operator asks for multiple unrelated changes in one turn, split them into separate contained releases. Each release has:

- A single named scope (e.g. "v0.4.0 — auth redesign"). The CHANGELOG and release-notes entries describe one concept top-to-bottom.
- A single contained documentation section. For `app/help/architecture/page.tsx` and `app/help/user/page.tsx`, the release adds or rewrites exactly one anchor (e.g. `#authentication`), not scattered edits across many sections.
- A single coherent test surface — the operator can verify the release with one user-journey walkthrough, not a checklist crossing six surfaces.

When you finish a release that touched the architecture or user-guide pages, tell the operator *exactly* which anchors to review (e.g. *"review `/help/architecture#authentication` and `/help/user#authentication`"*). Never make the operator hunt for what changed.

## CI/CD pipeline → see [`docs/CICD.md`](docs/CICD.md)

**Guardian's build/test/release pipeline mechanics, change scenarios, workflow contracts, and customer upgrade flows all live in [`docs/CICD.md`](docs/CICD.md).** This file (CLAUDE.md) keeps the **agent-behavior contracts** that touch CI/CD; the pipeline mechanics those contracts enforce live in the CI/CD guide.

### The three change scenarios (the most important thing to know before planning a release)

Every release classifies into one of three scenarios. See [docs/CICD.md § Change scenarios](docs/CICD.md#change-scenarios) for the full treatment + decision tree.

| Scenario | Trigger | Versioning | Customer | Volumes |
|---|---|---|---|---|
| **1** | Code-only, installer unchanged | Minor (v5.29 → v5.30) | **Re-run EXISTING installer** on disk · same major version | Preserved |
| **2** | Code + installer change (backwards-compatible storage) | **MAJOR (v5.29 → v6.0)** | Download NEW installer · installer flag `WIPE_VOLUMES=false` | Preserved (via installer flag) |
| **3** | Backwards-incompatible storage schema | **MAJOR (v5.29 → v6.0)** | Download NEW installer · installer flag `WIPE_VOLUMES=true` | Wiped → fresh defaults (operator-side backup is manual) |

**Before planning a release**, classify which scenario the change falls into and follow that scenario's discipline. The decision tree at [docs/CICD.md § Decision tree](docs/CICD.md#decision-tree) walks "what did the change touch?" → "which scenario?".

### Agent-behavior contracts that touch CI/CD

The full mechanics are in docs/CICD.md. The agent-behavior contracts below are MANDATORY and codified within this file:

1. **Spec-driven workflow** (§ Spec-driven workflow below) — for any non-trivial change, I MUST verify a GitHub Issue exists (open one if needed) BEFORE touching code; commit messages MUST reference the issue via `Refs #N` or `Closes #N`; I MUST apply mechanical `status:` labels at the right transitions; the smoke-test matrix MUST be posted to BOTH chat AND the issue comment.
2. **Pre-deploy gate** (§ Pre-deploy gate below) — I MUST run `npx tsc --noEmit && npm run lint && npm run build && (cd ../../bundles/spark/mcp && PYTHONPATH=$PWD/src python3 -m pytest tests/ -x)` locally before pushing.
3. **Smoke-test bullet contract** (§ Smoke-test bullet contract below) — every successful `build-dev-installer.yml` run, I MUST share a cumulative smoke-test matrix with the operator in chat (and as an issue comment when issues exist).
4. **Approval phrasing** (§ Approval phrasing below) — I MUST ask explicitly before tagging a customer release; never assume approval from silence.
5. **Post-tag closure deliverable** (§ Release closure report below) — after `release.yml` succeeds, I MUST produce a release closure report AND apply `status:released` + close all referenced issues.
6. **Documentation discipline** (§ Documentation discipline below) — every release ships its docs in the same PR as the code.
7. **Wait-for-CI discipline** (§ Wait-for-CI discipline below — v0.15.5 retrospective) — I OWN the verification end-to-end after every push. Never punt CI-watching to the operator. Watch the build chain, watch the auto-deploy, hit the deployed endpoints, surface any container-vs-image-vs-catalog mismatch BEFORE reporting back. Concurrency-cancel awareness, container-recreation triggers, dev-cycle gaps — all mine to detect.
8. **Feature completeness contract** (§ Feature completeness contract below — v0.15.5 retrospective) — every feature ships as a COMPLETE unit (backend + MCP surface + connector.yaml + agent proxy + UI surface + every JSON endpoint the UI reads + docs) in the SAME sub-release. No "piece-by-piece" delivery. Litmus test: open the UI page on the deployed install + confirm the feature is visible there before declaring it done. **Hardcoded-data audit per release**: grep for static/hand-maintained fallbacks the UI may read from — they drift silently (the v0.15.5 marketplace `toolCount` bug).

### Approval gates summary

| Action | Operator approval needed? |
|---|---|
| `git push origin main` (triggers per-service builds + dev-latest prerelease publish + **auto-deploy on guardian-vm via `build-dev-installer.yml`**) | **NO.** Builds + prerelease publish + dev-cycle install are fully automated. Push freely. |
| **Auto-deploy on guardian-vm** (CI runs `sudo /home/ayman/guardian-installer-dev` as the last step of `build-dev-installer.yml`, v0.6.8+) | **NO.** I do NOT wait for the operator to install. |
| Smoke test via IAP tunnel (read-only) | **NO.** Standard part of the dev loop — runs against the auto-deployed install. |
| Mid-arc iteration: fix smoke-uncovered bug + push next commit | **NO.** Under a multi-release arc the agent iterates autonomously. See § Release-readiness gate below. |
| `git tag vX.Y.Z && git push origin vX.Y.Z` **at arc completion** (triggers release.yml → customer release) | **YES.** Always ask explicitly. AND ONLY when the multi-release arc's capability acceptance check passes end-to-end on the deployed install. |
| `gh release edit vX.Y.Z --notes-file …` | NO — runs after operator approves the tag, before announcing. |

Pattern: **build freely (CI), auto-deploy in the dev cycle (CI), smoke test the auto-deployed code (agent), iterate autonomously inside the arc (no approval between commits), ask before tagging at arc completion (always).**

### "Local-mirrors-customer" — the design principle

The dev path and the customer path use the SAME install ceremony, SAME compose, SAME env file format, SAME install location (`/opt/guardian/`). The only divergence is which image digests get baked into the installer binary at build time. See [`installer/CLAUDE.md`](installer/CLAUDE.md) for the contract and [docs/CICD.md § The two installers](docs/CICD.md#the-two-installers).

### Customer-onboarding access semantics

GHCR enforces pull access **per IMAGE VERSION**, not per package or token scope alone. See [docs/CICD.md § GHCR per-version access](docs/CICD.md#ghcr-per-version-access).

### When CI/CD breaks — failure-mode catalog

When a workflow or install fails in a way that doesn't immediately reveal its cause, **check [docs/CICD.md § CI/CD failure modes + recovery playbook](docs/CICD.md#cicd-failure-modes--recovery-playbook) FIRST.** The catalog covers ~11 patterns we've actually hit. When you encounter a NEW failure mode, add it to the catalog as part of the fix.

### Other operator-facing CI/CD topics

- **Customer onboarding** — [docs/CICD.md § Customer onboarding flow](docs/CICD.md#customer-onboarding-flow-first-time-install).
- **PAT recipes** — [docs/CICD.md § PAT recipes](docs/CICD.md#pat-recipes).
- **Rollback procedure** — [docs/CICD.md § Rollback procedure](docs/CICD.md#rollback-procedure).
- **guardian-updater's role in releases** — [docs/CICD.md § guardian-updater in the release loop](docs/CICD.md#guardian-updater-in-the-release-loop). Also see [`updater/CLAUDE.md`](updater/CLAUDE.md).
- **Monorepo release invariant** — [docs/CICD.md § Monorepo release invariant](docs/CICD.md#monorepo-release-invariant). All 9 images ship at the same `vX.Y.Z`.
- **PR cycle vs main-push cycle** — [docs/CICD.md § PR cycle](docs/CICD.md#pr-cycle-vs-main-push-cycle).

## Agent credential guardrail (MANDATORY)

**The chat agent MUST NOT have any MCP tool in its catalog that reads, writes, mints, or rotates credentials.** Credentials here means: UI auth (admin password), provider auth (Vertex SA JSON, Gemini API key), per-connector instance secrets, API keys plaintext.

Concretely, these tools are **never** `mcp.tool()`-registered in [bundles/spark/mcp/src/usecase/connector_loader.py](bundles/spark/mcp/src/usecase/connector_loader.py)'s `_BUILTIN_LEGACY_TOOLS` list and never reachable via FastMCP from the agent:

- `providers_create`, `providers_update`, `providers_delete`
- `instances_create`, `instances_update`, `instances_delete`
- `api_keys_create`, `api_keys_rotate`, `api_keys_revoke`

These tools remain available at the **REST** surface (`POST /api/v1/providers`, etc.) so the operator UI keeps working. The agent simply has no handle to them. The system-prompt block in `mcp/agent/lib/system-prompt.ts` reinforces with a refusal recipe so the agent explains the boundary when asked.

When adding new MCP tools in future PRs, ask: does this tool read or write a SecretStore value? If yes, REST-only — never register as an `mcp.tool()`.

### Catalog boundary ≠ credential boundary (v0.5.0)

v0.5.0 added agent tools for the **marketplace catalogue** — `marketplace_list`, `marketplace_install`, `marketplace_uninstall`, `connector_upload`. These are intentionally on the **catalog** side of the boundary, NOT the credential side:

| Boundary | What's in it | Agent permission |
|---|---|---|
| **Credential** | SecretStore values: UI password, provider creds, per-instance secrets, API keys plaintext, KEK material | **Forbidden** — no mcp.tool() registered for read OR write |
| **Catalog** | Connector schemas, marketplace install state, registry membership, manifest-level metadata | **Permitted** — agent can read AND mutate via the v0.5.0 tools |

**Why the distinction matters:** catalog operations (*"install the web connector"*, *"upload this connector.yaml"*) are administrative metadata operations that don't touch any secret — the worst case if the agent gets one wrong is a confused operator who has to click Uninstall in the UI. Credential operations (*"create a Vertex provider with this API key"*, *"rotate the XSIAM connector instance's API key"*) are security-relevant — if the agent gets one wrong, a secret either lands in the wrong place or is destroyed.

When adding new MCP tools, ask BOTH questions:
1. **Does this tool read or write a SecretStore value?** If yes → credential side → REST-only.
2. **Does this tool mutate catalog metadata (install state, schemas, registry membership)?** If yes AND #1 is no → catalog side → safe to `mcp.tool()`-register.

A tool can only be on the catalog side if **#1 is no AND #2 is yes**. If both are yes (e.g. a hypothetical "rotate the API key AND mark the connector installed"), split it.

### Operator workflow state — the third category (v0.5.1)

v0.5.1 introduced a third state category distinct from credentials and catalogue:

| Category | Storage | Agent access |
|---|---|---|
| **Credential** | SecretStore (`/app/data/secrets/`) — AES-GCM at rest | **Forbidden** |
| **Catalog** | `marketplace.db` + `instances.db` + manifest | Permitted (catalog tools only) |
| **Operator workflow state** | `operator_state.db` (key-value) | Not exposed today; per-key narrow tools when a use case emerges |

Operator workflow state holds the operator's own UI progress markers that aren't secrets AND aren't platform catalogue: tested-journey marks, saved metric-query bookmarks, future saved filters / favorite skills / chat compose drafts. The shape is intentionally narrow — a key-value table where the hook owns the value's JSON shape.

**Migration discipline**: when a UI surface starts persisting state, ask:
- Is it a secret? → SecretStore, REST-only.
- Is it platform metadata? → `marketplace.db` / `instances.db` / similar, agent-accessible per the catalog rules.
- Is it operator-personal progress that should follow them across devices? → `operator_state.db`, operator-only.
- Is it a device-local UI preference (theme, sidebar collapsed, debug-panel open)? → `localStorage`, NOT in `operator_state.db`.

If you find yourself writing to `localStorage` for anything in category 3, that's a v0.5.1+ regression.

### Operator config-file separation (v0.6.7+)

Two operator-managed config files on a customer install. Each has a precise role; mixing the two is a regression.

| File | Owns | Read by |
|---|---|---|
| **`/opt/guardian/.env`** | Service credentials + the 5 core compose-substitution digests + runtime version marker | `docker compose` + guardian-updater (`/host/.env`) |
| **`/opt/guardian/connector-digests.env`** | Per-connector image pins (`DIGEST_GUARDIAN_CONNECTOR_*`) | guardian-updater ONLY (`/host/connector-digests.env`) |

**Forbidden going forward**: adding `DIGEST_GUARDIAN_CONNECTOR_*` writes to `.env`, adding connector configuration to `.env`, documenting the connector-digest workflow in `.env`. See [`installer/CLAUDE.md`](installer/CLAUDE.md) + [`updater/CLAUDE.md`](updater/CLAUDE.md) for the full contract.

## guardian-vm operator environment

Operational details for working with guardian-vm. CI/CD pipeline mechanics live in [`docs/CICD.md`](docs/CICD.md); this section covers the operator-environment-specific knowledge (VM coordinates, credentials, IAP access) that the agent needs to do anything against guardian-vm.

### VM coordinates

- Project: `cortex-gcp-labs`
- Zone: `us-central1-f`
- Instance: `guardian` (internal IP `10.10.0.17`, no external IP)
- Network tags: `allow-ssh`, `guardian-services`
- Firewall rules: `allow-iap-guardian-services` (tcp 22/3000/8080/8090 from the IAP range `35.235.240.0/20`) + `allow-internal-guardian-services`
- Access path: **IAP tunnel → password SSH** as user `ayman`
- Preinstalled: Docker CE + compose plugin + git
- GitHub Actions runner v2.334.0 named `guardian`, registered to `github.com/kite-production/guardian`, running as the systemd service `actions.runner.kite-production-guardian.guardian` (user `ayman`, member of the `docker` group)

### Credentials — never commit

Credentials live in `.env.vm` at the repo root, which is **gitignored**. Do not paste the password into commits, commands that end up in shell history, scripts that are tracked, or `git log` messages. Load it into the current shell instead:

```bash
set -a && source .env.vm && set +a
```

Required keys: `VM_NAME`, `VM_ZONE`, `VM_PROJECT`, `VM_USER`, `VM_PASSWORD`, `VM_LOCAL_SSH_PORT`, `VM_REMOTE_REPO`.

**`VM_REMOTE_REPO` must point at the live runner workspace.** Set: `VM_REMOTE_REPO=/home/ayman/actions-runner/_work/guardian/guardian`.

**Avoid multi-line values when sourcing.** `set -a && source .env.vm` parses the file as bash; multi-line values (typically service-account JSON) trip on every nested line. Store JSON at `.gcp/service-account.json` (gitignored, mode 0600) and reference: `GOOGLE_APPLICATION_CREDENTIALS="${PWD}/.gcp/service-account.json"`.

### Agent-API auth — authenticate with `GUARDIAN_API_KEY` (v0.17.108+)

The Next.js agent surface (`/api/chat`, `/api/agent/*`, `/api/skills/*`) accepts **API-key bearer auth** as of v0.17.108. The operator minted a superset-scope (`*`) key and stored it as **`GUARDIAN_API_KEY`** in `.env.vm` (gitignored). **Always authenticate to the agent API with this key** — the credential guardrail blocks me from logging in with the admin password, but a bearer key needs no interactive login:

```bash
set -a && source .env.vm && set +a
# Reach the agent's TLS proxy (remote :3000) via an IAP service-port tunnel, then:
curl -sk -H "Authorization: Bearer $GUARDIAN_API_KEY" https://localhost:3000/api/agent/jobs
```

- **Never embed the key value** in any tracked file (this file, commits, `git log`, scripts). It lives ONLY in `.env.vm`; always reference `$GUARDIAN_API_KEY`.
- **Scope model (v0.17.108):** `agent:read` → GETs, `agent:write` → mutations + `/api/chat`, `agent:*` → both, legacy `*` → admin-equivalent. The operator's key is `*`.
- **Security invariant holds even at `*`:** API keys are REFUSED with **403** on credential-management routes (`/api/agent/providers`, `/api/agent/instances`, `/api/agent/api-keys`). Minting/rotating/revoking keys still requires the MCP_TOKEN-gated REST surface — a bearer key can never escalate to manage credentials.

### Standard access pattern (IAP tunnel + password)

The VM has no external IP, so every SSH-like operation goes through a Google IAP TCP tunnel. Canonical session:

```bash
set -a && source .env.vm && set +a

# 1. Open the tunnel in the background
gcloud compute start-iap-tunnel "$VM_NAME" 22 \
  --local-host-port="localhost:$VM_LOCAL_SSH_PORT" \
  --zone="$VM_ZONE" --project="$VM_PROJECT" &
TUNNEL_PID=$!
sleep 3

# 2. Run any remote command with password auth (sshpass reads from env, not argv)
SSHPASS="$VM_PASSWORD" sshpass -e ssh \
  -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  -p "$VM_LOCAL_SSH_PORT" "$VM_USER@localhost" \
  "cd $VM_REMOTE_REPO && docker compose ps"

# 3. Tear the tunnel down when done
kill "$TUNNEL_PID"
```

Prefer `sshpass -e` (reads `SSHPASS` from environment) over `sshpass -p` (exposes password in `ps`).

Interactive shell: `gcloud compute ssh "ayman@$VM_NAME" --zone="$VM_ZONE" --tunnel-through-iap`.

Service-port tunnels (when smoke-testing the deployed UI): see [docs/CICD.md § Smoke-test commands](docs/CICD.md#smoke-test-commands). Local-port mapping intentionally offsets by +1 from the remote port (3001→3000, 8081→8080, 8091→8090) so the operator can run a parallel local dev server on the same port without collision.

Never upload `.env.vm` anywhere — it's local-only. The VM's own `.env` (for `docker compose`) lives at `$VM_REMOTE_REPO/.env` and is managed in the runner's environment + GitHub Secrets, not in the repo.

## Build & release workflow contracts (agent behavior — MANDATORY)

Full pipeline mechanics live in [docs/CICD.md § Build & release workflow](docs/CICD.md#build--release-workflow-mechanics). This section covers the agent-behavior contracts that touch the build/release flow.

### Spec-driven workflow (MANDATORY for non-trivial changes)

Every non-trivial change MUST have a GitHub Issue documenting the spec BEFORE code lands. The issue body becomes the CHANGELOG entry at release time; the labels track lifecycle.

**The agent's responsibilities**:

1. **Before starting any non-trivial work, verify or open an issue.** Open via `gh issue create --template release.md`. If the operator describes a change in chat and there's no issue yet, I open one — body uses the `.github/ISSUE_TEMPLATE/release.md` template's structure. I prefill what I can; the operator applies `status:spec-approved` to greenlight implementation.
2. **Commits reference the issue.** Every commit includes `Refs #N` (work-in-progress) or `Closes #N` (this commit completes the issue) in the message footer. Multiple OK: `Refs #N #M`.
3. **Apply mechanical `status:` labels at the right transitions.** I own `status:in-progress` (first commit), `status:dev-built` (after `build-dev-installer.yml` success), `status:ready-for-testing` (after my own headless smoke passes), and `status:released` (after `release.yml` success). I do NOT apply `status:spec-approved`, `status:testing-complete`, or `status:release-approved` — those are operator decisions.

   **Issue closure rule (v0.5.39+)**: there are TWO closure flavors:
   - **Operator-testable issues** (default for any operator-visible behavior change): I run my own headless smoke, apply `status:ready-for-testing`, AND STOP THERE. **I do NOT close the issue.** Operator runs hands-on smoke + applies `status:testing-complete`. Closure happens at `status:released` via `release.yml`.
   - **Auto-closable issues** (bug fixes with deterministic reproducers, docs-only changes, internal refactors that preserve observable behavior): I close directly via `Closes #N` in the commit message + `status:released` on the next release.
   - **Decision rule**: any new UI surface / API endpoint / operator workflow / operator-facing behavior → operator-testable. Prose rewrites + broken-behavior fixes → auto-closable. **When in doubt: operator-testable.**

   Apply ALL relevant classification labels at creation: one `scenario:*` (required), any `component:*` matching touched paths, any `area:*` matching the feature surface.
4. **Smoke-test matrix goes to BOTH chat AND issue comment.** Cumulative bullets I share when `dev-latest` republishes — also posted as a comment on each open issue in the unreleased queue.
5. **Trivial-change escape hatch.** Issues labeled `scenario:trivial` skip the full spec body. Still respect contained-release discipline. **When in doubt: open a full-spec issue.**
6. **`status:release-approved` is metadata-only (Option A).** Adding the label does NOT trigger automation. Still ask in chat for explicit tag approval.

**Forbidden**:
- Pushing non-trivial code to main without an open issue. Recovery path: open the issue retroactively in the same commit (`Closes #N`).
- Applying operator-owned labels (`status:spec-approved`, `status:testing-complete`, `status:release-approved`) on my own. Prompt: "would you like me to apply `status:release-approved` now?"
- Closing an issue without a release. Issues close when `status:released` applies, which happens only after `release.yml` succeeds.

### Pre-deploy gate (MANDATORY before every push to main)

Before pushing source that triggers any per-service build, run all four locally:

```bash
cd mcp/agent
npx tsc --noEmit                  # type-check (TS)
npm run lint                      # ESLint (TS)
npm run build                     # full Next.js production build — catches strict route validation
cd ../../bundles/spark/mcp
PYTHONPATH=$PWD/src python3 -m pytest tests/ -x   # embedded MCP tests (~7-8s, ~349 tests)
```

**`PYTHONPATH=$PWD/src` is REQUIRED.** Half the test files use `from usecase.X import Y` which needs `src/` on the path.

**Why all four.** `tsc` catches type errors but is happy with stale eslint-disable directives. `lint` catches unconfigured-rule references but doesn't run Next.js's strict Route-type validation. **Only `npm run build` catches everything TS-side**, including strict-route validation. **`pytest` covers the Python embedded MCP side.**

If any fails locally, fix before pushing. CI catches the same things but slower.

### Smoke-test bullet contract (MANDATORY)

**Every time `build-dev-installer.yml` completes successfully and republishes `dev-latest`, I share a smoke-test bullet list with the operator in chat.**

- **WHEN**: at the moment the dev-latest republishes. One bullet list per build-dev-installer success.
- **WHERE**: only in the chat. NOT in `dev-latest` body. NOT in `release-notes.ts`. NOT in CHANGELOG.md.
- **SCOPE**: cumulative — covers every unreleased commit since the last customer `vX.Y.Z`. Resets when a tag fires `release.yml`.
- **SHAPE**: 5-15 operator-facing bullets. Each bullet: specific user-journey action + surface to verify + unambiguous pass/fail signal.
- **SOURCE OF TRUTH**: the unreleased CHANGELOG.md entries' "What ships" + "Files" sections.
- **OUTCOME**: auto-deploy already landed the install on guardian-vm (v0.6.8+). I run the matrix myself via IAP tunnel + report back. Passed → I summarize + operator decides on release approval. Failed → I push a fix; cycle re-runs automatically.

**Forbidden**: skipping the bullet list because "the change is small"; posting bullets that aren't checkable; posting bullets without a corresponding CHANGELOG entry.

### Agent-side headless smoke (MANDATORY before `status:ready-for-testing`)

**The bullets I write are commitments to RUN them.** Pre-v0.5.75 my "headless smoke" was API-shape only — five regressions in a row taught the lesson.

**v0.6.8 auto-deploy contract**: `build-dev-installer.yml` auto-deploys to guardian-vm at the end of every successful run. By the time I'm smoking, the running stack ALREADY matches `HEAD`.

Concretely:
- Monitor `build-dev-installer.yml` to completion.
- Verify version: `ssh guardian 'sudo grep ^GUARDIAN_VERSION /opt/guardian/.env'` matches `git rev-parse --short HEAD`.
- Run bullets against the deployed install via IAP tunnel.

**Going forward, agent-side headless smoke for `dev-built` → `ready-for-testing` requires:**

1. **Execute each bullet I author.** Open the IAP tunnel, hit the actual endpoint or load the actual UI page. Use Playwright or curl. Operator's hands-on is the SECOND validation, not the first.
2. **State verification on every "X happens" bullet.** Pair "submit creates Y" with "GET /api/v1/Y/<id> shows the expected shape." Verify the persisted shape, not just the submit interaction.
3. **End-to-end probe for connector-system changes.** Any change touching `bundles/spark/connectors/**`, `mcp/agent/app/connectors/page.tsx`, `bundles/spark/mcp/src/api/instances.py`, `bundles/spark/mcp/src/usecase/connector_*.py`, or `updater/src/main.py` requires:
   - Resolve any existing connector instance OR create one
   - Hit the agent-side probe via `POST /api/v1/instances/<id>/test`
   - Hit the MCP tool dispatch via `tools/call`
   - Confirm a non-error response or a clean expected error
4. **Dev-cycle gap awareness in the smoke matrix.** When a fix touches `updater/src/main.py` or `guardian-browser/`, the matrix LEADS with: *"This release ships agent-side code that pairs with an updater-side change. The updater image is not rebuilt on the dev cycle — only on customer release tags. Until `vX.Y.Z` ships, the agent-side change works but the end-to-end loop returns `<specific error message>` until then."* DO NOT bury this. **Same trap for the browser sidecar (CDW-F14):** `build-browser.yml` only triggers on `guardian-browser/**` — web-connector source under `bundles/spark/connectors/web/**` triggers `build-connectors.yml` (the connector image) but NOT a browser-image rebuild. And `guardian-browser` is profile-gated (compose `profile=browser`), so it does NOT auto-start on a plain `docker compose up`. If the sidecar container isn't manually running, every `web.*` tool call fails with *"could not connect to browser sidecar"* — verify the container is up before smoking any web-connector change, and LEAD the matrix with this gap when the change is web-only.
5. **Smoke-matrix state-classification.** Each bullet annotated:
   - `✓ agent-verified` — ran through the tunnel + got expected result
   - `⨯ agent-verified-blocked` — known gap prevented full verification; needs operator hands-on
   - `? agent-skipped` — needs operator hands-on as primary verification
6. **Bug-found-in-released-code postmortem.** Every time the operator catches a bug in `dev-built` code my smoke missed, the next release ships a CLAUDE.md/CICD.md addendum naming the specific gap.
7. **Bug-family audit.** When fixing a bug in a connector-system file, audit sibling files in the same release. Identify the bug as a grep expression. Run across `bundles/spark/connectors/*/src/` + `bundles/spark/mcp/src/` + `guardian-connector-runtime/runtime/`. For each hit, fix in the same release OR document the gap inline with a tracking-issue reference. **The fix isn't done until the grep returns no hits or every remaining hit has a documented reason.**

**Forbidden**: claiming `ready-for-testing` without an end-to-end probe per touched subsystem; burying dev-cycle gaps in prose; authoring bullets without an unambiguous pass signal; skipping state-verification on persistence-touching releases.

### Wait-for-CI discipline (MANDATORY — never offload the wait to the operator)

**Codified after the v0.15.5 retrospective.** Operator feedback: *"never say that go check after the build is done to the operator. You have to wait for the build. Check yourself."*

After pushing any commit, **I own the verification end-to-end**. Don't punt to the operator with "watch CI", "refresh in 5 min", "let me know when deployed". The operator already gave me the work; they shouldn't have to babysit my deploy.

Concretely, after every push that produces an operator-visible change:

1. **Watch the build chain to completion** — `gh run watch <id>` in the background or polling. Don't ask the operator to wait for me.
2. **Watch the auto-deploy** — `build-dev-installer.yml` runs `sudo /home/ayman/guardian-installer-dev` on guardian-vm at the end of the build chain (v0.6.8+). Verify it actually ran by checking `GUARDIAN_VERSION` on the VM.
3. **Verify the change is live** — for backend changes, hit the relevant REST endpoint via the bearer + IAP tunnel. For UI changes, fetch the page or read the affected JSON endpoint and confirm the rendered/served content matches expectations.
4. **Catch dev-cycle gaps before reporting back** — if the agent image rebuilt but the connector image didn't (or vice versa), surface this AS PART OF MY REPORT. The R5 cascade-cancel CI bug was undetected because I assumed the build chain "just worked" after each push.
5. **Concurrency-cancel awareness.** GitHub Actions cancels in-progress workflows on the same branch when a newer commit pushes. If I'm shipping a multi-sub-release arc, the connector-build workflow may get cancelled before completing — I must either (a) pace pushes so each connector-build finishes (~3-5 min apart) OR (b) re-dispatch `Build connectors` after the final arc push to ensure the final state has a published image. **Failing silently because CI cancelled is on me, not on the operator.**
6. **Container vs image vs catalog mismatch is mine to detect.** When guardian-updater doesn't auto-recreate a connector container after a digest change, I MUST trigger the restart via `POST /api/v1/connectors/<connector_id>/instances/<instance_name>/start` on the updater (port 8090, with the bearer + `{"instance_id": "<uuid>"}` body). Operator should never have to ask me "is the new image actually running?"

**Phrasing forbidden in responses to the operator**:
- ❌ "Wait for the CI build to finish + I'll check then"
- ❌ "Refresh in a few minutes to see the change"
- ❌ "Let me know when it's deployed"
- ❌ "When the build catches up, the X will be visible"
- ✅ Instead: do the wait myself (via background watcher + ScheduleWakeup if cross-session), verify the deployed state, then report results.

**Operator-side commands are only acceptable for**: hands-on UI smoke that requires the operator's session cookie (credential guardrail blocks me from logging in) — and even then I should pre-verify the underlying REST endpoints so the operator's smoke is "is it pretty" not "is it working".

### Feature completeness contract (MANDATORY — UI ships with the backend)

**Codified after the v0.15.5 retrospective.** Operator feedback: *"never forget the UI updates for each feature that we introduce. When I ask for a feature, I want everything to be delivered. I don't want to keep getting pieces and pieces of things."*

Every feature ships as a **complete unit**: backend, MCP surface, UI surface, agent-side proxies, docs. **No piece-by-piece delivery.** A "feature" is operator-defined — when the operator says "add X" the deliverable is "the operator can use X end-to-end."

**Before declaring a feature sub-release complete, I must verify ALL of these were touched:**

1. **Backend** — Python in `bundles/spark/mcp/src/`, connector source under `bundles/spark/connectors/<id>/src/`, or wherever the logic lives.
2. **MCP surface (if applicable)** — new MCP tool registered, or REST endpoint added under `bundles/spark/mcp/src/api/`.
3. **`connector.yaml` (if a connector tool was added)** — entry in `spec.tools[]` matching the new function. Otherwise the agent's catalog won't see it.
4. **Agent-side proxy (if a new REST endpoint was added)** — `mcp/agent/app/api/agent/<resource>/route.ts` that forwards to the MCP via `resolveMcp()`. UI code can't reach the MCP directly.
5. **UI surface** — every operator-visible feature gets a UI affordance in the SAME release. New page → `app/<feature>/page.tsx` + sidebar entry. New action → button/modal/panel on the relevant existing page. **The R4/R5 "Show Tools" panel + ToolsTogglePanel was correct, but the v0.15.5 bug — operator seeing stale tool counts on the cards — happened because the `/api/marketplace/connectors` HARDCODED data was forgotten. Every operator-visible JSON endpoint that the UI reads from must be audited when a feature lands.**
6. **Hardcoded-data audit** — when a feature changes the shape, count, or list of something the UI displays, grep for ALL paths the UI could read that data from. `grep -rn "<entity-name>" mcp/agent/app/api/` catches static/hardcoded fallbacks that drift. Pre-v0.15.5 the `/api/marketplace/connectors` route had a hand-maintained `toolCount` array that nobody updated as R4/R5 expanded the surface. **The check that would have caught it: `curl /api/marketplace/connectors | jq '.[] | {id, toolCount}'` before declaring R5 complete.**
7. **Docs + journeys** — per the existing § Documentation discipline + § Pre-release docs checklist, every operator-visible change updates `/help/architecture`, `/help/user`, `mcp/agent/lib/journeys.ts`, `CHANGELOG.md`, `mcp/agent/lib/release-notes.ts`.
8. **Smoke matrix probe + endpoint audit per release** — the smoke matrix must include EVERY endpoint the UI reads for the feature's data. If the feature has a `toolCount` shown in the UI, the matrix asserts the deployed `toolCount` is correct from the actual route the UI consumes.

**Forbidden — these are anti-patterns that surfaced during R4/R5**:
- ❌ "Backend infrastructure ships now; UI lands in v0.X.Y+1" — every feature ships its UI in the same sub-release, not a follow-on
- ❌ Validating a feature via a NEW endpoint while the UI continues to read a DIFFERENT (stale) endpoint
- ❌ "The UI will pick it up automatically" without checking the data path the UI actually reads
- ❌ Adding new MCP tools without verifying they appear in the marketplace catalog endpoint that the cards display

**Litmus test before declaring a feature done**: open the relevant UI page on the deployed install, take a screenshot OR fetch the API endpoint the UI reads, and confirm the feature's deliverable is visible there. If I can't see it on the UI, the feature isn't done.

### Approval phrasing (MANDATORY)

**Tagging happens at CAPABILITY completion, not at COMMIT completion.** See § Release-readiness gate below.

When ready to release at the END of a multi-release arc, ask plainly:

> "v0.6.5N completes the `<capability>` arc. End-state acceptance check passed on the deployed install: `<one-line summary of what the operator can now do>`. **Approve release of vX.Y.Z?**"

Then wait. Do not proceed on silence, on a thumbs-up emoji on a previous message, or on inferred consent from earlier "go ahead" instructions about implementation work.

**Approval is for the tag, not for the build, deploy, or smoke test.** Build workflows + auto-deploy + smoke tests run without operator approval. Only `git tag vX.Y.Z && git push origin vX.Y.Z` (which fires `release.yml` → publishes to GHCR) needs explicit go-ahead.

**Mid-arc commits NEVER trigger the approval phrasing.** Asking "approve v0.6.52?" mid-arc is a category error — the arc is still in flight; the tag fires at arc completion.

### Release-readiness gate (MANDATORY — use case complete before tagging)

A customer release tag is appropriate **only when the user-facing capability the release is meant to deliver is working end-to-end on the deployed install** — not when individual commits' smoke bullets pass.

**Agent behavior under a multi-release arc**:

1. **Iterate the dev cycle autonomously.** Each commit goes through pre-deploy gate → push → CI build → auto-deploy → agent-side smoke → fix-and-push next iteration. **No operator approval between iterations.**
2. **Smoke-uncovered bugs are fixed inline, not deferred.** If smoke uncovers a bug — even outside the current commit's stated scope — file the fix as the NEXT iteration of the SAME arc.
3. **Tag only on capability completion.** Run the end-state acceptance check (declared at arc-open time in the FIRST commit's CHANGELOG entry). When ALL bullets pass end-to-end AND docs reflect the capability, ask for tag approval.
4. **Mid-arc commits get CHANGELOG entries, not release tags.** Each entry names the prerequisite role: *"v0.6.5M is a prerequisite for the `<capability>` arc; the capability ships in v0.6.5N."*
5. **Arc declaration goes in the FIRST commit.** CHANGELOG entry includes a "Capability acceptance criteria" section enumerating end-state checks.

**Forbidden**: asking "approve tag?" between arc iterations; deferring an arc-blocking smoke-uncovered bug; tagging mid-arc commits as if standalone; skipping CHANGELOG entries for mid-arc commits.

### Post-tag closure deliverable

After `release.yml` reports `success`, BEFORE I announce the release URL, I MUST produce a release closure report in chat (see § Release closure report template below).

## Pre-build context refresh (MANDATORY — every build)

**Before starting work on any new build (issue, feature, fix), refresh context by reading the docs that describe what was already implemented and how it's specified.** Guardian is an enterprise product; drift between code, spec, UI, and docs is the single largest source of regressions. The way to prevent drift is to enter every build with current knowledge of what exists.

### What to read before touching code

For any non-trivial build, open and skim ALL of:

| Doc | Why |
|---|---|
| **`CHANGELOG.md`** (last 3-5 entries) | Recent operator-language deltas. |
| **`mcp/agent/lib/release-notes.ts`** (last 3-5 entries) | Version-bundled bullets shipped to customers. |
| **`mcp/agent/app/help/architecture/page.tsx`** | Canonical SPEC for substrate behavior. |
| **`mcp/agent/app/help/user/page.tsx`** | User-facing feature descriptions, tagged by version. |
| **`mcp/agent/lib/journeys.ts`** | Click-paths through the product. |
| **`mcp/agent/app/observability/**`** | Runtime-introspection surfaces. |

The 5-15 minutes of skim-time pays for itself ten times over by preventing "oh, that already existed, I just re-built it differently" drift.

### Pre-build context refresh fits where in the dev cycle?

```
new task / issue / feature
   ↓
PRE-BUILD CONTEXT REFRESH
   ↓
plan code changes that conform to the spec
   ↓
local edit → local pre-deploy gate → git push → CI build → auto-deploy → smoke test
   ↓
DOCS CHECKLIST → ASK FOR APPROVAL → git tag → release.yml
```

The "read before code, write after build" pattern is symmetric. Skip either side and the drift returns.

<!-- [guardian v0.1.0] Retired: § Data-source validation doctrine — the marketplace data-sources catalog, its validation skill, and the synthetic-log delivery doctrine were removed when Guardian was carved out of the upstream platform -->

## Architecture page is the spec (MANDATORY — read before editing)

[mcp/agent/app/help/architecture/page.tsx](mcp/agent/app/help/architecture/page.tsx) is the **canonical specification** for how Guardian's substrate behaves. It describes the target state — not just what the code currently does. When the code and the architecture page disagree, **the architecture page wins** and the code is the gap that needs fixing.

**Before editing any of the following code paths, READ the architecture page sections that govern them:**

| Code path | Required architecture-page section |
|---|---|
| `app/api/setup/*`, `app/setup/page.tsx`, `lib/runtime-config.ts`, `app/api/agent/providers/config/*`, `app/providers/page.tsx`, `app/api/auth/change-password/*`, `app/profile/page.tsx` | `#setup-wiring` |
| Connector instances | `#instance-store`, `#setup-wiring` |
| Provider instances | `#provider-store`, `#setup-wiring` |
| TLS, cert generation, SSL_CERT_PEM/SSL_KEY_PEM, /tls/ volume | `#tls-proxy` |
| Per-instance connector containers | `#connector-containers` |
| MCP / agent topology, ports, auth surface | `#stack` |
<!-- [guardian v0.1.0] Retired row: Data sources / #data-sources — subsystem removed when Guardian was carved out of the upstream platform -->

**The rule**: if about to change behaviour in any of those areas, open the architecture page first and confirm what you're about to do conforms to the spec. If it doesn't, EITHER update the code to match the spec, OR get explicit operator approval to update the spec itself + update the page in the same PR.

**Don't silently drift.** When the architecture page describes target state the code doesn't yet meet, the gap goes in the section's `Implementation gap` subsection. If you fix one, remove the bullet in the same PR — the gap list is a living checklist, not a permanent record.

## Documentation discipline (MANDATORY — every release)

Every release ships a coherent platform: code, **and** the docs that explain it. Backend changes that aren't reflected in the UI surfaces and help pages are bugs — silent gaps that confuse users and rot under future work.

### Pre-release docs checklist

Before tagging any `v*.*.*`, every backend feature merged since the last release must have:

1. **Architecture page reflects reality** ([mcp/agent/app/help/architecture/page.tsx](mcp/agent/app/help/architecture/page.tsx)). Service list matches `docker compose ps -a`. Every new service has a section with container name, source path, runtime, host ports, role, **explicit inter-service connections**. Removed services are removed. Volume mounts, build args, env-var contracts current.
2. **User guide reflects every operator-visible feature** ([mcp/agent/app/help/user/page.tsx](mcp/agent/app/help/user/page.tsx)). For every PR adding a UI affordance, a corresponding paragraph or subsection. Tag new content with the introducing version. **Removed/changed features need their description updated or removed in the same PR.**
3. **User journeys cover every documented flow** ([mcp/agent/lib/journeys.ts](mcp/agent/lib/journeys.ts)). Each journey is a click path. Add when a flow ships; retire when a flow goes away.
4. **Observability surfaces reflect runtime reality** ([mcp/agent/app/observability/](mcp/agent/app/observability/)). Silent telemetry that doesn't surface in observability is rot waiting to happen.
5. **Skills page (`mcp/agent/app/skills/page.tsx`) in sync with on-disk skills.** Hardcoded `SKILLS: SkillDef[]` array IS allowed to lag (live fetch covers current state) but clean up when it drifts.
6. **No backend feature without a UI surface (or a documented deferral).** For every new MCP tool / `/api/agent/*` endpoint / config knob: either (a) a UI page or panel, or (b) a code comment + help-docs note "API-only for now, UI tracked in `<issue>`". Silent endpoints rot.

6a. **No new UI page without a sidebar nav entry in the SAME release** (v0.5.49 retrospective). Grep test before committing: `find mcp/agent/app -maxdepth 3 -name 'page.tsx' | xargs dirname | sort` vs the `href:` entries in `mcp/agent/components/sidebar.tsx`'s `navEntries`. Every page (except redirects + `[param]` dynamic routes) should appear. If deliberately operator-hidden, document with a code comment near `export default`.

7. **Release notes describe user-visible deltas — in BOTH places.** [CHANGELOG.md](CHANGELOG.md) (long-form, operator language). [mcp/agent/lib/release-notes.ts](mcp/agent/lib/release-notes.ts) (3-7 highlights, ~10-15 words each, **newest first**). They ship together; customers see them on upgrade.
8. **Spec drift is fixed in the same PR, not deferred.** "I'll fix this in a follow-up" is the lie that ships documented-but-broken features.
9. **MCP tool docstrings stay in lockstep with UI forms.** When a UI form field is added/changed/removed on a system-management page, the matching MCP tool's docstring (`bundles/spark/mcp/src/usecase/builtin_components/self_mod_tools.py`) MUST be updated in the same PR. The agent picks fields by reading the docstring, not just the signature. **Operator-visible UI form changes without docstring updates are silent capability gaps.**

   For a new UI form field: identify the matching MCP tool. Add to docstring Args: parameter name, type, default, what it does, **when the agent should set it** (concrete trigger phrases work — *"set when the operator says 'don't ask me each time'"*). For discriminated-union actions, update the example shapes. For destructive parameters, flag in the docstring.

## Release closure report — vX.Y.Z

After `release.yml` reports `success`, BEFORE announcing the release URL, produce this 5-section report in chat:

```
## Release closure report — vX.Y.Z

### Help docs landed
- /help/architecture#<anchor> — added/rewritten section: <one-line>
- /help/user#<anchor> — added/rewritten section: <one-line>
  (if no help-docs change: "no operator-visible behavior change; help docs unchanged")

### Journeys landed
- <id>:journeys.ts — added/retired: <one-line>
  (if none: "no operator-visible flow added/retired; journeys.ts unchanged")

### Release notes landed
- CHANGELOG.md — v<X.Y.Z> entry: <one-line>
- mcp/agent/lib/release-notes.ts — same entry, customer-readable in About modal

### Image digests published
- guardian-agent@<digest> [REBUILT|RETAGGED from v<prev>]
- (all images)

### Operator review checklist
- [ ] https://localhost:3001/help/architecture#<anchor> — new content renders
- [ ] https://localhost:3001/help/user#<anchor> — new content renders
- [ ] About modal — v<X.Y.Z> highlights present
- [ ] gh release view v<X.Y.Z> — installer + sha256 + tarball + manifest all attached
```

**SOURCE OF TRUTH**: `git diff vX.Y.Z-1..vX.Y.Z -- mcp/agent/app/help mcp/agent/lib/journeys.ts CHANGELOG.md mcp/agent/lib/release-notes.ts`. If the diff shows changes I didn't name, the report is incomplete. If it shows no changes in a claimed category, the work didn't land — the release is broken and needs a follow-up tag.

**Forbidden**: skipping the report because "the release was small"; populating it from imagination without opening the docs to confirm; treating it as customer-facing (it's an internal review aid).

## Quality-first principle (MANDATORY — enterprise product)

Guardian is an **enterprise product**. The bar for code quality is not "the test passes"; it's "the change fits cohesively into the existing architecture, the spec stays consistent, and the next person inheriting it doesn't have to untangle a shortcut."

When fixing issues during a build, the priority order is:

1. **Standard architecture first.** If the existing pattern in the codebase solves your problem, use it. New abstractions must be justified explicitly and wired into existing infrastructure, not alongside.
2. **Clean cohesive builds over random patching.** "Minimal-diff fix" is only minimal if it's also coherent. Patching one symptom while leaving the root cause unchanged creates compounding debt.
3. **Spec consistency over speed.** Drift from the architecture page → update the page in the same PR OR back out the change.
4. **No "I'll fix it in a follow-up" debt** unless explicitly tracked with an issue + a code comment.
5. **Token / effort cost is not a reason to take a shortcut.** Burn the tokens, take the longer code path. If a clean fix needs 3x the diff size, it's still the right fix.

### Concrete anti-patterns to avoid

- **Stapling instead of integrating.** New endpoint duplicating 70% of an existing one — refactor the existing one instead.
- **Symptom suppression.** try/except that swallows an unexpected error to make the test pass. Investigate.
- **Magic-number config.** Wire through `pydantic-settings` from the start.
- **Drive-by partial documentation.** Updating CHANGELOG but not release-notes.ts; updating architecture but not user-guide. Either do the full doc cycle or don't claim the build is done.
- **"It works on my machine."** Guardian is a multi-container stack. Always smoke-test against guardian-vm post-deploy.

### Inter-service connections — emphasize these

When updating architecture docs, **the connections between services matter as much as the services themselves**. For every service-to-service call document:

- Source service + outgoing port
- Destination service + listening port
- Auth mechanism (bearer token? cookie? mTLS? unauthenticated?)
- Failure mode (retries? circuit breaker? graceful degrade?)
- Whether the call is sync or async

Example: *`guardian-agent` (Next.js, port 3000) → embedded MCP subprocess (Python FastMCP, port 8080) — bearer auth via `MCP_TOKEN`, in-process loopback over HTTPS, ~5s timeout, no retry. The agent proxies every `/api/agent/*` call to the MCP at `/api/v1/*` via [lib/mcp-proxy.ts](mcp/agent/lib/mcp-proxy.ts).*

Boxes-with-labels diagrams are not enough. Drift hides in the wires.

## Canonical-state discipline (MANDATORY — v0.4.0 retrospective, applies to every future refactor)

The v0.4.0 authentication redesign collapsed 5 separate auth-state stores into 1, deleted every legacy fallback path, and shipped clean documentation + journeys + diagrams + observability coverage in the SAME release. Codifying the five rules so the next refactor argues against the same principles instead of relearning them.

### Rule 1 — One state surface = one storage home

Every persisted value lives in **exactly one** place. No fallback chains, no env-var override at the read path, no "try X first, fall back to Y." The architecture page documents that one home; the code reads from it without compatibility shims.

**Before adding new persisted state**: *"Where will this value live? Is there an existing surface that owns this concept already? If two surfaces could own it, which one becomes canonical and which one becomes a delete?"* The wrong answer is "both, with sync between them."

### Rule 2 — When you refactor a state surface, delete the legacy paths in the SAME release

Migration code is a regression magnet: more branches than the new path, more failure modes, operators trip on it for years after the cutover. Concrete v0.4.0 example: when the `SecretStore` hash path became canonical, the `setup.json` plaintext compare path didn't get a deprecation warning — it was deleted from the route handler, env vars deleted from compose, `setup.json` deleted from the repo + install kit, and the operator-facing `/setup` page deleted entirely.

**Safety requirement**: a complete operator-facing communication plan (CHANGELOG + release-notes + architecture #section + user-guide #section + journeys) AND a fresh-volume install test on guardian-vm before the deletion lands.

**Does NOT require**: automatic migration tooling. Operators get clear release notes + a CLI to recover.

### Rule 3 — Derive runtime state from observable evidence, not env vars that mid-process scripts mutate

The v0.4.0 CLI reset bug: `entrypoint.sh` correctly flips `MCP_URL` from `http:` to `https:` in its own process scope. But `docker exec` inherits the **image's original env config** (unflipped), not the entrypoint's in-process mutation. The CLI trusted `MCP_URL`, POSTed plain HTTP to a TLS-only listener, got `other side closed`.

Fix: derive from **observable filesystem state** instead. The CLI now checks `existsSync("/tls/cert.pem")` — the cert is physically on disk, independent of which process tree you arrived through.

**General principle**: env vars are fragile across process boundaries. If a code path can be invoked from outside the entrypoint's process tree (`docker exec`, sidecars, debuggers), it must derive runtime state from observable evidence (file existence, cert presence, lockfile content).

### Rule 4 — Customer-facing surfaces don't carry developer context

Design context (what we're building toward, why a feature is limited, internal references) goes in code comments OR the developer-facing architecture page OR CHANGELOG.md — **not on customer-facing UI pages**. The customer-facing path for "how do I reset my password" is the user guide at `/help/user#authentication`, not a paragraph wedged into `/profile`.

**Practical test before shipping any UI text**: would a customer who installed the product yesterday be confused by this sentence? If it references "v0.4.0 vs roadmap," internal mechanics, or "we used to do X but now we do Y," it doesn't belong on a customer-facing page.

### Rule 5 — Retire docs + journeys + diagrams in the SAME release that retires the code

Deleting a host script isn't done until the journey that walked operators through running it is also retired. Otherwise six months later an operator finds the stale journey via google, types the command, gets "command not found," and has no idea what's authoritative.

**Stub-comment over silent deletion**: a retired journey ID stays in `journeys.ts` as a `// [v0.4.0] Retired: <id>. Replaced by <new-id> because <reason>` comment, NOT a raw `git rm`. Same for architecture-page sections. The comment is a breadcrumb for future debugging.

### How to apply this rule to a future refactor

1. **Enumerate every storage location** the current state lives in.
2. **Pick ONE as canonical.** The others become deletes, not stale-fallback shims.
3. **Plan the deletion calendar**: what code gets deleted, what env vars get removed from compose, what files get removed from the install kit, **AND what CI workflows / release scripts / installer templates reference the file.** The cheap check: `grep -rn <filename> .github/ installer/ scripts/ mcp/agent/lib/ mcp/agent/app/help/` BEFORE declaring the deletion plan complete.
4. **Plan the docs calendar**: architecture-page section to rewrite, user-guide section, journeys to retire, CHANGELOG + release-notes entries, diagrams.
5. **Plan the observability surface**: what events does the new path emit? Are they visible in `/observability/events`?
6. **Test the full operator path on guardian-vm** via the customer-mirror dev installer (NOT `docker compose up -d --force-recreate`).
7. **Same release ships** code deletion + docs replacement + journey retirement + diagram update.

If you find yourself thinking "I'll delete the legacy fallback later" or "the docs can lag one release," you're recreating the v0.3.x trap. **Do it together or don't do it at all.**
