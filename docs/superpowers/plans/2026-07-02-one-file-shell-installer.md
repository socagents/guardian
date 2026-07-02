# One-File Self-Extracting Shell Installer Implementation Plan

> **For agentic workers:** executed inline this session. Steps use `- [ ]` tracking.

**Goal:** Replace the socagents public distribution (installer binary + 619 MB tar.gz bundle + registry images) with a **single self-extracting `guardian-installer.sh`** that embeds every image, detects the OS + container runtime, and installs the whole stack with **zero registry/network access** beyond the one download URL.

**Architecture:** The `.sh` = the existing installer template (reworked for runtime auto-detection + both composes embedded) on top, a marker line, then an appended gzipped tar payload containing (a) `images.tar.gz` — `docker save` of all 9 images, and (b) the Docker Compose v2 provider binaries (amd64 + arm64) so an air-gapped RHEL box needs nothing from `download.docker.com`. At runtime the script extracts its own payload to a temp dir, sets `OFFLINE_BUNDLE` to the images tar, installs the bundled compose provider if none is present, then runs the existing offline install ceremony. `kite-production` private release + dev cycle are UNCHANGED — only socagents becomes one-file.

**Tech Stack:** Bash (self-extracting via `awk` payload offset + `tar`/`gzip`), Docker/Podman, GitHub Actions.

## Global Constraints

