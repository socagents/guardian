# Connector Tool Flat-Args Consistency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every connector tool dispatched through the central MCP takes **flat named kwargs** that match its `connector.yaml` `args` list exactly — eliminating the single-`request:`-model parameter pattern that the agent cannot call (Refs #111).

**Architecture:** Each tool's three surfaces — `connector.yaml` args, the Python function signature, and (any) internal Pydantic model — are reconciled to ONE flat shape using names = **what the function actually uses**. The Pydantic model is dropped (or rebuilt internally from kwargs) so it's never the tool's parameter. Mirrors the v0.17.77 `phantom_create_data_worker` flattening. A CI validator then enforces signature ⟺ connector.yaml so it can't drift again.

**Tech Stack:** Python (FastMCP connectors under `bundles/spark/connectors/`), connector-local pytest, `scripts/maintainer/validate_all.py` for the CI guard.

---

## The canonical pattern (apply to every tool)

For each tool the executor MUST:
1. **Read the function body** to find which fields it ACTUALLY uses (`request.X`).
2. **Define canonical flat args = the actually-used fields**, names taken from the model field names (the function already references them), types from the model.
3. **Flatten the signature**: `async def tool(request: Model, ctx)` → `async def tool(*, field1: T1 = default, field2: ..., ctx: Context = None)`.
4. **Rebuild the model internally** (one line) so the body is unchanged: `request = Model(field1=field1, field2=field2, ...)`. (If the model adds no validation beyond types, you may drop it and use the kwargs directly — prefer rebuilding to minimize body diff.)
5. **Align `connector.yaml`** `args` to the SAME names/types — drop args the function never uses (YAGNI; e.g. `run_xql_query` advertises `tenant_ids`/`timeframe` the function ignores → remove them), add any used field the yaml lacks.
6. **Update the docstring example** from `{"arguments": {"request": {...}}}` to flat `{"arguments": {...}}`.
7. **Connector-local test**: assert the tool is callable with flat kwargs.
8. The CI validator (Task 1) must pass.

### Worked example — `xsiam_run_xql_query` (the proof tool, Task 2)

BEFORE — `bundles/spark/connectors/xsiam/src/connector.py:346`:
```python
async def xsiam_run_xql_query(request: RunXqlQueryRequest, ctx: Context) -> dict:
    """... Example: {"arguments": {"request": {"query": "..."}}} ..."""
    if not request.query or not request.query.strip():
        return _create_response({"error": "XQL query is required"}, is_error=True)
    ...
    start_payload = {"request_data": {"query": request.query.strip(), ...}}
```
The body uses ONLY `request.query`. `connector.yaml` over-advertises `query, tenant_ids, timeframe`.

AFTER:
```python
async def xsiam_run_xql_query(query: str = "", ctx: Context = None) -> dict:
    """... Example: {"arguments": {"query": "dataset = phantom_logs_raw | limit 10"}} ..."""
    if not query or not query.strip():
        return _create_response({"error": "XQL query is required"}, is_error=True)
    ...
    start_payload = {"request_data": {"query": query.strip(), ...}}
```
`connector.yaml` xsiam `run_xql_query.args` → `[{name: query, type: string, required: true}]` (drop `tenant_ids`/`timeframe`).

---

## Task 1: CI validator — connector tool signature ⟺ connector.yaml

**Files:**
- Modify: `scripts/maintainer/validate_all.py` (add `check_connector_tool_args_flat()` + register it)
- Test: `scripts/maintainer/tests/test_connector_tool_args_flat.py` (create if a tests dir exists; else a `__main__` self-check)

- [ ] **Step 1: Write the failing test** — assert the checker flags a `request:`-model tool.

```python
# Given a connector dir with a tool def `async def t(request: M, ctx)` and connector.yaml listing flat args,
# check_connector_tool_args_flat() returns a non-empty list of violations naming that tool.
from scripts.maintainer.validate_all import check_connector_tool_args_flat
violations = check_connector_tool_args_flat(connectors_root="bundles/spark/connectors")
# Before the refactor this is non-empty (xsiam_run_xql_query etc.); the test asserts the CHECKER works,
# not that the tree is clean yet:
assert isinstance(violations, list)
```

