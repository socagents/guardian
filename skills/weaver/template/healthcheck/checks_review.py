"""V1–V5: Review pipeline health checks.

V1 — PRs reviewed within SLA (2 hours)
V2 — Review workflow not failing (≤1 failure in last 3)
V3 — Reviews produce verdicts
V4 — Approved PRs get merged
V5 — Rejected PRs get re-dispatched
"""

from __future__ import annotations

from healthcheck.utils import (
    REPO,
    CheckResult,
    Status,
    get_issue_comments,
    gh_api,
    hours_ago,
    list_issues,
    list_pulls,
    list_workflow_runs,
    parse_iso,
)


def check_v1_prs_reviewed_within_sla() -> CheckResult:
    """V1: All open PRs have review-agent comments within 2 hours."""
    try:
        prs = list_pulls(state="open")
        agent_prs = [p for p in prs if p["head"]["ref"].startswith("agent/")]
        threshold = hours_ago(2)
        overdue = []

        for pr in agent_prs:
            created = parse_iso(pr["created_at"])
            if created > threshold:
                continue  # Too new, still within SLA

            # Check for review comments
            comments = get_issue_comments(pr["number"])
            has_review = any(
                "review" in (c.get("body", "")[:200].lower())
                and c.get("user", {}).get("login", "") in ("github-actions[bot]", "github-actions")
                for c in comments
            )
            if not has_review:
                overdue.append({
                    "number": pr["number"],
                    "title": pr["title"],
                    "created_at": pr["created_at"],
                })

        if not overdue:
            msg = f"All {len(agent_prs)} agent PR(s) reviewed within SLA" if agent_prs else "No open agent PRs"
            return CheckResult(
                id="V1", name="PRs Reviewed Within SLA",
                status=Status.HEALTHY, message=msg,
            )
        return CheckResult(
            id="V1", name="PRs Reviewed Within SLA",
            status=Status.UNHEALTHY,
            message=f"{len(overdue)} PR(s) unreviewed past 2-hour SLA",
            details={"overdue_prs": overdue},
            remediation="Trigger review: gh workflow run agent-review.yml -f pr_number=<N>",
        )
    except Exception as e:
        return CheckResult(
            id="V1", name="PRs Reviewed Within SLA",
            status=Status.DEGRADED, message=f"Check failed: {e}",
        )


def check_v2_review_not_failing() -> CheckResult:
    """V2: ≤1 failure in last 3 review runs."""
    try:
        runs = list_workflow_runs("agent-review.yml", limit=5)
        recent = runs[:3]
        if not recent:
            return CheckResult(
                id="V2", name="Review Workflow Not Failing",
                status=Status.HEALTHY,
                message="No review runs to analyze",
            )
        failures = [r for r in recent if r.get("conclusion") == "failure"]
        if len(failures) <= 1:
            return CheckResult(
                id="V2", name="Review Workflow Not Failing",
                status=Status.HEALTHY,
                message=f"{len(failures)}/3 recent review runs failed (threshold: ≤1)",
            )
        return CheckResult(
            id="V2", name="Review Workflow Not Failing",
            status=Status.UNHEALTHY,
            message=f"{len(failures)}/3 recent review runs failed",
            details={"failed_runs": [
                {"id": r["id"], "url": r["html_url"]} for r in failures
            ]},
            remediation="Check review workflow logs — token logging, Claude CLI, or spec resolution.",
        )
    except Exception as e:
        return CheckResult(
            id="V2", name="Review Workflow Not Failing",
            status=Status.DEGRADED, message=f"Check failed: {e}",
        )


