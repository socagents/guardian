# XSOAR Action Toolset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 8 action tools to the Cortex XSOAR connector (13 → 21) — a command-execution engine, indicator enrichment, playbook-task completion, XSOAR Lists management, incident creation, and playbook execution — plus an optional `playground_id` config field.

**Architecture:** Every tool follows the existing connector pattern exactly: `@_wrap_xsoar_call async def xsoar_<name>(...) -> dict` → `_get_fetcher()` → `XSOARFetcher.post/get(path, body)` (dual v6/v8 auth, automatic `/xsoar/public/v1` prefix) → `{ok, …}` envelope. Three command-engine tools share a private `_execute_command` helper that runs `!commands` synchronously in a configured playground/war-room. List + lifecycle tools use direct XSOAR REST endpoints. No new HTTP machinery.

**Tech Stack:** Python 3.11 (async), httpx (via the existing `XSOARFetcher`), pytest (no network — `_RecordingFetcher`/`_ScriptedFetcher` fakes). Spec: `docs/spec-xsoar-action-toolset.md`. Issue: kite-production/guardian#5.

**Reference:** `docs/ref/trevor-mcp.py:489-591` (command engine + cmd_map). Current connector: `bundles/spark/connectors/xsoar/src/connector.py`, `connector.yaml`, `src/_xsoar_client.py`, `tests/test_connector.py`.

---

## File structure

| File | Responsibility | Change |
|---|---|---|
| `bundles/spark/connectors/xsoar/src/connector.py` | Tool implementations | Add `import json`; `_get_playground_id`, `_parse_war_room_entries`, `_execute_command` helpers; 8 `xsoar_*` functions; `_ENRICH_CMD_MAP`; `playground_id` in `_get_xsoar_config`; 8 names in `__all__`; module-docstring tool catalog 13→21 |
| `bundles/spark/connectors/xsoar/connector.yaml` | Tool + config declarations | `playground_id` in `configSchema.properties`; 8 entries in `spec.tools[]`; bump `version` 0.1.0→0.2.0 |
| `bundles/spark/connectors/xsoar/tests/test_connector.py` | Unit tests | `_ScriptedFetcher` helper; per-tool tests (v6+v8 shapes, envelopes); updated export-set test |
| `mcp/agent/app/help/architecture/page.tsx` | Spec/architecture | One `#xsoar-actions` anchor |
| `mcp/agent/app/help/user/page.tsx` | User guide | One `#xsoar-actions` subsection |
| `mcp/agent/lib/journeys.ts` | Click-paths | One command/enrich journey |
| `CHANGELOG.md` + `mcp/agent/lib/release-notes.ts` | Release notes | The operator-visible delta (newest first in release-notes) |

**Commit cadence:** Group A (Tasks 1-5) → commit. Group B (Tasks 6-8) → commit. Group C (Tasks 9-11) → commit. Docs (Tasks 12-15) → commit. Each commit footer: `Refs #5`. Tag once at arc completion (operator approval).

**Test command (run from the connector dir):**
```bash
cd bundles/spark/connectors/xsoar && python3 -m pytest tests/ -x -q
```

---

## GROUP A — Command engine

### Task 1: `playground_id` config + resolver

**Files:**
- Modify: `bundles/spark/connectors/xsoar/connector.yaml` (configSchema)
- Modify: `bundles/spark/connectors/xsoar/src/connector.py` (`_get_xsoar_config`, new `_get_playground_id`)
- Test: `bundles/spark/connectors/xsoar/tests/test_connector.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_connector.py` (after the existing config-error tests, near line 462):

```python
# ─── playground_id resolver ──────────────────────────────────────────


def test_get_playground_id_returns_configured_value(monkeypatch):
    monkeypatch.setattr(
        connector, "_get_xsoar_config",
        lambda: {"api_url": "u", "api_key": "k", "api_id": None,
                 "verify_ssl": True, "playground_id": "PG-1"},
    )
    assert connector._get_playground_id() == "PG-1"


def test_get_playground_id_missing_raises_valueerror(monkeypatch):
    monkeypatch.setattr(
        connector, "_get_xsoar_config",
        lambda: {"api_url": "u", "api_key": "k", "api_id": None,
                 "verify_ssl": True, "playground_id": None},
    )
    with pytest.raises(ValueError) as ei:
        connector._get_playground_id()
    assert "playground_id" in str(ei.value)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd bundles/spark/connectors/xsoar && python3 -m pytest tests/test_connector.py -k playground_id -x -q`
Expected: FAIL — `AttributeError: module 'src.connector' has no attribute '_get_playground_id'`.

- [ ] **Step 3: Add `playground_id` to `_get_xsoar_config`**

In `src/connector.py`, in `_get_xsoar_config()`'s returned dict (currently ends at line 125), add the `playground_id` key:

```python
    return {
        "api_url": api_url,
        "api_id": getattr(proxy, "api_id", None),
        "api_key": getattr(proxy, "api_key", None),
        "verify_ssl": getattr(proxy, "verify_ssl", True),
        "playground_id": getattr(proxy, "playground_id", None),
    }
```

- [ ] **Step 4: Add the `_get_playground_id` resolver + `import json`**

At the top of `src/connector.py`, add `import json` to the stdlib imports (the block at lines 38-40 — alongside `import functools` / `import re`):

```python
import functools
import json
import re
```

Then add this helper immediately AFTER `_get_fetcher()` (after line 150), and ABOVE `_wrap_xsoar_call`:

```python
# ─── Command-engine helpers (playground war-room) ────────────────────


# XSOAR's "investigation not found" error markers — used to give a clean
# "bad playground_id" message instead of a raw 4xx.
_PLAYGROUND_NOT_FOUND_MARKERS = ("noInv", "Could not find investigation")


def _get_playground_id() -> str:
    """Resolve the playground/war-room investigation id from instance config.

    The three command-engine tools (run_command, enrich_indicator,
    complete_task) run XSOAR `!commands` inside a playground investigation,
    which needs an id. Raising ValueError here surfaces as the standard
    operator-actionable error envelope via _wrap_xsoar_call.
    """
    cfg = _get_xsoar_config()
    playground_id = cfg.get("playground_id")
    if not playground_id:
        raise ValueError(
            "playground_id is not configured on this XSOAR instance. Set it "
            "(the Playground / War Room investigation ID — find it in the XSOAR "
            "UI: open your Playground and copy the id from the URL) at "
            "/connectors to use run_command, enrich_indicator, or complete_task."
        )
    return str(playground_id)
```

- [ ] **Step 5: Declare `playground_id` in `connector.yaml`**

In `connector.yaml`, add to `configSchema.properties` (after the `verify_ssl` block ending line 57, still inside `properties:`). Do NOT add it to `required:` — it stays optional/backwards-compatible:

```yaml
    playground_id:
      type: "string"
      description: "Playground / War Room investigation ID, used to run XSOAR commands (REQUIRED for run_command, enrich_indicator, complete_task; the other tools work without it). Find it in XSOAR: open your Playground and copy the investigation ID from the URL. Leave blank if you don't use the command tools."
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd bundles/spark/connectors/xsoar && python3 -m pytest tests/test_connector.py -k playground_id -x -q`
Expected: PASS (2 passed). Then run the full file: `python3 -m pytest tests/ -x -q` → all existing tests still pass.

---

### Task 2: `_parse_war_room_entries` + `_execute_command` helper

**Files:**
- Modify: `bundles/spark/connectors/xsoar/src/connector.py`
- Test: `bundles/spark/connectors/xsoar/tests/test_connector.py`

- [ ] **Step 1: Add the `_ScriptedFetcher` test helper**

In `tests/test_connector.py`, after the `_RecordingFetcher` class + `_install_fetcher` (after line 266), add a path-keyed fake (the engine makes multiple posts to different paths in one call):

