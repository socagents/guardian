"""Playbook-builder tools (v0.2.24).

The agent drafts NEW Cortex XSOAR playbooks grounded in the `soar-playbooks`
KB examples (see the `build_xsoar_playbook` skill). A drafted playbook YAML is
only useful if it's structurally importable, so this module exposes a
deterministic validator the agent (and the /playbooks/build UI) calls before
presenting a draft.

`playbook_validate` is a PURE validation utility — it reads no SecretStore value
and mutates no catalog state, so it's safe to register as an agent `mcp.tool()`
(credential + catalog boundaries both clear).
"""
from __future__ import annotations

import dataclasses
from typing import Any


def _walk_next_task_ids(task: dict[str, Any]) -> list[str]:
    """Collect every task id referenced by a task's nexttasks map.
    nexttasks is {condition-label: [task-id, ...]} (e.g. {"#none#": ["1"]})."""
    out: list[str] = []
    nxt = task.get("nexttasks")
    if isinstance(nxt, dict):
        for ids in nxt.values():
            if isinstance(ids, list):
                out.extend(str(i) for i in ids)
    return out


def playbook_validate(playbook_yaml: str) -> dict[str, Any]:
    """Validate a drafted Cortex XSOAR playbook YAML for structural soundness.

    Use this AFTER drafting a playbook (the `build_xsoar_playbook` skill) and
    BEFORE presenting it — a subtly-malformed playbook won't import. It does NOT
    execute anything; it only checks structure.

    Args:
        playbook_yaml: the full playbook as a YAML string.

    Checks (errors block import; warnings are advisable fixes):
      * parses as a YAML mapping
      * required top-level fields: id, name, starttaskid, tasks
      * tasks is a non-empty mapping; starttaskid is one of its keys
      * every task has an id + type
      * task-graph integrity: every id referenced by a task's nexttasks exists
      * (warn) a `type: start` task exists; description/inputs present;
        unreachable tasks

    Returns {valid: bool, errors: [str], warnings: [str], task_count: int}.
    `valid` is true iff errors is empty.

    Example: playbook_validate(playbook_yaml="id: my-pb\\nname: My PB\\n...").
    """
    import yaml  # noqa: PLC0415

    errors: list[str] = []
    warnings: list[str] = []
    try:
        pb = yaml.safe_load(playbook_yaml)
    except yaml.YAMLError as exc:
        return {"valid": False, "errors": [f"not valid YAML: {exc}"],
                "warnings": [], "task_count": 0}
    if not isinstance(pb, dict):
        return {"valid": False, "errors": ["top level must be a YAML mapping"],
                "warnings": [], "task_count": 0}

    for field in ("id", "name", "starttaskid", "tasks"):
        if field not in pb or pb.get(field) in (None, ""):
            errors.append(f"missing required field: {field}")

    tasks = pb.get("tasks")
    task_count = len(tasks) if isinstance(tasks, dict) else 0
    if not isinstance(tasks, dict) or not tasks:
        errors.append("tasks must be a non-empty mapping of task-id -> task")
        return {"valid": not errors, "errors": errors, "warnings": warnings,
                "task_count": task_count}

    task_ids = {str(k) for k in tasks.keys()}
    start = str(pb.get("starttaskid"))
    if start not in task_ids:
        errors.append(f"starttaskid {start!r} is not a key in tasks")

    has_start_type = False
    for tid, task in tasks.items():
        if not isinstance(task, dict):
            errors.append(f"task {tid!r} must be a mapping")
            continue
        if not task.get("type"):
            errors.append(f"task {tid!r} is missing 'type'")
        if task.get("type") == "start":
            has_start_type = True
        for ref in _walk_next_task_ids(task):
            if ref not in task_ids:
                errors.append(f"task {tid!r} nexttasks references unknown task {ref!r}")

    if not has_start_type:
        warnings.append("no task with type 'start' — XSOAR playbooks usually begin with one")
    if not (pb.get("description") or "").strip():
        warnings.append("no top-level description — add one so the playbook is discoverable")
    if not pb.get("inputs"):
        warnings.append("no inputs declared — confirm the playbook needs none")

    # unreachable tasks (reachable from start via nexttasks)
    reachable: set[str] = set()
    frontier = [start] if start in task_ids else []
    while frontier:
        cur = frontier.pop()
        if cur in reachable:
            continue
        reachable.add(cur)
        frontier.extend(_walk_next_task_ids(tasks.get(cur, {})))
    unreachable = task_ids - reachable
    if unreachable and start in task_ids:
        warnings.append(f"{len(unreachable)} task(s) unreachable from the start task: "
                        f"{', '.join(sorted(unreachable)[:8])}")

    return {"valid": not errors, "errors": errors, "warnings": warnings,
            "task_count": task_count}