- The **9 images are runtime-agnostic** (same OCI images for docker + podman). Detection picks the runtime *path* (which compose file + load/run commands), NOT different images.
- **Offline cannot install a container runtime** (no repo access). The box must have `podman` (RHEL base) or `docker` present. Detect; if neither → clear message + exit. The **compose provider IS bundled** (it's the one piece RHEL base lacks).
- **One firewall URL chain**: `github.com` + `release-assets.githubusercontent.com`. No `ghcr.io`, no token, no `download.docker.com`.
- **socagents = one file per release** (`guardian-installer.sh`). Turn OFF the socagents image-mirror. kite-production + dev untouched.
- Tested-OS matrix: RHEL/Rocky/Alma 8–9 = tested; Ubuntu/Debian = supported-untested (warn+continue); else warn+attempt.
- Version: **v0.4.0** (MAJOR — customer artifact changes).
- GitHub release asset limit ~2 GiB; the `.sh` ≈ 620–700 MB — fine.

---

## Task 1: Runtime auto-detection in the template

**Files:** Modify `installer/guardian-installer.template.sh` (constants + Step 2 head).

- Add sentinel: `GUARDIAN_RUNTIME` may be baked (`docker`/`podman`) OR `auto` (self-extracting build).
- New `detect_runtime()`: if `GUARDIAN_RUNTIME=auto` → set `podman` if `command -v podman`, else `docker` if `command -v docker`, else `die` with the offline-friendly message ("Guardian's one-file installer bundles every image but cannot install a container runtime offline. Install podman (RHEL: `sudo dnf install -y podman podman-docker`) or docker, then re-run."). Run BEFORE Step 2.
- [ ] Implement + `bash -n`.

## Task 2: Embed BOTH composes; pick by runtime

**Files:** Modify template Step 6 (compose write) + `build-guardian-installer.sh` (embed both).

- Template holds two heredocs: `_GUARDIAN_COMPOSE_DOCKER_` + `_GUARDIAN_COMPOSE_PODMAN_` (placeholders the build fills from `installer/docker-compose.yml` + `installer/podman-compose.yml`). At runtime write the one matching detected `GUARDIAN_RUNTIME`. Non-self-extracting (baked-runtime) builds keep writing the single baked compose — guard with `if [ "$GUARDIAN_RUNTIME_BAKED" = auto ]`.
- [ ] Implement + `bash -n`.

## Task 3: Self-extraction of the embedded payload

**Files:** Modify template (new Step 0.5 before Step 4 offline branch).

- Marker: `__GUARDIAN_PAYLOAD_BELOW__` on its own line. If present in `$0`:
  `PAYLOAD_LINE=$(awk '/^__GUARDIAN_PAYLOAD_BELOW__$/{print NR+1; exit}' "$0")`
  `tail -n +"$PAYLOAD_LINE" "$0" | tar -xz -C "$TMP"` → yields `images.tar.gz` + `compose/`.
  Set `OFFLINE_BUNDLE="$TMP/images.tar.gz"`. Register a trap to `rm -rf "$TMP"`.
- Disk preflight: require ≥ 3 GB free in `$TMPDIR` + `/opt` (images unpack ~2 GB).
- [ ] Implement + `bash -n`.

## Task 4: Tested-OS matrix message

**Files:** Modify template Step 1 (after `. /etc/os-release`).

- `os_support_tier()`: rhel/rocky/almalinux/centos 8|9 → `tested`; ubuntu/debian → `supported-untested`; else `untested`. Print:
  `✓ <PRETTY_NAME> — tested & supported` / `⚠ <PRETTY_NAME> — supported, not yet tested; continuing` / `⚠ <PRETTY_NAME> — untested; continuing (report issues to Kite)`. Never blocks (keep existing hard-fail only for no `/etc/os-release`).
- [ ] Implement + `bash -n`.

## Task 5: Bundled compose-provider install (offline)

**Files:** Modify template Step 2 (both paths).

- New `ensure_compose_offline()`: if `docker compose version` fails AND a bundled binary exists at `$TMP/compose/docker-compose-$(uname -m)`, install it to `/usr/libexec/docker/cli-plugins/docker-compose` (chmod +x) and, for podman, write `~/.config/containers/containers.conf` (or `/etc/containers/containers.conf`) `compose_providers` — reuse the existing podman provider-registration block. If offline AND no provider AND no bundled binary → `die` with a clear message.
- Guard the existing `download.docker.com` install so it's SKIPPED when `OFFLINE_BUNDLE` is set (never touch the network offline).
- [ ] Implement + `bash -n`.

## Task 6: Robust failure messaging

**Files:** template (extraction, load, compose-up sites).

- Wrap extraction, `docker/podman load`, and `compose up` with explicit `|| die "<specific message + remediation>"`. Confirm every failure path prints a message and exits non-zero.
- [ ] Implement + `bash -n`.

## Task 7: Self-extracting build mode

**Files:** Modify `installer/build-guardian-installer.sh`; NEW `installer/build-self-extracting-installer.sh` (or a `--self-extracting` flag).

- Inputs: the 9 image refs (pull), the compose provider binaries (download at build for amd64+arm64 from download.docker.com — build host has egress), `INSTALLER_OWNER=socagents`, `GUARDIAN_RUNTIME=auto`.
- Steps: render the template (runtime=auto, both composes embedded, owner substituted) → header. `docker save <9 images> | gzip > images.tar.gz`. `tar -cz images.tar.gz compose/ > payload.tgz`. `cat header.sh <(echo __GUARDIAN_PAYLOAD_BELOW__) payload.tgz > guardian-installer.sh`. `chmod +x`. Emit sha256.
- Post-checks: `bash -n` on the header portion; assert `__INSTALLER_OWNER__`/`__INSTALLER_RUNTIME__` fully substituted; assert payload marker present exactly once.
- [ ] Implement + local build with a TINY fake payload to validate the concat + extraction round-trip.

## Task 8: release.yml — build the .sh, socagents = one file

**Files:** Modify `.github/workflows/release.yml`.

- Add a step (after images build) that runs the self-extracting build → `guardian-installer.sh` + `.sha256`; attach to the kite-production Release (so the private repo also has it for mirroring).
- **Turn OFF** the socagents image-mirror step (comment/remove) — socagents no longer receives images.
- Keep the tar.gz bundle step? NO — replaced by the .sh. Remove it (or keep for one release as fallback? → remove per operator "one file only").
- [ ] Implement + `actionlint`/YAML validate.

## Task 9: Docs — README (socagents) + iptables + help/changelog

**Files:** socagents `README.md` (Contents API); `CHANGELOG.md`; `mcp/agent/lib/release-notes.ts`; `mcp/agent/app/help/architecture` + `user` (distribution note); `mcp/agent/lib/journeys.ts` if a flow changes.

- README: replace the offline section with the one-file flow + an **iptables allow-list recipe** (block all egress, allow only github.com + release-assets.githubusercontent.com; note podman must be pre-installed).
- CHANGELOG + release-notes v0.4.0 entry.
- [ ] Implement.

## Task 10: Local dry-run + pre-deploy gate

- Build a self-extracting installer with a 3-tiny-image payload locally; run `bash guardian-installer.sh --help`; extract-only dry run to confirm payload offset + tar round-trip; `bash -n` the built script.
- Run the mcp/agent gate (tsc/lint/build) IF any TS touched (docs only → build to be safe) + pytest if Python touched (none expected).
- [ ] Green.

## Task 11: Fresh RHEL smoke (after push + release build)

- Spin fresh RHEL VM (podman pre-present, no compose). Lock iptables to the 2 allowed hosts. `curl` the `.sh` from socagents → run → assert: OS-tier message, runtime auto-detected=podman, compose provider installed from bundle (no download.docker.com hit), all 9 images loaded, stack healthy, UI 200 — with NOTHING but the 2 URLs reachable.
- Then hand a clean VM + tunnel + username to the operator.

---

## Self-Review

- **Coverage:** runtime detect (T1), both composes (T2), self-extract (T3), OS matrix (T4), bundled compose (T5), failure msgs (T6), build (T7), release+socagents-one-file (T8), docs+iptables (T9), gate (T10), smoke (T11). ✓ maps to operator spec.
- **Type/name consistency:** `GUARDIAN_RUNTIME=auto` sentinel; marker `__GUARDIAN_PAYLOAD_BELOW__`; `OFFLINE_BUNDLE` reused as the bridge to the existing offline path.
- **Backwards compat:** baked-runtime builds (kite-production dev + private) still work (guards on `auto`). Existing `--offline <bundle>` flag preserved.
