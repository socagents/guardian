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
import logging
import os
import re
import urllib.request
from typing import Any

from usecase.investigation_store import (
    CASE_RELATIONSHIP_TYPES,
    ISSUE_VERDICTS,
    investigation_store,
)
from usecase.tool_dispatcher import get_tool_dispatcher

logger = logging.getLogger("Guardian MCP")

_SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


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
    # #INV-F2 — the Activity tab is driven by the issue_events table only;
    # a structured verdict write left zero timeline trace. Append one so the
    # verdict change shows up in the issue's activity history.
    conf_txt = (
        f" (confidence {float(confidence):.2f})" if confidence is not None else ""
    )
    s.add_event(issue_id, "verdict_set", f"Verdict set to {verdict}{conf_txt}")
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
    # #INV-F2 — mirror the verdict change into the issue timeline so the
    # Activity tab reflects technique mappings (issue_events is the sole
    # source for that tab).
    tactic_txt = f" [{tactic}]" if tactic else ""
    s.add_event(
        issue_id, "technique_mapped",
        f"ATT&CK technique {technique_id}{tactic_txt} mapped",
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


REPORT_TEMPLATES = ("technical", "executive", "ioc-list")


def _blast_lines(blast) -> list[str]:
    out: list[str] = []
    if not blast:
        return out
    out += ["", "## Blast radius"]
    if isinstance(blast, dict):
        for k in ("hosts", "accounts", "related_issue_ids"):
            v = blast.get(k)
            if v:
                out.append(f"- **{k}** ({len(v)}): {', '.join(map(str, v))}")
        if blast.get("summary"):
            out.append(blast["summary"])
    else:
        out.append(str(blast))
    return out


def generate_investigation_report(issue_id: str, template: str = "technical") -> dict[str, Any]:
    """Assemble a closure report for an Issue from its structured record and
    persist it on the Issue's `report` field. Pure read+assemble — no external
    calls. Templates (v0.2.48):

    - **technical** (default) — the full report: verdict, summary/scope/
      conclusions/recommendations/next-steps, blast radius, ATT&CK techniques,
      indicators, and the activity timeline.
    - **executive** — a brief: verdict + one-paragraph summary + blast radius +
      recommendations (no timeline, no per-indicator dump).
    - **ioc-list** — machine-pasteable: just the indicators + ATT&CK technique ids.

    Returns: {"markdown": "...", "json": {...}} or {"error": ...}.
    """
    if template not in REPORT_TEMPLATES:
        return {"error": f"template must be one of {', '.join(REPORT_TEMPLATES)}"}
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

    if template == "ioc-list":
        lines = [f"# IOC list — {issue.title}", "", f"Verdict: {issue.verdict or '(none)'}"]
        if indicators:
            lines += ["", "## Indicators"]
            for i in indicators:
                score = f" dbot={i['dbot_score']}" if i.get("dbot_score") is not None else ""
                lines.append(f"- {i['value']}\t{i['type']}{score}")
        if techniques:
            lines += ["", "## ATT&CK techniques", ", ".join(t["technique_id"] for t in techniques)]
    elif template == "executive":
        lines = [
            f"# Executive summary — {issue.title}", "",
            f"**Verdict:** {issue.verdict or '(none)'}{conf}",
            f"**Severity:** {issue.severity} | **Kind:** {issue.kind}",
        ]
        if issue.source_ref:
            lines.append(f"**Source incident:** {issue.source_ref}")
        for label, val in (("Summary", issue.summary), ("Recommendations", issue.recommendations)):
            if val:
                lines += ["", f"## {label}", val]
        lines += _blast_lines(blast)
        if techniques:
            lines += ["", "## ATT&CK techniques", ", ".join(t["technique_id"] for t in techniques)]
    else:  # technical
        lines = [
            f"# Investigation Report — {issue.title}", "",
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
        lines += _blast_lines(blast)
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
        "timeline": events, "template": template,
    }
    return {"markdown": markdown, "json": report_json}


def generate_campaign_report(case_id: str) -> dict[str, Any]:
    """Assemble a campaign-level report for a Case from its rollup (C) + member
    issues — campaign summary, threat actor, severity rollup, the ATT&CK technique
    union, shared infrastructure, and the member issues with their verdicts.
    Pure read+assemble. Returns {"markdown": ..., "json": ...} or {"error": ...}.
    """
    s, err = _store()
    if err:
        return err
    case = s.get_case(case_id)
    if case is None:
        return {"error": f"case {case_id!r} not found"}
    members = s.list_issues(case_id=case_id)
    try:
        techniques = json.loads(case.techniques) if case.techniques else []
    except (ValueError, TypeError):
        techniques = []
    try:
        infra = json.loads(case.infrastructure) if case.infrastructure else {}
    except (ValueError, TypeError):
        infra = {}
    shared = infra.get("shared_indicators", []) if isinstance(infra, dict) else []

    lines = [f"# Campaign Report — {case.title}", ""]
    if case.threat_actor:
        lines.append(f"**Threat actor:** {case.threat_actor}")
    if case.severity_rollup:
        lines.append(f"**Severity:** {case.severity_rollup}")
    lines.append(f"**Member issues:** {len(members)}")
    if case.campaign_summary:
        lines += ["", "## Summary", case.campaign_summary]
    if techniques:
        lines += ["", "## ATT&CK techniques (union)", ", ".join(techniques)]
    if shared:
        lines += ["", "## Shared infrastructure", ", ".join(f"`{v}`" for v in shared)]
    if members:
        lines += ["", "## Member issues"]
        for m in members:
            v = f" — {m.verdict}" if m.verdict else ""
            lines.append(f"- **{m.title}** ({m.severity}){v}")
    related = s.list_case_relationships(case_id)
    if related:
        lines += ["", "## Related cases"]
        for r in related:
            other_id = r.target_case_id if r.source_case_id == case_id else r.source_case_id
            oc = s.get_case(other_id)
            lines.append(f"- {r.relationship_type}: {oc.title if oc else other_id}")
    markdown = "\n".join(lines)
    return {"markdown": markdown, "json": {
        "case_id": case.id, "title": case.title, "threat_actor": case.threat_actor,
        "severity_rollup": case.severity_rollup, "campaign_summary": case.campaign_summary,
        "techniques": techniques, "shared_infrastructure": shared,
        "members": [{"id": m.id, "title": m.title, "severity": m.severity, "verdict": m.verdict} for m in members],
    }}


# ─── Webhook handoff (stage D, v0.2.48) — opt-in + approval-gated ────

def _webhook_post(url: str, headers: dict, body: bytes) -> tuple[int, str]:
    """The single outbound HTTP call (factored so tests mock it)."""
    req = urllib.request.Request(url, data=body, method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=15) as r:  # noqa: S310 (url is operator config)
        return r.status, r.read().decode("utf-8", "replace")[:500]


def _webhook_payload(s, issue_id: str | None, case_id: str | None):
    """Assemble the outbound payload for an issue or a case, or (None, error)."""
    if bool(issue_id) == bool(case_id):
        return None, {"error": "pass exactly one of issue_id or case_id"}
    if issue_id:
        issue = s.get_issue(issue_id)
        if issue is None:
            return None, {"error": f"issue {issue_id!r} not found"}
        report = generate_investigation_report(issue_id, template="executive")
        stix = export_issue_stix(issue_id)
        iocs = [{"value": i.value, "type": i.type, "dbot_score": i.dbot_score}
                for i in s.list_indicators_for_issue(issue_id)]
        return {
            "source": "guardian", "kind": "issue", "issue_id": issue.id,
            "title": issue.title, "verdict": issue.verdict,
            "verdict_confidence": issue.verdict_confidence, "severity": issue.severity,
            "source_ref": issue.source_ref, "report": report.get("markdown"),
            "iocs": iocs, "stix": stix.get("bundle"),
        }, None
    case = s.get_case(case_id)
    if case is None:
        return None, {"error": f"case {case_id!r} not found"}
    report = generate_campaign_report(case_id)
    stix = export_case_stix(case_id)
    return {
        "source": "guardian", "kind": "case", "case_id": case.id, "title": case.title,
        "threat_actor": case.threat_actor, "severity_rollup": case.severity_rollup,
        "report": report.get("markdown"), "stix": stix.get("bundle"),
    }, None


def webhook_preview(issue_id: str | None = None, case_id: str | None = None) -> dict[str, Any]:
    """Show EXACTLY what `export_to_webhook` would send (and to which configured
    target), without sending anything. Read-only — NOT approval-gated. Use this
    to surface the outbound to the operator before they approve the actual send.

    Returns {"target": <url or None>, "would_send": {...}} or {"error": ...}.
    """
    s, err = _store()
    if err:
        return err
    payload, perr = _webhook_payload(s, issue_id, case_id)
    if perr:
        return perr
    target = os.environ.get("GUARDIAN_WEBHOOK_URL", "").strip() or None
    return {"target": target, "would_send": payload}


async def export_to_webhook(issue_id: str | None = None, case_id: str | None = None) -> dict[str, Any]:
    """Send the structured verdict + report + IOCs + STIX to the operator's
    configured outbound webhook (e.g. a SOAR / ticketing / Slack ingress).

    SAFETY: this SENDS DATA TO AN EXTERNAL SYSTEM. It is **opt-in** (off unless
    the operator sets `GUARDIAN_WEBHOOK_URL`), the target comes ONLY from that
    operator config (never a tool arg or observed content), and it is
    **approval-gated** (listed in manifest.approvals.humanRequired). Call
    `webhook_preview` first to show what will be sent.

    #76: export_to_webhook is a built-in, so it never passed through the
    connector wrapper's approval gate even though it's listed in
    humanRequired — the gate silently never ran. It now self-gates via
    `gate_and_execute` (the same path the other self-mod built-ins use),
    so external data egress actually requires operator approval (or an
    explicit bypass session/job). `webhook_preview` stays read-only/ungated.

    Returns {"ok": bool, "status": int, ...} or {"error": ...}.
    """
    s, err = _store()
    if err:
        return err
    payload, perr = _webhook_payload(s, issue_id, case_id)
    if perr:
        return perr
    url = os.environ.get("GUARDIAN_WEBHOOK_URL", "").strip()
    if not url:
        return {"error": "no webhook configured — the operator must set GUARDIAN_WEBHOOK_URL "
                         "(this handoff is opt-in and off by default)"}
    headers = {"Content-Type": "application/json", "User-Agent": "Guardian"}
    token = os.environ.get("GUARDIAN_WEBHOOK_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    def _send() -> dict[str, Any]:
        try:
            status, _resp = _webhook_post(url, headers, json.dumps(payload).encode())
        except Exception as e:
            return {"error": f"webhook POST to {url} failed: {e}"}
        return {"ok": 200 <= status < 300, "status": status, "url": url, "kind": payload["kind"]}

    from usecase.builtin_components._approval_gate import gate_and_execute
    try:
        return await gate_and_execute(
            tool_name="export_to_webhook",
            args={"issue_id": issue_id, "case_id": case_id, "kind": payload["kind"]},
            risk_tier="destructive",
            executor=_send,
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "tool": "export_to_webhook"}


def _verdict_warroom_markdown(s, issue) -> str:
    """Compact war-room entry assembled from an Issue's STRUCTURED record —
    verdict + confidence + severity/kind, conclusions, blast radius, ATT&CK
    techniques, recommendations. Deliberately omits the full timeline (the
    XSOAR war room already holds the case's own activity); this is Guardian's
    disposition, posted back so it lives where the SOC works the case.
    """
    techniques = [dataclasses.asdict(t) for t in s.list_technique_mappings(issue.id)]
    try:
        blast = json.loads(issue.blast_radius) if issue.blast_radius else None
    except (ValueError, TypeError):
        blast = {"raw": issue.blast_radius}

    conf = f" (confidence {issue.verdict_confidence:.0%})" if issue.verdict_confidence is not None else ""
    lines = [
        "## Guardian investigation verdict",
        "",
        f"**Verdict:** {issue.verdict}{conf}",
        f"**Severity:** {issue.severity} | **Kind:** {issue.kind}",
    ]
    if issue.conclusions:
        lines += ["", "### Conclusions", issue.conclusions]
    if isinstance(blast, dict) and blast:
        lines += ["", "### Blast radius"]
        for k in ("hosts", "accounts", "related_issue_ids"):
            v = blast.get(k)
            if v:
                lines.append(f"- **{k}** ({len(v)}): {', '.join(map(str, v))}")
        if blast.get("summary"):
            lines.append(blast["summary"])
    if techniques:
        lines += ["", "### ATT&CK techniques"]
        for t in techniques:
            tac = f" [{t['tactic']}]" if t.get("tactic") else ""
            man = f": {t['manifestation']}" if t.get("manifestation") else ""
            lines.append(f"- **{t['technique_id']}**{tac}{man}")
    if issue.recommendations:
        lines += ["", "### Recommendations", issue.recommendations]
    lines += ["", f"— Recorded by Guardian (issue {issue.id})"]
    return "\n".join(lines)


async def push_verdict_to_xsoar(issue_id: str, instance: str | None = None) -> dict[str, Any]:
    """Write a resolved Issue's structured verdict back to the upstream XSOAR
    incident's war room as evidence (Stage B, v0.2.46).

    Closes the loop so the disposition Guardian reached lives where the SOC
    works the case. Reads the Issue's structured record, assembles a compact
    war-room entry, and writes it via the XSOAR connector's `xsoar_add_entry`
    + `xsoar_save_evidence` THROUGH the tool dispatcher — so the per-instance
    contextvar, the approval gate, and audit logging all apply (this is the one
    investigation tool that reaches a connector, and it does so on the governed
    path, never the raw proxy).

    Guards (no-op with error, connector untouched): the Issue must track an
    XSOAR incident (`source_ref` non-null) and must have a structured `verdict`
    set. For a tenant with 2+ enabled XSOAR instances, pass `instance`.

    Returns {"ok": True, "incident_id", "entry_id", "evidence"} or {"error": ...}.
    """
    s, err = _store()
    if err:
        return err
    issue = s.get_issue(issue_id)
    if issue is None:
        return {"error": f"issue {issue_id!r} not found"}
    if not issue.source_ref:
        return {"error": "issue has no source_ref — it does not track an XSOAR incident; nothing to push"}
    if not issue.verdict:
        return {"error": "issue has no structured verdict yet — set it with issue_set_verdict before pushing"}

    dispatcher = get_tool_dispatcher()
    if dispatcher is None:
        return {"error": "tool dispatcher not available on this MCP runtime"}

    content = _verdict_warroom_markdown(s, issue)
    inst = {} if instance is None else {"instance": instance}

    try:
        entry = await dispatcher("xsoar_add_entry", {"incident_id": issue.source_ref, "content": content, **inst})
    except Exception as e:  # KeyError (no/unknown instance), ConnectorProxyError, timeouts, …
        return {"error": f"could not write verdict to XSOAR incident {issue.source_ref}: {e}"}
    if not isinstance(entry, dict) or not entry.get("ok"):
        return {"error": f"xsoar_add_entry did not succeed for incident {issue.source_ref}", "raw": entry}

    # #INV-F3 — track each sub-step so a partial failure (entry landed but
    # evidence/timeline failed) is surfaced as ok:False + partial:True with a
    # per-step breakdown, instead of silently returning ok:True. The war-room
    # entry IS the verdict landing in XSOAR; the evidence tag + timeline are
    # secondary, so we report them honestly rather than swallow their failure.
    entry_id = entry.get("entry_id")
    steps: dict[str, bool] = {"add_entry": True}
    evidence = None
    if entry_id:
        try:
            evidence = await dispatcher(
                "xsoar_save_evidence",
                {"incident_id": issue.source_ref, "entry_id": entry_id,
                 "description": f"Guardian verdict: {issue.verdict}", **inst},
            )
        except Exception as e:
            evidence = {"ok": False, "error": str(e)}
        steps["save_evidence"] = bool(isinstance(evidence, dict) and evidence.get("ok"))

    # Record the pushback on the Issue timeline (the war-room write already
    # landed; a timeline-log failure is reported in steps, not swallowed).
    try:
        issue_add_event(
            issue_id, type="pushback",
            content=(f"Pushed structured verdict ({issue.verdict}) to XSOAR incident "
                     f"{issue.source_ref} as war-room evidence (entry {entry_id})."),
        )
        steps["timeline_event"] = True
    except Exception as e:
        logger.warning(
            "push_verdict_to_xsoar: timeline event failed for issue %s: %s",
            issue_id, e,
        )
        steps["timeline_event"] = False

    all_ok = all(steps.values())
    return {
        "ok": all_ok,
        # partial = the verdict reached XSOAR (add_entry ok) but a secondary
        # step failed; the caller should surface "landed, with caveats".
        "partial": (not all_ok) and steps.get("add_entry", False),
        "steps": steps,
        "issue_id": issue_id,
        "incident_id": issue.source_ref,
        "entry_id": entry_id,
        "evidence": evidence,
    }


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


# ─── Campaign / cross-incident analytics (stage C, v0.2.47) ──────────

def case_rollup(case_id: str, threat_actor: str | None = None,
                campaign_summary: str | None = None) -> dict[str, Any]:
    """Synthesize a campaign rollup for a Case from its member issues and
    persist it on the Case (campaign_summary, threat_actor, infrastructure,
    techniques, severity_rollup). Computes: the ATT&CK technique union, the
    shared infrastructure (indicator values seen on >=2 members), the max
    severity, and the verdict mix. `threat_actor` / `campaign_summary` are the
    two non-derivable fields — pass them to set, else a summary is generated.

    Returns {"rollup": {...}} or {"error": ...}.
    """
    s, err = _store()
    if err:
        return err
    case = s.get_case(case_id)
    if case is None:
        return {"error": f"case {case_id!r} not found"}
    members = s.list_issues(case_id=case_id)

    techniques: set[str] = set()
    value_member_counts: dict[str, int] = {}
    sev = None
    for m in members:
        for t in s.list_technique_mappings(m.id):
            techniques.add(t.technique_id)
        for v in {i.value for i in s.list_indicators_for_issue(m.id)}:
            value_member_counts[v] = value_member_counts.get(v, 0) + 1
        if m.severity and (sev is None or _SEVERITY_ORDER.get(m.severity, 0) > _SEVERITY_ORDER.get(sev, 0)):
            sev = m.severity
    techniques_sorted = sorted(techniques)
    shared = sorted(v for v, n in value_member_counts.items() if n >= 2)
    infrastructure = {"shared_indicators": shared}
    verdict_mix: dict[str, int] = {}
    for m in members:
        if m.verdict:
            verdict_mix[m.verdict] = verdict_mix.get(m.verdict, 0) + 1

    if not campaign_summary:
        parts = [f"{len(members)} issue(s)"]
        if verdict_mix:
            parts.append("verdicts " + ", ".join(f"{k}×{v}" for k, v in verdict_mix.items()))
        if techniques_sorted:
            parts.append(f"{len(techniques_sorted)} ATT&CK techniques")
        if shared:
            parts.append(f"{len(shared)} shared indicator(s)")
        if sev:
            parts.append(f"max severity {sev}")
        campaign_summary = "; ".join(parts)

    update = {
        "campaign_summary": campaign_summary,
        "techniques": json.dumps(techniques_sorted),
        "infrastructure": json.dumps(infrastructure),
    }
    if sev:
        update["severity_rollup"] = sev
    if threat_actor:
        update["threat_actor"] = threat_actor
    s.update_case(case_id, **update)

    return {"rollup": {
        "case_id": case_id, "member_count": len(members),
        "techniques": techniques_sorted, "infrastructure": infrastructure,
        "severity_rollup": sev, "verdict_mix": verdict_mix,
        "campaign_summary": campaign_summary,
        "threat_actor": threat_actor or s.get_case(case_id).threat_actor,
    }}


def issue_match_playbook(issue_id: str, playbook_doc_id: str,
                         score: float | None = None,
                         matched_criteria: str | None = None) -> dict[str, Any]:
    """Record (upsert) the KB playbook an investigation was routed through, so
    cases can be typed by playbook + queried. Returns {"match": {...}}."""
    s, err = _store()
    if err:
        return err
    if not playbook_doc_id:
        return {"error": "playbook_doc_id is required"}
    if s.get_issue(issue_id) is None:
        return {"error": f"issue {issue_id!r} not found"}
    if score is not None:
        try:
            score = float(score)
        except (TypeError, ValueError):
            return {"error": "score must be a number"}
    m = s.add_playbook_match(issue_id, playbook_doc_id, score=score, matched_criteria=matched_criteria)
    return {"match": dataclasses.asdict(m)}


def case_relate(source_case_id: str, target_case_id: str, relationship_type: str,
                note: str | None = None) -> dict[str, Any]:
    """Record a typed edge between two cases (sibling / escalation / reopen /
    same-campaign). Returns {"relationship": {...}} or {"error": ...}."""
    s, err = _store()
    if err:
        return err
    if relationship_type not in CASE_RELATIONSHIP_TYPES:
        return {"error": f"relationship_type must be one of {', '.join(CASE_RELATIONSHIP_TYPES)}"}
    if source_case_id == target_case_id:
        return {"error": "cannot relate a case to itself"}
    if s.get_case(source_case_id) is None:
        return {"error": f"case {source_case_id!r} not found"}
    if s.get_case(target_case_id) is None:
        return {"error": f"case {target_case_id!r} not found"}
    r = s.add_case_relationship(source_case_id, target_case_id, relationship_type, note=note)
    # #INV-F11 — a relate has no case-level activity timeline (there's no
    # case_events table; that's out of scope). Leave a forensic audit row so
    # "case X linked to case Y as same-campaign" is traceable in
    # /observability/events even though it isn't an issue-timeline entry.
    try:
        from usecase.audit_log import record_event
        record_event(
            "case_related",
            target=f"case:{source_case_id}",
            status="success",
            metadata={
                "source_case_id": source_case_id,
                "target_case_id": target_case_id,
                "relationship_type": relationship_type,
            },
        )
    except Exception:  # noqa: BLE001 — audit is best-effort
        pass
    return {"relationship": dataclasses.asdict(r)}


def case_related(case_id: str) -> dict[str, Any]:
    """List the cases related to this one (edges in either direction), each with
    the other case's title/status. Returns {"related": [...], "count": N}."""
    s, err = _store()
    if err:
        return err
    if s.get_case(case_id) is None:
        return {"error": f"case {case_id!r} not found"}
    out = []
    for r in s.list_case_relationships(case_id):
        outgoing = r.source_case_id == case_id
        other_id = r.target_case_id if outgoing else r.source_case_id
        oc = s.get_case(other_id)
        out.append({
            "relationship_type": r.relationship_type, "note": r.note,
            "direction": "outgoing" if outgoing else "incoming",
            "other_case": {"id": other_id, "title": oc.title if oc else None,
                           "status": oc.status if oc else None},
        })
    return {"related": out, "count": len(out)}


def infer_relationships(issue_id: str | None = None,
                        indicator_id: str | None = None) -> dict[str, Any]:
    """SUGGEST (never write) missing graph edges + sibling issues. Pass an
    indicator_id for transitive-edge suggestions over the STIX relationship
    graph (A resolves-to V, indicator(V) communicates-with C ⇒ suggest A→C), or
    an issue_id for sibling issues that share an ATT&CK technique or an IOC.
    The agent reviews + confirms; this tool makes no changes.

    Returns {"suggestions": [...], "count": N} or {"error": ...}.
    """
    s, err = _store()
    if err:
        return err
    if not issue_id and not indicator_id:
        return {"error": "pass issue_id or indicator_id"}
    suggestions: list[dict] = []

    if indicator_id:
        ind = s.get_indicator(indicator_id)
        if ind is None:
            return {"error": f"indicator {indicator_id!r} not found"}
        by_value: dict[str, str] = {}
        for d in s.list_indicators():
            by_value.setdefault(d["value"], d["id"])
        direct = s.list_relationships(source_id=indicator_id)
        direct_targets = {r["target_value"] for r in direct}
        for r in direct:
            mid = by_value.get(r["target_value"])
            if not mid or mid == indicator_id:
                continue
            for r2 in s.list_relationships(source_id=mid):
                tv2 = r2["target_value"]
                if tv2 == ind["value"] or tv2 in direct_targets:
                    continue
                suggestions.append({
                    "kind": "transitive-edge", "source_indicator_id": indicator_id,
                    "via": r["target_value"], "target_value": tv2,
                    "target_type": r2["target_type"],
                    "rationale": (f"{ind['value']} {r['relationship_type']} {r['target_value']}; "
                                  f"{r['target_value']} {r2['relationship_type']} {tv2}"),
                    "confidence": 0.6,
                })

    if issue_id:
        if s.get_issue(issue_id) is None:
            return {"error": f"issue {issue_id!r} not found"}
        sib_tech: dict[str, set] = {}
        for t in s.list_technique_mappings(issue_id):
            for other in s.list_issues_by_technique(t.technique_id):
                if other.id != issue_id:
                    sib_tech.setdefault(other.id, set()).add(t.technique_id)
        for oid, shared_t in sib_tech.items():
            suggestions.append({
                "kind": "technique-sibling", "issue_id": oid,
                "shared_techniques": sorted(shared_t),
                "rationale": f"shares {len(shared_t)} ATT&CK technique(s): {', '.join(sorted(shared_t))}",
                "confidence": min(0.4 + 0.2 * len(shared_t), 0.95),
            })
        my_vals = {i.value for i in s.list_indicators_for_issue(issue_id)}
        if my_vals:
            for other in s.list_issues():
                if other.id == issue_id:
                    continue
                shared_v = my_vals & {i.value for i in s.list_indicators_for_issue(other.id)}
                if shared_v:
                    suggestions.append({
                        "kind": "ioc-sibling", "issue_id": other.id,
                        "shared_indicators": sorted(shared_v),
                        "rationale": f"shares {len(shared_v)} indicator(s): {', '.join(sorted(shared_v))}",
                        "confidence": min(0.5 + 0.15 * len(shared_v), 0.95),
                    })

    suggestions.sort(key=lambda x: x.get("confidence", 0), reverse=True)
    return {"suggestions": suggestions, "count": len(suggestions)}


# ─── Export / interop (stage D, v0.2.48) ─────────────────────────────

def export_issue_stix(issue_id: str) -> dict[str, Any]:
    """Assemble a STIX 2.1 bundle from an Issue's structured record — an
    `incident` + `attack-pattern`s (technique mappings, with MITRE refs) +
    `indicator`s + `relationship`s, wrapped in a `report`. Read/assemble only
    (no external calls); deterministic ids so re-export is identical.

    Returns {"bundle": {...}} or {"error": ...}.
    """
    from usecase.builtin_components import _stix  # local import keeps load lean
    s, err = _store()
    if err:
        return err
    issue = s.get_issue(issue_id)
    if issue is None:
        return {"error": f"issue {issue_id!r} not found"}
    return {"bundle": _stix.build_issue_bundle(s, issue)}


def export_case_stix(case_id: str) -> dict[str, Any]:
    """Assemble a STIX 2.1 bundle for a Case (campaign) — a `campaign` +
    `threat-actor` (from the rollup) + each member issue's `incident` /
    `attack-pattern`s / `indicator`s / `relationship`s, wrapped in a `grouping`.

    Returns {"bundle": {...}} or {"error": ...}.
    """
    from usecase.builtin_components import _stix
    s, err = _store()
    if err:
        return err
    case = s.get_case(case_id)
    if case is None:
        return {"error": f"case {case_id!r} not found"}
    return {"bundle": _stix.build_case_bundle(s, case)}