# ─────────────────────────────────────────────────────────────────
# Playbook-build history (v0.2.50) — read + write tools over the
# playbook_build_store. The durable record of the playbooks the agent
# authored for an operator: each row is one "build" (use-case prompt,
# drafted YAML, validation result, deploy summary + test incident id),
# moving through drafted → validated → deployed → tested (or failed).
#
# State taxonomy (root CLAUDE.md §"Catalog boundary ≠ credential
# boundary"): the CATALOG domain, NOT credentials. These tools read +
# write build METADATA (use-case, YAML, status) in playbook_builds.db
# and touch NO SecretStore value (the XSOAR creds live in the connector
# instance's SecretStore, never in a build row). Mutating catalog
# metadata is permitted, so registering the write tools
# (record / update / delete) as agent mcp.tool()s is allowed.
#
# Each tool resolves the store via its module-level singleton at call
# time and returns the "store not initialized" error when the runtime
# (test harness, early boot) hasn't wired it — same convention as the
# self_mod_tools / cognitive_tools reads.
# ─────────────────────────────────────────────────────────────────


def _build_to_dict(b: Any) -> dict[str, Any]:
    """Full JSON-serializable view of a PlaybookBuild (every field)."""
    return dataclasses.asdict(b)


def _compact(b: Any) -> dict[str, Any]:
    """Lean view for list payloads — drops the two large free-text
    fields (`playbook_yaml`, `deploy_summary`) that bloat a history
    listing. The get / record / update tools return the full dict."""
    d = dataclasses.asdict(b)
    d.pop("playbook_yaml", None)
    d.pop("deploy_summary", None)
    return d


def playbook_builds_list(
    status: str | None = None,
    order: str = "desc",
) -> dict[str, Any]:
    """List recorded playbook builds (the build history), newest-first
    by default.

    Use this to answer "what playbooks have we built / deployed?" — it
    returns the lean per-build view (without the large playbook_yaml +
    deploy_summary fields); call `playbook_builds_get` for one build's
    full record incl. the YAML.

    Args:
        status: optional lifecycle filter — one of drafted / validated /
            deployed / tested / failed. Null = every build.
        order: "desc" (default) for newest-first, "asc" for oldest-first.

    Returns {builds: [{id, use_case, product, playbook_name, status,
                       validation_json, test_incident_id, session_id,
                       created_by, created_at, updated_at}], count}.
    """
    from usecase.playbook_build_store import playbook_build_store
    s = playbook_build_store()
    if s is None:
        return {"error": "playbook build store not initialized"}
    builds = s.list_builds(status=status, order=order)
    return {"builds": [_compact(b) for b in builds], "count": len(builds)}


def playbook_builds_get(build_id: str) -> dict[str, Any]:
    """Fetch one playbook build by id — the FULL record, including the
    drafted `playbook_yaml` + `deploy_summary`.

    Use this when the operator wants the actual playbook content of a
    build the history (`playbook_builds_list`) surfaced, or to inspect a
    build's validation / deploy detail.

    Args:
        build_id: the build's id (uuid hex).

    Returns the full build dict, or {error: "not found", build_id}.
    """
    from usecase.playbook_build_store import playbook_build_store
    s = playbook_build_store()
    if s is None:
        return {"error": "playbook build store not initialized"}
    b = s.get_build(build_id)
    if b is None:
        return {"error": "not found", "build_id": build_id}
    return _build_to_dict(b)


