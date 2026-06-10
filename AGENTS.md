# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## What Guardian is

Continuous SOC simulation platform: synthetic security log generation, scenario-based MITRE ATT&CK telemetry, and AI-orchestrated red/blue workflows over MCP. Ships as a 4-service Docker Compose stack.

## Remote-first workflow (MANDATORY)

**All builds, deploys, tests, and container runs happen on the remote `guardian` VM in GCP — never on the local workstation.** The local repo is for editing and version control only. Docker is not expected to run locally.

### VM coordinates

- Project: `cortex-gcp-labs`
- Zone: `us-central1-f`
- Instance: `guardian` (internal IP `10.10.0.81`, no external IP)
- Firewall tag: `allow-ssh`
- Access path: **IAP tunnel → password SSH** as user `ayman`

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

### All common commands, rewritten for remote execution

Every "command" in the sections below is meant to run **inside the VM**, either via an interactive SSH session or wrapped in the `sshpass -e ssh … "<cmd>"` form above. Do not run them on the workstation.

```bash
# Full stack
… "cd $VM_REMOTE_REPO && docker compose up -d"
… "cd $VM_REMOTE_REPO && docker compose ps"
… "cd $VM_REMOTE_REPO && docker compose logs -f guardian-mcp"
… "cd $VM_REMOTE_REPO && docker compose down"

# MCP server tests
… "cd $VM_REMOTE_REPO/bundles/spark/mcp && pytest"

# Agent lint/build
… "cd $VM_REMOTE_REPO/mcp/agent && npm run lint"
```

Local-only operations: editing files, `git` on the tracked repo, reading logs you already pulled down. Everything else → remote.

## Stack topology

| Service (container) | Source | Language | Host port | Purpose |
|---|---|---|---|---|
| `guardian` | [main.py](main.py), [app/](app/) | Python 3.12 (FastAPI + Strawberry GraphQL) | 8999 → 8000 | Log generator + streaming worker engine |
| `guardian-mcp` (`guardian_mcp`) | [bundles/spark/mcp/](bundles/spark/mcp/) | Python 3.12 (FastMCP) | 8080 | MCP tools for Guardian, XSIAM (PAPI), CALDERA |
| `guardian-agent` (`guardian_agent`) | [mcp/agent/](mcp/agent/) | Next.js 15 + React 19 | 3000 | Chat UI, skills browser, Gemini/Vertex orchestration |
| `caldera` | prebuilt image `aymanam/caldera:5.3.0` | — | 8888, 8443, etc. | Red-team operations backend |

Container-to-container URLs (use in `.env`, not `localhost`):
- `XLOG_URL=http://xlog:8000`
- `MCP_URL=http://guardian-mcp:8080/api/v1/stream/mcp`
- `CALDERA_URL=http://caldera:8888`

## Command reference (runs on the VM — wrap with the SSH pattern above)

```bash
# Full stack
cd "$VM_REMOTE_REPO" && docker compose up -d
cd "$VM_REMOTE_REPO" && docker compose ps
cd "$VM_REMOTE_REPO" && docker compose logs -f guardian-mcp
cd "$VM_REMOTE_REPO" && docker compose down

# Root GraphQL app (standalone, on the VM)
cd "$VM_REMOTE_REPO" && pip install -r requirements.txt
cd "$VM_REMOTE_REPO" && python main.py                # uvicorn on 0.0.0.0:8000, 4 workers

# MCP server (standalone — has its OWN deps)
cd "$VM_REMOTE_REPO/bundles/spark/mcp" && ./run.sh           # creates venv, installs via poetry, runs src.main
# OR manually:
cd "$VM_REMOTE_REPO/bundles/spark/mcp" && python -m venv venv && source venv/bin/activate && \
  pip install -r requirements.txt && PYTHONPATH=src python src/main.py

# MCP server tests
cd "$VM_REMOTE_REPO/bundles/spark/mcp" && pytest
cd "$VM_REMOTE_REPO/bundles/spark/mcp" && pytest tests/test_config.py::test_settings_defaults

# Next.js agent
cd "$VM_REMOTE_REPO/mcp/agent" && npm ci
cd "$VM_REMOTE_REPO/mcp/agent" && npm run dev          # :3000
cd "$VM_REMOTE_REPO/mcp/agent" && npm run build && npm run start
cd "$VM_REMOTE_REPO/mcp/agent" && npm run lint

# Force-reseed MCP skills (overrides volume with image defaults)
cd "$VM_REMOTE_REPO" && docker compose run --rm -e FORCE_SKILLS_SYNC=1 guardian-mcp
```

Service endpoints, when tunneled: use `gcloud compute start-iap-tunnel guardian <remote-port> --local-host-port=localhost:<local-port>` to reach them from your browser — e.g., tunnel `3000→3000` for the agent UI, `8080→8080` for the MCP server, `8999→8999` for GraphQL, `8888→8888` for Caldera.

## Architecture that isn't obvious from the tree

### GraphQL + in-process workers (`guardian` service)

- [main.py](main.py) mounts Strawberry GraphQL at `/` on the FastAPI app.
- [app/schema.py](app/schema.py) defines all queries/mutations. **Active workers are stored in a module-level `workers = {}` dict** — no persistence. Restarting the `guardian` container drops every streaming worker; `listWorkers` is per-replica.
- Log synthesis comes from the external `rosetta-ce` library (`Events`, `Observables`, `Sender`) — not in this repo. Format types, scenario shapes, and worker I/O are declared in [app/types/](app/types/) (`datafaker.py`, `scenarios.py`, `sender.py`).
- Webhook sender uses header `Authorization: <WEBHOOK_KEY>` (raw, not `Bearer`) — see `_get_webhook_headers` in `app/schema.py`. Any non-XSIAM webhook receiver must accept that form.
- Scenario files live in `scenarios/ready/*.json`. `createScenarioWorker` takes the filename **without `.json`**. For inline scenarios use `createScenarioWorkerFromQuery` instead.