- [ ] **Step 2: Implement `check_connector_tool_args_flat()`** — for each `connector.yaml` tool, find its Python `async def <prefix>?<name>(...)`; FAIL if the first non-`ctx` parameter is a single `*: SomePydanticModel` (i.e. a param named `request` / typed as a `*Request`/`*Input` model), OR if the function's parameter names don't match the yaml `args` names. Return `[(connector, tool, reason)]`.

```python
import re, glob, yaml, os
def check_connector_tool_args_flat(connectors_root="bundles/spark/connectors"):
    violations=[]
    for ydir in sorted(glob.glob(f"{connectors_root}/*/")):
        yf=os.path.join(ydir,"connector.yaml")
        if not os.path.exists(yf): continue
        spec=(yaml.safe_load(open(yf)) or {}).get("spec",{}) or {}
        srcs="\n".join(open(p).read() for p in glob.glob(os.path.join(ydir,"src","*.py")))
        for t in spec.get("tools",[]):
            name=t.get("name");  yargs={a.get("name") for a in t.get("args",[])}
            m=re.search(rf'^async def (?:[a-z_]+_)?{re.escape(name)}\(([^)]*)\)', srcs, re.M)
            if not m: continue
            params=[p.strip() for p in m.group(1).split(",") if p.strip()]
            sig=[p for p in params if not p.startswith("ctx") and p!="*" and not p.startswith("self")]
            # single request:Model violation
            if len(sig)==1 and re.match(r'request\s*:', sig[0]):
                violations.append((os.path.basename(ydir.rstrip('/')),name,"single request: model param"))
                continue
            pnames={re.split(r'[:=]',p)[0].strip().lstrip('*') for p in sig}
            pnames.discard("")
            missing=yargs - pnames
            if missing:
                violations.append((os.path.basename(ydir.rstrip('/')),name,f"yaml args not in signature: {sorted(missing)}"))
    return violations
```

- [ ] **Step 3: Register** the check in `validate_all.py`'s main runner so CI fails on violations.
- [ ] **Step 4: Run** `python3 scripts/maintainer/validate_all.py` — expect it to LIST the 19 known violations (proves the checker detects them). Commit the checker (it will go green after Tasks 2–4).
- [ ] **Step 5: Commit** `git add scripts/maintainer/validate_all.py && git commit -m "feat(ci): validator — connector tool signatures must be flat + match connector.yaml (Refs #111)"`

## Task 2: Flatten `xsiam_run_xql_query` (proof tool) + DEPLOY + verify on agent

This is the de-risking task: prove the flatten makes the live agent call it successfully before fanning out.

**Files:** Modify `bundles/spark/connectors/xsiam/src/connector.py:346` + `bundles/spark/connectors/xsiam/connector.yaml` (run_xql_query args) + `bundles/spark/connectors/xsiam/tests/`.

- [ ] **Step 1: connector-local test** — `xsiam_run_xql_query` accepts a flat `query=` kwarg (patch `_get_fetcher` to capture the payload; assert it builds `request_data.query`).
- [ ] **Step 2:** run it → FAIL (current signature wants `request`).
- [ ] **Step 3:** apply the AFTER from the worked example above (signature + body + connector.yaml + docstring).
- [ ] **Step 4:** run the test → PASS. Run `validate_all.py` → run_xql_query no longer in violations.
- [ ] **Step 5: Commit**, push, let CI build the xsiam connector, reconcile the xsiam connector instance on phantom-vm (updater `POST /connectors/reconcile/digests`), then drive `/api/chat`: *"Using XSIAM, show me 20 recent events in phantom_logs_raw"* → confirm `xsiam_run_xql_query` is called with flat `{query:...}` and returns rows (no validation loop). **This proves the pattern end-to-end before Tasks 3–4.**

## Task 3: Flatten remaining xsiam tools (10)

**Files:** `bundles/spark/connectors/xsiam/src/connector.py` + `bundles/spark/connectors/xsiam/connector.yaml` + tests.

Apply the canonical pattern to each. Per-tool model + yaml args (executor reads each body for actually-used fields):

