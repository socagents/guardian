# Store-driven Log-Destination Resolution — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When logs are generated, the target is resolved from the operator's configured Log Destinations (never a hardcoded address) — the agent lists by transport, uses the single match, asks when ambiguous, and can cold-start a plain syslog destination itself.

**Architecture:** The agent passes a destination *reference* (`logdest:<id>`) or a secretless `udp:host:port` to `phantom_create_data_worker`. The MCP-side connector-proxy chokepoint (`proxy_call_tool`) resolves `logdest:<id>` against `log_destinations.db` — including the secret for `xsiam_http`, which the agent never sees — and forwards a concrete address (+ `webhookUrl`/`webhookKey`) to the xlog connector → xlog service. Resolution logic lives in the simulation skills + a one-line system-prompt invariant.

**Tech Stack:** Python FastMCP (embedded MCP), Strawberry GraphQL (xlog), Next.js (agent system prompt/skills), pytest.

**Spec:** `docs/superpowers/specs/2026-05-30-store-driven-log-destination-resolution-design.md`
**Issue:** open before first code commit (Scenario 1, `component:agent`, `area:chat`/`area:rest-api`, `status:in-progress`). Target version **v0.17.113+** (one contained arc; mid-arc commits are prerequisites).

---

## File map

| File | Responsibility | Change |
|---|---|---|
| `bundles/spark/mcp/src/usecase/builtin_components/self_mod_tools.py` | builtin MCP tools | **add** `log_destinations_create` (secretless syslog) |
| `bundles/spark/mcp/src/usecase/connector_loader.py` | builtin-tool registry | **register** `log_destinations_create` in `_BUILTIN_LEGACY_TOOLS` (~line 158) |
| `bundles/spark/mcp/src/usecase/log_destination_resolver.py` | **new** — resolve `logdest:<id>` → address/secret (same-process store read) | **create** |
| `bundles/spark/mcp/src/pkg/connector_proxy.py` | connector dispatch chokepoint (`proxy_call_tool`, line 122) | **call resolver** for `phantom_create_data_worker` |
| `xlog/app/types/sender.py` | GraphQL input types (`DataWorkerCreateInput`, line 46) | **add** `webhook_url` / `webhook_key` optional fields |
| `xlog/app/schema.py` | `create_data_worker` resolver + `_get_webhook_headers` | **use** passed url/key in the 3 `XSIAM_WEBHOOK` branches (659/761/904), env fallback |
| `bundles/spark/connectors/xlog/src/workers.py` | connector tool `phantom_create_data_worker` (`CreateDataWorkerRequest`, line 17) | **add** `webhook_url`/`webhook_key` (forwarded as `webhookUrl`/`webhookKey`); rewrite the destination docstring |
| `bundles/spark/connectors/xlog/src/_graphql_client.py` (or the mutation builder) | createDataWorker mutation variables | **forward** webhookUrl/webhookKey |
| `bundles/spark/skills/generate-logs.md`, `bundles/spark/skills/run-scenario.md` | simulation skills | **add** the resolution recipe |
| `mcp/agent/lib/system-prompt.ts` | agent system prompt | **add** the no-hardcoded-destination invariant |
| `mcp/agent/app/help/architecture/page.tsx` (`#log-destinations`), `app/help/user/page.tsx`, `lib/journeys.ts`, `CHANGELOG.md`, `lib/release-notes.ts`, `CLAUDE.md` | docs | **update** |

---

## Task 1 — `log_destinations_create` MCP tool (secretless syslog)