def playbook_build_record(
    use_case: str,
    product: str | None = None,
    playbook_name: str | None = None,
    playbook_yaml: str | None = None,
    status: str = "drafted",
    validation_json: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Record a playbook build the agent just authored, so it shows in
    the build history + audit log.

    Call this AFTER drafting / validating / deploying a playbook (the
    `build_xsoar_playbook` skill) to persist the build as a row the
    /playbooks/build UI + the audit trail surface. Creating the build
    emits a `playbook_drafted` audit event.

    Args:
        use_case: the operator's use-case prompt that the playbook
            addresses (required).
        product: target product (e.g. "xsoar"). Null if unspecified.
        playbook_name: the drafted playbook's name. Null pre-naming.
        playbook_yaml: the full drafted playbook YAML. Null if not yet
            authored.
        status: lifecycle stage — drafted (default) / validated /
            deployed / tested / failed.
        validation_json: the `playbook_validate` result serialized as
            JSON, attached when the build has been validated.
        session_id: the chat session this build was authored in, so the
            UI can link the build back to its conversation.

    Returns the full created build dict. `created_by` is attributed to
    the resolved tool actor (operator / api-key / agent).
    """
    from usecase.audit_log import resolve_tool_actor
    from usecase.playbook_build_store import playbook_build_store
    s = playbook_build_store()
    if s is None:
        return {"error": "playbook build store not initialized"}
    b = s.create_build(
        use_case=use_case,
        product=product,
        playbook_name=playbook_name,
        playbook_yaml=playbook_yaml,
        status=status,
        validation_json=validation_json,
        session_id=session_id,
        created_by=resolve_tool_actor(),
    )
    return _build_to_dict(b)


def playbook_build_update(
    build_id: str,
    status: str | None = None,
    playbook_name: str | None = None,
    playbook_yaml: str | None = None,
    validation_json: str | None = None,
    deploy_summary: str | None = None,
    test_incident_id: str | None = None,
) -> dict[str, Any]:
    """Update a build as it moves through the lifecycle.

    Call this to advance a build's status (set status="deployed" once
    imported into XSOAR, "tested" after a test-run, "failed" on error)
    and to attach the `deploy_summary` + `test_incident_id` produced by
    the deploy / test-run step. A partial update — only the fields you
    pass (non-null) change; everything else is left alone.

    Setting `status` to deployed / tested / failed emits the matching
    audit event (playbook_deployed / playbook_test_run success / failure).

    Args:
        build_id: the build's id.
        status: new lifecycle stage — drafted / validated / deployed /
            tested / failed.
        playbook_name: set / correct the playbook's name.
        playbook_yaml: replace the drafted YAML (e.g. after a revision).
        validation_json: attach an updated `playbook_validate` result.
        deploy_summary: free-text summary of the XSOAR import / deploy.
        test_incident_id: the incident id the test-run fired against.

    Returns the full updated build dict, or {error: "not found",
    build_id}.
    """
    from usecase.playbook_build_store import playbook_build_store
    s = playbook_build_store()
    if s is None:
        return {"error": "playbook build store not initialized"}
    b = s.update_build(
        build_id,
        status=status,
        playbook_name=playbook_name,
        playbook_yaml=playbook_yaml,
        validation_json=validation_json,
        deploy_summary=deploy_summary,
        test_incident_id=test_incident_id,
    )
    if b is None:
        return {"error": "not found", "build_id": build_id}
    return _build_to_dict(b)


def playbook_build_delete(build_id: str) -> dict[str, Any]:
    """Remove a build record from the playbook-build history.

    Call this when the operator wants to prune a build from the history
    (e.g. an abandoned draft). Deleting a build emits a
    `playbook_build_deleted` audit event.

    Args:
        build_id: the build's id.

    Returns {deleted: bool, build_id}. `deleted` is false when no build
    with that id existed.
    """
    from usecase.playbook_build_store import playbook_build_store
    s = playbook_build_store()
    if s is None:
        return {"error": "playbook build store not initialized"}
    deleted = s.delete_build(build_id)
    return {"deleted": deleted, "build_id": build_id}
