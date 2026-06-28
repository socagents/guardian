# Installing Guardian — Red Hat (RHEL) with Podman

This guide is for servers running **Red Hat Enterprise Linux (RHEL 8 or newer) with Podman** and **no Docker**. If your server uses Docker, use the other guide (*Installing Guardian — Docker*) instead.

Guardian runs as a small set of containers on one Linux server. You install it once with a single command; everything else is automatic.

---

## Before you start

You need:

1. **A RHEL 8+ server** you can log into, with **`sudo`** (administrator) rights and **Podman** installed.
2. **The access token from Kite.** Kite sends you a long secret string that looks like `ghp_xxxx…` or `github_pat_xxxx…`.
   - Think of it as a **password that lets your server download Guardian's software**. You do **not** need a GitHub account, and you do **not** create anything — just keep the token Kite gave you handy. **Treat it like a password.**
3. **Outbound internet access** from the server to these addresses (your network/firewall team may need to allow them):
   - `ghcr.io` and `pkg-containers.githubusercontent.com` — where Guardian's software is downloaded from
   - `download.docker.com` — for the compose tool Guardian uses (this does **not** install Docker; it's just a small helper command)

You do **not** need to install anything yourself beforehand except Podman — the installer sets up the rest.

---

## Step 1 — Download the installer

Log into your server and run these three commands. They download the installer and make it runnable:

```bash
podman pull ghcr.io/kite-production/guardian-installer-podman:0.2.93
podman run --rm ghcr.io/kite-production/guardian-installer-podman:0.2.93 \
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

When Kite ships a new version, repeat **Step 1** with the new version number (e.g. `:0.2.94`), then run `sudo ./guardian-installer` again. It detects your existing install and **keeps all your settings, passwords, and data** — it only updates the software.

---

*Questions? Contact Kite — we're happy to do the first install with you over a call.*
