"""S1–S4: Sweep health checks.

S1 — Sweep running on schedule (≥1 run in last 2 hours)
S2 — No accumulating backlog (≤3 ready issues)
S3 — No stale in-progress issues (>2h with no activity, no PR)
S4 — Sweep not continuously cancelled (≥1 of last 3 completed)
"""

from __future__ import annotations

from healthcheck.utils import (
    CheckResult,
    Status,
    hours_ago,
    list_issues,
    list_workflow_runs,
    parse_iso,
)


def check_s1_sweep_running() -> CheckResult:
    """S1: Sweep has run in the last 2 hours."""
    try:
        runs = list_workflow_runs("agent-dispatch-sweep.yml", limit=5)
        threshold = hours_ago(2)

        recent = [r for r in runs if parse_iso(r["created_at"]) > threshold]
        if recent:
            return CheckResult(
                id="S1", name="Sweep Running on Schedule",
                status=Status.HEALTHY,
                message=f"{len(recent)} sweep run(s) in last 2 hours",
            )
        return CheckResult(
            id="S1", name="Sweep Running on Schedule",
            status=Status.DEGRADED,
            message="No sweep runs in last 2 hours",
            remediation="Check cron schedule. Manually trigger sweep if needed.",
        )
    except Exception as e:
        return CheckResult(
            id="S1", name="Sweep Running on Schedule",
            status=Status.DEGRADED, message=f"Check failed: {e}",
        )


def check_s2_no_backlog() -> CheckResult:
    """S2: No accumulating backlog of ready issues."""
    try:
        ready_issues = list_issues("status:ready")
        agent_ready = [
            i for i in ready_issues
            if any(l["name"].startswith("agent:") for l in i.get("labels", []))
        ]
        count = len(agent_ready)

        if count <= 3:
            return CheckResult(
                id="S2", name="No Accumulating Backlog",
                status=Status.HEALTHY,
                message=f"{count} issue(s) in status:ready with agent labels",
            )
        if count <= 8:
            return CheckResult(
                id="S2", name="No Accumulating Backlog",
                status=Status.DEGRADED,
                message=f"{count} issues in ready backlog (threshold: ≤3)",
                details={"issues": [i["number"] for i in agent_ready]},
                remediation="Check dispatch pipeline — may need more throughput.",
            )
        return CheckResult(
            id="S2", name="No Accumulating Backlog",
            status=Status.UNHEALTHY,
            message=f"{count} issues in ready backlog (>8 = unhealthy)",
            details={"issues": [i["number"] for i in agent_ready]},
            remediation="Investigate dispatch failures. Consider manual triage.",
        )
    except Exception as e:
        return CheckResult(
            id="S2", name="No Accumulating Backlog",
            status=Status.DEGRADED, message=f"Check failed: {e}",
        )


def check_s3_no_stale_in_progress() -> CheckResult:
    """S3: No issues stuck in status:in-progress for >2 hours."""
    try:
        in_progress = list_issues("status:in-progress")
        agent_ip = [
            i for i in in_progress
            if any(l["name"].startswith("agent:") for l in i.get("labels", []))
        ]
        threshold = hours_ago(2)
        stale = []
        for issue in agent_ip:
            updated = parse_iso(issue["updated_at"])
            if updated < threshold:
                stale.append({
                    "number": issue["number"],
                    "title": issue["title"],
                    "updated_at": issue["updated_at"],
                })

        if not stale:
            return CheckResult(
                id="S3", name="No Stale In-Progress Issues",
                status=Status.HEALTHY,
                message=f"0 stale in-progress issues ({len(agent_ip)} total in-progress)",
            )
        return CheckResult(
            id="S3", name="No Stale In-Progress Issues",
            status=Status.UNHEALTHY,
            message=f"{len(stale)} issue(s) stuck in-progress >2 hours",
            details={"stale_issues": stale},
            remediation="Sweep should auto-reset these. If persisting, check sweep (S1).",
        )
    except Exception as e:
        return CheckResult(
            id="S3", name="No Stale In-Progress Issues",
            status=Status.DEGRADED, message=f"Check failed: {e}",
        )


def check_s4_sweep_not_cancelled() -> CheckResult:
    """S4: At least 1 of last 3 sweep runs completed (not all cancelled)."""
    try:
        runs = list_workflow_runs("agent-dispatch-sweep.yml", limit=3)
        if not runs:
            return CheckResult(
                id="S4", name="Sweep Not Continuously Cancelled",
                status=Status.DEGRADED,
                message="No sweep runs found",
            )
        completed = [r for r in runs if r.get("conclusion") != "cancelled"]
        if completed:
            return CheckResult(
                id="S4", name="Sweep Not Continuously Cancelled",
                status=Status.HEALTHY,
                message=f"{len(completed)}/{len(runs)} recent sweep runs completed",
            )
        return CheckResult(
            id="S4", name="Sweep Not Continuously Cancelled",
            status=Status.DEGRADED,
            message="All 3 recent sweep runs were cancelled (concurrency conflict)",
            remediation="Check for rapid re-triggers or dispatch concurrency starvation.",
        )
    except Exception as e:
        return CheckResult(
            id="S4", name="Sweep Not Continuously Cancelled",
            status=Status.DEGRADED, message=f"Check failed: {e}",
        )


def run_all() -> list[CheckResult]:
    return [
        check_s1_sweep_running(),
        check_s2_no_backlog(),
        check_s3_no_stale_in_progress(),
        check_s4_sweep_not_cancelled(),
    ]