**Files:**
- Modify: `bundles/spark/mcp/src/usecase/builtin_components/self_mod_tools.py` (after `log_destinations_get`, ~line 2845)
- Modify: `bundles/spark/mcp/src/usecase/connector_loader.py:158`
- Test: `bundles/spark/mcp/tests/test_log_destinations_create_tool.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_log_destinations_create_tool.py
import importlib
from usecase.builtin_components import self_mod_tools

def test_create_secretless_syslog_first_is_default(tmp_path, monkeypatch):
    monkeypatch.setenv("PHANTOM_DATA_ROOT", str(tmp_path))
    # fresh store
    from usecase import log_destinations_store as lds
    importlib.reload(lds)
    out = self_mod_tools.log_destinations_create(
        name="probe-syslog", host="10.1.1.1", port=514, protocol="udp")
    assert out["type_id"] == "syslog"
    assert out["config"]["host"] == "10.1.1.1"
    assert out["is_default"] is True            # first syslog → default
    assert out["secrets"] == {}                 # no secret slot

def test_create_rejects_bad_protocol(tmp_path, monkeypatch):
    monkeypatch.setenv("PHANTOM_DATA_ROOT", str(tmp_path))
    from usecase import log_destinations_store as lds
    importlib.reload(lds)
    out = self_mod_tools.log_destinations_create(
        name="bad", host="h", port=514, protocol="https")
    assert "error" in out and "protocol" in out["error"].lower()
```

- [ ] **Step 2: Run it — expect FAIL** (`AttributeError: log_destinations_create`)

```bash
cd bundles/spark/mcp && PYTHONPATH=$PWD/src python3 -m pytest tests/test_log_destinations_create_tool.py -x
```

- [ ] **Step 3: Implement the tool** (mirror `log_destinations_list` at line 2803)

```python
def log_destinations_create(
    name: str, host: str, port: int, protocol: str = "udp"
) -> dict[str, Any]:
    """Create a plain (secretless) syslog Log Destination by prompt.

    SECRETLESS SYSLOG ONLY — this tool deliberately cannot create a
    destination that carries a secret (TLS-syslog, xsiam_http, splunk_hec).
    Those are operator-only: tell the operator to add them in the
    /log-destinations UI. (Catalog-side per the credential guardrail:
    writes NO SecretStore value.)

    Set the first syslog destination as the type default so a later bare
    "simulate" auto-routes to it.

    Args:
        name: operator-facing handle (unique).
        host: syslog target host/IP.
        port: syslog target port.
        protocol: 'udp' or 'tcp' (NOT tls — that needs a cert secret → UI).
    """
    proto = (protocol or "udp").lower()
    if proto not in ("udp", "tcp"):
        return {"error": f"protocol must be 'udp' or 'tcp' (got {protocol!r}); "
                         "TLS syslog carries a client-key secret — add it in the "
                         "/log-destinations UI."}
    from usecase.log_destinations_store import get_log_destination_store
    s = get_log_destination_store()
    first_of_type = not s.list_all(type_id="syslog")
    dest = s.create(
        name=name, type_id="syslog",
        config={"host": str(host), "port": str(port), "protocol": proto},
        secrets={}, is_default=first_of_type,
        description="Created via agent (secretless syslog).",
    )
    return dest.to_dict(include_secrets=False)
```

- [ ] **Step 4: Register the tool** — `connector_loader.py:158`, after the `log_destinations_get` entry:

```python
    ("log_destinations_create", self_mod_tools.log_destinations_create),
```

- [ ] **Step 5: Run tests — expect PASS** (same command as Step 2).

- [ ] **Step 6: Commit**

```bash
git add bundles/spark/mcp/src/usecase/builtin_components/self_mod_tools.py \
        bundles/spark/mcp/src/usecase/connector_loader.py \
        bundles/spark/mcp/tests/test_log_destinations_create_tool.py
git commit -m "feat(mcp): log_destinations_create — secretless syslog, first-of-type default (Refs #N)"
```

> **Verify `s.create` kwargs** against `log_destinations_store.py:249` before Step 3 — match the actual param names (`name, type_id, config, secrets, enabled, is_default, description`). Adjust if the signature differs.

---

## Task 2 — `logdest:<id>` resolver (MCP-side, reads the store + secret)

