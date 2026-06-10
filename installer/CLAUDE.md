# `installer/` — customer installer template

The phantom-installer build template. Produces a single binary the customer downloads + runs on their target host to bring up the Phantom stack at `/opt/phantom/`. Two install flows: dev-installer (auto-deployed on phantom-vm by CI) + customer-installer (downloaded from GHCR releases).

**Repo-wide rules live in the [root CLAUDE.md](../CLAUDE.md)** — change scenarios, image digest pinning, customer onboarding semantics. This file holds only conventions LOCAL to installer authoring.

## Layout

| Path | What it is |
|------|------------|
| `build.sh` | Builds the `phantom-installer` binary. Bakes the manifest's digests + the customer compose into a self-extracting script. |
| `docker-compose.yml` | Customer compose — 3 fixed services (phantom-agent, phantom-updater, phantom-browser), image refs use `@${DIGEST_*}` substitution from the install-time `.env`. |
| `template/` | Files copied into the customer install kit at `/opt/phantom/`. |
| `template/.env.example` | Reference env file. The installer writes the real `.env` at install time, populated with the release manifest's digests + operator-supplied credentials. |

## The two installers

Both use the SAME install ceremony + SAME compose + SAME env-file format + SAME install location (`/opt/phantom/`). The only divergence is which image digests get baked into the installer binary at build time:

| Variant | Digests | Trigger | Where it lives |
|---|---|---|---|
| **Customer installer** | `vX.Y.Z` tags | `release.yml` on tag push | GHCR release asset |
| **Dev installer** | `dev-<sha>` | `build-dev-installer.yml` on push to main | `dev-latest` prerelease asset + auto-deployed to phantom-vm |

The customer installer has zero knowledge of dev — no flags, no branches, no toggles.

## Compose: digest pinning contract

`docker-compose.yml` here uses `image: ghcr.io/.../<svc>@${DIGEST_PHANTOM_<SVC>}` substitution. The matching `${DIGEST_*}` values come from:

| File | Owned by | Content |
|---|---|---|
| `/opt/phantom/.env` | installer at install time | Service credentials + 3 core stack-service digests (`DIGEST_PHANTOM_AGENT`, `DIGEST_PHANTOM_UPDATER`, `DIGEST_PHANTOM_BROWSER`) + `PHANTOM_VERSION` marker |
| `/opt/phantom/connector-digests.env` | installer at install time, **phantom-updater reads** | 6 per-connector image pins (`DIGEST_PHANTOM_CONNECTOR_*`) |

**The split is load-bearing (v0.6.7+):** per-connector containers aren't declared in `docker-compose.yml`, so their digests are NOT compose-substitution variables — they're consumed at runtime by phantom-updater when an operator creates a connector instance.

**Forbidden going forward**:
- Adding `DIGEST_PHANTOM_CONNECTOR_*` writes to `.env` for any reason.
- Adding any connector configuration (instance ID, container URL, baseUrl, secret refs) to `.env`.
- Mixing the two files.

## The dev-cycle gap (updater + browser)

phantom-updater + phantom-browser images are NOT rebuilt on the dev cycle — only on customer release tags. When a fix touches `updater/src/main.py` or `phantom-browser/`, the dev-installer carries the OLD version of those two images. The fix only goes live on a customer release.

The agent must lead the smoke-test matrix with this warning when applicable — see root § Agent-side headless smoke rule 4.

## Customer-onboarding access semantics

GHCR enforces pull access **per IMAGE VERSION**, not per package or token scope alone. A package version becomes org-readable when associated with a GitHub Release. Customer `vX.Y.Z` versions get this via `release.yml`'s `gh release create`; dev `:dev` versions need an equivalent prerelease association (the `dev-latest` GitHub prerelease created by `build-dev-installer.yml`).

Full table: [docs/CICD.md § GHCR per-version access](../docs/CICD.md#ghcr-per-version-access).

## Cross-subsystem must-update-together list (when changing image-pinning code)

Any change to image-pinning behavior here MUST touch all of:
- `release.yml` (generates the manifest)
- `phantom-installer` template (writes `.env`)
- `updater/src/main.py` (reads `/host/connector-digests.env`)
- `mcp/agent/app/help/architecture/page.tsx` (canonical spec)
- `mcp/agent/app/observability/connectors/page.tsx` (operator-visible state)

Skip any of these → silent drift. See [docs/CICD.md § Image digest pinning contract](../docs/CICD.md#image-digest-pinning-contract-customer-compose).
