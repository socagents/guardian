# `updater/` — guardian-updater daemon

The `guardian-updater` customer container — manages per-instance connector container lifecycle + stack-level upgrades. No exposed ports; talks to Docker via `/var/run/docker.sock` and to the agent via `GUARDIAN_AGENT_INTERNAL_URL`.

**Repo-wide rules live in the [root CLAUDE.md](../CLAUDE.md)** — change scenarios, contained-release discipline. This file holds only conventions LOCAL to guardian-updater.

## Layout

| Path | What it is |
|------|------------|
| `src/main.py` | The daemon — reconciliation loop + endpoint server. |
| `Dockerfile` | Python 3.12 + docker-py + minimal deps. |
| `requirements.txt` | Runtime deps. |
| `tests/` | pytest suite. |

## Role (v0.5.20+)

guardian-updater's primary production role is **per-instance connector container lifecycle management**:
- When an operator creates an instance via `/connectors` → agent → REST, guardian-updater pulls the connector image + starts the container.
- When the operator deletes the instance, guardian-updater stops + removes the container.
- On boot, guardian-updater auto-spawns missing per-instance containers (v0.6.66 reconciliation).
- On digest drift (the image referenced by an instance differs from the running container's digest), guardian-updater reconciles by re-creating the container with the new digest.

Pre-v0.5.20 guardian-updater also drove an in-UI Update button for Scenario 1 upgrades; that path is removed. **Customer upgrades happen via the installer ONLY.**

## Per-instance container naming

`guardian-connector-<connector-id>-<instance-name>` — e.g. `guardian-connector-xsiam-primary-xsiam`. Connect from the agent via:

```
http://guardian-connector-<id>-<name>:9000
```

Network: all containers join `guardian_default` (the compose network). guardian-updater attaches each per-instance container to that network at create time.

## Config-file separation (v0.6.7+)

guardian-updater reads TWO mounted files from the host:

| File | Mount path | Owns |
|---|---|---|
| `/host/.env` | bind mount | Service credentials + the 3 core stack-service digests + `GUARDIAN_VERSION` |
| `/host/connector-digests.env` | bind mount | Per-connector image pins (`DIGEST_GUARDIAN_CONNECTOR_*`) |

**The split is load-bearing (v0.6.7+):** see [`../installer/CLAUDE.md`](../installer/CLAUDE.md) for the install-side contract.

**Legacy fallback (v0.6.7 transition only):** if `/host/connector-digests.env` is missing, guardian-updater reads `DIGEST_GUARDIAN_CONNECTOR_*` from `/host/.env` and logs a deprecation warning. This one-shot path covers the brief window between a pre-v0.6.7 guardian-updater image still running and a v0.6.7+ installer applying the new file layout. After one successful install cycle the legacy path goes silent.

**Forbidden going forward**: Re-introducing connector-digest reads from `.env`. The split exists for a reason.

## Dev-cycle deployment (v0.6.12+)

guardian-updater **is** rebuilt + deployed on the dev cycle, same as the agent. `Build updater` runs on every push that touches `updater/**`, and `build-dev-installer.yml` resolves the new `:dev` updater digest from GHCR + bakes it into the dev install, so the auto-deploy recreates the `guardian_updater` container with the new image. **Verified (v0.17.128):** a `src/main.py` change deployed to guardian-vm in the same dev cycle and the recreated container ran the new code. Smoke updater fixes directly on guardian-vm — do NOT gate on a customer-release tag.

> Pre-v0.6.12 the updater was customer-release-only; that constraint no longer applies. See `build-dev-installer.yml` — the `Build updater` trigger (workflows list) + the `for SVC in … guardian-updater` digest-resolution loop. (This section previously claimed the opposite; corrected after the v0.17.128 reconcile-gap fix confirmed dev-cycle deployment.)

## Tests

```bash
cd updater
python3 -m pytest -x
```

## Architecture-page spec

guardian-updater's behavior is specified in [mcp/agent/app/help/architecture/page.tsx](../mcp/agent/app/help/architecture/page.tsx) `#guardian-updater` section. Any behavior change here MUST be reflected there in the same PR (root § Architecture page is the spec).