**Files:**
- Create: `bundles/spark/mcp/src/usecase/log_destination_resolver.py`
- Test: `bundles/spark/mcp/tests/test_log_destination_resolver.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_log_destination_resolver.py
import importlib
from usecase.log_destination_resolver import resolve_worker_args

def _store(tmp_path, monkeypatch):
    monkeypatch.setenv("PHANTOM_DATA_ROOT", str(tmp_path))
    from usecase import log_destinations_store as lds
    importlib.reload(lds)
    return lds.get_log_destination_store()

def test_resolve_syslog_ref_to_address(tmp_path, monkeypatch):
    s = _store(tmp_path, monkeypatch)
    d = s.create(name="b", type_id="syslog",
                 config={"host": "10.0.0.8", "port": "514", "protocol": "udp"},
                 secrets={})
    args = resolve_worker_args({"destination": f"logdest:{d.id}", "type": "CEF"})
    assert args["destination"] == "udp:10.0.0.8:514"
    assert "webhook_url" not in args

def test_resolve_xsiam_http_injects_url_and_secret(tmp_path, monkeypatch):
    s = _store(tmp_path, monkeypatch)
    d = s.create(name="c", type_id="xsiam_http",
                 config={"url": "https://x/logs", "source": "tag"},
                 secrets={"auth_key": "SUPERSECRET"})
    args = resolve_worker_args({"destination": f"logdest:{d.id}"})
    assert args["destination"] == "XSIAM_WEBHOOK"
    assert args["webhook_url"] == "https://x/logs"
    assert args["webhook_key"] == "SUPERSECRET"

def test_passthrough_non_ref(tmp_path, monkeypatch):
    _store(tmp_path, monkeypatch)
    args = resolve_worker_args({"destination": "udp:1.2.3.4:514"})
    assert args["destination"] == "udp:1.2.3.4:514"
```

- [ ] **Step 2: Run it — expect FAIL** (module not found).

```bash
cd bundles/spark/mcp && PYTHONPATH=$PWD/src python3 -m pytest tests/test_log_destination_resolver.py -x
```

- [ ] **Step 3: Implement the resolver**

```python
# usecase/log_destination_resolver.py
"""Resolve a `logdest:<id>` worker destination reference to a concrete
address — MCP-side only (this process can read both log_destinations.db
and SecretStore). The agent passes the reference; the secret never reaches
the agent. Called from the connector-proxy chokepoint before forwarding to
the xlog connector."""
from __future__ import annotations
from typing import Any

_PREFIX = "logdest:"


def resolve_worker_args(args: dict[str, Any]) -> dict[str, Any]:
    dest = args.get("destination")
    if not isinstance(dest, str) or not dest.startswith(_PREFIX):
        return args  # raw address / XSIAM_WEBKOOK / etc. — untouched
    dest_id = dest[len(_PREFIX):]
    from usecase.log_destinations_store import get_log_destination_store
    store = get_log_destination_store()
    row = store.get(dest_id)
    if row is None:
        raise ValueError(f"log destination {dest_id!r} not found")
    cfg = row.config
    if row.type_id == "syslog":
        args["destination"] = f"{cfg['protocol']}:{cfg['host']}:{cfg['port']}"
    elif row.type_id == "xsiam_http":
        resolved = store.resolve_config_with_secrets(dest_id)  # store.py:226
        args["destination"] = "XSIAM_WEBHOOK"
        args["webhook_url"] = cfg["url"]
        args["webhook_key"] = resolved.get("auth_key")
    else:
        raise ValueError(
            f"destination type {row.type_id!r} is not wired into generation "
            "(webhook/splunk_hec land in a later release)")
    return args
```

- [ ] **Step 4: Run tests — expect PASS.** (Confirm `row.config`, `row.type_id`, `resolve_config_with_secrets` names against `log_destinations_store.py` first.)

- [ ] **Step 5: Commit**

```bash
git add bundles/spark/mcp/src/usecase/log_destination_resolver.py \
        bundles/spark/mcp/tests/test_log_destination_resolver.py
git commit -m "feat(mcp): logdest:<id> resolver — syslog address + xsiam_http secret injection (Refs #N)"
```

---

## Task 3 — Wire the resolver into the connector-proxy chokepoint

**Files:**
- Modify: `bundles/spark/mcp/src/pkg/connector_proxy.py` (`proxy_call_tool`, line 122)
- Test: `bundles/spark/mcp/tests/test_proxy_resolves_destination.py` (new)

