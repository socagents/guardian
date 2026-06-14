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
