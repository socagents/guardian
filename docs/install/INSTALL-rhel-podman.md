# Installing Guardian — Red Hat (RHEL) with Podman

This guide is for servers running **Red Hat Enterprise Linux (RHEL 8 or newer) with Podman** and **no Docker**. If your server uses Docker, use the other guide (*Installing Guardian — Docker*) instead.

Guardian runs as a small set of containers on one Linux server. You install it once with a single command; everything else is automatic.

---

## Before you start

You need:

1. **A RHEL 8+ server** you can log into, with **`sudo`** (administrator) rights and **Podman** installed.
2. **The access token from Kite.** Kite sends you a long secret string that looks like `ghp_xxxx…` or `github_pat_xxxx…`.
   - Think of it as a **password that lets your server download Guardian's software**. You do **not** need a GitHub account, and you do **not** create anything — just keep the token Kite gave you handy. **Treat it like a password.**
3. **Outbound internet access** (HTTPS / TCP 443) from the server to a small, fixed set of hosts. To **install + run** Guardian the server needs exactly three: `ghcr.io`, `pkg-containers.githubusercontent.com`, and `download.docker.com`. To **use** Guardian's AI it also needs your AI provider's host. Your firewall/security team will want the precise list with IP ranges — it's in **[Appendix — Firewall allow-list](#appendix--firewall-allow-list-for-your-networksecurity-team)** at the end of this guide (empirically validated, exact FQDNs + CIDRs).

You do **not** need to install anything yourself beforehand except Podman — the installer sets up the rest.

---

## Step 1 — Download the installer

Log into your server and run these three commands. They download the installer and make it runnable:

```bash
podman pull ghcr.io/kite-production/guardian-installer-podman:0.2.95
podman run --rm ghcr.io/kite-production/guardian-installer-podman:0.2.95 \
  cat /guardian-installer > guardian-installer
chmod +x guardian-installer
```

> **If you get a "denied" / "unauthorized" error here**, log in first with the token from Kite, then re-run the three commands above:
> ```bash
> echo "PASTE-YOUR-TOKEN-HERE" | podman login ghcr.io -u thekite-dev --password-stdin
> ```

---

## Step 2 — Run the installer

Run the installer with `sudo`. It will ask you for the access token (the screen stays blank while you paste it — that's normal, it's hidden for security):

```bash
sudo ./guardian-installer
```

When you see **`Token (input hidden):`**, paste the token Kite gave you and press **Enter**.

The installer then sets everything up — it installs the helper tools, downloads Guardian, and starts it. This takes a few minutes. When it's done you'll see a green **"Guardian is running"** message with a web address and a temporary password. **Keep that screen** — you need the password in the next step.

---

## Step 3 — Open Guardian and sign in

1. Open a web browser and go to the address shown at the end of the install — it looks like:

   ```
   https://YOUR-SERVER-ADDRESS:3000
   ```

2. Your browser will show a **security warning** (Guardian uses a self-signed certificate on first run). This is expected — choose **Advanced → Proceed / Continue** to go to the site.

