# Guardian

**Guardian** is an AI incident-response agent for Cortex XSIAM / XSOAR — it runs
evidence-grounded investigations, XQL hunts, case enrichment, and response
orchestration. It installs as a small set of containers on one Linux server.

This repository hosts the **public installer**: a single self-extracting file
that contains the entire product. One download, one command — no registry, no
token, no `ghcr.io`.

- 🚀 **Install** → [Requirements](#requirements) · [Install Guardian](#install-guardian)
- 🔥 **Locking down a firewall first?** → [Network access](#network-access-firewall-allow-list) · [Air-gapped: allow only one URL](#air-gapped-allow-only-one-url-iptables)

---

## Requirements

| # | Requirement | Detail |
|---|---|---|
| 1 | **A Linux server** | One host you can log into with **`sudo`** (administrator) rights. See [tested operating systems](#tested-operating-systems) below. |
| 2 | **A container runtime, already installed** | **Podman** or **Docker** must be present before you run the installer. The installer detects which one you have. It **cannot install a runtime itself** (that would need network access to a package repo), so this is the one prerequisite you provide. Podman ships in the RHEL / Rocky / AlmaLinux base repos:<br>• RHEL / Rocky / Alma: `sudo dnf install -y podman`<br>• Ubuntu / Debian: `sudo apt-get install -y docker.io` (or Docker CE)<br>Everything else — all 9 service images **and** the Docker Compose v2 provider — is bundled inside the one file. |
| 3 | **Disk space** | ~**700 MB** for the download + ~**3 GB** free in the temp dir while it unpacks the bundled images (they load into the container store). Budget ~**10 GB** free total on a fresh box. |
| 4 | **Memory** | 4 GB RAM minimum; **8 GB recommended** for comfortable operation of the agent + updater + any connectors you enable. |
| 5 | **Outbound HTTPS (443)** | Only to download the one file — see [Network access](#network-access-firewall-allow-list). After install, Guardian needs outbound 443 only to your **AI model provider**. It needs **no inbound** internet access. |
| 6 | **Browser access to port 3000** | The web UI listens on `https://<host>:3000`. Reach it directly, over your own network/VPN, or via a tunnel — it does not need to be internet-exposed. |

> **No Kite token needed.** The installer is a public download and carries every
> image inside it — there is nothing to authenticate against.

### Tested operating systems

| OS | Status |
|---|---|
| RHEL / Rocky / AlmaLinux 8 and 9 | ✅ **Tested & supported** |
| Ubuntu / Debian | Supported, not yet tested — the installer continues and tells you so |
| Fedora / openSUSE / other systemd distros | Untested — the installer continues with a warning |

The installer prints which tier your OS falls into during pre-flight.

---

## Install Guardian

Run these three lines on your server:

```bash
# 1. Download the one-file installer (public — no login, no token)
curl -fSL -o guardian-installer.sh \
  https://github.com/socagents/guardian/releases/latest/download/guardian-installer.sh

# 2. Make it executable
chmod +x guardian-installer.sh

# 3. Install — detects your OS + runtime (Podman/Docker) and brings up the stack
sudo ./guardian-installer.sh
```

What the installer does, in order:

1. **Pre-flight** — checks `sudo`, disk, and prints your OS support tier.
2. **Runtime** — auto-detects **Podman** or **Docker**; if neither is present it stops with a clear message (see [Requirements](#requirements) #2).
3. **Self-extract** — unpacks the bundled images + the Compose v2 provider from inside the file (no registry, no `download.docker.com`).
4. **Install** — loads every image, writes `/opt/guardian/{docker-compose.yml,.env}`, generates your secrets, and starts the stack.
5. **Done** — prints the web address and a **temporary admin password** — keep that screen for [First login](#first-login).

The file is large (~650 MB — every image is inside it). Installing a newer
release later? Re-download and re-run — see [Updating](#updating).

**Verify the download (optional):**

```bash
curl -fSL -O https://github.com/socagents/guardian/releases/latest/download/guardian-installer.sh.sha256
sha256sum -c guardian-installer.sh.sha256
```

---

## Network access (firewall allow-list)

Guardian runs on **one Linux server**, makes only **outbound HTTPS (port 443)**
connections, needs **no inbound** internet access, and does **not** phone home.
Allow-list by **hostname** — GitHub and Google rotate IP ranges, so hostname/SNI
rules are far more stable than CIDRs.

**To install** (download the one file), allow exactly these two hosts:

| Host | Purpose |
|---|---|
| `github.com` | The `releases/.../guardian-installer.sh` link — returns HTTP 302 redirects |
| `release-assets.githubusercontent.com` | Serves the actual file bytes (GitHub redirects here) |

That is the entire install allow-list — no `ghcr.io`, no registry, no token.

<details><summary><b>Exactly what the download does (captured on RHEL 8.10)</b></summary>

The one download resolves through **two** GitHub hosts and nothing else:

1. `GET github.com/.../releases/latest/download/guardian-installer.sh` → **302** to the versioned URL (still `github.com`)
2. `GET github.com/.../releases/download/vX.Y.Z/guardian-installer.sh` → **302** to a short-lived signed URL on `release-assets.githubusercontent.com`
3. `GET release-assets.githubusercontent.com/...` → **206**, streams the file

The signed URL contains a `...blob.core.windows.net` string **inside its token**
(GitHub's server-side storage backend) — your host never opens a connection to
it. Only `github.com` + `release-assets.githubusercontent.com` are contacted.
</details>

Once installed, Guardian needs your **AI model provider** to run:

| Provider | Hosts (port 443) |
|---|---|
| **Google Vertex AI** (default) | `aiplatform.googleapis.com` · `<region>-aiplatform.googleapis.com` (e.g. `us-central1-aiplatform.googleapis.com`) · `oauth2.googleapis.com` |
| **Google Gemini API key** | `generativelanguage.googleapis.com` — embeddings still use the two Vertex hosts above |
| **Cohere North** | your organization's Cohere North endpoint (typically inside your own network) — embeddings still use the two Vertex hosts above |

Optional — only if you enable these connectors:

| Host | When it's used |
|---|---|
| `docs-cortex.paloaltonetworks.com` | The **Cortex Docs** connector |
| `api.anthropic.com` | Cortex Docs deep-research (only if you provide an Anthropic API key) |

> Your **Cortex XSIAM / XSOAR tenant** is reached over your own network path (the
> host/port you configure per connector) — it is **not** an internet allow-list
> entry, and you should never publish it.

### Test your firewall

Run on the server. **Any HTTP number (`200` / `206` / `301` / `404`) means
reachable**; `curl: (28)` / `(7)` or a hang means blocked.

```bash
# Install (download the one file)
curl -sS -o /dev/null -w '%{http_code}\n' --connect-timeout 8 https://github.com
curl -sS -o /dev/null -w '%{http_code}\n' --connect-timeout 8 https://release-assets.githubusercontent.com

# AI provider — test only the one you use
curl -sS -o /dev/null -w '%{http_code}\n' --connect-timeout 8 https://aiplatform.googleapis.com
curl -sS -o /dev/null -w '%{http_code}\n' --connect-timeout 8 https://us-central1-aiplatform.googleapis.com   # swap your Vertex region
curl -sS -o /dev/null -w '%{http_code}\n' --connect-timeout 8 https://oauth2.googleapis.com
curl -sS -o /dev/null -w '%{http_code}\n' --connect-timeout 8 https://generativelanguage.googleapis.com       # Gemini API-key path
```

---

## Air-gapped: allow only one URL (iptables)

Because the installer carries every image, a locked-down box can install with
**only the two GitHub download hosts open** — nothing else. Example with
`iptables` (default-drop egress, allow loopback + established + DNS + the
download hosts):

```bash
# Prerequisite: a container runtime is already installed (e.g. sudo dnf install -y podman)
# while you still have network, BEFORE locking down.

# 1. Download the installer FIRST (needs the two hosts below)
curl -fSL -o guardian-installer.sh \
  https://github.com/socagents/guardian/releases/latest/download/guardian-installer.sh
chmod +x guardian-installer.sh

# 2. Lock egress: default-drop, then allow only what's needed
sudo iptables -P OUTPUT DROP
sudo iptables -A OUTPUT -o lo -j ACCEPT
sudo iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
sudo iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
sudo iptables -A OUTPUT -p tcp --dport 53 -j ACCEPT
for h in github.com release-assets.githubusercontent.com; do
  for ip in $(getent ahostsv4 "$h" | awk '{print $1}' | sort -u); do
    sudo iptables -A OUTPUT -p tcp -d "$ip" --dport 443 -j ACCEPT
  done
done

# 3. Install — everything is in the file; no other host is contacted
sudo ./guardian-installer.sh
```

> To let Guardian **run** afterward, allow your AI model provider host (see the
> table above) the same way. The install itself contacts nothing beyond the two
> GitHub hosts. GitHub rotates IPs, so re-resolve the hosts if you re-download
> later — hostname/SNI-based firewalls avoid that entirely.

---

## First login

1. Open a browser to the address shown at the end of the install — it looks like `https://YOUR-SERVER-ADDRESS:3000`.
2. Your browser warns about the certificate (Guardian uses a self-signed cert on first run). This is expected — choose **Advanced → Proceed / Continue**.
3. Sign in as **`admin`** with the **temporary password** shown at the end of the install.
   *(Lost it? It's on the server in `/opt/guardian/.env`, line `GUARDIAN_DEFAULT_ADMIN_PASSWORD`.)*
4. Guardian asks you to **set your own password** — do that, then sign back in with it.
5. Add your AI model under **Providers**, and connect your security tools under **Instances**. Kite will help with the exact values.

---

## Updating

Re-download the one file and re-run it — the download always fetches the latest release:

```bash
curl -fSL -o guardian-installer.sh \
  https://github.com/socagents/guardian/releases/latest/download/guardian-installer.sh
chmod +x guardian-installer.sh
sudo ./guardian-installer.sh
```

It detects your existing install at `/opt/guardian` and **keeps all your
settings, passwords, and data** — only the software is updated.

## Troubleshooting

| Problem | Fix |
|---|---|
| A firewall test above prints `curl: (28)` / `(7)` or hangs | That host is blocked — allow it (port 443) per [Network access](#network-access-firewall-allow-list), then re-test. |
| Installer says **no container runtime found** | Install one first — `sudo dnf install -y podman` (RHEL/Rocky/Alma) or Docker — then re-run `sudo ./guardian-installer.sh`. |
| Installer says **not enough disk** | Free up space (needs ~3 GB to unpack), or set `TMPDIR` to a larger filesystem, then re-run. |
| Can't reach `https://…:3000` in the browser | Make sure your firewall allows port **3000** to the server and you used `https://`. |
| Forgot the password | On the server: `sudo /opt/guardian/guardian-reset-admin-password` |
| Is it running? | On the server: `docker compose -f /opt/guardian/docker-compose.yml ps` (works on Podman too) |

---

*Questions? Contact Kite — we're happy to do the first install with you over a call.*
