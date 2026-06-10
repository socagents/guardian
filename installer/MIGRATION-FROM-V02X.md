# Migrating from Phantom v0.2.x → v0.3.0+

v0.3.0 introduces **image digest pinning** — a structural change that
swaps tag-based image references (`image: foo:0.2.4`) for content-digest
references (`image: foo@sha256:abc…`) in the customer compose file. The
operator-visible win is real: containers are now recreated by docker
compose **iff their image content actually changed**, not when a
version label is bumped. Caldera retains in-memory red-team operation
state, xlog retains streaming workers, phantom-agent retains in-flight
sessions — all across upgrades that don't touch their source.

The cost is a one-time migration. The compose file shape changes, so
the **first** v0.2.x → v0.3.0 hop recreates every container. Subsequent
v0.3.x → v0.3.x+1 upgrades are selective.

This document walks through the migration. Read it once; the actual
work takes about 5 minutes for a healthy install.

---

## What changes

| Surface | v0.2.x | v0.3.0+ |
|---|---|---|
| `image:` reference shape | `image: ghcr.io/…/svc:${PHANTOM_VERSION}` | `image: ghcr.io/…/svc@${DIGEST_PHANTOM_<SVC>}` |
| `.env` controls version | `PHANTOM_VERSION=0.2.4` | `PHANTOM_VERSION=0.3.0` PLUS 10 `DIGEST_PHANTOM_*` lines |
| `--upgrade-to` flag on installer | works for any version | sealed to the binary's stamped version |
| Container recreation on upgrade | always recreates all | recreates only services whose digest changed |
| In-memory state across upgrade | always lost | preserved when image content unchanged |

## What stays the same

- All operator data: secrets store, KEK, UI password, GHCR token, setup
  form values, chat sessions persisted to disk, audit log, jobs.
- All named volumes (caldera_data, xlog_data, phantom_mcp_data,
  phantom_mcp_skills, phantom_tls, phantom_operator_creds,
  phantom_agent_runtime).
- The first-run setup wizard's collected values (XSIAM tenant, model
  API keys, webhook destinations, etc.).
- File-system layout: `/opt/phantom/{docker-compose.yml,.env}` plus
  the named volumes Docker manages.

## What's lost in the one-time hop

- **Caldera in-memory state**: any active red-team operation is dropped.
  Operations queued or persisted on disk remain (caldera writes to
  `/usr/src/app/data` which is a named volume), but the in-process
  `Operations` registry resets.
- **xlog active streaming workers**: the module-level `workers = {}`
  dict is process-scoped; restart drops every active worker.
- **phantom-agent in-flight chat sessions**: any open browser tab with
  an active streaming response loses the stream (the assistant turn is
  not persisted until the stream completes, so partial output is gone;
  earlier turns persisted to the session store are kept).

These are the same things you'd lose on any container restart. The
difference vs. pre-v0.3.0 is that subsequent v0.3.x → v0.3.x+1 upgrades
**won't** lose them when the affected service's image content didn't
change.

---

## Migration steps

### 0. Prerequisites

You'll need:
- SSH access to the host running Phantom.
- Sudo on that host (the install dir is `/opt/phantom`).
- A v0.3.x phantom-installer binary or install kit. Download from the
  GitHub Release for v0.3.0+:

  ```sh
  gh release download v0.3.0 --repo kite-production/phantom \
    --pattern phantom-installer
  chmod +x phantom-installer
  ```

  (Or, for the multi-file kit:
  `gh release download v0.3.0 --pattern 'phantom-installer-0.3.0.tar.gz'`,
  extract, then run `./install.sh` from the extracted directory.)

### 1. (Optional) Quiesce active state

Stuff worth saving before the recreation:

- **In-flight caldera operations**: stop them via the caldera UI, or
  make a note of the red-team plan so you can re-run after upgrade.
- **Streaming xlog workers**: note their config (data class, count,
  rate, observables) so you can re-create. v0.3.0 also adds the
  `bootstrap_dataset_fields` skill which can re-seed common patterns
  in ~10 seconds.
- **Open chat sessions**: let any in-flight tool-using turn complete
  before starting the upgrade.

Skip this step if your install is idle.

### 2. Run the v0.3.x installer

```sh
sudo ./phantom-installer
```

The installer detects your existing `/opt/phantom/.env`, preserves
all secrets / KEK / UI password / registry token, **strips the stale
`PHANTOM_VERSION=` line**, and **appends the v0.3.0 manifest** (one
new `PHANTOM_VERSION=` line + 10 `DIGEST_PHANTOM_*` lines).

You'll see a notice like:

```
! v0.2.x → v0.3.0 migration detected
!   Pre-v0.3.0 installs used tag-based image refs. v0.3.0+ uses
!   digest pinning, which means this upgrade is a one-time
!   recreation of ALL containers as the compose file's image-ref
!   shape changes…
```

Followed by the standard install flow:
1. The installer stops the existing stack (clean break before the
   shape change).
