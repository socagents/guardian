# `installer/` — customer installer template

The guardian-installer build template. Produces a single binary the customer downloads + runs on their target host to bring up the Guardian stack at `/opt/guardian/`. Two install flows: dev-installer (auto-deployed on guardian-vm by CI) + customer-installer (downloaded from GHCR releases).

**Repo-wide rules live in the [root CLAUDE.md](../CLAUDE.md)** — change scenarios, image digest pinning, customer onboarding semantics. This file holds only conventions LOCAL to installer authoring.

## Layout

| Path | What it is |
|------|------------|
| `build.sh` | Builds the `guardian-installer` binary. Bakes the manifest's digests + the customer compose into a self-extracting script. |
| `docker-compose.yml` | Customer compose — 3 fixed services (guardian-agent, guardian-updater, guardian-browser), image refs use `@${DIGEST_*}` substitution from the install-time `.env`. |
| `template/` | Files copied into the customer install kit at `/opt/guardian/`. |
| `template/.env.example` | Reference env file. The installer writes the real `.env` at install time, populated with the release manifest's digests + operator-supplied credentials. |

## The two installers

Both use the SAME install ceremony + SAME compose + SAME env-file format + SAME install location (`/opt/guardian/`). The only divergence is which image digests get baked into the installer binary at build time:

| Variant | Digests | Trigger | Where it lives |
|---|---|---|---|
| **Customer installer** | `vX.Y.Z` tags | `release.yml` on tag push | GHCR release asset |
| **Dev installer** | `dev-<sha>` | `build-dev-installer.yml` on push to main | `dev-latest` prerelease asset + auto-deployed to guardian-vm |

The customer installer has zero knowledge of dev — no flags, no branches, no toggles.

## The one-file self-extracting installer (v0.4.0+) — the socagents customer artifact

The public `socagents` release is a **single self-extracting `guardian-installer.sh`**
built by [`build-self-extracting-installer.sh`](build-self-extracting-installer.sh):

```
[ header ]  ← build-guardian-installer.sh output with RUNTIME=auto (both compose
              variants embedded; runtime detected at install time)
exit 0      ← stops bash before the binary payload
__GUARDIAN_PAYLOAD_BELOW__
[ payload ] ← gzipped tar: images.tar.gz (docker save of all 9 images) +
              compose/docker-compose-{x86_64,aarch64} (Compose v2 provider)
```

Contract:
- **`RUNTIME=auto`** makes the template detect podman-vs-docker at install time and
  write the matching compose. The template ALWAYS embeds both composes now
  (`__INSTALLER_COMPOSE_DOCKER__` + `__INSTALLER_COMPOSE_PODMAN__`); baked
  docker/podman builds still work (they just fix the runtime at build time).
- **Everything is bundled** so the install needs no registry, no token, and no
  `download.docker.com` (the Compose v2 provider is in the payload). The one true
  external prerequisite is that a container runtime is already present — Podman
  ships in the RHEL base repos. If neither podman nor docker is found, the
  installer says so and exits.
- **The offline path is reused, not reinvented**: the header extracts its own
  payload, sets `OFFLINE_BUNDLE=<images.tar.gz>`, and runs the same offline
  install ceremony the `--offline <bundle>` flag uses.
- **socagents = one file per release.** `release.yml` no longer mirrors separate
  images to socagents; it builds the `.sh` and attaches it. The private
  kite-production release keeps per-image + the baked registry installers
  (INTERNAL, `INSTALLER_OWNER=kite-production`), and the dev cycle is unchanged.
- **When editing the runtime/compose/offline path**, `bash -n` all three variants
  (`RUNTIME=docker|podman|auto`) and re-run the payload round-trip
  (`awk` marker → `tail -n +N` → `tar -xz`) before pushing.

## Compose: digest pinning contract

`docker-compose.yml` here uses `image: ghcr.io/.../<svc>@${DIGEST_GUARDIAN_<SVC>}` substitution. The matching `${DIGEST_*}` values come from:

| File | Owned by | Content |
|---|---|---|
| `/opt/guardian/.env` | installer at install time | Service credentials + 3 core stack-service digests (`DIGEST_GUARDIAN_AGENT`, `DIGEST_GUARDIAN_UPDATER`, `DIGEST_GUARDIAN_BROWSER`) + `GUARDIAN_VERSION` marker |
| `/opt/guardian/connector-digests.env` | installer at install time, **guardian-updater reads** | 4 per-connector image pins (`DIGEST_GUARDIAN_CONNECTOR_*`) |

**The split is load-bearing (v0.6.7+):** per-connector containers aren't declared in `docker-compose.yml`, so their digests are NOT compose-substitution variables — they're consumed at runtime by guardian-updater when an operator creates a connector instance.

**Forbidden going forward**:
- Adding `DIGEST_GUARDIAN_CONNECTOR_*` writes to `.env` for any reason.
- Adding any connector configuration (instance ID, container URL, baseUrl, secret refs) to `.env`.
- Mixing the two files.

## The dev-cycle gap (updater + browser)

guardian-updater + guardian-browser images are NOT rebuilt on the dev cycle — only on customer release tags. When a fix touches `updater/src/main.py` or `guardian-browser/`, the dev-installer carries the OLD version of those two images. The fix only goes live on a customer release.

The agent must lead the smoke-test matrix with this warning when applicable — see root § Agent-side headless smoke rule 4.

## Customer-onboarding access semantics

GHCR enforces pull access **per IMAGE VERSION**, not per package or token scope alone. A package version becomes org-readable when associated with a GitHub Release. Customer `vX.Y.Z` versions get this via `release.yml`'s `gh release create`; dev `:dev` versions need an equivalent prerelease association (the `dev-latest` GitHub prerelease created by `build-dev-installer.yml`).

Full table: [docs/CICD.md § GHCR per-version access](../docs/CICD.md#ghcr-per-version-access).

## Cross-subsystem must-update-together list (when changing image-pinning code)

Any change to image-pinning behavior here MUST touch all of:
- `release.yml` (generates the manifest)
- `guardian-installer` template (writes `.env`)
- `updater/src/main.py` (reads `/host/connector-digests.env`)
- `mcp/agent/app/help/architecture/page.tsx` (canonical spec)
- `mcp/agent/app/observability/connectors/page.tsx` (operator-visible state)

Skip any of these → silent drift. See [docs/CICD.md § Image digest pinning contract](../docs/CICD.md#image-digest-pinning-contract-customer-compose).
