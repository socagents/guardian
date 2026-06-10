# Log Destinations — Design Spec (v0.17.x)

**Status**: spec approved 2026-05-24 (brainstorm session). Implementation in progress as v0.17.0 → v0.17.3 sub-release arc.
**Tracking issue**: GitHub `#TBD` — opened alongside this doc.
**Author**: Claude Opus 4.7 (1M context), brainstormed live with the operator.

---

## Goal

Introduce a first-class, type-discriminated **log destinations** domain object that the operator manages through a CRUD UI under the Integration group. Each destination has a stable id + display name; type-dependent config + secrets live in the row. The destination becomes the canonical handle that xlog (and future features) references when forwarding records.

## Operator-language statement

> "Create another subpage under Integration page for log destinations to support CRUD on those destinations. Each destination has parameters depending on the destination type. Syslog would need ip and port and protocol. Webhook would need url, authentication type, creds (would change based on auth type), and more types of log destinations."

## Brainstormed decisions (locked in)

| # | Question | Decision |
|---|---|---|
| Q1 | Use case | **Both** — xlog forwarding primarily, extensible to future features |
| Q2 | v1 destination types | **Four**: Syslog (UDP/TCP/TLS), Generic HTTP webhook, XSIAM HTTP Collector, Splunk HEC |
| Q3 | Webhook auth modes | **All four**: None / Bearer / Basic / API-key-in-custom-header — dropdown switches the visible cred fields |
| Q4 | xlog bridge | **Replace** the legacy `destination: str` field with `destination_id: str`; one-release deprecation shim |
| Q5 | Test/probe | **Yes — real test message per type**; persist `last_probe_at` / `last_probe_ok` / `last_probe_error` |
| Q6 | Architectural approach | **B — schema-driven yaml manifest** (one yaml + one Python handler per type; UI renders generically) |
| Q7 | `visible_when` clause | **Extend** `ConfigParam` (not fan-out into separate types per auth mode) |

---

## Section 1 — Architecture overview

```
bundles/spark/destinations/                          ← new domain root
├── destination.schema.json                          ← JSON Schema for the per-type spec.yaml
├── syslog/
│   ├── spec.yaml                                    ← display + ConfigParam-style fields[]
│   └── handler.py                                   ← probe() + send() implementations
├── webhook/
│   ├── spec.yaml
│   └── handler.py
├── xsiam_http/
│   ├── spec.yaml
│   └── handler.py
└── splunk_hec/
    ├── spec.yaml
    └── handler.py

bundles/spark/mcp/src/usecase/
├── log_destinations_store.py                        ← new SQLite store
├── destination_types_loader.py                      ← reads all spec.yaml at boot
└── destination_handler_registry.py                  ← maps type_id → handler module

bundles/spark/mcp/src/api/
└── log_destinations.py                              ← REST: CRUD + /probe + /set-default

mcp/agent/app/log-destinations/page.tsx              ← new UI page
mcp/agent/app/api/agent/log-destinations/            ← thin proxy routes
mcp/agent/components/sidebar.tsx                     ← +1 entry under Integration group
mcp/agent/lib/api/log-destinations.ts                ← TS client
mcp/agent/components/form-engine.tsx                 ← extracted reusable form renderer
```

### Service boundaries

- **`phantom-agent` (Next.js)** renders the page, calls embedded MCP via `/api/agent/log-destinations/*`.
- **Embedded MCP (Python FastMCP)** serves `/api/v1/log-destinations/*` REST (bearer auth) + holds the SQLite store + dispatches probes via the handler registry.
- **`xlog`** calls back to MCP at worker-create time via `GET /api/v1/log-destinations/<id>?include_secrets=true` (bearer auth, server-side only) to resolve the destination's config+secrets, then routes the worker's records through the appropriate type handler. Plaintext secrets never traverse the agent tool surface.

### Credential boundary (matches existing connector instances)

- **Agent MCP tools registered**: `log_destinations_list`, `log_destinations_get` — READ only, NO `include_secrets` flag, surfaces redacted "***" sentinel for secret slots.
- **REST-only** (operator UI): `POST`, `PATCH`, `DELETE`, `/probe`, `/set-default`.
- **Agent forbidden**: creating, updating, deleting, probing destinations. CLAUDE.md § Agent credential guardrail.

---

## Section 2 — Storage schema

**SQLite table** at `/app/data/log_destinations.db`:

```sql
CREATE TABLE log_destinations (
    id                   TEXT PRIMARY KEY,             -- uuid4
    name                 TEXT NOT NULL UNIQUE,         -- operator-friendly handle
    type_id              TEXT NOT NULL,                -- 'syslog' | 'webhook' | 'xsiam_http' | 'splunk_hec'
    config_json          TEXT NOT NULL,                -- non-secret config (host/port/url/etc.)
    secret_refs_json     TEXT NOT NULL,                -- {slot_name: secret_path} map
    enabled              INTEGER NOT NULL DEFAULT 1,
    is_default           INTEGER NOT NULL DEFAULT 0,   -- agent uses this when type is unambiguous
    description          TEXT,                          -- optional operator note
    created_at           TEXT NOT NULL,
    updated_at           TEXT NOT NULL,
    last_probe_at        TEXT,
    last_probe_ok        INTEGER,                       -- 1/0/NULL (never probed)
    last_probe_error     TEXT,
    consecutive_failures INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_log_dest_type_id ON log_destinations(type_id);
CREATE INDEX idx_log_dest_enabled ON log_destinations(enabled);
```

### Invariants

- `name` UNIQUE table-wide
- One `is_default=1` per `type_id` (enforced in `store.set_default()` — clears siblings in the same transaction)
- Secrets at `/log_destination/<id>/<slot>` in SecretStore; cascade-delete on row delete

### `LogDestination` dataclass

```python
@dataclass
class LogDestination:
    id: str
    name: str
    type_id: str
    config: dict[str, Any]
    secret_refs: dict[str, str]
    enabled: bool = True
    is_default: bool = False
    description: str | None = None
    created_at: str = ""
    updated_at: str = ""
    last_probe_at: str | None = None
    last_probe_ok: bool | None = None
    last_probe_error: str | None = None
    consecutive_failures: int = 0
```

### Store methods

```python
class LogDestinationStore:
    def create(self, *, name, type_id, config, secrets, description=None,
               is_default=False) -> LogDestination
    def get(self, id_or_name: str) -> LogDestination | None
    def list_all(self, *, type_id: str | None = None,
                 enabled_only: bool = False) -> list[LogDestination]
    def update(self, id, *, name=None, config=None, secrets=None,
               enabled=None, description=None, is_default=None) -> LogDestination | None
    def delete(self, id: str) -> bool
    def set_default(self, id: str) -> LogDestination | None  # clears siblings
    def record_probe(self, id, *, ok: bool, error: str | None,
                     latency_ms: int) -> None
    def merged_config(self, id: str) -> dict[str, Any] | None  # resolves secrets
```

---

## Section 3 — REST API surface

| Method | Path | Body | Returns | Agent-reachable? |
|---|---|---|---|---|
| GET | `/api/v1/destination-types` | — | `{types: [Manifest, ...]}` | **yes** |
| GET | `/api/v1/destination-types/{type_id}` | — | single Manifest | **yes** |
| GET | `/api/v1/log-destinations` | `?type_id=&enabled_only=` | `{destinations: [...]}` redacted | **yes** (`log_destinations_list`) |
| GET | `/api/v1/log-destinations/{id}` | `?include_secrets=true` (bearer-gated, server-side only) | single | **yes** (without `include_secrets`) |
| POST | `/api/v1/log-destinations` | `{name, type_id, config, secrets, description?, is_default?}` | 201 + row | **REST-only** |
| PATCH | `/api/v1/log-destinations/{id}` | partial; `"***"` preserves secret | 200 + row | **REST-only** |
| DELETE | `/api/v1/log-destinations/{id}` | — | 204 | **REST-only** |
| POST | `/api/v1/log-destinations/{id}/probe` | optional `{config?, secrets?}` for dry-run override | `{ok, error, latency_ms, last_probe_at}` | **REST-only** |
| POST | `/api/v1/log-destinations/{id}/set-default` | — | 200 + row | **REST-only** |

`include_secrets=true` is gated by **bearer + originating-from-loopback** check (xlog inside the same container). Operator UI never uses it; the agent NEVER uses it.

---

## Section 4 — YAML manifest format

`destination.schema.json` (JSON Schema Draft 2020-12) — top-level required fields: `schema_version`, `id`, `name`, `description`, `category`, `icon`, `iconColor`, `iconBg`, `fields`, `handler`. Each entry in `fields[]` extends `ConfigParam` with the optional `visible_when` clause.