| tool | model | connector.yaml args today |
|---|---|---|
| `get_cases` | GetCasesRequest | filter, limit |
| `send_webhook_log` | WebhookLogRequest | log, format |
| `add_lookup_data` | LookupDataRequest | table, rows |
| `get_lookup_data` | GetLookupDataRequest | table, filter |
| `remove_lookup_data` | RemoveLookupDataRequest | table, filter |
| `create_dataset` | CreateDatasetRequest | name, description, schema |
| `find_xql_examples_rag` | FindXqlExamplesRequest | intent, top_k |
| `get_asset_by_id` | GetAssetByIdRequest | asset_id |
| `get_assets` | GetAssetsRequest | filter, limit |
| `get_issues` | GetIssuesRequest | filter, limit |

- [ ] For each: test (flat kwarg callable) → flatten signature + rebuild model + align connector.yaml names to the model's actual fields + flat docstring → test passes → validator clean for that tool → **commit per tool** (`refactor(connector/xsiam): flatten <tool> to flat kwargs (Refs #111)`).

> NOTE — name reconciliation: where yaml names ≠ model fields (e.g. `get_cases` yaml `filter,limit` vs model `query`; `add_lookup_data` yaml `table,rows` vs model `dataset_name,data,key_fields`), the **model field names are the contract** (the function uses them) — update connector.yaml to those names. Pick the clearer name only if the model name is cryptic, and keep yaml ⟺ signature ⟺ model identical.

## Task 4: Flatten xlog tools (8)

**Files:** `bundles/spark/connectors/xlog/src/{field_info,observables_catalog,data_faker,scenarios,simulation_runs}.py` + `bundles/spark/connectors/xlog/connector.yaml` + tests.

| tool | file | model | yaml args today |
|---|---|---|---|
| `get_field_info` | field_info.py | FieldInfoRequest | vendor *(wrong — model is log_type, include_observables)* |
| `generate_observables` | observables_catalog.py | GenerateObservablesRequest | kind, count, seed *(model: count, observable_type, known)* |
| `generate_fake_data` | data_faker.py | FakeDataRequest | *(none — add the used ones)* |
| `generate_scenario_fake_data` | scenarios.py | GenerateScenarioRequest | scenario, limit |
| `create_scenario_worker` | scenarios.py | CreateScenarioWorkerRequest | scenario, destination |
| `run_detection_validation` | simulation_runs.py | DetectionValidationRequest | technique_id, expected_rule, destination |
| `get_simulation_result` | simulation_runs.py | SimulationResultRequest | validation_id *(model: simulation_id)* |
| `generate_coverage_report` | simulation_runs.py | CoverageReportRequest | format, since, until *(model: include_simulations, limit)* |

- [ ] Same pattern + per-tool commit. **`get_field_info` is the highest-value** (the agent uses it constantly) — its yaml `vendor` is simply wrong; canonical args are `log_type` (required) + `include_observables` (default false). Reconcile yaml + signature + model to those.

## Task 5: Pre-deploy gate + push + deploy + full re-test + tag

- [ ] **Pre-deploy gate:** `cd mcp/agent && npx tsc --noEmit && npm run lint && npm run build && (cd ../../bundles/spark/mcp && uv-pytest)` + `validate_all.py` clean.
- [ ] Push (batched); watch the connector build chain; reconcile ALL changed connector instances on phantom-vm (`POST /connectors/reconcile/digests`).
- [ ] **Re-run the exact session d4f6c222 prompts** that failed: XQL on phantom_logs_raw; FortiGate field_info; port-scan + XQL verify; Okta E2E. Confirm flat calls succeed first try, no `request:`/`unexpected_keyword` validation loops.
- [ ] Docs: CHANGELOG + release-notes (v0.17.114+); note in architecture `#stack` that all connector tools use flat kwargs. Update any MCP-tool docstrings referencing the `request` wrapper.
- [ ] Apply `status:ready-for-testing`; ask operator for the customer tag.

---

## Self-review notes
- **Spec coverage (#111):** Task 1 = validator; Tasks 2–4 = flatten all 19; Task 5 = deploy + re-test the failing prompts + the acceptance criteria. ✓
- **Name-reconciliation rule** is stated explicitly (model fields are the contract; yaml updated to match) — covers the deeper mismatch found during scoping.
- **De-risk:** Task 2 proves the pattern on one tool end-to-end (incl. live-agent verification) before fanning out.
- **Out of scope (separate):** XQL backend selection skill note; xlog worker-cleanup/timeout. Not in this plan.