3. Sign in with:
   - **Username:** `admin`
   - **Password:** the temporary password shown at the end of the install
     *(if you lost it, it's saved on the server in `/opt/guardian/.env` on the line `GUARDIAN_DEFAULT_ADMIN_PASSWORD`)*

4. Guardian will immediately ask you to **set your own password**. Do this — you'll be signed out and asked to sign back in with the new password. From then on, that's your password.

---

## Step 4 — Connect your AI model and your tools

After you've signed in with your new password:

1. Go to **Providers** and add your AI model provider (a Google Vertex AI service-account file, or a Gemini API key — whichever Kite set you up with).
2. Go to **Instances** to connect Guardian to your security tools (e.g. Cortex XSIAM / XSOAR).

Kite will walk you through the exact values for these if needed.

---

## If something goes wrong

| What you see | What to do |
|---|---|
| `denied` / `unauthorized` when downloading (Step 1) | Run the `podman login` command in the Step 1 note with your token, then retry. |
| Installer says the token is invalid or lacks access | The token may be expired or wrong — ask Kite for a fresh one, then re-run `sudo ./guardian-installer`. |
| `docker compose` / compose error during install | The installer needs `download.docker.com` reachable to fetch the compose tool. Ask your network team to allow it, then re-run the installer. |
| Browser can't reach `https://…:3000` | Make sure your firewall allows port **3000** to the server, and that you used `https://` (not `http://`). |
| Forgot your password | On the server, run: `sudo /opt/guardian/guardian-reset-admin-password` and follow the prompts. |
| Check it's running | On the server: `docker compose -f /opt/guardian/docker-compose.yml ps` (this works on Podman too). |

---

## Updating Guardian later

When Kite ships a new version, repeat **Step 1** with the new version number (e.g. `:0.2.95`), then run `sudo ./guardian-installer` again. It detects your existing install and **keeps all your settings, passwords, and data** — it only updates the software.

---

## Appendix — Firewall allow-list (for your network/security team)

Guardian needs a **small, fixed set of outbound HTTPS (TCP 443)** destinations from the server. This list was **empirically validated** on a fresh RHEL 8.10 + Podman 4.9 host: with the host firewall set to **deny all outbound traffic** and allow only the entries below, a full `guardian-installer-podman` install pulled every image and started the stack — and **nothing outside this list was attempted** (verified with a default-DROP `iptables` egress policy + connection logging).

> The hosts below are **specific endpoints** (e.g. `ghcr.io`, `pkg-containers.githubusercontent.com`) — not bare apex domains. You do **not** need to allow `github.com`.

### 1. Required to INSTALL + RUN Guardian — allow all three

| Destination (FQDN) | Purpose |
|---|---|
| `ghcr.io` | Pull Guardian's container images (registry API + authentication) — GitHub Container Registry |
| `pkg-containers.githubusercontent.com` | The image data itself (container layers) |
| `download.docker.com` | The Compose v2 plugin Guardian uses as Podman's compose runner — **this does not install Docker** |

**If your firewall filters by FQDN / SNI / HTTP proxy (recommended):** allow exactly those three hosts.

**If your firewall filters by IP range (CIDR):**

| Host | CIDR(s) | Authoritative source |
|---|---|---|
| `pkg-containers.githubusercontent.com` | **`185.199.108.0/22`** (stable) | `https://api.github.com/meta` → `web` |
| `ghcr.io` | GitHub: `140.82.112.0/20`, `192.30.252.0/22`, `185.199.108.0/22` **and** Microsoft Azure (e.g. `20.233.0.0/16`) | `https://api.github.com/meta` → `packages` + `web` |
| `download.docker.com` | AWS CloudFront ranges (large, rotating) | `https://ip-ranges.amazonaws.com/ip-ranges.json` → service `CLOUDFRONT` |

> **Important for `ghcr.io` and `download.docker.com`:** both are served from rotating cloud/CDN address pools (Azure, AWS CloudFront), so a fixed IP allow-list will drift. **Filter these two by FQDN/SNI if at all possible**; if you must use CIDRs, pull the current ranges from the authoritative sources above and refresh them periodically.

### 2. Required to USE Guardian's AI — allow the set matching your provider

Guardian calls your chosen AI provider at runtime. Allow **only** the one Kite set you up with:

- **Google Vertex AI** — `oauth2.googleapis.com`, `www.googleapis.com`, and `<region>-aiplatform.googleapis.com` (use your configured region, e.g. `us-central1-aiplatform.googleapis.com`).
- **Google Gemini API key** — `generativelanguage.googleapis.com`.

### 3. Explicitly NOT required (do not add these)

- **`github.com` / `objects.githubusercontent.com`** — only the *Docker* installer downloads from there; the Podman installer is delivered from `ghcr.io`, so these are never used on RHEL/Podman.
- **Your RHEL package repositories** (`cdn.redhat.com`, `subscription.rhsm.redhat.com`, Red Hat Satellite, or your cloud's RHUI) — the installer uses them to add `podman-docker` + the compose plugin, but these are the **same repositories you already use to patch RHEL**, not a Guardian-specific URL.
- **Your security tools (Cortex XSIAM / XSOAR)** — Guardian reaches these on your **internal** network, not the internet.

*Validation: fresh RHEL 8.10 + Podman 4.9; host `iptables` set to `OUTPUT` policy DROP with only the allow-list above (plus DNS + loopback); the full `guardian-installer-podman` install completed and re-pulled all service images with **zero** blocked connections logged.*

---

*Questions? Contact Kite — we're happy to do the first install with you over a call.*
