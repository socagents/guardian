# Guardian — outbound network allow-list (egress)

Guardian is an on-prem Docker/Podman stack. It requires **no inbound** access from the public internet (the operator reaches the UI on the local network / via a bastion). It **does** make a small set of **outbound HTTPS (443)** connections, listed below.

Allow-list by **hostname** wherever possible — Google and GitHub rotate their IP ranges, so hostname/SNI-based egress rules are far more stable than CIDRs. If your firewall is IP-based, see [§ CIDR / IP-range sources](#cidr--ip-range-sources).

All connections are **client-initiated, TLS 1.2+, port 443**. No plaintext, no non-standard ports.

---

## 1. Always required (runtime)

These are needed for Guardian to run, regardless of configuration.

| Host | Port | Purpose | Direction |
|---|---|---|---|
| `ghcr.io` | 443 | Container image pulls (install **and** every upgrade) | outbound |
| `pkg-containers.githubusercontent.com` | 443 | GHCR image blob/layer storage (ghcr.io redirects here) | outbound |

> If images are mirrored into a **private registry** inside the customer network, the two hosts above can be replaced by that registry's host. See [§ Air-gapped / mirrored registry](#air-gapped--mirrored-registry).

---

## 2. LLM provider — depends on which provider is configured

Guardian's agent runs on one configured model provider. **Allow-list only the row(s) for the provider(s) you use.**

### 2a. Google Vertex AI (default)

| Host | Port | Purpose |
|---|---|---|
| `aiplatform.googleapis.com` | 443 | **Chat inference + context caching** (non-regional endpoint) |
| `<region>-aiplatform.googleapis.com` | 443 | **Embeddings** for the knowledge base / vector search — regional endpoint, e.g. `us-central1-aiplatform.googleapis.com` |
| `oauth2.googleapis.com` | 443 | Service-account JSON → OAuth2 access-token exchange |

> **Both** aiplatform hosts are required when the knowledge base is used: chat/caching go to the **non-regional** `aiplatform.googleapis.com`, while embeddings go to the **region-prefixed** host matching your configured Vertex region. Substitute your region for `<region>`.

### 2b. Google Gemini API key (alternative to Vertex)

| Host | Port | Purpose |
|---|---|---|
| `generativelanguage.googleapis.com` | 443 | Gemini chat inference (API-key path) |

> Embeddings still use Vertex (`<region>-aiplatform.googleapis.com` + `oauth2.googleapis.com`) — the Gemini API-key path covers chat only.

### 2c. Cohere North (private deployment — new)

| Host | Port | Purpose |
|---|---|---|
| `core.stc.com.sa` (customer's own North host) | 443 | Chat inference + tool-calling on the customer's private Cohere deployment |

> This host is **internal to the customer's network** — typically no internet egress is involved. Embeddings still use Vertex (Cohere North exposes no embedding endpoint). A customer running Guardian's brain entirely on Cohere still needs the Vertex embedding host in §2a if they use the knowledge base.

---

## 3. Install / upgrade only (not needed at steady state)

Required when running the installer or applying an upgrade; can stay closed during normal operation.

| Host | Port | Purpose |
|---|---|---|
| `github.com` | 443 | Installer + release-asset download |
| `objects.githubusercontent.com` | 443 | Release-asset (tarball) blob storage (github.com redirects here) |
| `api.github.com` | 443 | Release/manifest metadata lookups |

---

## 4. What Guardian does **not** connect to

- **No inbound** ports from the public internet.
- **No telemetry / phone-home** to Guardian's vendor.
- **No outbound to the operator's own network** by default — the only egress to an operator-controlled destination is the **opt-in `export_to_webhook`** action (a SOAR/ticketing/chat URL the operator explicitly configures and approves). It is off unless configured.
- Connections to the **Cortex XSIAM/XSOAR tenant** are on the customer's own network path (tenant host + port per the connector instance config), not internet egress.

---

## Air-gapped / mirrored registry

If the environment cannot reach `ghcr.io`, mirror the Guardian images into an internal registry and point the installer's digests at it. Only §2 (LLM provider) egress then remains — and if that provider is on-prem Cohere North, Guardian can run with **zero internet egress** except the Vertex embedding host (drop that too if the knowledge base is disabled).

## CIDR / IP-range sources

For IP-based firewalls, resolve the ranges from the authoritative, published sources (they change — re-pull periodically):

- **Google APIs** (`*.googleapis.com`): Google publishes `goog.json` / `cloud.json` netblocks — see Google's "IP ranges for Google APIs and services" (`_spf.google.com` TXT chain / the published JSON).
- **GitHub / GHCR** (`ghcr.io`, `*.githubusercontent.com`, `github.com`): `https://api.github.com/meta` returns the current CIDR blocks (`packages`, `web`, `api` keys).

Hostname-based allow-listing avoids this maintenance entirely and is the recommended approach.

---

*Last updated: 2026-07-01. Cohere North row added with the provider-adapter work (guardian#98). The split Vertex chat-vs-embedding hosts reflect the v0.2.108 egress correction.*
