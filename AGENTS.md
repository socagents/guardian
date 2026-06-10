# AGENTS.md

This file provides guidance to coding agents (Codex and others) when working with code in this repository.

## What Guardian is

AI incident-response agent for Cortex XSIAM/XSOAR: investigates security incidents over MCP — evidence gathering, XQL queries, case/issue enrichment, and response orchestration. Ships as a Docker Compose stack of three core services (`guardian-agent`, `guardian-browser`, `guardian-updater`) plus per-instance connector containers created at runtime.

<!-- [guardian v0.1.0] Retired: SOC-simulation description (synthetic log generation, red/blue workflows) — simulation subsystem removed -->

## Remote-first workflow (MANDATORY)

**All builds, deploys, tests, and container runs happen on the remote `guardian` VM in GCP — never on the local workstation.** The local repo is for editing and version control only. Docker is not expected to run locally.

### VM coordinates

- Project: `cortex-gcp-labs`
- Zone: `us-central1-f`
- Instance: `guardian` (internal IP `10.10.0.17`, no external IP)
- Firewall tags: `allow-ssh`, `guardian-services` (IAP range → tcp 22, 3000, 8080, 8090)
- Access path: **IAP tunnel → password SSH** as user `ayman`
- GitHub Actions runner: registered against `kite-production/guardian`, installed at `/home/ayman/actions-runner`, runs as a systemd service

### Credentials — never commit

Credentials live in `.env.vm` at the repo root, which is **gitignored** (see `.gitignore`). Do not paste the password into commits, commands that end up in shell history, scripts that are tracked, or `git log` messages. Load it into the current shell instead:

```bash
set -a && source .env.vm && set +a
```

Required keys in `.env.vm`: `VM_NAME`, `VM_ZONE`, `VM_PROJECT`, `VM_USER`, `VM_PASSWORD`, `VM_LOCAL_SSH_PORT`, `VM_REMOTE_REPO`.

### Standard access pattern (IAP tunnel + password)

The VM has no external IP, so every SSH-like operation goes through a Google IAP TCP tunnel. Canonical session:

```bash
set -a && source .env.vm && set +a

# 1. Open the tunnel in the background (localhost:$VM_LOCAL_SSH_PORT -> guardian:22)
gcloud compute start-iap-tunnel "$VM_NAME" 22 \
  --local-host-port="localhost:$VM_LOCAL_SSH_PORT" \
  --zone="$VM_ZONE" --project="$VM_PROJECT" &
TUNNEL_PID=$!
sleep 3    # give the tunnel a moment to bind

# 2. Run any remote command with password auth (sshpass reads from env, not argv)
SSHPASS="$VM_PASSWORD" sshpass -e ssh \
  -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  -p "$VM_LOCAL_SSH_PORT" "$VM_USER@localhost" \
  "cd $VM_REMOTE_REPO && docker compose ps"

# 3. Tear the tunnel down when done
kill "$TUNNEL_PID"
```

Prefer `sshpass -e` (reads `SSHPASS` from environment) over `sshpass -p` (exposes the password in `ps` output).

Interactive shell (one-shot, no tunnel juggling):
```bash
gcloud compute ssh "ayman@$VM_NAME" --zone="$VM_ZONE" --tunnel-through-iap
```
Note: `gcloud compute ssh` installs an SSH key into instance metadata and does not use `VM_PASSWORD`. Use it only when a key-based interactive shell is acceptable; use the `start-iap-tunnel` + `sshpass` form above when password auth is required or when scripting.

### Syncing code to the VM

Edit locally, sync to `$VM_REMOTE_REPO` on the VM, then run there. Two options:

- **Git pull on the VM** (preferred when changes are committed):
  ```bash
  SSHPASS="$VM_PASSWORD" sshpass -e ssh -p "$VM_LOCAL_SSH_PORT" "$VM_USER@localhost" \
    "cd $VM_REMOTE_REPO && git pull"
  ```