```python
class _ScriptedFetcher:
    """Fake fetcher whose post/get replies are keyed by path suffix.

    The command engine posts to /entry (DeleteContext), /entry/execute/sync
    (run), and /investigation/{id}/context (retrieve) in one call — a single
    canned reply can't serve them. Match by exact path or path suffix.
    """

    def __init__(self, replies: dict, get_replies: Optional[dict] = None, is_v8: bool = False):
        self.replies = replies
        self.get_replies = get_replies or {}
        self.is_v8 = is_v8
        self.calls: list[tuple[str, str, Any]] = []

    def _match(self, table: dict, path: str):
        if path in table:
            return table[path]
        for key, val in table.items():
            if path.endswith(key):
                return val
        return {}

    async def post(self, path, body=None, **kw):
        self.calls.append(("POST", path, body))
        return self._match(self.replies, path)

    async def get(self, path, **kw):
        self.calls.append(("GET", path, kw.get("params")))
        return self._match(self.get_replies, path)
```

- [ ] **Step 2: Write the failing tests for the parse + engine**

Add (after the `_ScriptedFetcher` class):

```python
# ─── _parse_war_room_entries ─────────────────────────────────────────


def test_parse_war_room_includes_type1_contents():
    """type==1 (standard note) entries are INCLUDED (ref skipped them — bug)."""
    resp = {"data": [{"type": 1, "contents": "hello"}]}
    assert connector._parse_war_room_entries(resp) == "hello"


def test_parse_war_room_marks_type4_error():
    resp = {"data": [{"type": 4, "contents": "boom"}, {"type": 1, "contents": "ok"}]}
    out = connector._parse_war_room_entries(resp)
    assert "Error: boom" in out and "ok" in out


def test_parse_war_room_serializes_dict_contents():
    resp = {"data": [{"type": 1, "contents": {"k": "v"}}]}
    assert '"k": "v"' in connector._parse_war_room_entries(resp)


def test_parse_war_room_empty_is_friendly():
    assert connector._parse_war_room_entries({"data": []}) == (
        "Command executed (no text output returned)."
    )


# ─── _execute_command ────────────────────────────────────────────────


def test_execute_command_no_context_keys():
    f = _ScriptedFetcher(replies={
        "/entry/execute/sync": {"data": [{"type": 1, "contents": "printed"}]},
    })
    out = run(connector._execute_command(f, "PG-1", "!Print value=printed"))
    assert out == {"output": "printed"}
    # one POST: execute/sync with the playground id + command
    assert f.calls == [("POST", "/entry/execute/sync",
                        {"investigationId": "PG-1", "data": "!Print value=printed"})]


def test_execute_command_with_context_keys_clears_and_retrieves():
    f = _ScriptedFetcher(replies={
        "/entry": {"ok": 1},                                   # DeleteContext
        "/entry/execute/sync": {"data": [{"type": 1, "contents": "ran"}]},
        "/context": {"score": 3},                              # context retrieval
    })
    out = run(connector._execute_command(f, "PG-1", "!ip ip=\"8.8.8.8\"", "IP,DBotScore"))
    assert out["output"] == "ran"
    assert out["context"] == {"IP": {"score": 3}, "DBotScore": {"score": 3}}
    paths = [p for (_m, p, _b) in f.calls]
    # 2 DeleteContext + 1 execute + 2 context = 5 posts
    assert paths.count("/entry") == 2
    assert "/entry/execute/sync" in paths
    assert paths.count("/investigation/PG-1/context") == 2
    # context query uses the literal ${Key} syntax
    ctx_calls = [b for (_m, p, b) in f.calls if p == "/investigation/PG-1/context"]
    assert ctx_calls[0] == {"query": "${IP}"}


def test_execute_command_playground_not_found_raises_valueerror():
    class _NoInv:
        is_v8 = False
        calls: list = []
        async def post(self, path, body=None, **kw):
            from src._xsoar_client import XSOARRequestError
            raise XSOARRequestError("HTTP 400: noInv — investigation not found")
    with pytest.raises(ValueError) as ei:
        run(connector._execute_command(_NoInv(), "BAD", "!Print value=x"))
    assert "BAD" in str(ei.value) and "not found" in str(ei.value)
```

- [ ] **Step 3: Run to verify failure**

Run: `cd bundles/spark/connectors/xsoar && python3 -m pytest tests/test_connector.py -k "parse_war_room or execute_command" -x -q`
Expected: FAIL — `AttributeError: ... has no attribute '_parse_war_room_entries'`.

- [ ] **Step 4: Implement both helpers**

In `src/connector.py`, add directly after the `_get_playground_id` function from Task 1 (still in the command-engine-helpers section, above `_wrap_xsoar_call`):

```python
def _parse_war_room_entries(response: Any) -> str:
    """Concatenate war-room entry `contents` from an execute/sync response.

    The fetcher normalizes a bare-array body into {"data": [...]}, so entries
    arrive under `data`; a single-entry dict is treated as one entry. type==4
    entries are errors (prefixed "Error:"). Unlike the reference port
    (docs/ref/trevor-mcp.py:541) we do NOT skip type==1 — in XSOAR type 1 is the
    standard note entry, so skipping it drops legitimate output (e.g. !Print).
    We include every entry that carries non-empty contents.
    """
    if isinstance(response, dict) and isinstance(response.get("data"), list):
        entries = response["data"]
    elif isinstance(response, list):
        entries = response
    elif isinstance(response, dict):
        entries = [response]
    else:
        entries = []

    parts: list[str] = []
    for e in entries:
        if not isinstance(e, dict):
            continue
        contents = e.get("contents")
        if contents in (None, ""):
            continue
        text = contents if isinstance(contents, str) else json.dumps(contents)
        parts.append(f"Error: {text}" if e.get("type") == 4 else text)

    return "\n".join(parts).strip() or "Command executed (no text output returned)."


async def _execute_command(
    fetcher: XSOARFetcher,
    playground_id: str,
    command: str,
    return_context_keys: Optional[str] = None,
) -> dict:
    """Run an XSOAR `!command` synchronously in the playground war room.

    Ports docs/ref/trevor-mcp.py:489-577. When return_context_keys (a
    comma-separated string) is given, each key's context is cleared before the
    run and retrieved after; otherwise only the war-room text is returned.

    Returns {output, context?} — context is present only when keys were asked
    for. Raises ValueError on a missing/invalid playground (→ clean envelope).
    """
    keys = (
        [k.strip() for k in return_context_keys.split(",") if k.strip()]
        if return_context_keys
        else []
    )

    # 1. Clear context (best-effort — a clear failure must not abort the run).
    for key in keys:
        try:
            await fetcher.post(
                "/entry",
                {"investigationId": playground_id, "data": f"!DeleteContext key={key}"},
            )
        except XSOARError:
            pass

    # 2. Execute synchronously.
    try:
        response = await fetcher.post(
            "/entry/execute/sync",
            {"investigationId": playground_id, "data": command},
        )
    except XSOARRequestError as exc:
        if any(marker in str(exc) for marker in _PLAYGROUND_NOT_FOUND_MARKERS):
            raise ValueError(
                f"playground '{playground_id}' not found — check the playground_id "
                f"on the XSOAR instance."
            )
        raise

    output = _parse_war_room_entries(response)

    # 3. Retrieve requested context keys (literal ${Key} syntax).
    context: Optional[dict] = None
    if keys:
        context = {}
        for key in keys:
            try:
                context[key] = await fetcher.post(
                    f"/investigation/{playground_id}/context",
                    {"query": f"${{{key}}}"},
                )
            except XSOARError as exc:
                context[key] = {"error": str(exc)}

    result: dict[str, Any] = {"output": output}
    if context is not None:
        result["context"] = context
    return result
```

- [ ] **Step 5: Run to verify pass**

Run: `cd bundles/spark/connectors/xsoar && python3 -m pytest tests/test_connector.py -k "parse_war_room or execute_command" -x -q`
Expected: PASS (7 passed).

---

### Task 3: `xsoar_run_command` tool

