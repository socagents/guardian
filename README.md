# Guardian

**Guardian** is an AI incident-response agent for Cortex XSIAM / XSOAR — it runs evidence-grounded investigations, XQL hunts, case enrichment, and response orchestration. It installs as a small set of containers on one Linux server.

This repository hosts the **public installer**: a single self-extracting file that contains the entire product. One download, one command — no registry, no token.

- 🚀 **Install** → [Install Guardian](#install-guardian)
- 🔥 **Locking down a firewall first?** → [Network access](#network-access-firewall-allow-list) · [Air-gapped: allow only one URL](#air-gapped-allow-only-one-url-iptables)

---

## Before you start

You need:

1. **A Linux server** you can log into, with **`sudo`** (administrator) rights, and about **3 GB free disk** for the install.
2. **A container runtime already installed** — **Podman** (ships in the RHEL / Rocky / AlmaLinux base repos: `sudo dnf install -y podman`) or **Docker**. The installer detects which one you have. It bundles everything else (all images + the Compose tool), but it cannot install a container engine with no network, so this one piece must be present first.
3. **Outbound HTTPS (port 443)** to download the installer, and — once running — to reach your AI model provider. See [Network access](#network-access-firewall-allow-list).

> **No token needed.** The installer is a public download and carries every image inside it — there is nothing to authenticate against.

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

That is the whole install. The installer:

- tells you whether your OS is **tested & supported** (RHEL / Rocky / AlmaLinux 8–9), **supported but not yet tested** (Ubuntu / Debian — it continues and says so), or **untested**;
- detects **Podman** or **Docker** and installs down the right path;
- loads every Guardian image from inside the file — no registry, no token, no other downloads;
- brings the stack up (a few minutes) and prints a green **"Guardian is running"** message with a web address and a temporary password — keep that screen for [First login](#first-login).

The file is large (~620 MB — every image is inside it). Installing a newer release later? Re-download and re-run — see [Updating](#updating).

---

## Network access (firewall allow-list)

Guardian runs on **one Linux server**, makes only **outbound HTTPS (port 443)** connections, needs **no inbound** internet access, and does **not** phone home to any vendor. Allow-list by **hostname** — GitHub and Google rotate IP ranges, so hostname/SNI rules are far more stable than CIDRs.

**To install** (download the one file), allow just:

| Host | Purpose |
|---|---|
| `github.com` | Fetch the installer file |
| `release-assets.githubusercontent.com` | The actual file bytes (`github.com` redirects here) |

That is the entire install allow-list — no `ghcr.io`, no registry, no token. Once installed, Guardian needs your **AI model provider** to run:

| Provider | Hosts (port 443) |
|---|---|
| **Google Vertex AI** (default) | `aiplatform.googleapis.com` · `<region>-aiplatform.googleapis.com` (e.g. `us-central1-aiplatform.googleapis.com`) · `oauth2.googleapis.com` |
| **Google Gemini API key** | `generativelanguage.googleapis.com` — embeddings still use the two Vertex hosts above |
| **Cohere North** | your organization's Cohere North endpoint (typically inside your own network) — embeddings still use the two Vertex hosts above |

Optional — only if you enable these connectors:

| Host | When it's used |
|---|---|
| `docs-cortex.paloaltonetworks.com` | The **Cortex Docs** connector (searches public Palo Alto Cortex documentation) |
| `api.anthropic.com` | Cortex Docs deep-research (only if you provide an Anthropic API key) |

> Your **Cortex XSIAM / XSOAR tenant** is reached over your own network path (the host/port you configure on each connector) — it is **not** an internet allow-list entry, and you should never publish it.

### Test your firewall

Run on the server. **Any HTTP number (`200` / `301` / `404`) means reachable**; `curl: (28)` / `(7)` or a hang means blocked.

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

Because the installer carries every image, a locked-down box can install with **only the two GitHub download hosts open** — nothing else. Example with `iptables` (default-drop egress, allow loopback + established + DNS + the download hosts):

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

> To let Guardian **run** afterwards, allow your AI model provider host (see the table above) the same way. The install itself contacts nothing beyond the two GitHub hosts. GitHub rotates IPs, so re-resolve the hosts if you re-download later — hostname/SNI-based firewalls avoid that entirely.

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

It detects your existing install and **keeps all your settings, passwords, and data** — only the software is updated.

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
