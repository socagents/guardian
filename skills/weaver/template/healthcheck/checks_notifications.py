"""N1–N2: Notification health checks.

N1 — Slack notifications firing (≥1 success in 24h if pipeline active)
N2 — No silent notification failures (≤2 skipped, 0 failures in last 5)
"""

from __future__ import annotations

from healthcheck.utils import (
    CheckResult,
    Status,
    hours_ago,
    list_workflow_runs,
    parse_iso,
)


def check_n1_notifications_firing() -> CheckResult:
    """N1: Slack notifications have fired in the last 24 hours."""
    try:
        runs = list_workflow_runs("agent-slack-notify.yml", limit=20)
        threshold = hours_ago(24)

        recent = [r for r in runs if parse_iso(r["created_at"]) > threshold]
        successes = [r for r in recent if r.get("conclusion") == "success"]

        if successes:
            return CheckResult(
                id="N1", name="Slack Notifications Firing",
                status=Status.HEALTHY,
                message=f"{len(successes)} notification(s) sent in last 24h",
            )

        # Check if there was any pipeline activity
        dispatch_runs = list_workflow_runs("agent-dispatch.yml", limit=5)
        recent_dispatches = [
            r for r in dispatch_runs if parse_iso(r["created_at"]) > threshold
        ]

        if not recent_dispatches:
            return CheckResult(
                id="N1", name="Slack Notifications Firing",
                status=Status.HEALTHY,
                message="No pipeline activity in 24h — no notifications expected",
            )

        return CheckResult(
            id="N1", name="Slack Notifications Firing",
            status=Status.DEGRADED,
            message="Pipeline had activity but no notifications fired in 24h",
            remediation="Check Slack webhook URL, workflow triggers, and event types.",
        )
    except Exception as e:
        return CheckResult(
            id="N1", name="Slack Notifications Firing",
            status=Status.DEGRADED, message=f"Check failed: {e}",
        )


def check_n2_no_silent_failures() -> CheckResult:
    """N2: No notification failures (skips are normal and expected).

    The Slack notify workflow has 7 independent jobs per run. On any given
    trigger, only 1-2 jobs are relevant (e.g. "PR merged" only fires on PR
    events). The other 5-6 jobs legitimately skip. GitHub reports the entire
    workflow as "skipped" when all jobs skip. This is expected behavior, so
    we only flag actual failures — not skips.
    """
    try:
        runs = list_workflow_runs("agent-slack-notify.yml", limit=10)
        if not runs:
            return CheckResult(
                id="N2", name="No Silent Notification Failures",
                status=Status.HEALTHY,
                message="No notification runs to analyze",
            )

        failed = [r for r in runs if r.get("conclusion") == "failure"]

        if not failed:
            return CheckResult(
                id="N2", name="No Silent Notification Failures",
                status=Status.HEALTHY,
                message=f"No notification failures in last {len(runs)} runs",
            )

        if len(failed) <= 2:
            return CheckResult(
                id="N2", name="No Silent Notification Failures",
                status=Status.DEGRADED,
                message=f"{len(failed)} notification failure(s) in last {len(runs)} runs",
                details={"failed_runs": [r["id"] for r in failed]},
                remediation="Check Slack webhook URL and API errors.",
            )

        return CheckResult(
            id="N2", name="No Silent Notification Failures",
            status=Status.UNHEALTHY,
            message=f"{len(failed)} notification failures in last {len(runs)} runs",
            details={"failed_runs": [r["id"] for r in failed]},
            remediation="Check Slack webhook URL, API errors, and workflow configuration.",
        )
    except Exception as e:
        return CheckResult(
            id="N2", name="No Silent Notification Failures",
            status=Status.DEGRADED, message=f"Check failed: {e}",
        )


def run_all() -> list[CheckResult]:
    return [check_n1_notifications_firing(), check_n2_no_silent_failures()]
