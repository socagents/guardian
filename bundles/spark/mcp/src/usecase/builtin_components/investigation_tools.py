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
import json
import re
from typing import Any

from usecase.investigation_store import ISSUE_VERDICTS, investigation_store


def _store():
    s = investigation_store()
    if s is None:
        return None, {"error": "investigation store not initialized on this MCP runtime"}
    return s, None


def _clean_svg(svg: Any) -> tuple[str | None, dict | None]:
    """Validate + sanitize an agent-produced SVG for sandboxed render.

    Shared by the four diagram tools (issue/case × attack-chain/relations).
    Returns (cleaned_svg, None) on success or (None, {"error": ...}) on
    rejection. The UI renders the SVG sandboxed (an <img> data-URI never
    executes script), but we strip active content as defense-in-depth so we
    never STORE executable markup.
    """
    if not isinstance(svg, str):
        return None, {"error": "svg must be a string"}
    cleaned = svg.strip()
    low = cleaned.lower()
    if "<svg" not in low or "</svg>" not in low:
        return None, {"error": "svg must be SVG markup containing <svg> … </svg>"}
    if len(cleaned) > 256_000:
        return None, {"error": f"svg too large ({len(cleaned)} bytes; cap 256000)"}
    cleaned = re.sub(r"<script\b[^>]*>.*?</script>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    # <foreignObject> can embed arbitrary HTML — strip it (the skills forbid it).
    # The <img> data-URI render is already a no-script context, so this is
    # defense-in-depth, but it keeps the stored markup matching the contract.
    cleaned = re.sub(r"<foreignObject\b[^>]*>.*?</foreignObject>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"<foreignObject\b[^>]*/?>", "", cleaned, flags=re.IGNORECASE)
    # Inline on* handlers in all three attribute forms: "double", 'single', unquoted.
    cleaned = re.sub(r"\son\w+\s*=\s*\"[^\"]*\"", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\son\w+\s*=\s*'[^']*'", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\son\w+\s*=\s*[^\s>]+", "", cleaned, flags=re.IGNORECASE)
    return cleaned, None


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


def issue_set_verdict(
    issue_id: str,
    verdict: str,
    confidence: float | None = None,
    blast_radius: Any = None,
) -> dict[str, Any]:
    """Set an Issue's STRUCTURED verdict, confidence, and blast radius.

    The queryable counterpart to writing a `VERDICT:` line in the summary —
    call this when you conclude an investigation so the outcome is structured
    (dashboards, the judge, and reports read it).

    Args:
        issue_id: The Issue id.
        verdict: one of TRUE_POSITIVE / FALSE_POSITIVE / BENIGN /
            NEEDS_ESCALATION / INCONCLUSIVE.
        confidence: 0.0–1.0 — how sure you are.
        blast_radius: a dict (or JSON string) like
            {"hosts": [...], "accounts": [...], "related_issue_ids": [...],
             "summary": "…"} enumerating what the incident touched.

    Returns: {"issue": {...}} or {"error": ...}.
    """
    if verdict not in ISSUE_VERDICTS:
        return {"error": f"verdict must be one of {', '.join(ISSUE_VERDICTS)}"}
    if confidence is not None and not (0.0 <= float(confidence) <= 1.0):
        return {"error": "confidence must be between 0.0 and 1.0"}
    br = blast_radius
    if isinstance(br, (dict, list)):
        br = json.dumps(br)
    s, err = _store()
    if err:
        return err
    updated = s.update_issue(
        issue_id, verdict=verdict, verdict_confidence=confidence, blast_radius=br,
    )
    if updated is None:
        return {"error": f"issue {issue_id!r} not found"}
    return {"issue": dataclasses.asdict(updated)}


def issue_add_technique(
    issue_id: str,
    technique_id: str,
    tactic: str | None = None,
    manifestation: str | None = None,
    evidence_ref: str | None = None,
    confidence: float | None = None,
) -> dict[str, Any]:
    """Map a MITRE ATT&CK technique to an Issue (queryable, with evidence).

    Record each technique you confirmed/suspected so investigations are
    queryable by technique (incidents_by_technique) and the attack chain is
    structured — not just cited in prose.

    Args:
        issue_id: The Issue id.
        technique_id: ATT&CK id, e.g. "T1566.001".
        tactic: ATT&CK tactic, e.g. "initial-access".
        manifestation: how it showed up in THIS incident (markdown).
        evidence_ref: an indicator id / event id / war-room entry id backing it.
        confidence: 0.0–1.0 (confirmed vs suspected).

    Re-adding the same technique on an issue updates it. Returns
    {"technique": {...}} or {"error": ...}.
    """
    if not technique_id:
        return {"error": "technique_id is required"}
    s, err = _store()
    if err:
        return err
    if s.get_issue(issue_id) is None:
        return {"error": f"issue {issue_id!r} not found"}
    tm = s.add_technique_mapping(
        issue_id, technique_id, tactic=tactic, manifestation=manifestation,
        evidence_ref=evidence_ref, confidence=confidence,
    )
    return {"technique": dataclasses.asdict(tm)}


def incidents_by_technique(technique_id: str) -> dict[str, Any]:
    """List the Issues mapped to a given ATT&CK technique (the inverse query).

    Args:
        technique_id: ATT&CK id, e.g. "T1566.001".

    Returns: {"issues": [...], "count": N}.
    """
    s, err = _store()
    if err:
        return err
    issues = s.list_issues_by_technique(technique_id)
    return {"issues": [dataclasses.asdict(i) for i in issues], "count": len(issues)}


def generate_investigation_report(issue_id: str) -> dict[str, Any]:
    """Assemble a structured closure report for an Issue and store it.

    Pulls the Issue's fields + verdict/confidence/blast-radius + ATT&CK
    technique mappings + indicators + timeline into a single human-readable
    markdown report (and a machine-readable JSON mirror), and persists the
    markdown on the Issue's `report` field. Pure read+assemble — no external
    calls. Call at resolve time (or regenerate any time).

    Returns: {"markdown": "...", "json": {...}} or {"error": ...}.
    """
    s, err = _store()
    if err:
        return err
    issue = s.get_issue(issue_id)
    if issue is None:
        return {"error": f"issue {issue_id!r} not found"}
    techniques = [dataclasses.asdict(t) for t in s.list_technique_mappings(issue_id)]
    indicators = [dataclasses.asdict(i) for i in s.list_indicators_for_issue(issue_id)]
    events = [dataclasses.asdict(e) for e in s.list_events(issue_id)]
    try:
        blast = json.loads(issue.blast_radius) if issue.blast_radius else None
    except (ValueError, TypeError):
        blast = {"raw": issue.blast_radius}

    conf = f" (confidence {issue.verdict_confidence:.0%})" if issue.verdict_confidence is not None else ""
    lines: list[str] = [
        f"# Investigation Report — {issue.title}",
        "",
        f"**Verdict:** {issue.verdict or '(none)'}{conf}",
        f"**Severity:** {issue.severity} | **Kind:** {issue.kind} | **Status:** {issue.status}",
    ]
    if issue.source_ref:
        lines.append(f"**Source incident:** {issue.source_ref}")
    for label, val in (
        ("Summary", issue.summary), ("Scope", issue.scope),
        ("Conclusions", issue.conclusions), ("Recommendations", issue.recommendations),
        ("Next steps", issue.next_steps),
    ):
        if val:
            lines += ["", f"## {label}", val]
    if blast:
        lines += ["", "## Blast radius"]
        if isinstance(blast, dict):
            for k in ("hosts", "accounts", "related_issue_ids"):
                v = blast.get(k)
                if v:
                    lines.append(f"- **{k}** ({len(v)}): {', '.join(map(str, v))}")
            if blast.get("summary"):
                lines.append(blast["summary"])
        else:
            lines.append(str(blast))
    if techniques:
        lines += ["", "## ATT&CK techniques"]
        for t in techniques:
            c = f" — confidence {t['confidence']:.0%}" if t.get("confidence") is not None else ""
            tac = f" [{t['tactic']}]" if t.get("tactic") else ""
            man = f": {t['manifestation']}" if t.get("manifestation") else ""
            lines.append(f"- **{t['technique_id']}**{tac}{c}{man}")
    if indicators:
        lines += ["", "## Indicators"]
        for i in indicators:
            score = f" (DBotScore {i['dbot_score']})" if i.get("dbot_score") is not None else ""
            lines.append(f"- `{i['value']}` ({i['type']}){score}")
    if events:
        lines += ["", "## Timeline"]
        for e in events:
            lines.append(f"- {e['ts']} | *{e['type']}* — {e['content']}")
    markdown = "\n".join(lines)

    s.update_issue(issue_id, report=markdown)
    report_json = {
        "issue_id": issue.id, "title": issue.title, "verdict": issue.verdict,
        "verdict_confidence": issue.verdict_confidence, "severity": issue.severity,
        "kind": issue.kind, "status": issue.status, "source_ref": issue.source_ref,
        "summary": issue.summary, "scope": issue.scope, "conclusions": issue.conclusions,
        "recommendations": issue.recommendations, "next_steps": issue.next_steps,
        "blast_radius": blast, "techniques": techniques, "indicators": indicators,
        "timeline": events,
    }
    return {"markdown": markdown, "json": report_json}


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


def issue_set_attack_chain(issue_id: str, svg: str) -> dict[str, Any]:
    """Attach an attack-chain (causality) diagram to an Issue as an SVG.

    Call this when you RESOLVE an investigation (after recording the verdict)
    to add a visual attack chain — the ordered path of the attack across
    entities (e.g. attacker → entry → host/account → action → impact). It is
    rendered on the Issue's "Attack chain" tab in the Investigation UI.

    Produce the SVG per the `svg_attack_chain` skill: a SELF-CONTAINED SVG —
    inline styles/attributes only, NO <script>, NO external fonts / images /
    links — with a viewBox and left-to-right nodes connected by labelled
    arrows. The UI renders it sandboxed (as an <img> data-URI, so scripts can
    never execute); keeping it self-contained ensures it displays correctly.

    Args:
        issue_id: The Issue id (from issue_create / issues_list).
        svg: The full SVG markup, starting with "<svg" and ending "</svg>".

    Returns: {"ok": true, "issue_id": ..., "bytes": n} or {"error": ...}.
    """
    s, err = _store()
    if err:
        return err
    cleaned, verr = _clean_svg(svg)
    if verr:
        return verr
    if not s.set_attack_chain(issue_id, cleaned):
        return {"error": f"issue {issue_id!r} not found"}
    return {"ok": True, "issue_id": issue_id, "bytes": len(cleaned)}


def issue_set_relation_graph(issue_id: str, svg: str) -> dict[str, Any]:
    """Attach a relations-canvas diagram to an Issue as an SVG.

    Record a STIX-style relations graph for the issue — its indicators and the
    entities they relate to (other IoCs, ATT&CK techniques, malware, campaigns,
    threat-actors), edges labelled by the STIX relationship verb. Rendered on
    the Issue's "Relations" tab.

    Produce the SVG per the `svg_relation_graph` skill: SELF-CONTAINED (inline
    styles + a single <style> block only, NO <script>, NO external refs,
    XML-escaped labels), layered by STIX node type with verb-labelled edges.
    Rendered sandboxed as an <img> data-URI.

    Args:
        issue_id: The Issue id.
        svg: The full SVG markup, starting "<svg" and ending "</svg>".

    Returns: {"ok": true, "issue_id": ..., "bytes": n} or {"error": ...}.
    """
    s, err = _store()
    if err:
        return err
    cleaned, verr = _clean_svg(svg)
    if verr:
        return verr
    if not s.set_relations_canvas(issue_id, cleaned):
        return {"error": f"issue {issue_id!r} not found"}
    return {"ok": True, "issue_id": issue_id, "bytes": len(cleaned)}


def case_set_attack_chain(case_id: str, svg: str) -> dict[str, Any]:
    """Attach a CASE-level attack-chain (campaign causality) diagram as an SVG.

    Like issue_set_attack_chain, but for a Case — the campaign-level view that
    synthesizes the attack across ALL the issues grouped under the case (shared
    actor / infrastructure / kill-chain). Call this when a multi-issue case is
    resolved, after the individual issues' chains. Read the case + its issues
    first with case_get(case_id). Rendered on the Case's "Attack chain" tab.

    Produce the SVG per the `svg_attack_chain` skill (it handles the case =
    multiple issues input): SELF-CONTAINED, NO <script> / external refs,
    rendered sandboxed as an <img> data-URI.

    Args:
        case_id: The Case id (from case_create / cases_list / case_get).
        svg: The full SVG markup, starting "<svg" and ending "</svg>".

    Returns: {"ok": true, "case_id": ..., "bytes": n} or {"error": ...}.
    """
    s, err = _store()
    if err:
        return err
    cleaned, verr = _clean_svg(svg)
    if verr:
        return verr
    if not s.set_case_attack_chain(case_id, cleaned):
        return {"error": f"case {case_id!r} not found"}
    return {"ok": True, "case_id": case_id, "bytes": len(cleaned)}


def case_set_relation_graph(case_id: str, svg: str) -> dict[str, Any]:
    """Attach a CASE-level relations-canvas (STIX graph) diagram as an SVG.

    Like issue_set_relation_graph, but for a Case — the campaign-level STIX
    graph spanning the indicators of ALL issues grouped under the case, showing
    the shared infrastructure / techniques / actors that tie the case together.
    Read the case + its issues first with case_get(case_id), then the issues'
    indicators + relationships. Rendered on the Case's "Relations" tab.

    Produce the SVG per the `svg_relation_graph` skill (it handles the case =
    multiple issues input): SELF-CONTAINED, NO <script> / external refs,
    rendered sandboxed as an <img> data-URI.

    Args:
        case_id: The Case id.
        svg: The full SVG markup, starting "<svg" and ending "</svg>".

    Returns: {"ok": true, "case_id": ..., "bytes": n} or {"error": ...}.
    """
    s, err = _store()
    if err:
        return err
    cleaned, verr = _clean_svg(svg)
    if verr:
        return verr
    if not s.set_case_relations_canvas(case_id, cleaned):
        return {"error": f"case {case_id!r} not found"}
    return {"ok": True, "case_id": case_id, "bytes": len(cleaned)}


def issues_list(
    status: str | None = None,
    case_id: str | None = None,
    source_ref_not_null: bool = False,
    order: str = "desc",
) -> dict[str, Any]:
    """List Issues, optionally filtered by status or case.

    Use to find existing Issues — e.g. to check whether a related Issue
    already exists before grouping into a Case.

    Args:
        status: filter to open / investigating / resolved / closed.
        case_id: filter to Issues grouped under a specific Case.
        source_ref_not_null: when true, return ONLY Issues that track an
            XSOAR incident (non-empty source_ref) — i.e. skip manual/
            standalone Issues with nothing to fetch. The autonomous
            investigation loop sets this so a sourceless Issue can never
            jam its "oldest open" pick.
        order: "asc" = oldest-first by creation time (use with status='open'
            to deterministically take the OLDEST awaiting Issue); "desc"
            (default) = newest-first.

    Returns: {"issues": [...], "count": n}.

    Example (the loop's pick): issues_list(status="open",
    source_ref_not_null=True, order="asc") → take issues[0].
    """
    s, err = _store()
    if err:
        return err
    issues = s.list_issues(
        status=status,
        case_id=case_id,
        source_ref_not_null=bool(source_ref_not_null),
        order=order,
    )
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