### Field shape (extends `ConfigParam`)

```yaml
- name: <field_name>
  display: <Display Label>
  type: text | url | string | number | password | secret | textarea
        | select | radio | multi_select | boolean | array | json
  required: bool (default false)
  defaultValue: <string|null>
  description: <inline hint shown under the input>
  options: [<list of strings>]    # for select|radio|multi_select
  visible_when:                    # OPTIONAL — conditional visibility
    field: <other_field_name>      # must be select/radio
    value: <string> | [<string>, ...]
```

**`visible_when` semantics**:
- Frontend: skips rendering the field when the referenced `field`'s current value doesn't match. Hidden fields don't validate `required` and don't submit to the backend.
- Backend: treats hidden-as-absent on POST/PATCH (mirrors frontend behaviour for safety; rejects a hidden field that is present in the body with 400).

### v1 type manifests (full)

#### `syslog/spec.yaml`

```yaml
schema_version: 1
id: syslog
name: Syslog
description: >
  Forward records to a syslog server over UDP, TCP, or TLS.
  Supports RFC3164 and RFC5424 framing with configurable facility.
category: On-prem SIEM
icon: settings_ethernet
iconColor: '#a7c8ff'
iconBg: rgba(167, 200, 255, 0.15)
handler: bundles.spark.destinations.syslog.handler
probe:
  send_test_message: true
fields:
  - name: host
    display: Host
    type: string
    required: true
    description: Syslog server hostname or IP
  - name: port
    display: Port
    type: number
    required: true
    defaultValue: '514'
  - name: protocol
    display: Protocol
    type: select
    required: true
    options: [udp, tcp, tls]
    defaultValue: udp
  - name: framing
    display: Framing
    type: select
    options: [rfc3164, rfc5424]
    defaultValue: rfc5424
    description: >
      Message format. RFC5424 includes structured data;
      RFC3164 is the older BSD format.
  - name: facility
    display: Facility
    type: select
    options:
      - kern
      - user
      - mail
      - daemon
      - auth
      - syslog
      - local0
      - local1
      - local2
      - local3
      - local4
      - local5
      - local6
      - local7
    defaultValue: local0
  - name: tls_ca_cert
    display: CA certificate (PEM)
    type: textarea
    visible_when:
      field: protocol
      value: tls
    description: >
      Optional PEM-encoded CA cert for verifying the server.
      Leave blank to use system trust store.
  - name: tls_client_cert
    display: Client certificate (PEM)
    type: textarea
    visible_when:
      field: protocol
      value: tls
  - name: tls_client_key
    display: Client key (PEM)
    type: secret
    visible_when:
      field: protocol
      value: tls
```

#### `webhook/spec.yaml`

```yaml
schema_version: 1
id: webhook
name: HTTP Webhook
description: >
  POST records to any HTTP endpoint. Supports four auth modes:
  none, bearer token, HTTP basic, or a custom API-key header.
category: Webhook
icon: webhook
iconColor: '#7bdc7b'
iconBg: rgba(123, 220, 123, 0.15)
handler: bundles.spark.destinations.webhook.handler
probe:
  send_test_message: true
fields:
  - name: url
    display: URL
    type: url
    required: true
  - name: method
    display: HTTP method
    type: select
    options: [POST, PUT]
    defaultValue: POST
  - name: content_type
    display: Content-Type
    type: select
    options:
      - application/json
      - application/x-ndjson
      - text/plain
    defaultValue: application/json
  - name: auth_type
    display: Authentication
    type: select
    required: true
    options: [none, bearer, basic, api_key_header]
    defaultValue: none
  - name: bearer_token
    display: Bearer token
    type: secret
    required: true
    visible_when:
      field: auth_type
      value: bearer
  - name: basic_username
    display: Username
    type: text
    required: true
    visible_when:
      field: auth_type
      value: basic
  - name: basic_password
    display: Password
    type: secret
    required: true
    visible_when:
      field: auth_type
      value: basic
  - name: header_name
    display: Header name
    type: text
    required: true
    description: 'e.g. X-API-Key, X-Auth-Token'
    visible_when:
      field: auth_type
      value: api_key_header
  - name: header_value
    display: Header value
    type: secret
    required: true
    visible_when:
      field: auth_type
      value: api_key_header
  - name: custom_headers
    display: Additional headers (JSON)
    type: textarea
    description: >
      Optional. JSON object of additional headers,
      e.g. {"X-Source": "phantom"}
```

