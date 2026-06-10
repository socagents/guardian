# Guardian — All-in-One Quickstart

> **Audience:** the single operator (or demo author) who wants the
> whole Guardian stack — agent, browser sidecar, connectors — running
> on **one host** from the repo-root compose.

<!-- [guardian v0.1.0] Retired: split-deploy.md reference + the "agent vs simulation backends on separate machines" deployment shape — simulation subsystem removed; Guardian's only first-party deployment shapes are this local-dev compose and the customer installer (see CICD.md). -->

---

## What you get

```
┌────────────────────────────────────────────────────────────────────┐
│ One Docker host                                                    │
│                                                                    │
│  ┌──────────────────────────────┐    ┌──────────────────────────┐  │
│  │ guardian-agent               │    │ guardian-browser         │  │
│  │  ├─ Next.js UI         :3000 │───►│ headless Chromium (CDP)  │  │
│  │  └─ Embedded MCP       :8080 │    │  :9222 — profile-gated   │  │
│  └──────────────┬───────────────┘    └──────────────────────────┘  │
│                 │ outbound HTTPS                                   │
│                 ▼                                                  │
│   Cortex XSIAM tenant API · Google Vertex AI / Gemini              │
└────────────────────────────────────────────────────────────────────┘
```

`guardian-agent` ships both the Next.js UI and the embedded MCP per the
spark-agents v1.2 bundle design (one image, two processes, single trust
boundary). `guardian-browser` stays down until you enable its compose
profile — only the web connector needs it.

---

## Prerequisites

- Docker Engine 24+ with `docker compose` v2.
- ~12 GB free disk for images + volumes.
- A web browser to log in to the agent UI.
- (Recommended) A Gemini API key from [Google AI Studio](https://aistudio.google.com/) **OR** a GCP service-account JSON for Vertex AI.
- (Recommended) A Cortex XSIAM tenant with API-key credentials so the agent's XSIAM tools have something to talk to.

---

## First-run flow

```bash
# 1. Clone
git clone https://github.com/kite-production/guardian.git
cd guardian

# 2. Generate the operator-supplied secrets:
#      MCP_TOKEN          — bundle-internal coordination token. Pin
#                           in .env to keep it stable across restarts.
#      GUARDIAN_SECRET_KEK — 32-byte AES-256-GCM key for encrypting
#                           secrets at rest. Without this, the
#                           SecretStore refuses to construct.
#      GUARDIAN_DEFAULT_ADMIN_PASSWORD — seeds the admin login hash
#                           on first boot (fresh volume only). The
#                           agent refuses to boot without it.
{
  echo "MCP_TOKEN=$(openssl rand -hex 32)"
  echo "GUARDIAN_SECRET_KEK=$(openssl rand -base64 32)"
  echo "GUARDIAN_DEFAULT_ADMIN_PASSWORD=$(openssl rand -hex 12)"
} > .env
chmod 600 .env

# 3. Bring up the stack
docker compose up -d
# Optional — bring up the browser sidecar too (web connector only):
# docker compose --profile browser up -d guardian-browser

# 4. Wait for healthy (~60 seconds for first boot, less on subsequent)
until [ "$(docker inspect -f '{{.State.Health.Status}}' guardian_agent 2>/dev/null)" = "healthy" ]; do
  sleep 3
done

# 5. Open the UI (self-signed cert — accept the browser warning)
echo "→ Open https://$(hostname):3000 in your browser"
```

Log in as `admin` with the `GUARDIAN_DEFAULT_ADMIN_PASSWORD` value from
your `.env`, change the default password when the banner asks, then
configure:

| Surface | What to fill in |
|---|---|
| **`/providers`** | A model provider — Gemini API key from Google AI Studio, or a Vertex AI service-account JSON (project + region + SA JSON) |
| **`/connectors`** | Connector instances per your environment. For the XSIAM connector: `api_url` (PAPI base URL), `api_id` (X-Auth-ID), the `api_key` secret slot, and optionally `playgroundId` / `webhookEndpoint` + `webhookKey` |

Guardian materializes one connector instance per binding (Phase 5
SecretStore-backed), reloads its tool registry, and the agent's chat
can start calling the connector tools.

---

## Verify the deploy

```bash
# Smoke test the capability surface against your stack.
MCP_TOKEN=$(docker compose exec -T guardian-agent printenv MCP_TOKEN) \
  ./bundles/spark/mcp/scripts/smoke_test.sh
```

Expected: all checks PASS, no skips. If any check fails, the script
reports which capability and why.

You can also confirm each service is reachable:

```bash
docker compose exec -T guardian-agent curl -sk https://localhost:3000/api/auth/status
docker compose exec -T guardian-agent curl -sf http://localhost:8080/ping/
```

---

## Common operations

### Apply settings overrides

```bash
TOKEN=$(docker compose exec -T guardian-agent printenv MCP_TOKEN)
curl -X PUT http://localhost:8080/api/v1/settings \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"updates": {"requireHumanApprovalForOperations": true}, "actor": "operator"}'
```

Settings are persisted to `<data_root>/settings.db` and survive restarts.

### Mint a scoped API key for an external integration

```bash
TOKEN=$(docker compose exec -T guardian-agent printenv MCP_TOKEN)
curl -X POST http://localhost:8080/api/v1/api_keys \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"label":"siem-poller","scopes":["audit:read"],"actor":"ayman"}'
# Response includes "key": "guardian_ak_..." — copy it now; not recoverable.
```

### Update credentials later

Edit the instance on `/connectors` and resubmit. The instance store
updates atomically; old credentials are deleted from the SecretStore.
The audit log records every rotation with the operator who initiated it.

### Backup before upgrades

```bash
scripts/backup_guardian.sh --label pre-upgrade
# → ./guardian-backup-pre-upgrade-<UTC stamp>.tar.gz
```

### Stop the stack

```bash
docker compose down
# Volumes (guardian_mcp_data, guardian_mcp_skills, guardian_tls) persist.
# Add -v to drop them — destructive.
```

---

## Production installs

This quickstart is the **repo-root local-dev recipe** (`:local` image
tags, built on your machine). Customer/production installs use the
single-file `guardian-installer` instead — digest-pinned images, the
guardian-updater lifecycle daemon, and host-side recovery utilities.
See [`CICD.md` § Customer onboarding flow](CICD.md#customer-onboarding-flow-first-time-install).

---

## Troubleshooting

### Container marks itself unhealthy

```bash
docker compose logs guardian-agent | grep ERROR
```

Common causes:
- `guardian_mcp_data` volume not writable (filesystem permissions on the host)
- Embedded MCP failed to import a connector source — usually means the image was built against a different bundle version than what's currently in `/app/bundle`. Rebuild or pull a fresh image.

### Smoke test reports connector/provider failures

Connector- and provider-dependent checks require connector instances +
a configured model provider. If you skipped those, the corresponding
tools won't be advertised and these tests will be the first to fail.
Create the missing instances on `/connectors` and `/providers`.

### "MCP_TOKEN is not configured" at the API surface

The entrypoint normally generates an ephemeral MCP_TOKEN if `.env`
doesn't pin one. If the agent starts but the token never gets set,
check `docker logs guardian_agent | grep MCP_TOKEN` for the
entrypoint's bootstrap line.