**Files:**
- Modify: `src/connector.py` (function + `__all__`), `connector.yaml` (tool entry), `tests/test_connector.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_connector.py`:

```python
# ─── run_command ─────────────────────────────────────────────────────


def test_run_command_executes_in_playground(monkeypatch):
    monkeypatch.setattr(connector, "_get_playground_id", lambda: "PG-1")
    f = _ScriptedFetcher(replies={
        "/entry/execute/sync": {"data": [{"type": 1, "contents": "printed"}]},
    })
    monkeypatch.setattr(connector, "_get_fetcher", lambda: f)

    out = run(connector.xsoar_run_command("!Print value=printed"))
    assert out["ok"] is True
    assert out["output"] == "printed"
    assert f.calls[0] == ("POST", "/entry/execute/sync",
                          {"investigationId": "PG-1", "data": "!Print value=printed"})


def test_run_command_requires_command(monkeypatch):
    monkeypatch.setattr(connector, "_get_playground_id", lambda: "PG-1")
    out = run(connector.xsoar_run_command(""))
    assert out["ok"] is False and "command" in out["error"]


def test_run_command_missing_playground_returns_envelope(monkeypatch):
    def _boom():
        raise ValueError("playground_id is not configured on this XSOAR instance.")
    monkeypatch.setattr(connector, "_get_playground_id", _boom)
    out = run(connector.xsoar_run_command("!Print value=x"))
    assert out["ok"] is False and "playground_id" in out["error"]
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_connector.py -k run_command -x -q`
Expected: FAIL — `AttributeError: ... has no attribute 'xsoar_run_command'`.

- [ ] **Step 3: Implement `xsoar_run_command`**

In `src/connector.py`, add at the END of the file (after `xsoar_health_check`, line 1046):

```python
# ─── xsoar_run_command ───────────────────────────────────────────────


@_wrap_xsoar_call
async def xsoar_run_command(
    command: str,
    return_context_keys: Optional[str] = None,
) -> dict:
    """Run an arbitrary Cortex XSOAR command in the playground war room.

    The escape hatch onto XSOAR's full command surface — run any `!command`
    (e.g. '!ip ip=8.8.8.8', '!Print value=hi', '!setIncident ...') synchronously
    and get the war-room output back. For indicator reputation specifically,
    prefer xsoar_enrich_indicator (it picks the right command + context keys).

    Requires the instance's playground_id to be set (the War Room the command
    runs in). Returns a clean error if it isn't.

    Args:
        command: The full XSOAR command including the leading '!'
            (e.g. '!ip ip=8.8.8.8'). Quote values with spaces.
        return_context_keys: Optional comma-separated XSOAR context keys to
            return as structured data after the run (e.g. 'IP,DBotScore'). Each
            key is cleared before the run and read back after. Omit to get only
            the war-room text output.

    Returns:
        {ok, output: <war-room text>, context?: {<key>: <value>, ...}}.
    """
    if not command:
        raise ValueError("command is required (e.g. '!ip ip=8.8.8.8')")
    playground_id = _get_playground_id()
    fetcher = _get_fetcher()
    return await _execute_command(fetcher, playground_id, command, return_context_keys)
```

- [ ] **Step 4: Add to `__all__`**

In `src/connector.py`, append `"xsoar_run_command",` to the `__all__` list (after `"xsoar_health_check",` at line 70).

- [ ] **Step 5: Add the `connector.yaml` tool entry**

In `connector.yaml` `spec.tools:`, add after the `health_check` block (end of file, line 251). Keep the existing 2-space list indent:

```yaml
    # ─── Command engine (needs playground_id) ────────────────────
    - name: "run_command"
      method: "POST /entry/execute/sync"
      description: |
        Run an arbitrary Cortex XSOAR command in the playground war room — the
        escape hatch onto XSOAR's full command surface. Run any `!command`
        (e.g. '!Print value=hi', '!setIncident ...') and get the war-room output
        back. For indicator reputation, prefer xsoar_enrich_indicator. REQUIRES
        the instance's playground_id to be configured.
      args:
        - { name: "command",             type: "string", description: "Full XSOAR command including the leading '!' (e.g. '!ip ip=8.8.8.8'). Quote values containing spaces.", required: true }
        - { name: "return_context_keys", type: "string", description: "Optional comma-separated XSOAR context keys to return as structured data (e.g. 'IP,DBotScore'). Omit for war-room text only.", required: false }
      returns: { type: "object", description: "{ ok, output, context? }" }
```

- [ ] **Step 6: Run to verify pass**