#### `xsiam_http/spec.yaml`

```yaml
schema_version: 1
id: xsiam_http
name: XSIAM HTTP Collector
description: >
  Forward records to a Palo Alto XSIAM HTTP Collector endpoint
  using the XSIAM-specific authentication header pair.
category: Cloud SIEM
icon: shield
iconColor: '#fc7676'
iconBg: rgba(252, 118, 118, 0.15)
handler: bundles.spark.destinations.xsiam_http.handler
probe:
  send_test_message: true
fields:
  - name: url
    display: Collector URL
    type: url
    required: true
    description: >
      e.g. https://api-<tenant>.xdr.us.paloaltonetworks.com/logs/v1/<source>
  - name: source
    display: Source tag
    type: text
    required: true
  - name: vendor
    display: Vendor tag (optional)
    type: text
  - name: product
    display: Product tag (optional)
    type: text
  - name: auth_id
    display: Authentication ID
    type: text
    required: true
  - name: auth_key
    display: Authentication key
    type: secret
    required: true
```

#### `splunk_hec/spec.yaml`

```yaml
schema_version: 1
id: splunk_hec
name: Splunk HEC
description: Forward records to a Splunk HTTP Event Collector endpoint.
category: Cloud SIEM
icon: search
iconColor: '#65a30d'
iconBg: rgba(101, 163, 13, 0.15)
handler: bundles.spark.destinations.splunk_hec.handler
probe:
  send_test_message: true
fields:
  - name: url
    display: HEC URL
    type: url
    required: true
  - name: token
    display: HEC token
    type: secret
    required: true
  - name: index
    display: Index (optional)
    type: text
  - name: source
    display: Source
    type: text
    defaultValue: phantom
  - name: sourcetype
    display: Sourcetype
    type: text
    defaultValue: 'phantom:synthetic'
  - name: verify_ssl
    display: Verify SSL
    type: boolean
    defaultValue: 'true'
```

---

## Section 5 — Per-type handler interface

```python
# bundles/spark/destinations/<type_id>/handler.py
from typing import Any

async def probe(merged_config: dict[str, Any]) -> dict[str, Any]:
    """Send a probe message. Returns:
      {"ok": bool, "error": str | None, "latency_ms": int}
    Expected failures (ConnectionRefusedError, 401, timeout) → ok=False.
    Unexpected exceptions bubble (5xx from MCP).
    """


async def send(
    merged_config: dict[str, Any],
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Send a batch of records. Returns:
      {"sent": int, "failed": int, "errors": list[str]}
    Per-record failures are aggregated; partial success is acceptable.
    """
```

`destination_handler_registry.py` imports each module at MCP boot using `importlib.import_module(manifest.handler)` and caches. Missing handler → MCP fails to boot (loud failure, not silent).

### Probe specifics per type

| Type | Probe payload |
|---|---|
| syslog | `<165>1 2026-05-24T00:00:00Z phantom phantom 1 - - phantom test message` (RFC5424) |
| webhook | `POST <url>` with body `{"phantom_test": true, "ts": <iso>}` |
| xsiam_http | `POST <url>` with `{"events":[{"phantom_test":true,...}]}` and the XSIAM headers |
| splunk_hec | `POST <url>` with `{"event":"phantom test","sourcetype":"phantom:synthetic","index":...}` |

---

## Section 6 — xlog bridge + migration

### CreateDataWorkerRequest replacement

Pre-v0.17.0:
```python
class CreateDataWorkerRequest(BaseModel):
    destination: str = Field(default="XSIAM_WEBHOOK", description="...")
```

v0.17.0+:
```python
class CreateDataWorkerRequest(BaseModel):
    destination_id: str | None = Field(
        default=None,
        description=(
            "Stable id (uuid) or name of a configured log destination. "
            "Resolved at worker-create time via MCP. "
            "If null, uses the default destination of the type the "
            "data source's `log_destination` configures."
        ),
    )
    # v0.17.0 deprecation shim — accepts the legacy raw string for ONE
    # release. Logs a deprecation warning and resolves to the closest
    # matching destination (XSIAM_WEBHOOK → the auto-migrated default).
    # Drops in v0.18.0.
    destination: str | None = Field(
        default=None, deprecated=True,
        description="DEPRECATED in v0.17.0 — use destination_id.",
    )
```

### xlog resolver flow