- [ ] **Step 1: Read `proxy_call_tool` (connector_proxy.py:122)** to confirm the `(container_url, tool_name, args)` signature + where args are sent. Inject the resolver at the top of the function body.

- [ ] **Step 2: Write the failing test** — monkeypatch the HTTP send, assert a `logdest:` destination is rewritten before send:

```python
# tests/test_proxy_resolves_destination.py
import importlib, asyncio
from pkg import connector_proxy

def test_proxy_rewrites_logdest(tmp_path, monkeypatch):
    monkeypatch.setenv("PHANTOM_DATA_ROOT", str(tmp_path))
    from usecase import log_destinations_store as lds
    importlib.reload(lds)
    d = lds.get_log_destination_store().create(
        name="b", type_id="syslog",
        config={"host": "10.0.0.8", "port": "514", "protocol": "udp"}, secrets={})
    captured = {}
    async def fake_send(url, tool, args):
        captured.update(args); return {"ok": True}
    monkeypatch.setattr(connector_proxy, "_send_tool_call", fake_send)  # match real inner fn
    asyncio.run(connector_proxy.proxy_call_tool(
        "http://x:9000", "phantom_create_data_worker",
        {"destination": f"logdest:{d.id}", "type": "CEF"}))
    assert captured["destination"] == "udp:10.0.0.8:514"
```

- [ ] **Step 3: Implement** — at the top of `proxy_call_tool`, before the dispatch:

```python
    if tool_name == "phantom_create_data_worker":
        try:
            from usecase.log_destination_resolver import resolve_worker_args
            args = resolve_worker_args(args)
        except Exception as exc:  # surface as a tool error, do NOT fall back to a hardcoded addr
            return {"isError": True, "error": f"destination resolution failed: {exc}"}
```

> Adjust the test's `_send_tool_call` name to the real inner send fn read in Step 1. The guard keeps the generic proxy untouched for every other tool.

- [ ] **Step 4: Run tests — expect PASS.** Then the full MCP suite:

```bash
cd bundles/spark/mcp && PYTHONPATH=$PWD/src python3 -m pytest tests/ -x
```

- [ ] **Step 5: Commit**

```bash
git add bundles/spark/mcp/src/pkg/connector_proxy.py \
        bundles/spark/mcp/tests/test_proxy_resolves_destination.py
git commit -m "feat(mcp): resolve logdest:<id> in proxy_call_tool before forwarding to xlog connector (Refs #N)"
```

---

## Task 4 — xlog accepts a passed webhook URL + key

**Files:**
- Modify: `xlog/app/types/sender.py:46` (`DataWorkerCreateInput`)
- Modify: `xlog/app/schema.py` (`_get_webhook_headers` ~line 90; the 3 `XSIAM_WEBHOOK` branches at 659 / 761 / 904)
- Test: `xlog/tests/test_create_data_worker_webhook_override.py` (new)

- [ ] **Step 1: Add the input fields** — at the end of `DataWorkerCreateInput` (after `schema_override`):

```python
    # v0.17.x — store-driven xsiam_http: when the MCP resolves an
    # xsiam_http Log Destination it passes the row's url + secret here so
    # xlog uses them instead of the WEBHOOK_ENDPOINT/WEBHOOK_KEY env vars.
    webhook_url: Optional[str] = None
    webhook_key: Optional[str] = None
```

- [ ] **Step 2: Make `_get_webhook_headers` accept an override key** (schema.py ~90):

```python
def _get_webhook_headers(key_override: str | None = None) -> dict:
    key = key_override or WEBHOOK_KEY
    endpoint_ok = True  # endpoint checked by caller now
    if not key:
        raise ValueError("webhook key required for XSIAM_WEBHOOK destination.")
    return {"Authorization": key, "Content-Type": "application/json"}
```

- [ ] **Step 3: In each `XSIAM_WEBHOOK` branch (659, 761, 904)** use the passed values, env fallback:

```python
            wh_url = request_input.webhook_url or WEBHOOK_ENDPOINT
            if not wh_url:
                raise ValueError("WEBHOOK_ENDPOINT or a resolved destination URL is required.")
            headers = _get_webhook_headers(request_input.webhook_key)
            data_worker = WebhookSender(
                worker_name=worker_name,
                destination=wh_url,
                payloads=payloads,
                interval=request_input.interval,
                verify_ssl=request_input.verify_ssl,
                headers=headers,
            )
```

- [ ] **Step 4: Write + run the test** (xlog uses passed url/key; absent → env). Use xlog's existing test harness/fixtures:

```bash
cd xlog && PYTHONPATH=$PWD python3 -m pytest tests/test_create_data_worker_webhook_override.py -x
```

- [ ] **Step 5: Commit**

```bash
git add xlog/app/types/sender.py xlog/app/schema.py xlog/tests/test_create_data_worker_webhook_override.py
git commit -m "feat(xlog): createDataWorker accepts webhook_url/webhook_key (store-driven xsiam_http; env fallback) (Refs #N)"
```

---

## Task 5 — Connector tool forwards the webhook fields + new docstring

**Files:**
- Modify: `bundles/spark/connectors/xlog/src/workers.py` (`CreateDataWorkerRequest` line 17; `phantom_create_data_worker` line 306; the mutation builder)
- Modify: `bundles/spark/connectors/xlog/src/_graphql_client.py` (or wherever the createDataWorker mutation variables are assembled)
- Test: `bundles/spark/connectors/xlog/tests/` (extend the existing worker test)

- [ ] **Step 1:** Add to `CreateDataWorkerRequest` + the `phantom_create_data_worker` signature: `webhook_url: Optional[str] = None`, `webhook_key: Optional[str] = None`. Thread them into the GraphQL `createDataWorker` variables as `webhookUrl` / `webhookKey` (strawberry maps camelCase↔snake).
- [ ] **Step 2:** Rewrite the `destination` field docstring (lines 26–87): remove the "xsiam_http → 'XSIAM_WEBHOOK' (env vars)" guidance; document that the agent passes `logdest:<id>` (resolved MCP-side) or a raw `udp:host:port`, and that `webhook_url`/`webhook_key` are **MCP-injected, not operator-set** (mark them internal). Keep destination NOT required (resolution rewrites it); the v0.17.111/112 narration filter already hides the read calls.
- [ ] **Step 3:** Run the connector test suite; **bug-family audit** — grep `bundles/spark/connectors/*/src/` for other tools that hardcode `XSIAM_WEBHOOK` defaults.
- [ ] **Step 4: Commit** `feat(xlog-connector): forward webhook_url/key; logdest:<id> destination docstring (Refs #N)`

---

## Task 6 — Resolution recipe in the simulation skills + system-prompt invariant

**Files:**
- Modify: `bundles/spark/skills/generate-logs.md`, `bundles/spark/skills/run-scenario.md`
- Modify: `mcp/agent/lib/system-prompt.ts`

- [ ] **Step 1:** In both skills, replace the "use `phantom_get_technology_stack.full_address`" destination guidance with the recipe:

```markdown
## Choosing the destination (NEVER hardcode one)
1. Determine transport: explicit operator words ("via syslog" / "HTTP collector"),
   else the data source's format (CEF/LEEF/syslog → syslog; raw-JSON → xsiam_http).
2. `log_destinations_list(type_id=<that type>)`.
3. - 1 result → use it: pass `destination="logdest:<id>"`.
   - 2+ → if the operator named one (by name or host/IP) use it; else STOP and ask
     them to pick from the list.
   - 0 → syslog: offer `log_destinations_create(name, host, port, protocol)` then use it.
         secret type (xsiam_http/etc.): tell the operator to add it in /log-destinations
         (you cannot create secret destinations); do NOT fall back to a hardcoded address.
4. Pass `destination="logdest:<id>"` to phantom_create_data_worker. The MCP resolves
   the concrete address (and any secret) — you never handle the secret.
```

- [ ] **Step 2:** In `system-prompt.ts`, add the invariant near the action-cadence section:

