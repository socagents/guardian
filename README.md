# Guardian

**Guardian** is an AI incident-response agent for Cortex XSIAM / XSOAR — it runs evidence-grounded investigations, XQL hunts, case enrichment, and response orchestration. It installs as a small set of containers on one Linux server.

This repository hosts the **public installer releases**. Pick the guide that matches your server:

- 🟥 **Red Hat (RHEL) with Podman, no Docker** → [Install on RHEL / Podman](#install-on-rhel--podman)
- 🐧 **Any other Linux with Docker** → [Install on Docker](#install-on-docker)

---

## Before you start

You need:

1. **A Linux server** you can log into, with **`sudo`** (administrator) rights.
2. **An access token from Kite.** Kite sends you a long secret string that looks like `ghp_xxxx…`. Think of it as a **password that lets your server download Guardian's software** — you don't need a GitHub account and you don't create anything; just keep it handy and **treat it like a password**. You'll paste it once, when the installer asks.
3. **Outbound internet access** from the server to:
   - `ghcr.io` and `pkg-containers.githubusercontent.com` (Guardian's software)
   - `github.com` (to download the installer below)
   - **RHEL/Podman only:** also `download.docker.com` (for the Compose tool — this does *not* install Docker)

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
| `denied` / `unauthorized` when downloading | The installer download is public and needs no login. If your firewall blocks `github.com`, ask Kite for the registry-image delivery method. |
| Installer says the token is invalid | Ask Kite for a fresh token, then re-run `sudo ./guardian-installer`. |
| Can't reach `https://…:3000` in the browser | Make sure your firewall allows port **3000** to the server and you used `https://`. |
| Forgot the password | On the server: `sudo /opt/guardian/guardian-reset-admin-password` |
| Is it running? | On the server: `docker compose -f /opt/guardian/docker-compose.yml ps` (works on Podman too) |

---

*Questions? Contact Kite — we're happy to do the first install with you over a call.*
