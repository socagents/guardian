# Installing Guardian — Docker (Linux)

This guide is for servers running **Docker** (most Linux servers). If your server uses **Podman on Red Hat (RHEL) and has no Docker**, use the other guide (*Installing Guardian — Red Hat (RHEL) with Podman*) instead.

Guardian runs as a small set of containers on one Linux server. You install it once with a single command; everything else is automatic.

---

## Before you start

You need:

1. **A Linux server** you can log into, with **`sudo`** (administrator) rights. Docker will be installed automatically if it isn't already present.
2. **The access token from Kite.** Kite sends you a long secret string that looks like `ghp_xxxx…` or `github_pat_xxxx…`.
   - Think of it as a **password that lets your server download Guardian's software**. You do **not** need a GitHub account, and you do **not** create anything — just keep the token Kite gave you handy. **Treat it like a password.**
3. **Outbound internet access** from the server to `ghcr.io`, `pkg-containers.githubusercontent.com`, and (if Docker isn't already installed) `get.docker.com` / `download.docker.com`.

---

## Step 1 — Download the installer

Kite gives you the installer one of two ways. Use whichever Kite tells you:

**Option A — direct download** (if your server can reach `github.com`):

```bash
curl -fSL -o guardian-installer \
  https://github.com/kite-production/guardian/releases/download/v0.2.95/guardian-installer
chmod +x guardian-installer
```

**Option B — from the container registry** (if your firewall allows `ghcr.io` but not `github.com`):

```bash
docker pull ghcr.io/kite-production/guardian-installer:0.2.95
docker run --rm ghcr.io/kite-production/guardian-installer:0.2.95 \
  cat /guardian-installer > guardian-installer
chmod +x guardian-installer
```
> If Option B gives a "denied"/"unauthorized" error, log in first with your token, then retry:
> ```bash
> echo "PASTE-YOUR-TOKEN-HERE" | docker login ghcr.io -u thekite-dev --password-stdin
> ```

---

## Step 2 — Run the installer

Run it with `sudo`. It will ask you for the access token (the screen stays blank while you paste it — that's normal, it's hidden for security):

```bash
sudo ./guardian-installer
```

When you see **`Token (input hidden):`**, paste the token Kite gave you and press **Enter**.

The installer downloads Guardian and starts it (and installs Docker first if needed). This takes a few minutes. When it's done you'll see a green **"Guardian is running"** message with a web address and a temporary password. **Keep that screen** — you need the password in the next step.

---

## Step 3 — Open Guardian and sign in

1. Open a web browser and go to the address shown at the end of the install — it looks like:

   ```
   https://YOUR-SERVER-ADDRESS:3000
   ```

2. Your browser will show a **security warning** (Guardian uses a self-signed certificate on first run). This is expected — choose **Advanced → Proceed / Continue**.

3. Sign in with:
   - **Username:** `admin`
   - **Password:** the temporary password shown at the end of the install
     *(if you lost it, it's saved on the server in `/opt/guardian/.env` on the line `GUARDIAN_DEFAULT_ADMIN_PASSWORD`)*

4. Guardian will immediately ask you to **set your own password**. Do this — you'll be signed out and asked to sign back in with the new password.

---

## Step 4 — Connect your AI model and your tools

After signing in with your new password:

1. Go to **Providers** and add your AI model provider (Google Vertex AI service-account file, or a Gemini API key).
2. Go to **Instances** to connect Guardian to your security tools (e.g. Cortex XSIAM / XSOAR).

Kite will walk you through the exact values if needed.

---

## If something goes wrong

| What you see | What to do |
|---|---|
| `denied` / `unauthorized` when downloading | Use the `docker login` command in the Step 1 note with your token, then retry. |
| Installer says the token is invalid or lacks access | The token may be expired — ask Kite for a fresh one, then re-run `sudo ./guardian-installer`. |
| Browser can't reach `https://…:3000` | Make sure your firewall allows port **3000** to the server, and that you used `https://`. |
| Forgot your password | On the server: `sudo /opt/guardian/guardian-reset-admin-password` |
| Check it's running | On the server: `docker compose -f /opt/guardian/docker-compose.yml ps` |

---

## Updating Guardian later

When Kite ships a new version, repeat **Step 1** with the new version number, then run `sudo ./guardian-installer` again. It detects your existing install and **keeps all your settings, passwords, and data** — it only updates the software.

---

*Questions? Contact Kite — we're happy to do the first install with you over a call.*