```
**Never hardcode or invent a log destination.** Always resolve the simulation
target from the operator's configured Log Destinations (log_destinations_list);
pass `destination="logdest:<id>"`. If none match: ask, or offer to create a plain
syslog one (log_destinations_create) — never fall back to a literal address.
```

- [ ] **Step 3:** Pre-deploy gate (`tsc && lint && build`). **Commit** `feat(skills+prompt): store-driven destination resolution recipe (Refs #N)`

---

## Task 7 — Docs

**Files:** `mcp/agent/app/help/architecture/page.tsx` (`#log-destinations`), `app/help/user/page.tsx`, `lib/journeys.ts`, `CHANGELOG.md`, `lib/release-notes.ts`, `CLAUDE.md`

- [ ] Architecture `#log-destinations`: rewrite to the real resolution flow (store → MCP `proxy_call_tool` resolution → xlog); **remove the dead `send()`-is-wired claim** (the spec-drift fix).
- [ ] User guide: "Phantom routes simulated logs to your configured Log Destinations; asks when ambiguous; can create a plain syslog destination for you."
- [ ] `journeys.ts`: a "simulate → auto-routed destination" journey.
- [ ] `CLAUDE.md`: note `log_destinations_create` is catalog-side (secretless → no SecretStore write); document the `proxy_call_tool` secret-resolution contract (agent never sees the secret).
- [ ] `CHANGELOG.md` + `release-notes.ts`: the arc's customer-facing entry.
- [ ] **Commit** `docs: store-driven log-destination resolution (Refs #N)`

---

## Task 8 — E2E verify + arc close

- [ ] Full pre-deploy gate: `cd mcp/agent && npx tsc --noEmit && npm run lint && npm run build` + `cd bundles/spark/mcp && PYTHONPATH=$PWD/src python3 -m pytest tests/ -x`.
- [ ] Push; watch the build chain → auto-deploy (own the wait).
- [ ] **Capability acceptance check** on the deployed install (drive `/api/chat` with `PHANTOM_API_KEY`, same probe pattern as v0.17.112):
  - One syslog destination configured → "simulate 3 FortiGate logs" routes to it with **no hardcoded address** (verify the worker's resolved destination + XSIAM XQL landing in `fortinet_fortigate_raw`).
  - Two syslog destinations → the agent **asks** which one.
  - Zero → the agent offers to **create** a plain syslog one, then uses it.
  - xsiam_http path → the worker sends to the **store URL** (edit the row's URL, confirm it's honored — the env hardcode no longer authoritative).
- [ ] Apply `status:ready-for-testing`; post the smoke matrix to chat + the issue.
- [ ] Ask the operator for the customer-release tag (do NOT tag without approval).

---

## Self-review

- **Spec coverage:** Resolution recipe (T6) · `log_destinations_create` secretless-syslog + is_default (T1) · worker destination resolution incl. xsiam_http secret MCP-side (T2/T3/T4/T5) · system-prompt invariant (T6) · spec-drift fix (T7) · scope `webhook`/`splunk_hec` out (T2 raises a clear error) · E2E (T8). All spec sections mapped. ✓
- **Sequencing:** T1→T2→T3 (MCP) then T4→T5 (xlog) then T6 (agent) then T7 (docs) then T8 (verify). Each commits independently. T3 depends on T2; T5 depends on T4.
- **Open items resolved:** (1) arg-injection = `proxy_call_tool` rewrites `args.destination` + injects `webhook_url`/`webhook_key` → connector forwards as `webhookUrl`/`webhookKey` → xlog `DataWorkerCreateInput`. (2) one agent tool (`phantom_create_data_worker`); the scenario paths are internal xlog branches (covered by T4's 761/904 edits). (3) `resolve_config_with_secrets` (store.py:226) is same-process — no network hop.
- **Verify-before-code reminders:** confirm `store.create` / `row.config` / `resolve_config_with_secrets` names (store.py) and the `proxy_call_tool` inner-send fn name (connector_proxy.py:122) at execution — the only two spots where a name might differ from this plan.