- **rsync over the tunnel** (for uncommitted work):
  ```bash
  SSHPASS="$VM_PASSWORD" rsync -az --delete \
    -e "sshpass -e ssh -p $VM_LOCAL_SSH_PORT -o StrictHostKeyChecking=no" \
    ./ "$VM_USER@localhost:$VM_REMOTE_REPO/"
  ```

Never upload `.env.vm` to the VM — it's local-only. The VM's own `.env` (for `docker compose`) lives at `$VM_REMOTE_REPO/.env` and is managed separately on the VM.

## Stack topology

| Service (container) | Source | Language | Host port | Purpose |
|---|---|---|---|---|
| `guardian-agent` | [mcp/agent/](mcp/agent/) + [bundles/spark/mcp/](bundles/spark/mcp/) | Next.js 15 + React 19, embedded Python 3.12 FastMCP subprocess | 3000 (UI), 8080 (MCP) | Chat UI + embedded MCP — one container, two processes, TLS proxy in front |
| `guardian-browser` | [guardian-browser/](guardian-browser/) | headless Chromium | internal (CDP) | Browser sidecar for the `web` connector, profile-gated |
| `guardian-updater` | [updater/](updater/) | Python 3.12 | 8090 | Per-instance connector container lifecycle + stack upgrades |
| connector containers | [bundles/spark/connectors/](bundles/spark/connectors/) on the [guardian-connector-runtime/](guardian-connector-runtime/) base | Python 3.12 | internal | One per materialized connector instance (`xsiam`, `cortex-xdr`, `cortex-docs`, `cortex-content`, `web`) |

The embedded MCP is part of the agent's trust boundary, not a sibling service — the Next.js side proxies every `/api/agent/*` call to it over loopback with `MCP_TOKEN` bearer auth.

## Command reference (runs on the VM — wrap with the SSH pattern above)

```bash
# Full stack
cd "$VM_REMOTE_REPO" && docker compose up -d
cd "$VM_REMOTE_REPO" && docker compose ps
cd "$VM_REMOTE_REPO" && docker compose logs -f guardian-agent
cd "$VM_REMOTE_REPO" && docker compose down

# MCP server tests (PYTHONPATH=src is REQUIRED — tests import `from usecase.X`)
cd "$VM_REMOTE_REPO/bundles/spark/mcp" && PYTHONPATH=$PWD/src python3 -m pytest tests/ -x
cd "$VM_REMOTE_REPO/bundles/spark/mcp" && PYTHONPATH=$PWD/src python3 -m pytest tests/test_config.py -x

# Next.js agent
cd "$VM_REMOTE_REPO/mcp/agent" && npm ci
cd "$VM_REMOTE_REPO/mcp/agent" && npm run dev          # :3000
cd "$VM_REMOTE_REPO/mcp/agent" && npm run build && npm run start
cd "$VM_REMOTE_REPO/mcp/agent" && npm run lint

# Force-reseed default skills (overrides volume content with image defaults)
cd "$VM_REMOTE_REPO" && docker compose run --rm -e FORCE_SKILLS_SYNC=1 guardian-agent
```

Local-only operations: editing files, `git` on the tracked repo, reading logs you already pulled down. Everything else → remote.

Service endpoints, when tunneled: use `gcloud compute start-iap-tunnel guardian <remote-port> --local-host-port=localhost:<local-port>` to reach them from your browser — e.g., tunnel `3000` for the agent UI, `8080` for the MCP server, `8090` for the updater.

## Architecture that isn't obvious from the tree

### Embedded MCP server (inside `guardian-agent`)

