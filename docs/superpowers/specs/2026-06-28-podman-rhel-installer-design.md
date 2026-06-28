# Podman / RHEL installer — design spec

**Date:** 2026-06-28
**Goal:** A Docker-free Guardian installer for **RHEL 8 + rootful Podman** customers, delivered through the container registry (the only egress some customers allow). The existing Docker installer + Docker customers are untouched.

## Decisions (operator-confirmed)
- **Target:** RHEL 8 (+ compatibles). | **Privilege:** rootful Podman. | **Runtime API:** Podman's Docker-compatible socket is acceptable (no Docker Engine).
- **No test VM** — validation happens on the customer VM. ⇒ the installer must be **self-validating** (preflight + clear diagnostics) and the high-risk paths handled **defensively in code**.

## Approach — "Podman-as-Docker" (lowest diff)
Podman serves a Docker-compatible API socket; `podman-docker` provides `/var/run/docker.sock` + a `docker` CLI shim. The updater (docker-py SDK + the docker-compose-plugin baked in its image) then drives that socket largely unchanged.

### Runtime model
- `dnf install -y podman podman-docker` + a **bundled Docker Compose v2 binary** (not in RHEL/EPEL → ship in the install kit / image).
- `systemctl enable --now podman.socket` (rootful → `/run/podman/podman.sock`; symlinked to `/var/run/docker.sock`).
- A **systemd unit** brings the stack up on boot (Podman doesn't revive `unless-stopped` after reboot like dockerd).

## Changes (single source, runtime-switched)
1. **`installer/build-guardian-installer.sh`** — add `RUNTIME` env (default `docker`). `podman` selects the podman compose + `guardian-installer-podman` output name + sets `__INSTALLER_RUNTIME__`. Docker path unchanged (RUNTIME unset ⇒ docker).
2. **`installer/guardian-installer.template.sh`** — Step 2 (runtime setup) branches on `__INSTALLER_RUNTIME__`: docker branch = current logic **verbatim**; podman branch = podman/podman-docker install (dnf), enable `podman.socket`, install bundled compose v2, `podman info` reachability, SELinux preflight, boot unit. Add a **preflight**: probe `podman.socket`, an authenticated `ghcr.io` pull, wait-healthy.
3. **`installer/podman-compose.yml`** — copy of `docker-compose.yml` with SELinux handling: `security_opt: [label=disable]` on `guardian-updater` (it mounts the runtime socket) + `:z` on the `.:/host` bind. Named volumes auto-label.
4. **`updater/src/main.py`** — **defensive, harmless-on-Docker**: pass explicit `auth_config={username,password}` (from `GUARDIAN_REGISTRY_USER`/`TOKEN`) to `images.pull` + `api.pull` (fixes the #1 Podman risk: auth-file lookup divergence on pull); pin the client (`base_url`/`version="auto"` if `DOCKER_HOST` mis-parses); make `api.pull(stream=True)` fall back to a non-streaming `images.pull(auth_config=...)` on failure.
5. **CI** — `release.yml` + `build-dev-installer.yml`: add a parallel `RUNTIME=podman OUTPUT_NAME=guardian-installer-podman` build + attach as a release asset; `publish-installer-image.yml`: also publish `ghcr.io/<owner>/guardian-installer-podman:<ver>`.
6. **Docs** — architecture + CICD onboarding: the RHEL/Podman path + the registry-delivery channel.

## Risks (no test box → defensive + flagged BETA)
- **R1 (highest):** authenticated ghcr pull through Podman's socket — mitigated by explicit `auth_config` (4).
- **R2:** `api.pull(stream=True)` Moby-streaming on the compat socket — mitigated by the non-streaming fallback (4).
- **R3:** SELinux denies the socket mount — mitigated by `security_opt: label=disable` + preflight check (2,3).
- **R4:** dynamic connector spawn + compose-network join + service-name DNS — cannot be unit-tested; **must be smoke-tested on the customer VM** (the certify step).
- Ship labeled **RHEL/Podman (beta — validated on first customer install)**.

## Acceptance (on the customer VM)
Installer brings the 3 fixed services healthy; agent reachable on :3000; a connector instance spawns + its container joins the network + agent→connector DNS resolves; an authenticated ghcr pull succeeds; stack survives a reboot.
