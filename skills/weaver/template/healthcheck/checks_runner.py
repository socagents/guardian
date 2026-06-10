"""R1–R2: Runner health checks.

R1 — Runner Online: ≥1 self-hosted runner with status=online
R2 — Runner Not Stuck: No workflow run active > 90 minutes on self-hosted
R3 — Disk space: Skipped (requires runner-side agent, not API-accessible)
"""

from __future__ import annotations

from healthcheck.utils import (
    REPO,
    CheckResult,
    Status,
    gh_api,
    hours_ago,
    list_workflow_runs,
    parse_iso,
)


def check_r1_runner_online() -> CheckResult:
    """R1: At least one self-hosted runner is online."""
    try:
        data = gh_api(f"/repos/{REPO}/actions/runners")
        runners = data.get("runners", [])
        online = [
            r for r in runners
            if r.get("status") == "online"
            and any(l.get("name") == "{{RUNNER_LABEL}}" for l in r.get("labels", []))
        ]
        if online:
            names = ", ".join(r["name"] for r in online)
            return CheckResult(
                id="R1", name="Runner Online",
                status=Status.HEALTHY,
                message=f"{len(online)} runner(s) online: {names}",
            )
        return CheckResult(
            id="R1", name="Runner Online",
            status=Status.CRITICAL,
            message=f"0 {{RUNNER_LABEL}} runners online ({len(runners)} total registered)",
            remediation="Check runner machine — may be powered off or service stopped.",
        )
    except Exception as e:
        return CheckResult(
            id="R1", name="Runner Online",
            status=Status.DEGRADED,
            message=f"Could not query runners: {e}",
            remediation="Ensure GITHUB_TOKEN has admin:org or repo scope for runners API.",
        )


def check_r2_runner_not_stuck() -> CheckResult:
    """R2: No in-progress run on self-hosted runners exceeds 90 minutes."""
    try:
        runs = list_workflow_runs("agent-dispatch.yml", limit=5, status="in_progress")
        threshold = hours_ago(1.5)  # 90 minutes
        stuck = []
        for run in runs:
            started = parse_iso(run["created_at"])
            if started < threshold:
                stuck.append({
                    "run_id": run["id"],
                    "started": run["created_at"],
                    "html_url": run["html_url"],
                })
        if not stuck:
            return CheckResult(
                id="R2", name="Runner Not Stuck",
                status=Status.HEALTHY,
                message="No dispatch runs stuck (0 in-progress > 90min)",
            )
        return CheckResult(
            id="R2", name="Runner Not Stuck",
            status=Status.UNHEALTHY,
            message=f"{len(stuck)} dispatch run(s) active > 90 minutes",
            details={"stuck_runs": stuck},
            remediation="Cancel stuck runs via GitHub Actions UI or API.",
        )
    except Exception as e:
        return CheckResult(
            id="R2", name="Runner Not Stuck",
            status=Status.DEGRADED,
            message=f"Could not check running dispatches: {e}",
        )


def run_all() -> list[CheckResult]:
    return [check_r1_runner_online(), check_r2_runner_not_stuck()]
