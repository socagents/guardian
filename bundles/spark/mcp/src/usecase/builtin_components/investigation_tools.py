"""Investigation MCP tools — agent-facing Issue + Case management (v0.1.3).

These let the agent record its investigations LOCALLY on Guardian: open an
Issue when it starts investigating an incident, log what it does + finds,
fill in the structured investigation fields, and group related Issues into
Cases. The operator sees all of this in the Investigation UI.

Catalog-vs-credential boundary (root CLAUDE.md): Issues + Cases are
investigation metadata — NOT secrets, NOT platform catalogue membership.
So these tools are on the **safe (catalog) side** of the guardrail and ARE
agent-callable (registered in connector_loader._BUILTIN_LEGACY_TOOLS). They
read/write only `investigation_store` — no SecretStore access.

Convention (mirrors self_mod_tools): plain sync functions that fetch the
store via the `investigation_store()` singleton and return a JSON-able dict
(success → the data; failure → {"error": ...}).
"""

from __future__ import annotations

import dataclasses
from typing import Any

from usecase.investigation_store import investigation_store


def _store():
    s = investigation_store()
    if s is None:
        return None, {"error": "investigation store not initialized on this MCP runtime"}
    return s, None


def issue_create(
    title: str,
    kind: str = "other",
    severity: str = "medium",
    source_ref: str | None = None,
    scope: str | None = None,
    summary: str | None = None,
) -> dict[str, Any]:
    """Open a local Guardian Issue for an investigation.

    Call this at the START of investigating an incident — whether the
    operator asked you to investigate, or you fetched an incident from the
    XSOAR store. The Issue is where you record the investigation; the
    operator sees it in the Investigation UI. Log your steps with
    issue_add_event and fill the findings with issue_update as you go.

    Args:
        title: Short title (e.g. "Phishing — credential harvest from acme-login.com").
        kind: Incident type — one of phishing / lateral_movement /
            access_violation / malware / other (free-form allowed).
        severity: low / medium / high / critical (default medium).
        source_ref: The upstream XSOAR incident id, when investigating a
            fetched incident (so the Issue links back to the case). Omit for
            a standalone finding.
        scope: What you're investigating (markdown). Optional at create;
            can be set later via issue_update.
        summary: An initial summary (markdown). Optional.

    Example: issue_create(title="Malware on host WS-12", kind="malware",
             severity="high", source_ref="1234")

    Returns: {"issue": {...}} with the created issue (note its `id` for
    subsequent issue_update / issue_add_event / case_add_issue calls).
    """
    s, err = _store()
    if err:
        return err
    if not title or not str(title).strip():
        return {"error": "title is required"}
    issue = s.create_issue(
        title=str(title).strip(), kind=kind or "other", severity=severity or "medium",
        origin="agent", source_ref=source_ref, scope=scope, summary=summary,
    )
    return {"issue": dataclasses.asdict(issue)}


