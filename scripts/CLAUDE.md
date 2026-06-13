# `scripts/` — maintainer research + build tooling

This directory contains **maintainer-side scripts**. They are NOT part of the customer-facing Guardian runtime, NOT installed on customer machines, and NOT triggered by any customer action.

**Repo-wide rules live in the [root CLAUDE.md](../CLAUDE.md)**. This file holds only conventions LOCAL to `scripts/`.

## What goes here, what does NOT

| Belongs in `scripts/` | Does NOT belong in `scripts/` |
|---|---|
| Research tools that harvest data once per upstream refresh | Anything that runs at customer install/upgrade time |
| YAML/bundle builders that produce committed artifacts | Anything customers' running stack imports at runtime |
| One-shot migrations + cohort cleanups | Service code (use `mcp/agent/`, `bundles/spark/mcp/`) |
| Validation + audit checks the maintainer runs before shipping | Tooling that bakes into a Docker image |

If a script is consumed by service-runtime code, the runtime code is broken. Refactor the dependency out.

## How to tell whether a new script belongs here

Ask: *"Does a customer install ever run this code?"*

- **No** → `scripts/`. Document what the output is and where it lands in the runtime tree.
- **Yes** → NOT `scripts/`. Pick the right runtime module: `mcp/agent/`, `bundles/spark/mcp/`, or `bundles/spark/connectors/<id>/`.

If the answer is *"only if the operator runs it manually"* — still `scripts/`. Operator-invoked maintenance ≠ customer-runtime.

## Script catalogue

| Script | Purpose | Cadence |
|---|---|---|
| `agent_lifecycle.sh` | Compose lifecycle wrapper: start/stop/restart/status/health/logs/apply-setup | Manual, dev loop |
| `backup_guardian.sh` | Archive `guardian_mcp_data` + `guardian_mcp_skills` volumes + the `.guardian-agent/` runtime dir into a manifest-carrying tarball | Manual, before risky upgrades |
| `restore_guardian.sh` | Restore a `backup_guardian.sh` tarball onto this or another host | Manual, disaster recovery |
| `check-vm-compose.sh` | Diff local `docker-compose.yml` against the copy deployed on guardian-vm — catches silent VM drift before a sync | Manual, pre-sync gate |
| `guardian_tunnels.sh` | Manage the IAP tunnels to guardian-vm (ssh 22, agent 3000, mcp 8080) with start/stop/status/smoke | Manual, dev loop |
| `ci_bootstrap_setup_body.py` | Build the placeholder JSON body CI POSTs to `/api/v1/setup` (XSIAM + Vertex placeholders, non-destructive `replace: false`) | Auto, CI bootstrap |
| `e2e_xdr_tools_battery.py` | Catalog-presence + toggle-filter battery against the deployed cortex-xdr connector tools | Per-release, manual |
| `e2e_xsiam_tools_battery.py` | Same battery shape for the xsiam connector tools | Per-release, manual |
| `refresh_cortex_baked_catalog.py` | Re-bake `bundles/spark/connectors/cortex-content/baked/` from upstream demisto/content (logos, pack metadata, schemas, manifest) | Manual, ~quarterly |
| `export_spark_agent_bundle.sh` | Validate + package `bundles/spark/` into `dist/<name>.tar.zst` with checksums | Manual, bundle publishing |
| `validate_spark_bundle.py` | Structural validation of the `bundles/spark/` tree (invoked by the exporter; runnable standalone) | Paired with export |
| `generate_bundle_manifest.py` | Create a file manifest + optional HMAC signature for a bundle directory | Paired with export |
| `loop/loop_state.py` | The loop's on-disk memory writer (`.guardian-loop/state.json` + `docs/loop/state.md`); `init`/`record`/`render` | Auto, every loop cycle |
| `loop/run_gate.sh` | Runs the full Guardian gate (tsc/lint/build · mcp+updater pytest · validator) | Auto, loop VERIFY step + manual |
| `bootstrap_loop_jobs.sh` | Codify + (re)provision the autonomous investigation-loop scheduler jobs — `guardian-incident-seeder` + `guardian-investigation-loop` + `guardian-investigation-judge` (the v0.2.12 self-improvement evaluator); idempotent upsert via the agent jobs API. DEV/DEMO harness — seeds synthetic XSOAR incidents | Manual, after a fresh install / volume wipe |
| `loop/loop_bootstrap.sh` | One-time clone provisioning (npm ci + repo-root .venv + deps) | Manual, VM provisioning |
| `loop/guardian_loop.sh` | launchd payload: guard → reset clone → best-effort tunnel → run headless `claude -p` against the playbook | Auto, nightly LaunchAgent |

(CI's only script dependency outside this directory is `.github/scripts/push-with-retry.sh` — it does not live here.)