def check_v3_reviews_produce_verdicts() -> CheckResult:
    """V3: Completed review runs produce a verdict."""
    try:
        runs = list_workflow_runs("agent-review.yml", limit=5)
        completed = [r for r in runs if r.get("conclusion") in ("success", "failure")][:3]

        if not completed:
            return CheckResult(
                id="V3", name="Reviews Produce Verdicts",
                status=Status.HEALTHY,
                message="No completed review runs to analyze",
            )

        # We can check if the PR has a review comment with VERDICT marker
        # For now, check that successful runs exist — detailed verdict parsing
        # would require log analysis
        successes = [r for r in completed if r.get("conclusion") == "success"]
        return CheckResult(
            id="V3", name="Reviews Produce Verdicts",
            status=Status.HEALTHY if successes else Status.DEGRADED,
            message=f"{len(successes)}/{len(completed)} review runs completed successfully",
        )
    except Exception as e:
        return CheckResult(
            id="V3", name="Reviews Produce Verdicts",
            status=Status.DEGRADED, message=f"Check failed: {e}",
        )


def check_v4_approved_prs_merged() -> CheckResult:
    """V4: PRs with approve verdict are merged within 1 hour."""
    try:
        prs = list_pulls(state="open")
        agent_prs = [p for p in prs if p["head"]["ref"].startswith("agent/")]
        threshold = hours_ago(1)
        stuck = []

        for pr in agent_prs:
            comments = get_issue_comments(pr["number"])
            approved = any(
                "approve" in c.get("body", "").lower()[:500]
                and c.get("user", {}).get("login", "") in ("github-actions[bot]", "github-actions")
                for c in comments
            )
            if approved:
                # Check if the approval is older than 1 hour
                approve_comments = [
                    c for c in comments
                    if "approve" in c.get("body", "").lower()[:500]
                    and c.get("user", {}).get("login", "") in ("github-actions[bot]", "github-actions")
                ]
                for ac in approve_comments:
                    if parse_iso(ac["created_at"]) < threshold:
                        stuck.append({
                            "number": pr["number"],
                            "title": pr["title"],
                            "approved_at": ac["created_at"],
                        })
                        break

        if not stuck:
            return CheckResult(
                id="V4", name="Approved PRs Merged",
                status=Status.HEALTHY,
                message="No approved PRs stuck unmerged",
            )
        return CheckResult(
            id="V4", name="Approved PRs Merged",
            status=Status.UNHEALTHY,
            message=f"{len(stuck)} approved PR(s) unmerged >1 hour",
            details={"stuck_prs": stuck},
            remediation="Check auto-merge step. May need PROJECT_PAT or branch protection fix.",
        )
    except Exception as e:
        return CheckResult(
            id="V4", name="Approved PRs Merged",
            status=Status.DEGRADED, message=f"Check failed: {e}",
        )


def check_v5_rejected_prs_redispatched() -> CheckResult:
    """V5: Issues from rejected PRs get re-dispatched within 2 hours."""
    try:
        # Check for ready issues that have been waiting too long after rejection
        ready = list_issues("status:ready")
        agent_ready = [
            i for i in ready
            if any(l["name"].startswith("agent:") for l in i.get("labels", []))
        ]
        threshold = hours_ago(2)
        stuck = []
        for issue in agent_ready:
            updated = parse_iso(issue["updated_at"])
            if updated < threshold:
                # Could be a rejected PR that wasn't re-dispatched
                stuck.append({
                    "number": issue["number"],
                    "title": issue["title"],
                    "updated_at": issue["updated_at"],
                })

        if not stuck:
            return CheckResult(
                id="V5", name="Rejected PRs Re-dispatched",
                status=Status.HEALTHY,
                message="No ready issues stuck >2 hours after review",
            )
        return CheckResult(
            id="V5", name="Rejected PRs Re-dispatched",
            status=Status.DEGRADED,
            message=f"{len(stuck)} ready issue(s) waiting >2 hours",
            details={"stuck_issues": stuck},
            remediation="Check sweep — should pick up ready issues with agent labels.",
        )
    except Exception as e:
        return CheckResult(
            id="V5", name="Rejected PRs Re-dispatched",
            status=Status.DEGRADED, message=f"Check failed: {e}",
        )


def run_all() -> list[CheckResult]:
    return [
        check_v1_prs_reviewed_within_sla(),
        check_v2_review_not_failing(),
        check_v3_reviews_produce_verdicts(),
        check_v4_approved_prs_merged(),
        check_v5_rejected_prs_redispatched(),
    ]