At worker-create time:
1. If `destination_id` is set: `GET /api/v1/log-destinations/<id>?include_secrets=true` via bearer + loopback → merged_config
2. Else if legacy `destination` string is set: log deprecation warning + map to a destination (`XSIAM_WEBHOOK` → the migration default; `udp:host:port` → reject with helpful error pointing at the new UI)
3. Else: 400

The xlog worker invokes `<handler>.send(merged_config, records)` rather than the previous inline UDP/HTTP code.

### First-boot migration

On MCP boot (in `main.py`'s startup), check:
- `os.environ.get("WEBHOOK_ENDPOINT")` set AND no destination with `type_id=xsiam_http` exists in the store?
- If yes: auto-create a destination named "XSIAM Default" of `type_id=xsiam_http` with:
  - `config.url = WEBHOOK_ENDPOINT`
  - `secret.auth_key = WEBHOOK_KEY`
  - `is_default = true`
- Log the auto-migration; emit audit event `log_destination_migrated`.

No env-var migration for `udp:host:port` syslog (operator-specific values; we can't know hosts).

---

## Section 7 — UI design

### Page layout

`app/log-destinations/page.tsx` follows the connector instances tab pattern but at top level (no sub-tabs).

**Header**:
- H1 "Log Destinations" + blurb "Configure where Phantom forwards synthesized security records."
- Right side: search box, "Filter by type" dropdown (All / Syslog / Webhook / XSIAM / Splunk HEC), [+ New Destination] button.

**List** (cards grouped by type, similar to /connectors instance grouping):
- Per-row: icon (from manifest) · name · type badge · default-of-type badge (if `is_default`) · status dot (last_probe_ok green / red / never grey) · enabled toggle · last-probe-time + button row [Test, Edit, Set Default, Delete]
- Expandable: shows resolved config (secrets redacted) inline

**Create / Edit slide-over panel** (mirrors `CreateInstancePanel` shape):
1. Identity section: name, optional description
2. Type selector: dropdown of `destination-types` (with icon + category)
3. Dynamic configuration form: rendered by the new `<FormEngine />` component using the type manifest's `fields[]`. `visible_when` evaluated live.
4. Sticky footer: [Cancel] [Test before save] [Save]

**Test result** banner overlays the panel briefly (green/red, 4s) when Test fires.

### FormEngine component

Extracted from `connectors/page.tsx` so /log-destinations and /connectors share the form renderer (DRY win for the v0.17.x arc — fixes a future-drift hazard).

```tsx
<FormEngine
  fields={typeManifest.fields}
  values={formValues}
  onChange={(name, value) => setFormValues(...)}
  errors={validationErrors}
/>
```

Internally: handles every `ConfigParam.type` widget AND the new `visible_when` skip logic. Single source of truth for form rendering.

### Sidebar entry

`mcp/agent/components/sidebar.tsx` — add under the Integration group:
```ts
{ href: "/log-destinations", label: "Log Destinations", icon: "cloud_upload" }
```

### Per-page docs

- `/help/architecture#log-destinations` — new section: how destinations + handlers + secrets compose
- `/help/user#log-destinations` — operator user-guide section: how to add a syslog destination, how to test, how to set default
- `journeys.ts` — new journey: "Configure log destinations" (4-step click path)

---

## Section 8 — Credential guardrail boundaries

| Operation | Surface | Allowed for agent? |
|---|---|---|
| List destinations (redacted) | MCP tool `log_destinations_list` | YES |
| Get single destination (redacted) | MCP tool `log_destinations_get` | YES |
| Get with secrets resolved | REST `?include_secrets=true` (loopback-gated) | NO — server-internal only |
| Create destination | REST POST | NO — REST-only |
| Update destination | REST PATCH | NO |
| Delete destination | REST DELETE | NO |
| Probe destination | REST POST `/probe` | NO |
| Set default | REST POST `/set-default` | NO |

Per CLAUDE.md § Catalog boundary ≠ credential boundary — log destinations carry secrets, so they're firmly on the **credential side**. Even though catalog mutations (e.g. marketplace install) ARE allowed for the agent, destinations are NOT.

Agent UX when asked "create a Splunk HEC destination for me":
> I can't create log destinations directly — they carry credentials and live on the credential side of the boundary. Open `/log-destinations` and click "+ New Destination" to add a Splunk HEC. Once it's saved, I can reference it by name when creating data workers.

---

## Section 9 — Sub-release plan

Per CLAUDE.md § Release-readiness gate: this is a multi-release arc; tag fires at arc completion.

| Sub-release | Concept | Verification |
|---|---|---|
| **v0.17.0** | Backend foundation. destination.schema.json + 4 spec.yaml + handler stubs + loader + registry + store + REST + agent MCP read tools + pytest. **No UI yet.** | REST surface verified via curl/script |
| **v0.17.1** | UI page + FormEngine extraction + ConfigParam.visible_when. Operator can CRUD destinations end-to-end. | UI smoke + e2e API surface |
| **v0.17.2** | xlog bridge: `destination_id` replaces `destination` on CreateDataWorkerRequest. Migration of `WEBHOOK_ENDPOINT` env var. Agent's `phantom_create_data_worker` tool docstring updated. | Synthetic worker round-trip: create syslog dest → attach → run worker → confirm UDP receipt |
| **v0.17.3** | E2E battery (`scripts/e2e_v0173_log_destinations.py`) + help/architecture + help/user + journeys.ts + CHANGELOG/release-notes for the arc. | Battery passes 100%; arc-acceptance criteria all green; ready for tag |

### Capability acceptance criteria (gate to tag v0.17.3)

- [ ] Operator opens `/log-destinations`, sees the page with the [+ New Destination] button and an empty list (or just the auto-migrated XSIAM Default)
- [ ] Create a Syslog destination targeting `udp:127.0.0.1:5514`, save, see it in the list
- [ ] Click Test → green badge appears within 2s; `last_probe_at` updates
- [ ] Create a Generic HTTP webhook with `auth_type=bearer` → form re-renders to show the bearer_token secret field; cred basic fields stay hidden
- [ ] Change `auth_type` to `basic` → bearer_token hides, username + basic_password fields appear; previously-entered bearer token is preserved in form state but won't submit
- [ ] Save the webhook → REST POST with only the visible fields
- [ ] PATCH the webhook with `auth_type` change → secret refs cleaned up via SecretStore cascade
- [ ] Delete the syslog destination → confirm two-click pattern; secret store cleanup; instance removed from list
- [ ] Mark a destination as default → set-default endpoint clears default flag on siblings of same type
- [ ] Create a data worker with `destination_id=<syslog id>` → records UDP-arrive at the listener
- [ ] Legacy `destination="XSIAM_WEBHOOK"` on a worker-create call → logs deprecation warning, resolves to the auto-migrated default
- [ ] Agent calls `log_destinations_list` → returns redacted list (no plaintext secrets ever)
- [ ] Agent attempts to call a write tool that doesn't exist → tool catalog confirms only `log_destinations_list` + `log_destinations_get` are registered

### Forbidden going forward

- Hardcoding new destination types into the codebase — must ship as `<type>/spec.yaml` + handler module
- Adding write tools (`create`, `update`, `delete`, `probe`) to the agent's MCP catalog — REST-only forever (credential guardrail)
- Bypassing the FormEngine in either /connectors or /log-destinations — drift between the two will silently rot field rendering
- Accepting the legacy `destination: str` field on `CreateDataWorkerRequest` past v0.17.x — drops in v0.18.0

---

## Section 10 — Documentation discipline

Every sub-release ships docs in lockstep with code (CLAUDE.md § Documentation discipline):

| Sub-release | Doc deltas |
|---|---|
| v0.17.0 | CHANGELOG + release-notes (backend foundation; no operator-visible UI yet — docs note this) |
| v0.17.1 | `/help/architecture#log-destinations` (new section) + `/help/user#log-destinations` (new section) + sidebar entry verified |
| v0.17.2 | architecture page's "xlog ↔ MCP" connections section updated to show destination resolution callback |
| v0.17.3 | journeys.ts new journey, CHANGELOG + release-notes for arc closure, E2E battery script ships |

Architecture-page section to update specifically:
- New section `#log-destinations`: storage table schema, REST surface, type loader, handler registry, secrets boundary
- New connection in the "Inter-service connections" enumeration: `xlog (Python) → embedded MCP (loopback HTTPS, bearer auth, `GET /api/v1/log-destinations/<id>?include_secrets=true`)`

User-guide section content:
- "What are log destinations" — one paragraph
- "Configure a syslog destination" — numbered steps
- "Configure a webhook destination" — including auth-type discriminator
- "Test before save" — workflow
- "Set the default for a type" — semantics