2. Pulls the new images by digest (typically ~30s if your daemon
   has the previous version's bytes cached, longer for a cold pull).
3. `docker compose up -d --remove-orphans` brings the new stack up.
4. Waits for `phantom-agent` to report healthy.

Total wall-clock: ~2-5 minutes depending on image-cache freshness.

### 3. Verify

After the installer reports `✓ Phantom v0.3.0 is running.`:

```sh
# Confirm the new compose file has digest refs (not tag refs):
grep -c '@\${DIGEST_PHANTOM_' /opt/phantom/docker-compose.yml
# → expect 5 (xlog, caldera, browser, updater, agent)

# Confirm .env has the manifest section:
grep -c '^DIGEST_PHANTOM_' /opt/phantom/.env
# → expect 10 (5 stack + 5 per-instance connector)

# Confirm running containers are pinned by digest:
docker inspect phantom_agent --format '{{.Config.Image}}'
# → ghcr.io/kite-production/phantom-agent@sha256:abc...

# Open the agent UI and check the observability panel:
# https://<your-host>:3000/observability/connectors
# → should show 5 stack-tier rows with green "digest" badges
```

### 4. (Optional) Re-establish active state

- Caldera: re-launch any red-team operations you stopped in step 1.
- xlog: re-create the streaming workers, or run the
  `bootstrap_dataset_fields` skill to seed the standard pattern set.

---

## Subsequent upgrades

After the v0.3.0 baseline, each phantom-installer binary is sealed
to a single version. To upgrade from v0.3.0 → v0.3.1:

```sh
gh release download v0.3.1 --repo kite-production/phantom \
  --pattern phantom-installer
chmod +x phantom-installer
sudo ./phantom-installer
```

The installer:
1. Detects an existing v0.3.x install (sees `DIGEST_PHANTOM_*` lines
   in `.env`).
2. Strips the stale digests, appends the v0.3.1 manifest.
3. Runs `docker compose pull` (only changed digests get fetched).
4. Runs `docker compose up -d` — compose recreates only the services
   whose digest changed; containers with unchanged digests keep
   running, retaining their in-memory state.

You can also use the in-app updater: click "Update now" in the agent
UI sidebar. Same end result; the phantom-updater service handles
manifest fetch + .env write + selective recreate.

---

## If something goes wrong

| Symptom | Most likely cause | Fix |
|---|---|---|
| `pull access denied` after starting installer | GHCR token expired or scope insufficient | Re-paste the token when prompted (or set `PHANTOM_REGISTRY_TOKEN` env var before invoking) |
| `invalid reference format` on `compose up` | `.env` is missing `DIGEST_PHANTOM_*` values | Re-run installer; the strip + append is idempotent |
| `phantom-agent` doesn't become healthy | Caldera's `service_healthy` dependency timed out | `docker compose -f /opt/phantom/docker-compose.yml logs caldera` — the conf-rewrite logic on first boot can take ~60s; bumping `HEALTH_TIMEOUT_SECS` env when invoking the installer helps |
| One service recreated when its digest didn't change | The compose file or `.env` was hand-edited between releases | Compose-drift sanity: `diff /opt/phantom/docker-compose.yml ./docker-compose.yml` (the installer's bundled version). Re-run installer to reconcile |
| Want to roll back to v0.2.x | v0.3.0 is forward-only; v0.2.x installers cannot install v0.3.0 manifest | Download a v0.2.x phantom-installer + manually clean `/opt/phantom/.env` of `DIGEST_*` lines before running |

---

## What changed under the hood (for the curious)

If you're operationally curious about the wiring:

- The release pipeline ([`.github/workflows/release.yml`](https://github.com/kite-production/phantom/blob/main/.github/workflows/release.yml))
  captures every image's digest after `docker push` and writes a
  manifest file (`release-manifest-vX.Y.Z.env`).
- The phantom-installer build script
  ([`installer/build-phantom-installer.sh`](https://github.com/kite-production/phantom/blob/main/installer/build-phantom-installer.sh))
  embeds the manifest verbatim into the installer binary at build time.
- The customer compose
  ([`installer/docker-compose.yml`](https://github.com/kite-production/phantom/blob/main/installer/docker-compose.yml))
  references each image as `@${DIGEST_PHANTOM_<SVC>}` with a fail-loud
  fallback (`sha256:invalid_digest_run_installer_first`).
- The phantom-updater service
  ([`updater/src/main.py`](https://github.com/kite-production/phantom/blob/main/updater/src/main.py))
  fetches manifests from GitHub Releases for in-app upgrades and
  applies them to `/host/.env` before `docker compose up`.
- Operator visibility surfaces in `/observability/connectors`
  (digest column per service + per-instance connector).
- The architecture page (`/help/architecture` → `#image-pinning`)
  is the canonical spec.

The full implementation landed in commit
[`35f6d9f`](https://github.com/kite-production/phantom/commit/35f6d9f)
across 8 files (release.yml, installer template + compose + build,
updater main.py, agent /api/agent/{version,digests}, observability
connectors page). 1,560 insertions / 204 deletions.

---

**Questions or weird symptoms?** Open an issue at
https://github.com/kite-production/phantom/issues with `docker compose
ps`, `docker compose logs phantom-agent`, and the bottom of `/opt/phantom/.env`
(redact the registry token + KEK before sharing).