def issue_update(
    issue_id: str,
    status: str | None = None,
    severity: str | None = None,
    summary: str | None = None,
    scope: str | None = None,
    recommendations: str | None = None,
    conclusions: str | None = None,
    next_steps: str | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    """Update an Issue's investigation fields (partial — only what you pass).

    Use as the investigation progresses to record findings + the verdict:
    set the summary, what you investigated (scope), recommendations,
    conclusions, next_steps, and move status (open → investigating →
    resolved / closed). All text fields are markdown.

    Args:
        issue_id: The Issue id (from issue_create).
        status: open / investigating / resolved / closed.
        severity: low / medium / high / critical.
        summary / scope / recommendations / conclusions / next_steps: markdown.
        title: rename the issue (rarely needed).

    Example: issue_update(issue_id="…", status="resolved",
             conclusions="Confirmed phishing; credentials not entered.",
             recommendations="Block sender domain; reset the targeted user.",
             next_steps="Hunt for the domain across mail logs.")

    Returns: {"issue": {...}} updated, or {"error": ...} if not found.
    """
    s, err = _store()
    if err:
        return err
    updated = s.update_issue(
        issue_id, status=status, severity=severity, summary=summary, scope=scope,
        recommendations=recommendations, conclusions=conclusions,
        next_steps=next_steps, title=title,
    )
    if updated is None:
        return {"error": f"issue {issue_id!r} not found"}
    return {"issue": dataclasses.asdict(updated)}


def issue_add_event(issue_id: str, type: str, content: str) -> dict[str, Any]:
    """Append an entry to an Issue's activity timeline.

    Log what you DID and what you FOUND during the investigation so the
    operator can see Guardian's work. Call after each meaningful step.

    Args:
        issue_id: The Issue id.
        type: action / finding / note / conversation.
        content: Free text (markdown) — e.g. "Ran enrich_indicator on
            8.8.8.8 → DBotScore 1 (good)" or "Confirmed the attachment hash
            matches known Emotet."

    Returns: {"event": {...}} appended, or {"error": ...} if the issue
    doesn't exist.
    """
    s, err = _store()
    if err:
        return err
    event = s.add_event(issue_id, type or "note", content or "")
    if event is None:
        return {"error": f"issue {issue_id!r} not found"}
    return {"event": dataclasses.asdict(event)}


def issue_get(issue_id: str) -> dict[str, Any]:
    """Fetch one Issue with its activity timeline + its case (if grouped).

    Returns: {"issue": {...}, "events": [...], "case": {...}|null} or {"error": ...}.
    """
    s, err = _store()
    if err:
        return err
    issue = s.get_issue(issue_id)
    if issue is None:
        return {"error": f"issue {issue_id!r} not found"}
    case = s.get_case(issue.case_id) if issue.case_id else None
    return {
        "issue": dataclasses.asdict(issue),
        "events": [dataclasses.asdict(e) for e in s.list_events(issue_id)],
        "case": dataclasses.asdict(case) if case else None,
    }


def issues_list(status: str | None = None, case_id: str | None = None) -> dict[str, Any]:
    """List Issues, optionally filtered by status or case.

    Use to find existing Issues — e.g. to check whether a related Issue
    already exists before grouping into a Case.

    Args:
        status: filter to open / investigating / resolved / closed.
        case_id: filter to Issues grouped under a specific Case.

    Returns: {"issues": [...], "count": n}.
    """
    s, err = _store()
    if err:
        return err
    issues = s.list_issues(status=status, case_id=case_id)
    return {"issues": [dataclasses.asdict(i) for i in issues], "count": len(issues)}


def case_create(title: str, description: str | None = None) -> dict[str, Any]:
    """Create a Case to group related Issues.

    Use when you decide several Issues are similar/related (same campaign,
    same actor, same root cause). Then add Issues with case_add_issue.

    Args:
        title: Case title (e.g. "Phishing campaign — acme-login lookalike").
        description: Optional markdown description of the grouping rationale.

    Returns: {"case": {...}} (note its `id` for case_add_issue).
    """
    s, err = _store()
    if err:
        return err
    if not title or not str(title).strip():
        return {"error": "title is required"}
    case = s.create_case(title=str(title).strip(), description=description)
    return {"case": dataclasses.asdict(case)}


def case_add_issue(case_id: str, issue_id: str) -> dict[str, Any]:
    """Group an Issue under a Case (sets the issue's case).

    Args:
        case_id: The Case id (from case_create or cases_list).
        issue_id: The Issue id to add.

    Returns: {"issue": {...}} updated, or {"error": ...} if either is missing.
    """
    s, err = _store()
    if err:
        return err
    updated = s.add_issue_to_case(issue_id, case_id)
    if updated is None:
        return {"error": "issue or case not found"}
    return {"issue": dataclasses.asdict(updated)}


def cases_list() -> dict[str, Any]:
    """List all Cases with their Issue counts.

    Returns: {"cases": [{..., "issue_count": n}], "count": n}.
    """
    s, err = _store()
    if err:
        return err
    cases = s.list_cases()
    return {"cases": cases, "count": len(cases)}


def case_get(case_id: str) -> dict[str, Any]:
    """Fetch one Case with the Issues grouped under it.

    Returns: {"case": {...}, "issues": [...]} or {"error": ...}.
    """
    s, err = _store()
    if err:
        return err
    case = s.get_case(case_id)
    if case is None:
        return {"error": f"case {case_id!r} not found"}
    issues = s.list_issues(case_id=case_id)
    return {
        "case": dataclasses.asdict(case),
        "issues": [dataclasses.asdict(i) for i in issues],
    }