- Entry: [bundles/spark/mcp/src/main.py](bundles/spark/mcp/src/main.py) — registers the `/api/v1/*` REST routes and the tool catalogs inside `async_main`.
- Built-in tools live in `src/usecase/builtin_components/` (`cognitive_tools`, `skills_crud`, `self_mod_tools`) and are registered from the `_BUILTIN_LEGACY_TOOLS` list in [src/usecase/connector_loader.py](bundles/spark/mcp/src/usecase/connector_loader.py). Connector tools are registered dynamically at boot per materialized connector instance — a connector's tools are advertised ONLY once an instance exists.
- **Credential guardrail (MANDATORY)**: `providers_*`, `instances_*`, and `api_keys_*` create/update/delete/rotate are NEVER `mcp.tool()`-registered — they stay REST-only so the chat agent has no handle to credentials. See root [`CLAUDE.md`](CLAUDE.md) before adding any tool.
- Layout is intentional (clean-architecture flavor): `src/config/config.py` (pydantic-settings, env via `validation_alias`), `src/service/` (FastMCP factory), `src/usecase/` (stores + tool logic), `src/api/` (REST routes), `src/pkg/` (shared helpers like `connector_proxy.py`).
- Transports: `MCP_TRANSPORT=stdio` (default) or `streamable-http`. HTTP path configurable via `MCP_PATH` (default `/api/v1/stream/mcp`).

### Skills library — volume-seeded

Default skills ship in the image and seed a volume-mounted `/app/skills` on first boot (per-release marker controls re-merge). **Edits to `bundles/spark/mcp/skills/*.md` in the repo do not appear in a running container** unless the volume is dropped or `FORCE_SKILLS_SYNC=1` is set.

Skill categories under `bundles/spark/mcp/skills/`: `foundation/` (`cortex_kb_search`, `cortex_kb_search_patterns`, `cortex_kb_api_reference`, `cortex_xql_query_authoring`) and `workflows/` (`build_xql_query`). The `skills_crud` MCP tools operate on the mounted `/app/skills/` inside the container.

### Agent (Next.js side of `guardian-agent`)

- Next.js App Router ([mcp/agent/app/](mcp/agent/app/)). Feature pages live directly under `app/`; API routes under `app/api/{auth,chat,skills,marketplace,agent}`.
- Authenticates MCP calls with `MCP_TOKEN` (shared secret). The `/api/agent/*` routes are thin proxies via [mcp/agent/lib/mcp-proxy.ts](mcp/agent/lib/mcp-proxy.ts).
- Gemini via API key; Vertex AI via a GCP service-account JSON — both materialized through the provider setup flow, not env vars.
- TLS terminates at [mcp/agent/tls-proxy.js](mcp/agent/tls-proxy.js) in front of UI (3000) + MCP (8080).

### Connectors

Each connector under [bundles/spark/connectors/](bundles/spark/connectors/) is one directory: `connector.yaml` (tool specs — `spec.tools[]` MUST match the functions in `src/`), `Dockerfile`, `src/`. The agent dispatches tool calls to per-instance connector containers over HTTP; the `guardian-updater` (port 8090) creates/recreates those containers.

## Configuration

**No env vars for behavior.** The operator fills out the first-run setup form; values land in the SecretStore (secrets) and sqlite metadata stores (everything else). What remains in `.env` on an install: service credentials (e.g. `MCP_TOKEN`), the compose image digests (`DIGEST_*`), and the runtime version marker. Per-connector image pins live in `connector-digests.env`, read by the updater only — see [installer/CLAUDE.md](installer/CLAUDE.md) and [updater/CLAUDE.md](updater/CLAUDE.md) for the two-file contract.

## Conventions to preserve

- When adding a built-in MCP tool, implement it under `bundles/spark/mcp/src/usecase/builtin_components/` and register it in `connector_loader.py`'s `_BUILTIN_LEGACY_TOOLS`. First ask the credential/catalog boundary questions in root [`CLAUDE.md`](CLAUDE.md) — credential-touching tools are REST-only, never `mcp.tool()`-registered. Config goes through `src/config/config.py` (pydantic-settings with `validation_alias`), not raw `os.environ`.
- When adding a connector tool, the `connector.yaml` `spec.tools[]` entry and the `src/` function ship together — otherwise the agent's catalog won't see it.
- Every operator-visible change ships its UI surface + help docs + journeys in the same release (feature completeness contract — see root [`CLAUDE.md`](CLAUDE.md)).