Run: `python3 -m pytest tests/test_connector.py -k run_command -x -q`
Expected: PASS (3 passed). (The export-set test `test_all_exported_tools_are_callable` will fail until Task 11 updates it — that's expected; keep `-k run_command` scoped here.)

---

### Task 4: `xsoar_enrich_indicator` tool

**Files:** `src/connector.py`, `connector.yaml`, `tests/test_connector.py`

- [ ] **Step 1: Write the failing test**

```python
# ─── enrich_indicator ────────────────────────────────────────────────


def test_enrich_indicator_ip_builds_command_and_keys(monkeypatch):
    monkeypatch.setattr(connector, "_get_playground_id", lambda: "PG-1")
    f = _ScriptedFetcher(replies={
        "/entry": {},
        "/entry/execute/sync": {"data": [{"type": 1, "contents": "done"}]},
        "/context": {"v": 1},
    })
    monkeypatch.setattr(connector, "_get_fetcher", lambda: f)

    out = run(connector.xsoar_enrich_indicator("IP", "8.8.8.8"))
    assert out["ok"] is True
    assert out["indicator_type"] == "ip" and out["value"] == "8.8.8.8"
    # command quotes the value; context keys come from the cmd_map
    exec_call = [b for (_m, p, b) in f.calls if p == "/entry/execute/sync"][0]
    assert exec_call["data"] == '!ip ip="8.8.8.8"'
    assert "IP" in out["context"] and "DBotScore" in out["context"]


def test_enrich_indicator_unknown_type_returns_envelope(monkeypatch):
    monkeypatch.setattr(connector, "_get_playground_id", lambda: "PG-1")
    out = run(connector.xsoar_enrich_indicator("banana", "x"))
    assert out["ok"] is False and "unsupported indicator_type" in out["error"]
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_connector.py -k enrich_indicator -x -q` → FAIL (no attribute).

- [ ] **Step 3: Implement `xsoar_enrich_indicator` + `_ENRICH_CMD_MAP`**

In `src/connector.py`, append after `xsoar_run_command`:

```python
# ─── xsoar_enrich_indicator ──────────────────────────────────────────


# Indicator-type → (command template, comma-separated context keys to return).
# Ported from docs/ref/trevor-mcp.py:580. The value is double-quoted into the
# command (e.g. !ip ip="8.8.8.8").
_ENRICH_CMD_MAP: dict[str, tuple[str, str]] = {
    "ip": ("!ip ip={}", "IP,DBotScore,IPinfo,AutoFocus"),
    "url": ("!url url={}", "URL,DBotScore,AutoFocus"),
    "domain": ("!domain domain={}", "Domain,DBotScore,Whois,AutoFocus"),
    "file": ("!file file={}", "File,DBotScore"),
    "cve": ("!cve cve_id={}", "CVE"),
}


@_wrap_xsoar_call
async def xsoar_enrich_indicator(indicator_type: str, value: str) -> dict:
    """Enrich an indicator (IoC) with reputation + threat context.

    Runs the matching XSOAR enrichment command in the playground and returns the
    structured DBotScore + reputation context. The investigation workhorse: "is
    this IP/domain/hash malicious?". Requires the instance's playground_id.

    Args:
        indicator_type: One of ip, url, domain, file, cve (case-insensitive).
        value: The indicator value (e.g. '8.8.8.8', 'evil.com', a SHA256, a
            CVE id like 'CVE-2024-1234').

    Returns:
        {ok, indicator_type, value, output, context: {<key>: <value>, ...}}
        where context carries the enrichment keys (e.g. IP, DBotScore).
    """
    if not value:
        raise ValueError("value is required")
    normalized = (indicator_type or "").lower()
    if normalized not in _ENRICH_CMD_MAP:
        return _err(
            f"unsupported indicator_type '{indicator_type}' "
            f"(expected one of: ip, url, domain, file, cve)"
        )
    template, context_keys = _ENRICH_CMD_MAP[normalized]
    command = template.format(f'"{value}"')

    playground_id = _get_playground_id()
    fetcher = _get_fetcher()
    result = await _execute_command(fetcher, playground_id, command, context_keys)
    return {"indicator_type": normalized, "value": value, **result}
```

- [ ] **Step 4: Add `"xsoar_enrich_indicator",` to `__all__`.**

- [ ] **Step 5: Add the `connector.yaml` tool entry** (after the `run_command` block):

```yaml
    - name: "enrich_indicator"
      method: "POST /entry/execute/sync (!ip/!url/!domain/!file/!cve)"
      description: |
        Enrich an indicator (IoC) with reputation + threat context — runs the
        matching XSOAR enrichment command (!ip/!url/!domain/!file/!cve) in the
        playground and returns the structured DBotScore + reputation. The
        investigation workhorse: "is this IP/domain/hash malicious?". REQUIRES
        the instance's playground_id.
      args:
        - { name: "indicator_type", type: "string", description: "One of ip, url, domain, file, cve (case-insensitive).", required: true }
        - { name: "value",          type: "string", description: "The indicator value (e.g. '8.8.8.8', 'evil.com', a SHA256, 'CVE-2024-1234').", required: true }
      returns: { type: "object", description: "{ ok, indicator_type, value, output, context }" }
```

- [ ] **Step 6: Run to verify pass**

Run: `python3 -m pytest tests/test_connector.py -k enrich_indicator -x -q` → PASS (2 passed).

---

### Task 5: `xsoar_complete_task` tool + Group A commit

**Files:** `src/connector.py`, `connector.yaml`, `tests/test_connector.py`

- [ ] **Step 1: Write the failing test**

```python
# ─── complete_task ───────────────────────────────────────────────────


def test_complete_task_builds_taskcomplete_command(monkeypatch):
    monkeypatch.setattr(connector, "_get_playground_id", lambda: "PG-1")
    f = _ScriptedFetcher(replies={
        "/entry/execute/sync": {"data": [{"type": 1, "contents": "Task completed"}]},
    })
    monkeypatch.setattr(connector, "_get_fetcher", lambda: f)

    out = run(connector.xsoar_complete_task(incident_id="42", task_id="7", comment="done by guardian"))
    assert out["ok"] is True
    assert out["incident_id"] == "42" and out["task_id"] == "7"
    exec_call = [b for (_m, p, b) in f.calls if p == "/entry/execute/sync"][0]
    assert exec_call["data"] == '!taskComplete id=7 incidentId=42 comment="done by guardian"'


def test_complete_task_requires_ids(monkeypatch):
    monkeypatch.setattr(connector, "_get_playground_id", lambda: "PG-1")
    out = run(connector.xsoar_complete_task(incident_id="", task_id="7"))
    assert out["ok"] is False and "incident_id" in out["error"]
```

- [ ] **Step 2: Run to verify failure** → `python3 -m pytest tests/test_connector.py -k complete_task -x -q` → FAIL.

- [ ] **Step 3: Implement `xsoar_complete_task`** (append after `xsoar_enrich_indicator`):

```python
# ─── xsoar_complete_task ─────────────────────────────────────────────


@_wrap_xsoar_call
async def xsoar_complete_task(
    incident_id: str,
    task_id: str,
    comment: Optional[str] = None,
) -> dict:
    """Complete a playbook / war-room task on an incident.

    Runs XSOAR's `!taskComplete` command (a war-room automation command, not a
    REST endpoint) in the playground, targeting the given incident's task. Use
    to advance a stuck playbook task. Requires the instance's playground_id.

    Args:
        incident_id: The XSOAR incident id that owns the task.
        task_id: The playbook task id (or tag) to complete.
        comment: Optional completion note recorded on the task.

    Returns:
        {ok, incident_id, task_id, output}.
    """
    if not incident_id:
        raise ValueError("incident_id is required")
    if not task_id:
        raise ValueError("task_id is required")
    command = f"!taskComplete id={task_id} incidentId={incident_id}"
    if comment:
        command += f' comment="{comment}"'

    playground_id = _get_playground_id()
    fetcher = _get_fetcher()
    result = await _execute_command(fetcher, playground_id, command)
    return {"incident_id": incident_id, "task_id": task_id, **result}
```

- [ ] **Step 4: Add `"xsoar_complete_task",` to `__all__`.**

- [ ] **Step 5: Add the `connector.yaml` tool entry** (after `enrich_indicator`):

```yaml
    - name: "complete_task"
      method: "POST /entry/execute/sync (!taskComplete)"
      description: |
        Complete a playbook / war-room task on an incident. Runs XSOAR's
        `!taskComplete` command in the playground, targeting the incident's task
        — use to advance a stuck playbook task. REQUIRES the instance's
        playground_id.
      args:
        - { name: "incident_id", type: "string", description: "The XSOAR incident id that owns the task.", required: true }
        - { name: "task_id",     type: "string", description: "The playbook task id (or tag) to complete.", required: true }
        - { name: "comment",     type: "string", description: "Optional completion note recorded on the task.", required: false }
      returns: { type: "object", description: "{ ok, incident_id, task_id, output }" }
```

- [ ] **Step 6: Run the full suite** (engine group complete):

Run: `cd bundles/spark/connectors/xsoar && python3 -m pytest tests/ -x -q -k "not all_exported_tools"`
Expected: all PASS. (Skip the export-set test until Task 11.)

- [ ] **Step 7: Commit Group A**

```bash
cd /Users/ayman/Documents/Kite/guardian
git add bundles/spark/connectors/xsoar/
git commit -m "$(cat <<'EOF'
xsoar: command engine — run_command, enrich_indicator, complete_task

Adds the playground/war-room command-execution engine (_execute_command)
+ 3 tools: run_command (any !command), enrich_indicator (ip/url/domain/
file/cve → DBotScore context), complete_task (!taskComplete). New optional
playground_id config field. Group A of the XSOAR action-toolset arc.

Refs #5

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## GROUP B — XSOAR Lists

### Task 6: `xsoar_get_list` tool

**Files:** `src/connector.py`, `connector.yaml`, `tests/test_connector.py`

- [ ] **Step 1: Write the failing test**

```python
# ─── get_list / set_list / append_to_list ────────────────────────────


def test_get_list_filters_by_name(monkeypatch):
    rf = _RecordingFetcher(get_reply={"data": [
        {"id": "a", "name": "allowlist", "data": "1.1.1.1", "type": "plain_text"},
        {"id": "b", "name": "blocklist", "data": "2.2.2.2", "type": "plain_text"},
    ]})
    _install_fetcher(monkeypatch, rf)
    out = run(connector.xsoar_get_list("blocklist"))
    assert out["ok"] is True
    assert out["name"] == "blocklist" and out["data"] == "2.2.2.2"
    assert rf.calls[0][0:2] == ("GET", "/lists/")


def test_get_list_not_found(monkeypatch):
    rf = _RecordingFetcher(get_reply={"data": []})
    _install_fetcher(monkeypatch, rf)
    out = run(connector.xsoar_get_list("nope"))
    assert out["ok"] is False and "not found" in out["error"]
```

- [ ] **Step 2: Run to verify failure** → `python3 -m pytest tests/test_connector.py -k get_list -x -q` → FAIL.

- [ ] **Step 3: Implement `xsoar_get_list`** (append after `xsoar_complete_task`):

```python
# ─── xsoar_get_list ──────────────────────────────────────────────────


def _find_list(lists: Any, name: str) -> Optional[dict]:
    """Find a list object by name (or id) in a GET /lists/ response array."""
    if isinstance(lists, dict) and "data" in lists:
        lists = lists.get("data")
    if not isinstance(lists, list):
        return None
    for lst in lists:
        if isinstance(lst, dict) and (lst.get("name") == name or lst.get("id") == name):
            return lst
    return None


@_wrap_xsoar_call
async def xsoar_get_list(name: str) -> dict:
    """Read a Cortex XSOAR list (a named key/value or line list) by name.

    XSOAR Lists hold reusable data — allow/block lists, lookup tables, config.
    Use to read one during an investigation or before appending to it.

    Args:
        name: The list name (or id).

    Returns:
        {ok, name, data, type} where type is 'plain_text' or 'json', or
        {ok: false, error} when no list matched.
    """
    if not name:
        raise ValueError("name is required")
    fetcher = _get_fetcher()
    response = await fetcher.get("/lists/")
    lst = _find_list(response, name)
    if lst is None:
        return _err(f"list '{name}' not found", name=name)
    return {"name": lst.get("name"), "data": lst.get("data"), "type": lst.get("type")}
```

- [ ] **Step 4: Add `"xsoar_get_list",` to `__all__`.**

- [ ] **Step 5: Add the `connector.yaml` tool entry** (after `complete_task`):

```yaml
    # ─── XSOAR Lists ─────────────────────────────────────────────
    - name: "get_list"
      method: "GET /lists/ (filter by name)"
      description: |
        Read a Cortex XSOAR list by name — XSOAR Lists hold reusable data like
        allow/block lists, lookup tables, and config. Use to read one during an
        investigation or before appending to it.
      args:
        - { name: "name", type: "string", description: "The list name (or id).", required: true }
      returns: { type: "object", description: "{ ok, name, data, type }" }
```

- [ ] **Step 6: Run to verify pass** → `python3 -m pytest tests/test_connector.py -k get_list -x -q` → PASS (2 passed).

---

### Task 7: `xsoar_set_list` tool

**Files:** `src/connector.py`, `connector.yaml`, `tests/test_connector.py`

- [ ] **Step 1: Write the failing test**

```python
def test_set_list_saves(monkeypatch):
    rf = _RecordingFetcher(post_reply={"id": "x"})
    _install_fetcher(monkeypatch, rf)
    out = run(connector.xsoar_set_list("blocklist", "1.1.1.1\n2.2.2.2"))
    assert out["ok"] is True and out["name"] == "blocklist" and out["type"] == "plain_text"
    method, path, body = rf.calls[0]
    assert (method, path) == ("POST", "/lists/save")
    assert body == {"name": "blocklist", "data": "1.1.1.1\n2.2.2.2", "type": "plain_text"}


def test_set_list_json_type(monkeypatch):
    rf = _RecordingFetcher(post_reply={})
    _install_fetcher(monkeypatch, rf)
    run(connector.xsoar_set_list("cfg", '{"a":1}', list_type="json"))
    assert rf.calls[0][2]["type"] == "json"
```

- [ ] **Step 2: Run to verify failure** → `-k set_list` → FAIL.

- [ ] **Step 3: Implement `xsoar_set_list`** (append after `xsoar_get_list`):

```python
# ─── xsoar_set_list ──────────────────────────────────────────────────


@_wrap_xsoar_call
async def xsoar_set_list(name: str, data: str, list_type: str = "plain_text") -> dict:
    """Create or overwrite a Cortex XSOAR list.

    Writes the full contents (creating the list if it doesn't exist). To add a
    single value without clobbering the rest, use xsoar_append_to_list.

    Args:
        name: The list name.
        data: The full list contents. For list_type 'plain_text' this is the raw
            text (often newline-separated); for 'json' a JSON string.
        list_type: 'plain_text' (default) or 'json'.

    Returns:
        {ok, name, type}.
    """
    if not name:
        raise ValueError("name is required")
    body = {
        "name": name,
        "data": data if data is not None else "",
        "type": list_type or "plain_text",
    }
    fetcher = _get_fetcher()
    response = await fetcher.post("/lists/save", body)
    return {
        "name": name,
        "type": body["type"],
        "raw_response": {"id": response.get("id")} if isinstance(response, dict) else response,
    }
```

- [ ] **Step 4: Add `"xsoar_set_list",` to `__all__`.**

- [ ] **Step 5: Add the `connector.yaml` tool entry** (after `get_list`):

```yaml
    - name: "set_list"
      method: "POST /lists/save (overwrite)"
      description: |
        Create or overwrite a Cortex XSOAR list — writes the full contents
        (creating the list if absent). To add a single value without clobbering
        the rest, use xsoar_append_to_list.
      args:
        - { name: "name",      type: "string", description: "The list name.", required: true }
        - { name: "data",      type: "string", description: "Full list contents. plain_text: raw text (often newline-separated). json: a JSON string.", required: true }
        - { name: "list_type", type: "string", description: "'plain_text' (default) or 'json'.", required: false }
      returns: { type: "object", description: "{ ok, name, type }" }
```

- [ ] **Step 6: Run to verify pass** → `-k set_list` → PASS (2 passed).

---

### Task 8: `xsoar_append_to_list` tool + Group B commit

**Files:** `src/connector.py`, `connector.yaml`, `tests/test_connector.py`

- [ ] **Step 1: Write the failing test**

```python
def test_append_to_list_plain_text(monkeypatch):
    rf = _RecordingFetcher(
        get_reply={"data": [{"name": "bl", "data": "1.1.1.1", "type": "plain_text"}]},
        post_reply={},
    )
    _install_fetcher(monkeypatch, rf)
    out = run(connector.xsoar_append_to_list("bl", "2.2.2.2"))
    assert out["ok"] is True and out["data"] == "1.1.1.1\n2.2.2.2"
    # last call is the save with the merged data
    method, path, body = rf.calls[-1]
    assert (method, path) == ("POST", "/lists/save")
    assert body["data"] == "1.1.1.1\n2.2.2.2"


def test_append_to_list_creates_when_absent(monkeypatch):
    rf = _RecordingFetcher(get_reply={"data": []}, post_reply={})
    _install_fetcher(monkeypatch, rf)
    out = run(connector.xsoar_append_to_list("new", "first"))
    assert out["ok"] is True and out["data"] == "first" and out["type"] == "plain_text"


def test_append_to_list_json(monkeypatch):
    rf = _RecordingFetcher(
        get_reply={"data": [{"name": "j", "data": "[\"a\"]", "type": "json"}]},
        post_reply={},
    )
    _install_fetcher(monkeypatch, rf)
    out = run(connector.xsoar_append_to_list("j", "b"))
    assert out["ok"] is True
    import json as _j
    assert _j.loads(out["data"]) == ["a", "b"]
```

- [ ] **Step 2: Run to verify failure** → `-k append_to_list` → FAIL.

- [ ] **Step 3: Implement `xsoar_append_to_list`** (append after `xsoar_set_list`):

```python
# ─── xsoar_append_to_list ────────────────────────────────────────────


@_wrap_xsoar_call
async def xsoar_append_to_list(name: str, value: str) -> dict:
    """Append a value to a Cortex XSOAR list (read-modify-write).

    Reads the current list, adds `value` (a newline for plain_text lists, an
    array push for json lists), and saves. Creates a new plain_text list with
    the value if the list doesn't exist yet. Use to add an IoC to a block/allow
    list during response without overwriting the rest.

    Args:
        name: The list name.
        value: The value to append.

    Returns:
        {ok, name, data, type} with the post-append contents.
    """
    if not name:
        raise ValueError("name is required")
    if value is None:
        raise ValueError("value is required")

    fetcher = _get_fetcher()
    existing = _find_list(await fetcher.get("/lists/"), name)

    if existing is None:
        new_data, list_type = str(value), "plain_text"
    else:
        list_type = existing.get("type") or "plain_text"
        current = existing.get("data")
        if list_type == "json":
            try:
                arr = json.loads(current) if isinstance(current, str) else (current or [])
            except (json.JSONDecodeError, TypeError):
                return _err(
                    f"list '{name}' is type json but its data isn't valid JSON; "
                    f"refusing to overwrite",
                    name=name,
                )
            if not isinstance(arr, list):
                return _err(f"list '{name}' json data isn't an array; refusing to append", name=name)
            arr.append(value)
            new_data = json.dumps(arr)
        else:
            current_str = current if isinstance(current, str) else ("" if current is None else str(current))
            new_data = f"{current_str}\n{value}" if current_str else str(value)

    await fetcher.post("/lists/save", {"name": name, "data": new_data, "type": list_type})
    return {"name": name, "data": new_data, "type": list_type}
```

- [ ] **Step 4: Add `"xsoar_append_to_list",` to `__all__`.**

- [ ] **Step 5: Add the `connector.yaml` tool entry** (after `set_list`):

```yaml
    - name: "append_to_list"
      method: "GET /lists/ + POST /lists/save"
      description: |
        Append a value to a Cortex XSOAR list (read-modify-write) — a newline for
        plain_text lists, an array push for json lists. Creates a new plain_text
        list if it doesn't exist. Use to add an IoC to a block/allow list during
        response without overwriting the rest.
      args:
        - { name: "name",  type: "string", description: "The list name.", required: true }
        - { name: "value", type: "string", description: "The value to append.", required: true }
      returns: { type: "object", description: "{ ok, name, data, type }" }
```

- [ ] **Step 6: Run full suite** → `python3 -m pytest tests/ -x -q -k "not all_exported_tools"` → all PASS.

- [ ] **Step 7: Commit Group B**

```bash
cd /Users/ayman/Documents/Kite/guardian
git add bundles/spark/connectors/xsoar/
git commit -m "$(cat <<'EOF'
xsoar: Lists — get_list, set_list, append_to_list

Adds XSOAR Lists management via the Lists REST API (GET /lists/,
POST /lists/save): read a list by name, overwrite it, or append a value
(newline for plain_text, array push for json). Group B of the action-
toolset arc.

Refs #5

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## GROUP C — Incident lifecycle

### Task 9: `xsoar_create_incident` tool

**Files:** `src/connector.py`, `connector.yaml`, `tests/test_connector.py`

- [ ] **Step 1: Write the failing test**

```python
# ─── create_incident / run_playbook ──────────────────────────────────


def test_create_incident_assembles_body(monkeypatch):
    rf = _RecordingFetcher(post_reply={"id": "100", "version": 1})
    _install_fetcher(monkeypatch, rf)
    out = run(connector.xsoar_create_incident(
        name="guardian smoke", incident_type="Phishing", severity=3,
        details="seen in email", owner="alice",
        labels=["src:guardian"], custom_fields={"detectionsource": "Guardian"},
    ))
    assert out["ok"] is True and out["incident_id"] == "100"
    method, path, body = rf.calls[0]
    assert (method, path) == ("POST", "/incident")
    assert body["name"] == "guardian smoke"
    assert body["type"] == "Phishing"
    assert body["severity"] == 3
    assert body["createInvestigation"] is True
    assert {"type": "Label", "value": "src:guardian"} in body["labels"]
    assert body["CustomFields"] == {"detectionsource": "Guardian"}


def test_create_incident_requires_name(monkeypatch):
    rf = _RecordingFetcher(post_reply={})
    _install_fetcher(monkeypatch, rf)
    out = run(connector.xsoar_create_incident(name=""))
    assert out["ok"] is False and "name" in out["error"]


def test_create_incident_omits_unset_fields(monkeypatch):
    rf = _RecordingFetcher(post_reply={"id": "101"})
    _install_fetcher(monkeypatch, rf)
    run(connector.xsoar_create_incident(name="bare"))
    body = rf.calls[0][2]
    assert "type" not in body and "severity" not in body and "owner" not in body
    assert body == {"name": "bare", "createInvestigation": True}
```

- [ ] **Step 2: Run to verify failure** → `-k create_incident` → FAIL.

- [ ] **Step 3: Implement `xsoar_create_incident`** (append after `xsoar_append_to_list`):

```python
# ─── xsoar_create_incident ───────────────────────────────────────────


@_wrap_xsoar_call
async def xsoar_create_incident(
    name: str,
    incident_type: Optional[str] = None,
    severity: Optional[int] = None,
    details: Optional[str] = None,
    owner: Optional[str] = None,
    labels: Optional[list] = None,
    custom_fields: Optional[dict] = None,
    create_investigation: bool = True,
) -> dict:
    """Create a new Cortex XSOAR incident (case).

    Use to open a case from Guardian — e.g. to record a finding as a tracked
    incident. Only `name` is required; createInvestigation spins up the war room.

    Args:
        name: The incident name/title (required).
        incident_type: The XSOAR incident type (e.g. 'Phishing'). Discover types
            via xsoar_list_incident_types. Optional.
        severity: Severity level 0-4 (0 unknown … 4 critical). Optional.
        details: Free-text description / details. Optional.
        owner: Owner username. Optional.
        labels: List of label strings (or [{type, value}] dicts). Optional.
        custom_fields: Dict of {cliName: value} written under CustomFields
            (lowercase machine names from xsoar_get_incident_fields). Optional.
        create_investigation: Create the war-room investigation (default True).

    Returns:
        {ok, incident_id, name, created: true}.
    """
    if not name:
        raise ValueError("name is required")
    if custom_fields is not None and not isinstance(custom_fields, dict):
        return _err("custom_fields must be a dict of {cliName: value}")

    body: dict[str, Any] = {"name": name, "createInvestigation": bool(create_investigation)}
    if incident_type:
        body["type"] = incident_type
    if severity is not None:
        body["severity"] = _clamp_int(severity, 0, 0, 4)
    if details:
        body["details"] = details
    if owner:
        body["owner"] = owner
    label_list = _as_list(labels)
    if label_list is not None:
        body["labels"] = [
            x if isinstance(x, dict) else {"type": "Label", "value": x}
            for x in label_list
        ]
    if custom_fields:
        body["CustomFields"] = custom_fields

    fetcher = _get_fetcher()
    response = await fetcher.post("/incident", body)

    incident_id = response.get("id") if isinstance(response, dict) else None
    return {
        "incident_id": incident_id,
        "name": name,
        "created": True,
        "raw_response": {"id": incident_id, "version": response.get("version")}
        if isinstance(response, dict) else response,
    }
```

- [ ] **Step 4: Add `"xsoar_create_incident",` to `__all__`.**

- [ ] **Step 5: Add the `connector.yaml` tool entry** (after `append_to_list`):

```yaml
    # ─── Incident lifecycle ──────────────────────────────────────
    - name: "create_incident"
      method: "POST /incident"
      description: |
        Create a new Cortex XSOAR incident (case). Use to open a case from
        Guardian — e.g. record a finding as a tracked incident. Only `name` is
        required; createInvestigation spins up the war room.
      args:
        - { name: "name",                 type: "string",  description: "The incident name/title.", required: true }
        - { name: "incident_type",        type: "string",  description: "The XSOAR incident type (e.g. 'Phishing'). Discover via xsoar_list_incident_types.", required: false }
        - { name: "severity",             type: "integer", description: "Severity 0-4 (0 unknown … 4 critical).", required: false }
        - { name: "details",              type: "string",  description: "Free-text description / details.", required: false }
        - { name: "owner",                type: "string",  description: "Owner username.", required: false }
        - { name: "labels",               type: "array",   description: "Label strings (or [{type, value}] dicts).", required: false }
        - { name: "custom_fields",        type: "object",  description: "Dict of {cliName: value} (lowercase machine names from xsoar_get_incident_fields).", required: false }
        - { name: "create_investigation", type: "boolean", description: "Create the war-room investigation (default true).", required: false }
      returns: { type: "object", description: "{ ok, incident_id, name, created }" }
```

- [ ] **Step 6: Run to verify pass** → `-k create_incident` → PASS (3 passed).

---

### Task 10: `xsoar_run_playbook` tool

**Files:** `src/connector.py`, `connector.yaml`, `tests/test_connector.py`

⚠️ **Endpoint is the primary live-verify item (spec §6.2).** Implement against `POST /inv-playbook/{playbook_id}/{incident_id}`; the live smoke (Task 16) confirms or adjusts it.

- [ ] **Step 1: Write the failing test**

```python
def test_run_playbook_posts_inv_playbook(monkeypatch):
    rf = _RecordingFetcher(post_reply={"investigationId": "42"})
    _install_fetcher(monkeypatch, rf)
    out = run(connector.xsoar_run_playbook(incident_id="42", playbook_id="Phishing Investigation"))
    assert out["ok"] is True
    assert out["incident_id"] == "42" and out["playbook_id"] == "Phishing Investigation"
    method, path, body = rf.calls[0]
    assert method == "POST"
    assert path == "/inv-playbook/Phishing Investigation/42"


def test_run_playbook_requires_ids(monkeypatch):
    rf = _RecordingFetcher(post_reply={})
    _install_fetcher(monkeypatch, rf)
    out = run(connector.xsoar_run_playbook(incident_id="42", playbook_id=""))
    assert out["ok"] is False and "playbook_id" in out["error"]
```

- [ ] **Step 2: Run to verify failure** → `-k run_playbook` → FAIL.

- [ ] **Step 3: Implement `xsoar_run_playbook`** (append after `xsoar_create_incident`):

```python
# ─── xsoar_run_playbook ──────────────────────────────────────────────


@_wrap_xsoar_call
async def xsoar_run_playbook(incident_id: str, playbook_id: str) -> dict:
    """Assign + run a playbook on an existing XSOAR incident.

    Sets the playbook on the incident's investigation and starts it. Use to kick
    off an automated response/enrichment flow on a case.

    Args:
        incident_id: The XSOAR incident id (its investigation id) to run on.
        playbook_id: The playbook id/name to assign and run.

    Returns:
        {ok, incident_id, playbook_id, started: true}.
    """
    if not incident_id:
        raise ValueError("incident_id is required")
    if not playbook_id:
        raise ValueError("playbook_id is required")

    fetcher = _get_fetcher()
    response = await fetcher.post(f"/inv-playbook/{playbook_id}/{incident_id}", {})
    return {
        "incident_id": incident_id,
        "playbook_id": playbook_id,
        "started": True,
        "raw_response": response,
    }
```

- [ ] **Step 4: Add `"xsoar_run_playbook",` to `__all__`.**

- [ ] **Step 5: Add the `connector.yaml` tool entry** (after `create_incident`):

```yaml
    - name: "run_playbook"
      method: "POST /inv-playbook/{playbook_id}/{incident_id}"
      description: |
        Assign and run a playbook on an existing XSOAR incident — sets the
        playbook on the incident's investigation and starts it. Use to kick off
        an automated response/enrichment flow on a case.
      args:
        - { name: "incident_id", type: "string", description: "The XSOAR incident id (its investigation id) to run on.", required: true }
        - { name: "playbook_id", type: "string", description: "The playbook id/name to assign and run.", required: true }
      returns: { type: "object", description: "{ ok, incident_id, playbook_id, started }" }
```

- [ ] **Step 6: Run to verify pass** → `-k run_playbook` → PASS (2 passed).

---

### Task 11: Update `__all__` export test + module docstring + version bump; Group C commit

**Files:** `src/connector.py` (docstring, version is in yaml), `connector.yaml` (version), `tests/test_connector.py` (export-set)

- [ ] **Step 1: Update the export-set test**

In `tests/test_connector.py`, replace the `expected` set in `test_all_exported_tools_are_callable` (line 480-494) with all 21 names:

```python
    expected = {
        "xsoar_list_incidents",
        "xsoar_get_incident",
        "xsoar_get_war_room",
        "xsoar_add_entry",
        "xsoar_add_note",
        "xsoar_update_incident",
        "xsoar_close_incident",
        "xsoar_list_incident_types",
        "xsoar_get_incident_fields",
        "xsoar_search_indicators",
        "xsoar_save_evidence",
        "xsoar_search_evidence",
        "xsoar_health_check",
        "xsoar_run_command",
        "xsoar_enrich_indicator",
        "xsoar_complete_task",
        "xsoar_get_list",
        "xsoar_set_list",
        "xsoar_append_to_list",
        "xsoar_create_incident",
        "xsoar_run_playbook",
    }
```

- [ ] **Step 2: Run to verify it passes** (all 21 are now implemented + exported):

Run: `python3 -m pytest tests/test_connector.py -k all_exported_tools -x -q`
Expected: PASS.

- [ ] **Step 3: Update the module docstring tool catalog**

In `src/connector.py`, extend the "Tool catalog (13):" block (lines 11-24) to 21 — change the header to `Tool catalog (21):` and append after the `xsoar_health_check` line:

```
  ── action toolset (v0.2.0) ──
  xsoar_run_command           POST /entry/execute/sync — run any !command (playground)
  xsoar_enrich_indicator      POST /entry/execute/sync — ip/url/domain/file/cve reputation
  xsoar_complete_task         POST /entry/execute/sync — !taskComplete a playbook task
  xsoar_get_list              GET /lists/ — read an XSOAR list by name
  xsoar_set_list              POST /lists/save — overwrite/create a list
  xsoar_append_to_list        GET /lists/ + POST /lists/save — append to a list
  xsoar_create_incident       POST /incident — create a case
  xsoar_run_playbook          POST /inv-playbook/{pb}/{inv} — run a playbook on a case
```

- [ ] **Step 4: Bump the connector version**

In `connector.yaml` line 20, change `version: "0.1.0"` → `version: "0.2.0"`.

- [ ] **Step 5: Run the full connector suite**

Run: `cd bundles/spark/connectors/xsoar && python3 -m pytest tests/ -x -q`
Expected: ALL PASS (every test incl. the export-set).

- [ ] **Step 6: Commit Group C**

```bash
cd /Users/ayman/Documents/Kite/guardian
git add bundles/spark/connectors/xsoar/
git commit -m "$(cat <<'EOF'
xsoar: incident lifecycle — create_incident, run_playbook

Adds create_incident (POST /incident) and run_playbook
(POST /inv-playbook/{pb}/{inv}). Updates the export-set test (21 tools),
module-docstring catalog, and bumps the connector to v0.2.0. Completes the
8-tool action-toolset arc (Group C). run_playbook's endpoint is confirmed
on the live tenant during smoke.

Refs #5

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## DOCS — ship with the arc (before the tag)

> Each docs task: READ the target file first, follow its existing component/pattern, then add the new content. The `superpowers`/`help-page-update` conventions apply: architecture page = the spec; user guide = operator-facing; tag new content with the version.

### Task 12: Architecture page `#xsoar-actions`

**Files:** Modify `mcp/agent/app/help/architecture/page.tsx`

- [ ] **Step 1:** Read `mcp/agent/app/help/architecture/page.tsx` and find the connector/XSOAR section + the `Section`/`SubSection` (or equivalent) component pattern + how `id=` anchors are set.

- [ ] **Step 2:** Add a section with `id="xsoar-actions"` (titled e.g. "XSOAR action toolset (v0.2.0)") documenting, in the page's existing component style:
  - The connector now exposes 21 tools across read/lifecycle (13) + the action toolset (8).
  - **The command engine + playground:** `run_command`/`enrich_indicator`/`complete_task` run `!commands` synchronously via `POST /entry/execute/sync` inside the instance's `playground_id` War Room; the dual-gen fetcher prepends `/xsoar/public/v1` on v8. Missing `playground_id` → operator-actionable error.
  - **The inter-service path:** `guardian-agent` (Next.js) → embedded MCP (`/api/v1/*`, bearer `MCP_TOKEN`) → per-instance `guardian-connector-xsoar` container (MCP-over-HTTP, port 9000) → Cortex XSOAR REST (`/entry/execute/sync`, `/lists/save`, `/incident`, `/inv-playbook/...`), dual v6/v8 auth.
  - **Config:** `playground_id` is an optional connector-instance field (backwards-compatible; the 13 read/lifecycle tools work without it).

- [ ] **Step 3:** If the architecture page has a per-section "Implementation gap" convention, note `run_playbook`'s endpoint is live-verified (remove the note once confirmed in Task 16).

- [ ] **Step 4:** Verify the page compiles (deferred to the agent-side gate in Task 15's commit — `npm run build`).

### Task 13: User guide `#xsoar-actions`

**Files:** Modify `mcp/agent/app/help/user/page.tsx`

- [ ] **Step 1:** Read `mcp/agent/app/help/user/page.tsx`; find the XSOAR usage section + the subsection/anchor pattern.

- [ ] **Step 2:** Add a subsection with `id="xsoar-actions"` (tagged v0.2.0) in the page's style:
  - What you can now ask Guardian to do: *"run `!Print value=hi` in XSOAR"*, *"enrich 8.8.8.8"*, *"add 1.2.3.4 to the blocklist"*, *"open an incident for this finding"*, *"run the Phishing playbook on case 42"*, *"complete task 7 on case 42"*.
  - **Setup note:** the command tools (run_command, enrich_indicator, complete_task) need a **Playground / War Room investigation ID** set as `playground_id` on the XSOAR instance (Settings → Connectors → XSOAR instance). Where to find it: open the Playground in XSOAR, copy the id from the URL. The other tools work without it.

### Task 14: Journey

**Files:** Modify `mcp/agent/lib/journeys.ts`

- [ ] **Step 1:** Read `mcp/agent/lib/journeys.ts`; match the existing journey object shape (id, title, steps, etc.).

- [ ] **Step 2:** Add one journey, e.g. `xsoar-run-command`:
  - Title: "Run an XSOAR command / enrich an indicator".
  - Steps (click-path): Connectors → open the XSOAR instance → set `playground_id` → save → open chat → ask *"enrich 8.8.8.8 in XSOAR"* → Guardian calls `xsoar_enrich_indicator` → see the DBotScore in the reply.

### Task 15: CHANGELOG + release-notes; docs commit + gate

**Files:** Modify `CHANGELOG.md`, `mcp/agent/lib/release-notes.ts`

- [ ] **Step 1:** Read the top entries of both files to match format + the current version header convention.

- [ ] **Step 2:** Add a CHANGELOG.md entry (newest first) — long-form, operator language. Use the issue #5 "What ships" as the source. Include: the 8 tools by group, the `playground_id` config field, Scenario 1, and a "Forbidden post-release" note (no XSIAM tools under XSOAR; no credential reads in these tools).

- [ ] **Step 3:** Add the matching `mcp/agent/lib/release-notes.ts` entry (NEWEST FIRST), 3-7 bullets ~10-15 words each, e.g.:
  - "XSOAR connector: run any `!command` in a configured playground War Room"
  - "Enrich IPs/URLs/domains/files/CVEs → DBotScore reputation, inline in chat"
  - "Manage XSOAR Lists (allow/block) — read, overwrite, append"
  - "Create incidents and run playbooks on cases from Guardian"
  - "New `playground_id` field on the XSOAR instance powers the command tools"

  Use the existing version constant the release will carry (set in the same place prior entries set it; if it references a `version` string, match the next minor — confirm against the prior entry's shape).

- [ ] **Step 4:** Run the **agent-side gate** (these docs are TS/TSX):

```bash
cd mcp/agent && npx tsc --noEmit && npm run lint && npm run build
```
Expected: all pass (strict route validation included).

- [ ] **Step 5:** Commit the docs:

```bash
cd /Users/ayman/Documents/Kite/guardian
git add mcp/agent/app/help CHANGELOG.md mcp/agent/lib/release-notes.ts mcp/agent/lib/journeys.ts
git commit -m "$(cat <<'EOF'
docs: XSOAR action toolset — architecture #xsoar-actions, user guide, journey, release notes

Documents the 8-tool action toolset + playground_id config: architecture
#xsoar-actions (command engine + inter-service path), user guide
#xsoar-actions (what to ask + the playground_id setup), a run-command
journey, CHANGELOG + release-notes. Completes the arc's docs.

Refs #5

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## VERIFY — full gate + live smoke (before the tag)

### Task 16: Full pre-deploy gate + push + live smoke

- [ ] **Step 1: Run the full pre-deploy gate** (root CLAUDE.md):

```bash
cd /Users/ayman/Documents/Kite/guardian/mcp/agent
npx tsc --noEmit && npm run lint && npm run build
cd ../../bundles/spark/mcp && PYTHONPATH=$PWD/src python3 -m pytest tests/ -x
cd ../connectors/xsoar && python3 -m pytest tests/ -x -q
```
Expected: all green. (Embedded-MCP pytest must still pass — the connector loads there.)

- [ ] **Step 2: Push the arc** (CI builds the xsoar connector image + auto-deploys to guardian-vm). Ensure `thekite-dev` is the active gh account; rebase on origin/main first (the loop co-authors main):

```bash
cd /Users/ayman/Documents/Kite/guardian
git pull --rebase origin main && git push origin main
```

- [ ] **Step 3: Watch CI to completion** (the `Build connectors` workflow + `build-dev-installer.yml` auto-deploy). I own the wait — do NOT punt to the operator. Verify the deployed `GUARDIAN_VERSION` and that the new xsoar connector image is what the instance container runs.

- [ ] **Step 4: Live smoke against guardian-vm** (IAP tunnel + `GUARDIAN_API_KEY` bearer). Set `playground_id` on the live XSOAR instance first, then run the issue #5 smoke bullets:
  - `run_command "!Print value=hello"` → `output` contains `hello` (confirms the type-1-include parse fix + the execute/sync path/prefix).
  - `enrich_indicator ip 8.8.8.8` → `context` has a `DBotScore`.
  - `set_list` / `get_list` / `append_to_list` round-trip a `guardian_test` list (confirms `GET /lists/` returns `data` inline — spec §14).
  - `create_incident name="guardian smoke"` → numeric `incident_id`; confirm via `get_incident`.
  - `run_playbook` on that incident → ok OR adjust the endpoint + re-commit (spec §6.2 fallback).
  - `complete_task` on a war-room task → completes.
  - blank-`playground_id` instance → `run_command` returns the clean `playground_id not configured` envelope.

- [ ] **Step 5: Apply `status:dev-built` → run smoke → `status:ready-for-testing`** on issue #5 (via `gh`, thekite-dev). Post the cumulative smoke matrix to chat AND as an issue comment.

- [ ] **Step 6: Ask the operator for tag approval** (capability acceptance — all 8 tools work end-to-end on the deployed install). Do NOT tag without it.

---

## Self-review (run after writing — done)

- **Spec coverage:** §4 engine → Tasks 2-5; §4.1 run_command → T3; §4.2 enrich → T4; §4.3 complete_task → T5; §5 Lists → T6-8; §6 lifecycle → T9-10; §7 playground_id → T1; §10 testing → per-task tests + T16; §11 docs → T12-15; §12 release/commits → group commits + T16. All covered.
- **Placeholder scan:** no TBD/TODO; every code step has complete code; docs tasks carry the actual prose to add (only the exact JSX wrapping defers to the file's existing pattern, which is correct for an existing-codebase edit).
- **Type/name consistency:** `_get_playground_id`, `_parse_war_room_entries`, `_execute_command`, `_find_list`, `_ENRICH_CMD_MAP`, `_ScriptedFetcher` used consistently across tasks; `list_type` (not `type`) param avoids the builtin shadow in set_list/append; `incident_type` (not `type`) in create_incident; all 8 names match between `__all__`, the functions, the `connector.yaml` entries, and the export-set test in T11.