### MCP server (`guardian-mcp` service)

- Entry: [bundles/spark/mcp/src/main.py](bundles/spark/mcp/src/main.py). Registers ~80 tools in one block inside `async_main` — `mcp.tool()(module.fn)` per tool. Add new tools by importing from `usecase/builtin_components/` and calling `mcp.tool()` there.
- Layout is intentional (clean-architecture flavor):
  - `src/config/config.py` — pydantic-settings, reads env vars via `validation_alias`.
  - `src/service/guardian_bundles/spark/mcp.py` — FastMCP instance factory.
  - `src/usecase/builtin_components/` — tool implementations (`data_faker`, `workers`, `scenarios`, `xsiam_tools`, `caldera_tools`, `simulation_skills`, `skills_crud`, `observables_catalog`, `field_info`).
  - `src/pkg/` — shared clients: `graphql_client` (talks to `guardian` service), `papi_client` (XSIAM), `caldera_factory`, `xql_rag_service` (chromadb + sentence-transformers for XQL examples retrieval).
- Transports: `MCP_TRANSPORT=stdio` (default in Dockerfile) or `streamable-http`. HTTP path is configurable via `MCP_PATH` (default `/api/v1/stream/mcp`).
- SSL: supports file paths (`SSL_CERT_FILE`/`SSL_KEY_FILE`) OR inline PEM with `\n` escapes (`SSL_CERT_PEM`/`SSL_KEY_PEM`). When PEM env is used, `main.py` writes tempfiles and cleans up via `atexit`.

### Skills library — volume-seeded

The MCP image builds skills into `/app/skills-default/` and `docker-compose.yml` mounts volume `guardian_mcp_skills` at `/app/skills`. [bundles/spark/mcp/entrypoint.sh](bundles/spark/mcp/entrypoint.sh):
1. On first run (empty volume), copies `skills-default/*` → `/app/skills/`.
2. On subsequent runs, leaves volume content alone — **edits to `bundles/spark/mcp/skills/*.md` in the repo do not appear in a running container unless you `docker compose down -v` (drops volume) or set `FORCE_SKILLS_SYNC=1`**.

Skill categories under `bundles/spark/mcp/skills/`: `foundation/`, `scenarios/`, `validation/`, `workflows/`. The `skills_crud` and `simulation_skills` MCP tools operate on the mounted `/app/skills/` inside the container.

### Agent (`guardian-agent` service)

- Next.js App Router ([mcp/agent/app/](mcp/agent/app/)). API routes under `app/api/{auth,chat,skills}`.
- Authenticates MCP calls with `MCP_TOKEN` (shared secret). `UI_USER` + `UI_PASSWORD` gate the UI itself.
- Gemini via `GEMINI_API_KEY`; Vertex AI via `GOOGLE_APPLICATION_CREDENTIALS` (GCP service account JSON).
- Build arg `ANIMATED` (default `true`) toggles the animated UI variant and is exposed at runtime via `NEXT_PUBLIC_ANIMATED`.

## Configuration

Two unrelated config surfaces:

1. **[config.yml](config.yml)** (root) — read by the GraphQL `guardian` service for worker count, log rotation, XSIAM mandatory/optional parsed fields. Mostly overridden by env vars (`WORKERS_NUMBER`, `LOGGING_*`, `XSIAM_*`), see [app/config.py](app/config.py).
2. **`.env`** (root, copy from `.env.example`) — the primary knob. Loaded by `docker compose`. Critical keys:
   - Shared auth: `MCP_TOKEN`
   - XSIAM PAPI: `CORTEX_MCP_PAPI_URL`, `CORTEX_MCP_PAPI_AUTH_HEADER`, `CORTEX_MCP_PAPI_AUTH_ID`, `PLAYGROUND_ID` (issue-war-room ID for remote execution context)
   - CALDERA: `CALDERA_URL`, `CALDERA_API_KEY`, `CALDERA_RED_USER`, `CALDERA_RED_PASSWORD` (required — compose uses `:?` to hard-fail without them)
   - Webhook: `WEBHOOK_ENDPOINT`, `WEBHOOK_KEY` (see header note above)
   - Agent defaults: `TECHNOLOGY_STACK` (JSON string; `log_destination.full_address` is used as default sink when the user doesn't specify one)
   - SSL: `SSL_CERT_PEM` / `SSL_KEY_PEM` as one-line values with `\n` escapes (README documents the `openssl` + `awk` recipe)

## Conventions to preserve

- When adding an MCP tool, keep the registration in [bundles/spark/mcp/src/main.py](bundles/spark/mcp/src/main.py) (one `mcp.tool()(...)` line per tool) and implement it under `src/usecase/builtin_components/`. Config goes through `src/config/config.py` (pydantic-settings with `validation_alias`), not raw `os.environ`.
- Worker type enums, faker format enums, and observable enums are defined in [app/types/datafaker.py](app/types/datafaker.py) / [app/types/sender.py](app/types/sender.py). New log formats or destinations require touching both the Strawberry enum and the dispatch in [app/schema.py](app/schema.py).
- The GraphQL endpoint is the single source of truth for log generation; the MCP server calls it via `graphql_client.py`. Do not duplicate faker logic into the MCP layer.
