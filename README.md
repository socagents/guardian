# Guardian

**Guardian** is an AI incident-response agent for Cortex XSIAM / XSOAR — it runs evidence-grounded investigations, XQL hunts, case enrichment, and response orchestration. It installs as a small set of containers on one Linux server.

This repository hosts the **public installer releases**. Pick the guide that matches your server:

- 🟥 **Red Hat (RHEL) with Podman, no Docker** → [Install on RHEL / Podman](#install-on-rhel--podman)
- 🐧 **Any other Linux with Docker** → [Install on Docker](#install-on-docker)
- 🔥 **Locking down a firewall first?** → [Network access (firewall allow-list)](#network-access-firewall-allow-list)

---

## Before you start

You need:

1. **A Linux server** you can log into, with **`sudo`** (administrator) rights.
2. **An access token from Kite.** Kite sends you a long secret string that looks like `ghp_xxxx…`. Think of it as a **password that lets your server download Guardian's software** — you don't need a GitHub account and you don't create anything; just keep it handy and **treat it like a password**. You'll paste it once, when the installer asks.
3. **Outbound internet access (HTTPS / port 443)** for image pulls and your AI model provider. See [Network access (firewall allow-list)](#network-access-firewall-allow-list) for the exact hosts and a copy-paste firewall test — run it before you install.

---

## Network access (firewall allow-list)

Guardian runs on **one Linux server** and makes only **outbound HTTPS (port 443)** connections. It needs **no inbound** access from the internet, and it does **not** phone home to any vendor. Allow-list by **hostname** — Google and GitHub rotate their IP ranges, so hostname/SNI rules are far more stable than CIDRs. Open only the rows that apply to you.

### Always required (image pulls — install and every upgrade)

| Host | Purpose |
|---|---|
| `ghcr.io` | Pull Guardian's container images |
| `pkg-containers.githubusercontent.com` | Image layer/blob storage (`ghcr.io` redirects here for the actual downloads) |

> **Firewall allows `ghcr.io` but not `github.com`?** The installer can be delivered as a registry image so you never touch `github.com` — ask Kite for the registry-image method.

### Install / upgrade only (can stay closed during normal operation)

| Host | Purpose |
|---|---|
| `github.com`, `objects.githubusercontent.com` | Download the installer and the per-release image-digest manifest |
| `api.github.com` | Look up the latest release version during an upgrade |
| `get.docker.com` | **Docker path only**, and only if Docker isn't already installed |
| `download.docker.com` | **RHEL/Podman path only** — installs the Compose plugin (not the Docker engine) |
| your OS's package mirrors | Install prerequisites (`curl`, `podman`, the compose plugin) from your distro's own repos — e.g. `archive.ubuntu.com`, `deb.debian.org`, `cdn.redhat.com` |

### AI model provider — open only the provider you use

| Provider | Hosts (port 443) |
|---|---|
| **Google Vertex AI** (default) | `aiplatform.googleapis.com` (chat) · `<region>-aiplatform.googleapis.com` (embeddings, e.g. `us-central1-aiplatform.googleapis.com`) · `oauth2.googleapis.com` (token exchange) |
| **Google Gemini API key** | `generativelanguage.googleapis.com` (chat) — embeddings still use the two Vertex hosts above |
| **Cohere North** | your organization's Cohere North endpoint (typically inside your own network) — embeddings still use the two Vertex hosts above |

### Optional — only if you enable these connectors

| Host | When it's used |
|---|---|
| `docs-cortex.paloaltonetworks.com` | The **Cortex Docs** connector (searches public Palo Alto Cortex documentation) |
| `api.anthropic.com` | The Cortex Docs deep-research feature — only if you provide an Anthropic API key |

> Your **Cortex XSIAM / XSOAR tenant** is reached over your own network path (the host and port you configure on each connector) — it is **not** an internet allow-list entry, and you should never publish it.

### Test your firewall

Run these on the server **before** installing. **A number printed (e.g. `200`, `401`, `404`) means the host is reachable** — any HTTP response proves the firewall let you through. `curl: (28)` / `(7)` or a hang means it's **blocked**.

```bash
# Always required
curl -sS -o /dev/null -w '%{http_code}\n' --connect-timeout 8 https://ghcr.io/v2/
curl -sS -o /dev/null -w '%{http_code}\n' --connect-timeout 8 https://pkg-containers.githubusercontent.com/

# Install / upgrade
curl -sS -o /dev/null -w '%{http_code}\n' --connect-timeout 8 https://github.com
curl -sS -o /dev/null -w '%{http_code}\n' --connect-timeout 8 https://api.github.com
curl -sS -o /dev/null -w '%{http_code}\n' --connect-timeout 8 https://objects.githubusercontent.com
curl -sS -o /dev/null -w '%{http_code}\n' --connect-timeout 8 https://get.docker.com             # Docker path
curl -sS -o /dev/null -w '%{http_code}\n' --connect-timeout 8 https://download.docker.com/linux/  # RHEL/Podman path

# AI provider — test only the one you use
curl -sS -o /dev/null -w '%{http_code}\n' --connect-timeout 8 https://aiplatform.googleapis.com
curl -sS -o /dev/null -w '%{http_code}\n' --connect-timeout 8 https://us-central1-aiplatform.googleapis.com   # swap your Vertex region
curl -sS -o /dev/null -w '%{http_code}\n' --connect-timeout 8 https://oauth2.googleapis.com
curl -sS -o /dev/null -w '%{http_code}\n' --connect-timeout 8 https://generativelanguage.googleapis.com       # Gemini API-key path

# Optional connectors
curl -sS -o /dev/null -w '%{http_code}\n' --connect-timeout 8 https://docs-cortex.paloaltonetworks.com
curl -sS -o /dev/null -w '%{http_code}\n' --connect-timeout 8 https://api.anthropic.com
```

Air-gapped or IP-based firewall? GitHub publishes its CIDR blocks at `https://api.github.com/meta` (`packages`, `web`, `api` keys); Google publishes its API ranges as netblocks. Hostname allow-listing avoids that maintenance and is recommended.

---

## Install on RHEL / Podman

For **RHEL 8+ with Podman and no Docker.** Run on your server:

```bash
# 1. Download the installer (no login needed — this is a public download)
curl -fSL -o guardian-installer \
  https://github.com/socagents/guardian/releases/latest/download/guardian-installer-podman
chmod +x guardian-installer

# 2. Run it — paste your Kite token when it asks
sudo ./guardian-installer
```

When you see **`Token (input hidden):`**, paste the token from Kite and press **Enter** (the screen stays blank while you paste — that's normal).

The installer sets up Podman + the Compose tool, downloads Guardian, and starts it (a few minutes). When it finishes you'll see a green **"Guardian is running"** message with a web address and a temporary password — keep that screen for the next step.

---

## Install on Docker

For **any other Linux** (Docker is installed automatically if missing). Run on your server:

```bash
# 1. Download the installer (no login needed — this is a public download)
curl -fSL -o guardian-installer \
  https://github.com/socagents/guardian/releases/latest/download/guardian-installer
chmod +x guardian-installer

# 2. Run it — paste your Kite token when it asks
sudo ./guardian-installer
```

When you see **`Token (input hidden):`**, paste the token from Kite and press **Enter**.

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

Re-run the same two steps from your install section above (the download always fetches the latest release), then `sudo ./guardian-installer` again. It detects your existing install and **keeps all your settings, passwords, and data** — only the software is updated.

## Troubleshooting

| Problem | Fix |
|---|---|
| A firewall test above prints `curl: (28)` / `(7)` or hangs | That host is blocked — allow it (port 443) per [Network access](#network-access-firewall-allow-list), then re-test. |
| `denied` / `unauthorized` when downloading | The installer download is public and needs no login. If your firewall blocks `github.com`, ask Kite for the registry-image delivery method. |
| Installer says the token is invalid | Ask Kite for a fresh token, then re-run `sudo ./guardian-installer`. |
| Can't reach `https://…:3000` in the browser | Make sure your firewall allows port **3000** to the server and you used `https://`. |
| Forgot the password | On the server: `sudo /opt/guardian/guardian-reset-admin-password` |
| Is it running? | On the server: `docker compose -f /opt/guardian/docker-compose.yml ps` (works on Podman too) |

---

*Questions? Contact Kite — we're happy to do the first install with you over a call.*
